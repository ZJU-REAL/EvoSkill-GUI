"""自进化技能包 Agent。

在 ``GeneralE2EAgentMCP`` 基础上：

1. 在 system prompt 中注入当前激活的技能包内容（plan/backup/recover/失败案例）
2. 提供文件操作 tool_call（read_file/write_file/...）以"沙箱化"的形式
   读写当前技能包文件
3. 这些 file_tool 调用在 ``predict`` 内部消化，对外仍然只暴露 GUI / MCP 动作
"""

from __future__ import annotations

import json
import time
from typing import Any

from loguru import logger

from mobile_world.agents.implementations.general_e2e_agent import (
    CLAUDE_IMAGE_SIZE,
    CLAUDE_OPUS_MAX_DIMENSION,
    GeneralE2EAgentMCP,
    parse_action,
    parse_response_to_action,
)
from mobile_world.agents.utils.helpers import pil_adaptive_resize
from mobile_world.agents.utils.prompts import EVO_SKILL_PROMPT_TEMPLATE
from mobile_world.runtime.utils.helpers import mask_api_key, pretty_print_messages
from mobile_world.runtime.utils.models import JSONAction
from mobile_world.skills.file_tools import (
    FILE_TOOLS,
    dispatch_file_tool,
    get_file_tool_specs,
)
from mobile_world.skills.skill_manager import SkillPackage

# 这一组工具名由 evo_skill_agent 在本地处理，**不会**透传到 MCP 环境
FILE_TOOL_NAMES: frozenset[str] = frozenset(
    spec["function"]["name"] for spec in FILE_TOOLS  # type: ignore[index]
)


