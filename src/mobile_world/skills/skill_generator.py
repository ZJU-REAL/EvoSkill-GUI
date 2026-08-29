"""使用 VLM 生成初始技能包。

此模块复用执行 Agent 的 OpenAI 客户端配置（同模型、同 base_url），调用
单轮对话拿到 JSON，然后通过 ``SkillManager.create`` 落盘。
"""

from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger
from openai import OpenAI
from PIL import Image

from mobile_world.agents.utils.helpers import pil_to_base64
from mobile_world.agents.utils.prompts.skill_gen import (
    SKILL_GEN_BACKUP_USER_PROMPT_TEMPLATE,
    SKILL_GEN_META_PLAN_USER_PROMPT_TEMPLATE,
    SKILL_GEN_RECOVER_USER_PROMPT_TEMPLATE,
    SKILL_GEN_SYSTEM_PROMPT,
)
from mobile_world.runtime.utils.parsers import parse_json_markdown
from mobile_world.skills.skill_manager import SkillManager, SkillMeta, SkillPackage


class SkillGenerator:
    """根据任务 instruction（+ 可选首屏截图 / a11y）生成初始技能包。"""

    def __init__(
        self,
        client: OpenAI,
        model_name: str,
        manager: SkillManager,
        max_tokens: int = 3072,
        temperature: float = 0.3,
    ):
        self.client = client
        self.model_name = model_name
        self.manager = manager
        self.max_tokens = max_tokens
        self.temperature = temperature

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        task_name: str,
        instruction: str,
        initial_screenshot: Image.Image | None = None,
        initial_a11y: str | None = None,
    ) -> SkillPackage:
        """按 meta+plan -> backup -> recover 顺序生成并保存技能包。"""
        payload = self._generate_sequential(
            task_name, instruction, initial_screenshot, initial_a11y
        )

        return self._materialize(task_name, instruction, payload)

    # ------------------------------------------------------------------
    # Sequential generation
    # ------------------------------------------------------------------

    def _generate_sequential(
        self,
        task_name: str,
        instruction: str,
        initial_screenshot: Image.Image | None,
        initial_a11y: str | None,
    ) -> dict:
        """三步顺序生成 plan -> backup -> recover.

        每步独立 LLM 调用；plan 拿到完整的输入（含 screenshot / a11y），
        backup 和 recover 仅以已确定的 plan / backup 文本为上下文。
        任何一步解析失败都回退到 ``_fallback_payload``，保证流程不中断。
        """
        a11y_excerpt = self._truncate_a11y(initial_a11y)

        # ---- Step 1: meta + plan ----
        meta_plan_user = SKILL_GEN_META_PLAN_USER_PROMPT_TEMPLATE.render(
            task_name=task_name,
            instruction=instruction,
            initial_a11y=a11y_excerpt,
        )
        try:
            raw1 = self._chat_completion(
                user_text=meta_plan_user,
                attach_screenshot=initial_screenshot,
                system_prompt=SKILL_GEN_SYSTEM_PROMPT,
            )
            meta_plan_payload = self._parse_payload(raw1)
        except Exception as e:
            logger.warning(
                f"[skill_gen.sequential] meta+plan step failed ({e}); "
                "falling back to minimal skill."
            )
            logger.debug(f"Raw response was:\n{raw1!r}" if 'raw1' in dir() else "")
            return self._fallback_payload(task_name, instruction)

        plan_md = str(meta_plan_payload.get("plan_md") or "").strip()
        if not plan_md:
            logger.warning(
                "[skill_gen.sequential] meta+plan step returned empty plan_md; "
                "falling back."
            )
            return self._fallback_payload(task_name, instruction)

        # ---- Step 2: backup (depends on final plan) ----
        backup_md = ""
        backup_user = SKILL_GEN_BACKUP_USER_PROMPT_TEMPLATE.render(
            instruction=instruction,
            plan_md=plan_md,
        )
        try:
            raw2 = self._chat_completion(
                user_text=backup_user,
                attach_screenshot=None,  # 已有 plan 上下文，无需再传图
                system_prompt=SKILL_GEN_SYSTEM_PROMPT,
            )
            backup_payload = self._parse_payload(raw2)
            backup_md = str(backup_payload.get("backup_md") or "").strip()
        except Exception as e:
            logger.warning(
                f"[skill_gen.sequential] backup step failed ({e}); "
                "leaving backup.md empty."
            )

        # ---- Step 3: recover (depends on final plan + backup) ----
        recover_md = ""
        recover_user = SKILL_GEN_RECOVER_USER_PROMPT_TEMPLATE.render(
            instruction=instruction,
            plan_md=plan_md,
            backup_md=backup_md or "(empty)",
        )
        try:
            raw3 = self._chat_completion(
                user_text=recover_user,
                attach_screenshot=None,
                system_prompt=SKILL_GEN_SYSTEM_PROMPT,
            )
            recover_payload = self._parse_payload(raw3)
            recover_md = str(recover_payload.get("recover_md") or "").strip()
        except Exception as e:
            logger.warning(
                f"[skill_gen.sequential] recover step failed ({e}); "
                "leaving recover.md empty."
            )

        # 合并：以 step1 的 meta 为主，补上 step2/3 的 doc 内容
        merged = dict(meta_plan_payload)
        merged["plan_md"] = plan_md
        merged["backup_md"] = backup_md
        merged["recover_md"] = recover_md
        return merged

    @staticmethod
    def _truncate_a11y(initial_a11y: str | None) -> str | None:
        if not initial_a11y:
            return None
        return (
            initial_a11y
            if len(initial_a11y) <= 4000
            else initial_a11y[:4000] + "\n... [truncated]"
        )

    def _chat_completion(
        self,
        user_text: str,
        attach_screenshot: Image.Image | None,
        system_prompt: str,
    ) -> str:
        """通用单轮 chat completion；可选附图。"""
        user_content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
        if attach_screenshot is not None:
            try:
                b64 = pil_to_base64(attach_screenshot)
                user_content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to attach initial screenshot: {e}")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        kwargs: dict[str, Any] = {
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        if "claude" in self.model_name.lower():
            kwargs.pop("temperature", None)
            kwargs["max_tokens"] = max(self.max_tokens, 4096)
        if "gpt" in self.model_name.lower() or "o1" in self.model_name.lower():
            kwargs["max_completion_tokens"] = kwargs.pop("max_tokens", self.max_tokens)

        response = self.client.chat.completions.create(
            model=self.model_name,
            timeout=300,
            messages=messages,
            **kwargs,
        )
        return response.choices[0].message.content or ""

    @staticmethod
    def _parse_payload(raw: str) -> dict:
        text = (raw or "").strip()
        if not text:
            raise ValueError("Empty LLM response")
        # 优先尝试解析 markdown JSON 块
        try:
            return parse_json_markdown(text)
        except Exception:
            pass
        # 兜底 1：从首个 '{' 到末尾找一个平衡的 JSON 子串
        start = text.find("{")
        if start == -1:
            raise ValueError("No JSON object detected in LLM response")
        depth = 0
        candidate: str | None = None
        for i in range(start, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    break
        if candidate is None:
            raise ValueError("Unbalanced JSON braces in LLM response")
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
        # 兜底 2：用 json_repair 修复 LLM 常见的 JSON 错误
        # （如未转义的内嵌引号、缺逗号、单引号、注释等）
        try:
            from json_repair import repair_json  # 延迟导入，避免硬依赖
        except ImportError as e:
            raise ValueError(
                f"JSON parse failed and json_repair is not installed: {e}. "
                "Please `pip install json-repair`."
            ) from e
        repaired = repair_json(candidate, return_objects=False)
        return json.loads(repaired)

    def _fallback_payload(self, task_name: str, instruction: str) -> dict:
        return {
            "skill_id": None,
            "task_intent": instruction[:160],
            "domain_app": [],
            "platform": "Android",
            "keywords": _auto_keywords(instruction),
            "arguments": [],
            "plan_md": (
                f"# Plan for {task_name}\n\n"
                "1. Read the task instruction carefully and identify the target app(s).\n"
                "2. Open the target app from the home screen.\n"
                "3. Perform the requested actions step by step.\n"
                "4. Verify the result on screen and answer the user if needed.\n"
            ),
            "backup_md": (
                "# Backup locator strategies\n\n"
                "- Prefer text/content-description match over absolute coordinates.\n"
                "- If the primary element is missing, scroll once in the most likely direction.\n"
                "- Fall back to OCR within the relevant region.\n"
            ),
            "recover_md": (
                "# Recovery strategies\n\n"
                "- Cookie / consent dialogs: dismiss with the most positive button.\n"
                "- Permission popups: grant the minimum required.\n"
                "- 'Use without account' / sign-in walls: pick the no-account path.\n"
            ),
        }

    def _materialize(self, task_name: str, instruction: str, payload: dict) -> SkillPackage:
        suggested = payload.get("skill_id") or None
        if suggested:
            suggested = re.sub(r"[^A-Za-z0-9_-]+", "_", str(suggested)).strip("_")
        skill_id = suggested if suggested and not self.manager.exists(suggested) else None
        if skill_id is None:
            skill_id = self.manager.make_skill_id(
                task_intent=payload.get("task_intent") or instruction,
                task_name=task_name,
            )

        meta = SkillMeta(
            skill_id=skill_id,
            task_intent=str(payload.get("task_intent") or instruction)[:280],
            domain_app=[str(x) for x in (payload.get("domain_app") or []) if x],
            platform=str(payload.get("platform") or "Android"),
            keywords=[str(x) for x in (payload.get("keywords") or []) if x][:20],
            arguments=[str(x) for x in (payload.get("arguments") or []) if x][:20],
        )

        pkg = self.manager.create(
            meta=meta,
            plan_md=str(payload.get("plan_md") or ""),
            backup_md=str(payload.get("backup_md") or ""),
            recover_md=str(payload.get("recover_md") or ""),
            overwrite=False,
        )
        logger.info(
            f"Generated skill package '{skill_id}' for task '{task_name}' at {pkg.root}"
        )
        return pkg


def _auto_keywords(text: str, k: int = 6) -> list[str]:
    tokens = re.findall(r"[\w']+", text or "", flags=re.UNICODE)
    seen = []
    for t in tokens:
        tl = t.lower()
        if len(tl) >= 3 and tl not in seen:
            seen.append(tl)
        if len(seen) >= k:
            break
    return seen
