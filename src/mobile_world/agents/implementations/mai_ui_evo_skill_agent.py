"""MAI-UI 风格的自进化技能包 Agent。

设计目标：让 ``mai_ui_agent`` 也能跑在 ``EvolutionLoop`` 的自进化闭环里，
**同时保留它原有的 XML/<tool_call> 输出格式**，不必把它改造成
``general_e2e`` 那种 ``Action: {...}`` 风格。

要点：

1. 继承 :class:`MAIUINaivigationAgent`，复用其 prompt、history、parsing 与 GUI
   动作转换；
2. 注入新的 system prompt 模板 :data:`MAI_UI_EVO_SKILL_SYS_PROMPT`，把当前激
   活的 ``SkillPackage`` 内容（plan/backup/recover/失败案例）拼进去；
3. 把文件操作工具（read_file/write_file/...）合并进 ``self.tools``，并在
   ``predict()`` 内部消化 —— 当 LLM 输出的 ``<tool_call>`` 里 ``name`` 命中
   file tool 时，本地 dispatch、把结果作为下一轮的 user message，循环直到模型
   输出一个 GUI/MCP 动作；
4. 对外暴露与 :class:`EvoSkillAgent` 完全一致的 4 个接口：``set_skill``、
   ``clear_skill``、``active_skill``、``skill_edit_log``、
   ``refine_skill_with_feedback``，因此可以直接被 ``EvolutionLoop`` 调度，
   ``runner.py`` 用 duck typing 检测即可。
"""

from __future__ import annotations

import json
import time
from typing import Any

from loguru import logger

from mobile_world.agents.implementations.mai_ui_agent import (
    MAIUINaivigationAgent,
    parse_action_to_structure_output,
)
from mobile_world.agents.utils.prompts import (
    MAI_UI_EVO_SKILL_REFINE_SYS_PROMPT,
    MAI_UI_EVO_SKILL_SYS_PROMPT,
)
from mobile_world.runtime.utils.helpers import mask_api_key, pretty_print_messages
from mobile_world.runtime.utils.models import UNKNOWN, JSONAction
from mobile_world.skills.file_tools import (
    FILE_TOOLS,
    dispatch_file_tool,
    get_file_tool_specs,
)
from mobile_world.skills.skill_manager import SkillPackage

# 这一组工具名由本 agent 在本地处理，**不会**透传到 MCP 环境
FILE_TOOL_NAMES: frozenset[str] = frozenset(
    spec["function"]["name"] for spec in FILE_TOOLS  # type: ignore[index]
)