class EvoSkillAgent(GeneralE2EAgentMCP):
    """带技能包注入与本地文件 tool_call 的 Agent。"""

    def __init__(
        self,
        model_name: str,
        llm_base_url: str,
        api_key: str = "empty",
        observation_type: str = "screenshot",
        runtime_conf: dict | None = None,
        tools: list[dict] | None = None,
        scale_factor: int = 1000,
        max_skill_tool_calls_per_step: int = 4,
        enable_user_interaction: bool = False,
        **kwargs,
    ):
        runtime_conf = runtime_conf or {
            "history_n_images": 3,
            "temperature": 0.0,
            "max_tokens": 2048,
        }
        env_tools = list(tools or [])

        # 把文件操作工具合并到 tools 中，让模型在 prompt 中看到
        # （重名时以 env tool 优先）
        env_tool_names = {t.get("function", {}).get("name") for t in env_tools if isinstance(t, dict)}
        file_specs = [
            spec
            for spec in get_file_tool_specs()
            if spec["function"]["name"] not in env_tool_names
        ]
        merged_tools = file_specs + env_tools

        super().__init__(
            model_name=model_name,
            llm_base_url=llm_base_url,
            api_key=api_key,
            observation_type=observation_type,
            runtime_conf=runtime_conf,
            tools=merged_tools,
            scale_factor=scale_factor,
            **kwargs,
        )

        self._env_tool_names = env_tool_names
        self._file_tool_names = set(FILE_TOOL_NAMES) - env_tool_names
        self._rollout_file_tool_names = set(self._file_tool_names)
        self.max_skill_tool_calls_per_step = max_skill_tool_calls_per_step
        self.enable_user_interaction = enable_user_interaction

        self._skill: SkillPackage | None = None
        self._skill_edit_log: list[dict[str, Any]] = []
        # 当前 step 的 a11y tree 文本，由 evolution_loop 通过 observation 传入
        # 仅注入到当前 turn 的 user message，不写入 history（避免历史轮次重复占 token）
        self._current_a11y_text: str | None = None

    # ------------------------------------------------------------------
    # Skill management API (called by evolution_loop)
    # ------------------------------------------------------------------

    def set_skill(self, skill: SkillPackage) -> None:
        """切换当前生效的技能包。"""
        self._skill = skill
        self._skill_edit_log = []
        logger.info(f"[evo_skill_agent] activated skill {skill.skill_id} at {skill.root}")

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

    def _build_system_prompt(self, scale_factor: Any) -> str:
        skill_context = ""
        if self._skill is not None:
            try:
                skill_context = self._skill.render_skill_context()
            except Exception as e:
                logger.warning(f"Failed to render skill context: {e}")

        tools_block = "\n".join(
            json.dumps(t, ensure_ascii=False) for t in self.tools or []
        )

        prompt = EVO_SKILL_PROMPT_TEMPLATE.render(
            skill_context=skill_context,
            tools=tools_block,
            scale_factor=scale_factor,
            enable_user_interaction=self.enable_user_interaction,
        )
        if "qwen" in self.model_name.lower():
            prompt += "\n\n/no_think"
        return prompt

    # ------------------------------------------------------------------
    # Override predict to handle file-tool inner loop
    # ------------------------------------------------------------------

    def predict(self, observation: dict[str, Any]) -> tuple[str, JSONAction]:
        # 仅当前 step 生效；inner-loop 多次重入时仍指当前 step
        self._current_a11y_text = observation.get("accessibility_tree") or None
        orig_width, orig_height = observation["screenshot"].size

        if self._use_adaptive_resize:
            obs_image, _, _ = pil_adaptive_resize(
                observation["screenshot"], CLAUDE_OPUS_MAX_DIMENSION
            )
            active_scale_factor = obs_image.size
        elif "claude" in self.model_name.lower():
            obs_image = observation["screenshot"].resize(CLAUDE_IMAGE_SIZE)
            active_scale_factor = self.scale_factor
        else:
            obs_image = observation["screenshot"]
            active_scale_factor = self.scale_factor

        tool_call = observation.get("tool_call", None)
        ask_user_response = observation.get("ask_user_response", None)
        self.history_images.append((obs_image, tool_call, ask_user_response))

        assert len(self.history_images) == len(self.history_responses) + 1

        local_tool_calls = 0

        while True:
            messages = self._compose_messages(active_scale_factor)
            pretty_print_messages(messages, max_messages=10)
            logger.debug("*" * 100)

            response = self._safe_chat_completion(messages)
            if response is None:
                logger.error("LLM returned no response after retries")
                return "Agent LLM failed", JSONAction(
                    action_type="unknown", text="Agent LLM failed"
                )

            try:
                thought, action_str = parse_action(response)
            except Exception as e:
                logger.warning(f"Failed to parse action: {e}; raw response:\n{response}")
                return response, JSONAction(action_type="unknown", text="parse_error")

            try:
                action_dict = parse_response_to_action(
                    action_str, orig_width, orig_height, active_scale_factor
                )
            except Exception as e:
                logger.warning(f"parse_response_to_action failed: {e}")
                self.history_responses.append({"role": "assistant", "content": response})
                return response, JSONAction(action_type="unknown", text="parse_error")

            # file_tool 调用在本地技能包沙箱中执行。
            if (
                action_dict.get("action_type") == "mcp"
                and action_dict.get("action_name") in self._rollout_file_tool_names
            ):
                if local_tool_calls >= self.max_skill_tool_calls_per_step:
                    logger.warning(
                        f"Reached max_skill_tool_calls_per_step={self.max_skill_tool_calls_per_step}; "
                        "forcing the model to return a GUI action next."
                    )
                    # 把 LLM 这次 file_tool 响应记录到 history，并构造一个"上限提示"作为下一轮的 tool_call observation
                    self._record_assistant_turn(response, obs_image, tool_call="(skill-edit budget exhausted, please emit a GUI action)")
                    local_tool_calls += 1
                    continue

                tool_name = action_dict["action_name"]
                tool_args = action_dict.get("action_json") or {}
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
                        {"ok": result.ok, "output": result.output, "error": result.error},
                        ensure_ascii=False,
                    )
                    if len(tool_result_text) > 4000:
                        tool_result_text = tool_result_text[:4000] + "\n... [truncated]"

                # 记录 assistant 这一步的 LLM 响应，并将 tool_result 作为下一轮的 tool_call observation
                self._record_assistant_turn(
                    response,
                    obs_image,
                    tool_call=f"[skill_tool:{tool_name}] {tool_result_text}",
                )
                local_tool_calls += 1
                continue

            # 一个普通的 GUI / MCP 动作 → 返回给外层
            self.history_responses.append({"role": "assistant", "content": response})
            self.actions.append(action_dict)
            logger.debug("Agent state updated for next turn.")
            logger.info(f"Parsed thought: {thought}")
            logger.info(f"Parsed action: {action_dict}")
            return response, JSONAction(**action_dict)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_action_json_fallback(self, response: str) -> dict | None:
        """Extract action JSON from Claude-style responses without 'Action:' prefix."""
        import re
        # Try to find JSON block with action_type: mcp
        patterns = [
            r'```(?:json)?\s*(\{[^`]*"action_type"\s*:\s*"mcp"[^`]*\})\s*```',
            r'(\{"action_type"\s*:\s*"mcp"[^\n]*\})',
        ]
        for pat in patterns:
            m = re.search(pat, response, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(1))
                except json.JSONDecodeError:
                    continue
        # Try to find write_file/append_file call directly
        m = re.search(
            r'(?:action_name|tool)\s*[":]\s*["\']?(write_file|append_file|read_file)["\']?',
            response,
        )
        if m:
            # Try to parse the whole response as JSON
            for line in response.splitlines():
                line = line.strip()
                if line.startswith("{") and "action_name" in line:
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError:
                        continue
        return None

    def _safe_chat_completion(self, messages: list[dict]) -> str | None:
        try_times = 3
        last_err = None
        while try_times > 0:
            try:
                return self.openai_chat_completions_create(
                    model=self.model_name,
                    messages=messages,
                    retry_times=1,
                    **self.runtime_conf,
                )
            except Exception as e:
                last_err = e
                try_times -= 1
                logger.warning(
                    f"Error fetching response from {self.model_name} ({mask_api_key(self.api_key)}): {e}; "
                    f"retrying ({try_times} left)"
                )
                if "timeout" in str(e).lower() or "connection" in str(e).lower():
                    time.sleep(2)
        if last_err is not None:
            logger.error(f"Final LLM error: {last_err}")
        return None

    def _record_assistant_turn(
        self, response: str, current_obs_image, tool_call: str | None
    ) -> None:
        """把一次 file_tool 往返记录进 history，让下一次 LLM 调用看到结果。"""
        self.history_responses.append({"role": "assistant", "content": response})
        # 复用上一次屏幕截图（屏幕未变，只是补一次 tool_call observation）
        self.history_images.append((current_obs_image, tool_call, None))

    def _compose_messages(self, active_scale_factor: Any) -> list[dict]:
        messages: list[dict] = [
            {
                "role": "system",
                "content": self._build_system_prompt(active_scale_factor),
            },
            self._get_user_message(
                self.history_images[0][0],
                self.history_images[0][1],
                self.history_images[0][2],
                instruction=self.instruction,
            ),
        ]
        for i, history_resp in enumerate(self.history_responses):
            history_img_data, tc_res, ask_resp = self.history_images[i + 1]
            user_message = self._get_user_message(history_img_data, tc_res, ask_resp)
            response_message = {
                "role": "assistant",
                "content": [{"type": "text", "text": history_resp.get("content", "")}],
            }
            messages.append(response_message)
            messages.append(user_message)
        messages = self._hide_history_images(messages)
        # 把当前 step 的 a11y 文本附到最后一条 user message 上（不写 history，
        # 这样下一 step 重新组装时旧 a11y 不会再出现，token 占用可控）
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

    # ------------------------------------------------------------------
    # Skill refinement (called between iterations by evolution_loop)
    # ------------------------------------------------------------------

    # 各文档的角色描述（用于 refine 阶段的 system prompt 上下文）
    _REFINE_DOC_ROLES: tuple[tuple[str, str], ...] = (
        (
            "plan.md",
            "the high-level step-by-step plan that the executor follows from "
            "the home screen to task completion (numbered actions referencing "
            "real Android UI elements)",
        ),
        (
            "backup.md",
            "alternative locator strategies (text match, content-description, "
            "region OCR, scroll-and-search) that the executor falls back on "
            "when a primary locator from the plan cannot be found",
        ),
        (
            "recover.md",
            "recovery rules for handling interruptions encountered mid-task "
            "(cookie banners, permission dialogs, login walls, keyboard "
            "popups, network errors, captchas)",
        ),
    )

    @staticmethod
    def _postprocess_refine_doc_response(response: str) -> str:
        """归一化 refine 阶段单个文档的 LLM 响应。

        - 去首尾空白
        - 去整段 ``` ``` 包裹（如果有）
        - 识别 KEEP_UNCHANGED（大小写 / 标点宽容）
        """
        content = (response or "").strip()
        if not content:
            return ""

        # 去掉整段 ``` 包裹
        if content.startswith("```") and content.endswith("```") and len(content) > 6:
            lines = content.split("\n")
            # 去掉首尾两行（可能形如 ```markdown ... ```）
            content = "\n".join(lines[1:-1]).strip()

        # 识别 KEEP_UNCHANGED（容忍少量噪声）
        token_test = content.strip().strip(".").strip().upper()
        if token_test == "KEEP_UNCHANGED" or token_test.endswith("KEEP_UNCHANGED"):
            return "KEEP_UNCHANGED"

        return content

    def refine_skill_with_feedback(
        self,
        feedback_text: str,
        max_tool_calls: int = 8,  # 保留参数兼容，新实现不再使用 multi-turn
    ) -> list[dict[str, Any]]:
        """Sequential dependency-aware refinement of plan/backup/recover.

        与 Phase 2 的生成阶段同构：按 plan -> backup -> recover 顺序，每个
        文档独立一次 single-shot LLM 调用；下游文档能看到上游已更新后的内容。

        每次调用要么输出该文档的完整新版本，要么输出单行 ``KEEP_UNCHANGED``。
        完全不依赖 file_tool / 多轮工具调度 / XML / JSON 解析，与 ``/no_think``
        兼容。

        参数 ``max_tool_calls`` 仅为向后兼容保留，新实现忽略。
        """
        _ = max_tool_calls  # 保留向后兼容签名

        if self._skill is None:
            logger.warning("No active skill; cannot refine")
            return []

        # 读取已有的 failure examples。
        failure_docs = ""
        fe_dir = self._skill.root / "failure_examples"
        if fe_dir.exists():
            for fe in sorted(fe_dir.glob("failure_*.md"))[:3]:
                failure_docs += (
                    f"\n### {fe.name}\n```\n"
                    f"{fe.read_text(encoding='utf-8').strip()[:1500]}\n```\n"
                )

        # 当前盘上每个文档的初始内容（顺序刷新过程中会逐步更新）
        latest_contents: dict[str, str] = {
            name: self._skill.read_doc(name).strip()
            for name, _desc in self._REFINE_DOC_ROLES
        }

        task_intent = (self._skill.meta.task_intent or "").strip()

        edits: list[dict[str, Any]] = []
        for doc_name, doc_role in self._REFINE_DOC_ROLES:
            sys_prompt = (
                "You are the skill-refinement module of a self-evolving GUI "
                "automation system. The previous rollout FAILED. The verifier "
                "has produced a behavioral diagnosis (it has NOT seen the "
                "skill package, so its suggestions are abstract).\n\n"
                f"Your job: rewrite the document `{doc_name}` of the "
                f"executor's skill package, which contains {doc_role}.\n\n"
                "Rules:\n"
                f"1. Output the COMPLETE updated content for {doc_name} as "
                "plain markdown. Do NOT wrap the output in ``` code fences. "
                "Do NOT add any commentary, preamble, or explanation before "
                "or after the document content.\n"
                f"2. If the current {doc_name} already adequately addresses "
                "the verifier's feedback and needs NO change, output ONLY "
                "the literal token KEEP_UNCHANGED on a single line, with "
                "nothing else.\n"
                "3. Translate the verifier's behavioral suggestions into "
                f"concrete edits appropriate for THIS document's role "
                f"({doc_role}). Do NOT copy-paste the feedback verbatim.\n"
                "4. Keep the document focused on its own role; content that "
                "belongs in a sibling document should not be duplicated here."
            )
            if "qwen" in self.model_name.lower():
                sys_prompt += "\n/no_think"

            # 上游已更新文档作为 context（顺序保证 backup 看到新 plan、
            # recover 看到新 plan + 新 backup）
            upstream_block = ""
            for upstream_name, _ in self._REFINE_DOC_ROLES:
                if upstream_name == doc_name:
                    break
                upstream_content = latest_contents.get(upstream_name, "").strip()
                if upstream_content:
                    upstream_block += (
                        f"\n### Latest `{upstream_name}` (just rewritten this "
                        "round; use as context for consistency)\n"
                        f"```\n{upstream_content[:3000]}\n```\n"
                    )

            current_content = latest_contents[doc_name]
            current_block = (
                f"```\n{current_content[:4000]}\n```"
                if current_content
                else "(empty / not yet authored)"
            )

            failure_block = (
                f"\n## Past failure examples\n{failure_docs}"
                if failure_docs
                else ""
            )
            task_block = f"\n## Task intent\n{task_intent}" if task_intent else ""

            user_prompt = (
                f"# Skill package: {self._skill.skill_id}"
                f"{task_block}\n\n"
                f"## Current `{doc_name}`\n{current_block}\n"
                f"{upstream_block}"
                f"\n## Verifier feedback (this rollout)\n{feedback_text}\n"
                f"{failure_block}\n"
                f"Now produce the new content for `{doc_name}`. Output either "
                "the complete new markdown document (no code fences, no "
                "commentary) OR the single token KEEP_UNCHANGED."
            )

            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ]
            response = self._safe_chat_completion(messages)
            if response is None:
                logger.warning(
                    f"[evo_skill_agent] refine {doc_name}: LLM returned None; "
                    "leaving document unchanged"
                )
                edits.append(
                    {
                        "tool": "refine_doc_skip",
                        "args": {"path": f"docs/{doc_name}"},
                        "ok": False,
                        "output_excerpt": "",
                        "error": "llm_returned_none",
                    }
                )
                continue

            new_content = self._postprocess_refine_doc_response(response)

            if new_content == "KEEP_UNCHANGED":
                logger.info(
                    f"[evo_skill_agent] refine {doc_name}: KEEP_UNCHANGED"
                )
                edits.append(
                    {
                        "tool": "keep_unchanged",
                        "args": {"path": f"docs/{doc_name}"},
                        "ok": True,
                        "output_excerpt": "(no change)",
                        "error": None,
                    }
                )
                continue

            if not new_content or len(new_content) < 20:
                logger.warning(
                    f"[evo_skill_agent] refine {doc_name}: output too short "
                    f"({len(new_content)} chars); leaving document unchanged"
                )
                edits.append(
                    {
                        "tool": "refine_doc_skip",
                        "args": {"path": f"docs/{doc_name}"},
                        "ok": False,
                        "output_excerpt": new_content[:200],
                        "error": "output_too_short",
                    }
                )
                continue

            self._skill.write_doc(doc_name, new_content)
            latest_contents[doc_name] = new_content
            edits.append(
                {
                    "tool": "write_doc",
                    "args": {"path": f"docs/{doc_name}"},
                    "ok": True,
                    "output_excerpt": new_content[:200],
                    "error": None,
                }
            )
            logger.info(
                f"[evo_skill_agent] refine {doc_name}: rewrote "
                f"({len(current_content)} -> {len(new_content)} chars)"
            )

        self._skill_edit_log.extend(edits)
        return edits

    def reset(self) -> None:
        super().reset()