class MaiUIEvoSkillAgent(MAIUINaivigationAgent):
    """MAI-UI 风格的 Agent，外加技能包注入和 file_tool 闭环。"""

    def __init__(
        self,
        llm_base_url: str,
        model_name: str,
        api_key: str = "empty",
        runtime_conf: dict[str, Any] | None = None,
        tools: list[dict] | None = None,
        max_skill_tool_calls_per_step: int = 4,
        enable_user_interaction: bool = False,
        **kwargs,
    ):
        env_tools = list(tools or [])
        env_tool_names = {
            t.get("function", {}).get("name") for t in env_tools if isinstance(t, dict)
        }
        # MCP 环境工具优先；冲突时 file tool 让位
        file_specs = [
            spec
            for spec in get_file_tool_specs()
            if spec["function"]["name"] not in env_tool_names
        ]
        merged_tools = env_tools + file_specs

        super().__init__(
            llm_base_url=llm_base_url,
            model_name=model_name,
            api_key=api_key,
            runtime_conf=runtime_conf or {},
            tools=merged_tools,
            **kwargs,
        )

        self._env_tool_names = env_tool_names
        self._file_tool_names = set(FILE_TOOL_NAMES) - env_tool_names
        self._rollout_file_tool_names = set(self._file_tool_names)
        self.max_skill_tool_calls_per_step = max_skill_tool_calls_per_step
        self.enable_user_interaction = enable_user_interaction

        self._skill: SkillPackage | None = None
        self._skill_edit_log: list[dict[str, Any]] = []
        # 当前 step 的 a11y tree 文本（仅注入到当前 turn，避免历史轮次重复）
        self._current_a11y_text: str | None = None

    # ------------------------------------------------------------------
    # Skill management API（与 EvoSkillAgent 同名同语义，被 EvolutionLoop 使用）
    # ------------------------------------------------------------------

    def set_skill(self, skill: SkillPackage) -> None:
        """切换当前生效的技能包。"""
        self._skill = skill
        self._skill_edit_log = []
        logger.info(f"[mai_ui_evo_skill] activated skill {skill.skill_id} at {skill.root}")

    def clear_skill(self) -> None:
        self._skill = None
        self._skill_edit_log = []

    @property
    def active_skill(self) -> SkillPackage | None:
        return self._skill

    @property
    def skill_edit_log(self) -> list[dict[str, Any]]:
        return list(self._skill_edit_log)

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    @property
    def system_prompt(self) -> str:
        """覆盖父类，使用带技能包注入的 mai_ui prompt。"""
        skill_context = ""
        if self._skill is not None:
            try:
                skill_context = self._skill.render_skill_context()
            except Exception as e:
                logger.warning(f"Failed to render skill context: {e}")

        mcp_tools_str = None
        if self.tools:
            mcp_tools_str = "\n".join(
                json.dumps(t, ensure_ascii=False) for t in self.tools
            )
        return MAI_UI_EVO_SKILL_SYS_PROMPT.render(
            skill_context=skill_context,
            tools=mcp_tools_str,
        )

    # ------------------------------------------------------------------
    # Override predict to handle file-tool inner loop
    # ------------------------------------------------------------------

    def predict(self, observation: dict[str, Any]) -> tuple[str, JSONAction]:
        obs_image = observation["screenshot"]
        tool_call = observation.get("tool_call", None)
        ask_user_response = observation.get("ask_user_response", None)
        self._current_a11y_text = observation.get("accessibility_tree") or None

        self.history_images.append((obs_image, tool_call, ask_user_response))

        logger.debug(f"Current history images count: {len(self.history_images)}")
        logger.debug(f"Current history responses count: {len(self.history_responses)}")
        assert len(self.history_images) == len(self.history_responses) + 1

        local_tool_calls = 0

        while True:
            messages = self._build_messages(obs_image, tool_call, ask_user_response)
            pretty_print_messages(messages, max_messages=10)
            logger.debug("*" * 100)

            response = self._safe_chat_completion(messages)
            if response is None:
                logger.error("Planner LLM failed after retries")
                return "Agent LLM failed", JSONAction(
                    action_type=UNKNOWN, text="Agent LLM failed"
                )
            logger.info(f"Raw LLM response:\n{response}")

            try:
                parsed = parse_action_to_structure_output(response)
            except Exception as e:
                logger.error(f"Error parsing LLM response: {e}")
                # 让父类做最后兜底（原始 mai_ui 也是这种处理）
                self.history_responses.append(
                    {"role": "assistant", "content": response}
                )
                return response, JSONAction(action_type=UNKNOWN, text=str(e))

            thinking = parsed.get("thinking")
            tool_name = parsed.get("tool_name", "mobile_use")
            action_json = parsed["action_json"]

            logger.info(f"Parsed thinking: {thinking}")
            logger.info(f"Parsed tool_name: {tool_name}")
            logger.info(f"Parsed action: {action_json}")

            # ---- 是 file_tool 调用？本地消化 ----
            if tool_name in self._rollout_file_tool_names:
                if local_tool_calls >= self.max_skill_tool_calls_per_step:
                    logger.warning(
                        f"Reached max_skill_tool_calls_per_step="
                        f"{self.max_skill_tool_calls_per_step}; forcing the model "
                        "to return a GUI action next."
                    )
                    self._record_assistant_turn(
                        response,
                        obs_image,
                        tool_call="(skill-edit budget exhausted, please emit a GUI action)",
                    )
                    local_tool_calls += 1
                    continue

                tool_args = action_json or {}
                if not isinstance(tool_args, dict):
                    try:
                        tool_args = json.loads(tool_args)
                    except Exception:
                        tool_args = {}

                if self._skill is None:
                    tool_result_text = (
                        "ERROR: no active skill package; file tools are disabled."
                    )
                else:
                    result = dispatch_file_tool(
                        tool_name,
                        tool_args,
                        self._skill.root,
                    )
                    self._skill_edit_log.append(
                        {
                            "tool": tool_name,
                            "args": tool_args,
                            "ok": result.ok,
                            "output_excerpt": (result.output or "")[:200],
                            "error": result.error,
                        }
                    )
                    tool_result_text = json.dumps(
                        {
                            "ok": result.ok,
                            "output": result.output,
                            "error": result.error,
                        },
                        ensure_ascii=False,
                    )
                    if len(tool_result_text) > 4000:
                        tool_result_text = tool_result_text[:4000] + "\n... [truncated]"

                self._record_assistant_turn(
                    response,
                    obs_image,
                    tool_call=f"[skill_tool:{tool_name}] {tool_result_text}",
                )
                local_tool_calls += 1
                continue

            # ---- 普通 GUI / MCP 动作：返回给外层 ----
            self.history_responses.append(
                {"role": "assistant", "content": response}
            )
            json_action = self._convert_to_json_action(tool_name, action_json, obs_image)
            return response, json_action

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_messages(
        self, obs_image: Any, tool_call: Any, ask_user_response: Any
    ) -> list[dict]:
        """复用父类组装结果，再把当前 step 的 a11y 文本追加到最后一条 user message。

        a11y 不写进 ``history_images``，避免下一 step 重新组装时旧 a11y 也被
        带上来反复占用 token。
        """
        messages = super()._build_messages(obs_image, tool_call, ask_user_response)
        if self._current_a11y_text:
            self._append_a11y_to_last_user_message(messages, self._current_a11y_text)
        return messages

    @staticmethod
    def _append_a11y_to_last_user_message(messages: list[dict], a11y_text: str) -> None:
        """把 a11y 文本附加到最后一条 user message。

        ``content`` 在不同上游路径下可能是 list 或 str，这里都做兼容，
        避免在某些条件下 a11y 被静默丢弃。"""
        a11y_part = {
            "type": "text",
            "text": (
                "Accessibility tree of the current screen "
                "(use as a complement to the screenshot for exact "
                "labels / coordinates / slider values):\n"
                f"{a11y_text}"
            ),
        }
        for j in range(len(messages) - 1, -1, -1):
            if messages[j].get("role") != "user":
                continue
            content = messages[j].get("content")
            if isinstance(content, list):
                content.append(a11y_part)
            elif isinstance(content, str):
                messages[j]["content"] = [
                    {"type": "text", "text": content},
                    a11y_part,
                ]
            else:
                messages[j]["content"] = [a11y_part]
            return

    def _record_assistant_turn(
        self,
        response: str,
        current_obs_image: Any,
        tool_call: str | None,
    ) -> None:
        """把一次 file_tool 往返记录进 history，让下一次 LLM 调用看到结果。

        语义跟 :class:`EvoSkillAgent._record_assistant_turn` 一致：复用同一张
        截图（屏幕未变），只是把 tool_result 当作新的 user observation。
        """
        self.history_responses.append({"role": "assistant", "content": response})
        self.history_images.append((current_obs_image, tool_call, None))

    def _safe_chat_completion(self, messages: list[dict]) -> str | None:
        try_times = 3
        last_err: Exception | None = None
        while try_times > 0:
            try:
                return self.openai_chat_completions_create(
                    model=self.model_name,
                    messages=messages,
                    retry_times=1,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    top_p=self.top_p,
                )
            except Exception as e:
                last_err = e
                try_times -= 1
                logger.warning(
                    f"Error fetching response from {self.model_name} "
                    f"({mask_api_key(self.api_key)}): {e}; retrying ({try_times} left)"
                )
                if "timeout" in str(e).lower() or "connection" in str(e).lower():
                    time.sleep(2)
        if last_err is not None:
            logger.error(f"Final LLM error: {last_err}")
        return None

    # ------------------------------------------------------------------
    # Skill refinement (called between iterations by evolution_loop)
    # ------------------------------------------------------------------

    def refine_skill_with_feedback(
        self,
        feedback_text: str,
        max_tool_calls: int = 8,
    ) -> list[dict[str, Any]]:
        """根据 Verifier 反馈，让模型用 file_tools 修改技能包。

        和 :meth:`EvoSkillAgent.refine_skill_with_feedback` 语义一致，但解析
        逻辑用 mai_ui 的 ``<tool_call>`` XML 风格。
        """
        if self._skill is None:
            logger.warning("No active skill; cannot refine")
            return []

        # 当前技能包内容
        current_docs = ""
        for label, rel_path in (
            ("plan.md", "docs/plan.md"),
            ("backup.md", "docs/backup.md"),
            ("recover.md", "docs/recover.md"),
        ):
            fpath = self._skill.root / rel_path
            if fpath.exists():
                content = fpath.read_text(encoding="utf-8").strip()
                current_docs += f"\n### 当前 {label}\n```\n{content[:3000]}\n```\n"

        # 已有失败案例
        failure_docs = ""
        fe_dir = self._skill.root / "failure_examples"
        if fe_dir.exists():
            for fe in sorted(fe_dir.glob("failure_*.md"))[:3]:
                failure_docs += (
                    f"\n### {fe.name}\n```\n"
                    f"{fe.read_text(encoding='utf-8').strip()[:1500]}\n```\n"
                )

        sys_prompt = MAI_UI_EVO_SKILL_REFINE_SYS_PROMPT.render()

        user_prompt = (
            f"# Skill package: {self._skill.skill_id}\n\n"
            f"## Current skill package contents\n{current_docs}\n"
            f"## Failure history\n{failure_docs}\n"
            f"## Verifier feedback (this rollout)\n{feedback_text}\n\n"
            "Now analyze the feedback and edit the skill package files to fix the "
            "identified issues. Start by reading any file you need, then write the "
            "corrected version. You MUST call write_file at least once."
        )

        messages: list[dict] = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ]

        edits: list[dict[str, Any]] = []
        for step in range(max_tool_calls):
            response = self._safe_chat_completion(messages)
            if response is None:
                logger.warning("Skill-refinement LLM returned None; aborting")
                break

            messages.append({"role": "assistant", "content": response})

            last_line = (
                response.splitlines()[-1].strip().upper() if response.strip() else ""
            )
            is_done = "DONE" in last_line or response.strip().upper().endswith("DONE")

            if is_done and len(edits) > 0:
                logger.info(f"Skill refinement finished after {step} tool calls")
                break
            if is_done and len(edits) == 0 and step == 0:
                # 模型没动手就喊 DONE，回压一下
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "You said DONE but made zero edits. The task FAILED — "
                            "the skill package MUST be updated. Please call "
                            "write_file now to improve at least plan.md based on "
                            "the verifier's suggestions. Do NOT skip this step."
                        ),
                    }
                )
                continue

            try:
                parsed = parse_action_to_structure_output(response)
            except Exception as e:
                logger.warning(
                    f"Refinement parse failure ({e}); response:\n{response[:500]}"
                )
                break

            tool_name = parsed.get("tool_name", "mobile_use")
            if tool_name not in self._file_tool_names:
                logger.info(
                    f"Refinement produced non-file action; stopping. "
                    f"tool_name={tool_name}"
                )
                break

            tool_args = parsed["action_json"] or {}
            if not isinstance(tool_args, dict):
                try:
                    tool_args = json.loads(tool_args)
                except Exception:
                    tool_args = {}

            result = dispatch_file_tool(
                tool_name,
                tool_args,
                self._skill.root,
            )
            edits.append(
                {
                    "tool": tool_name,
                    "args": tool_args,
                    "ok": result.ok,
                    "output_excerpt": (result.output or "")[:200],
                    "error": result.error,
                }
            )
            messages.append(
                {
                    "role": "user",
                    "content": json.dumps(
                        {"ok": result.ok, "output": result.output, "error": result.error},
                        ensure_ascii=False,
                    )[:4000],
                }
            )

        self._skill_edit_log.extend(edits)
        return edits

    def reset(self) -> None:
        """每个 rollout 之间清掉对话 history（但不清 skill）。"""
        super().reset()
