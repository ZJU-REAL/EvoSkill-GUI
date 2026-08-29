"""信息隔离的轨迹验证器（Verifier）。

Verifier 与执行 Agent 完全独立：
- 它不接受任何 ``thought`` / ``prediction`` 字段
- 它不读取技能包文档
- 它只读取从 ``traj.json`` / 截图目录 / a11y 日志 中提取的"客观事实"
- 它持有自己的 ``state_assertions`` 历史，并将其作为下一轮的输入
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger
from openai import OpenAI

from mobile_world.agents.utils.helpers import pil_adaptive_resize, pil_to_base64
from mobile_world.agents.utils.prompts.verifier import (
    VERIFIER_SYSTEM_PROMPT,
    VERIFIER_USER_PROMPT_TEMPLATE,
)
from mobile_world.runtime.utils.parsers import parse_json_markdown
from mobile_world.skills.a11y_utils import (
    _step_index_from_name,
    collect_a11y_summary,
)

# Verifier 允许看见的 action 字段（主动白名单：未列入的不会进入 prompt）
ALLOWED_ACTION_KEYS = {
    "action_type",
    "x",
    "y",
    "text",
    "direction",
    "goal_status",
    "app_name",
    "start_x",
    "start_y",
    "end_x",
    "end_y",
    "action_name",
    "action_json",
}


@dataclass
class VerifierFeedback:
    """Verifier 输出，对外的统一数据结构。"""

    task_success: bool = False
    failure_type: str = "other"
    failed_step: int | None = None
    diagnosis: str = ""
    root_cause: str = ""
    suggestions: list[str] = field(default_factory=list)
    state_assertions: list[str] = field(default_factory=list)
    raw: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("raw", None)
        return d

    @classmethod
    def from_payload(cls, payload: dict, raw: str = "") -> VerifierFeedback:
        return cls(
            task_success=bool(payload.get("task_success", False)),
            failure_type=str(payload.get("failure_type") or "other"),
            failed_step=_coerce_failed_step(payload.get("failed_step")),
            diagnosis=str(payload.get("diagnosis") or ""),
            root_cause=str(payload.get("root_cause") or ""),
            suggestions=[str(s) for s in (payload.get("suggestions") or []) if s],
            state_assertions=[str(s) for s in (payload.get("state_assertions") or []) if s],
            raw=raw,
        )


def _coerce_failed_step(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        s = value.strip()
        if s.lstrip("-").isdigit():
            return int(s)
    return None


def sanitize_action(action: dict | None) -> dict:
    """从 traj.json 中的 action dict 提炼出允许喂给 Verifier 的字段。"""
    if not isinstance(action, dict):
        return {}
    return {k: v for k, v in action.items() if k in ALLOWED_ACTION_KEYS}


def collect_traj_actions(
    traj_json_path: str | os.PathLike,
) -> list[dict[str, Any]]:
    """从 traj.json 提取 step / action，并排除执行 Agent 的内部推理。"""
    path = Path(traj_json_path)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8") or "{}")
    actions: list[dict[str, Any]] = []
    for task_id, task_blob in data.items():
        if not isinstance(task_blob, dict):
            continue
        for entry in task_blob.get("traj", []) or []:
            record: dict[str, Any] = {
                "step": int(entry.get("step", len(actions) + 1)),
                "action_json": json.dumps(
                    sanitize_action(entry.get("action") or {}),
                    ensure_ascii=False,
                ),
                "tool_call": entry.get("tool_call"),
            }
            actions.append(record)
    actions.sort(key=lambda x: x["step"])
    return actions


def collect_screenshots(
    screenshot_dir: str | os.PathLike,
    *,
    max_screenshots: int = 12,
) -> list[Path]:
    """收集截图文件，时间序保留首尾，多余者按等距采样。"""
    sdir = Path(screenshot_dir)
    if not sdir.exists():
        return []
    files = sorted(
        (p for p in sdir.iterdir() if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg"}),
        key=lambda p: _step_index_from_name(p.name),
    )
    if len(files) <= max_screenshots:
        return files
    # 等距采样，保留首尾
    n = len(files)
    indices = sorted({0, n - 1, *[round(i * (n - 1) / (max_screenshots - 1)) for i in range(max_screenshots)]})
    indices = sorted(set(indices))[:max_screenshots]
    return [files[i] for i in indices]


class Verifier:
    """信息隔离的 Verifier。

    与执行 Agent 共用同一个底层模型，但通过显式 prompt + 受控数据通道
    保证信息隔离。
    """

    def __init__(
        self,
        client: OpenAI,
        model_name: str,
        max_screenshots: int = 8,
        max_a11y_steps: int = 12,
        max_a11y_per_step: int = 12,
        max_tokens: int = 1500,
        temperature: float = 0.0,
        screenshot_max_dim: int = 1280,
    ):
        self.client = client
        self.model_name = model_name
        self.max_screenshots = max_screenshots
        # a11y 默认比截图多采几步，专门补截图未覆盖的"空隙"
        self.max_a11y_steps = max_a11y_steps
        self.max_a11y_per_step = max_a11y_per_step
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.screenshot_max_dim = screenshot_max_dim

        # 持久化自己历轮的 state assertions
        self.previous_assertions: list[str] = []

    def reset(self) -> None:
        self.previous_assertions = []

    def diagnose(
        self,
        instruction: str,
        traj_json_path: str | os.PathLike,
        screenshots_dir: str | os.PathLike,
        a11y_dir: str | os.PathLike | None = None,
        final_state: str | None = None,
        ground_truth_score: float | None = None,
        ground_truth_reason: str | None = None,
    ) -> VerifierFeedback:
        actions = collect_traj_actions(traj_json_path)
        screenshots = collect_screenshots(screenshots_dir, max_screenshots=self.max_screenshots)
        # 截图覆盖的 step indices；a11y 优先补充截图未覆盖的步骤。
        #
        # 注意截图与 a11y 的 step 语义不同：
        # - screenshot N (TaskName-0-N.png) = agent 在第 N 步看到的屏幕，
        #   对应 step N-1 执行*之后*的状态（step 1 = initialize_task 后）。
        # - a11y step_N.json 由 wrap_env 在 execute_action 之后抓取，
        #   表示 step N 的动作*之后*的屏幕。
        #   外加我们在 _capture_initial_a11y 里手动落了 step_000.json
        #   表示初始屏。
        # 因此 screenshot N ↔ a11y N-1 是同一画面。
        shot_step_indices = {_step_index_from_name(s.name) for s in screenshots}
        excluded_a11y_indices = {max(i - 1, 0) for i in shot_step_indices}
        a11y_summary = (
            collect_a11y_summary(
                a11y_dir,
                max_per_step=self.max_a11y_per_step,
                max_steps=self.max_a11y_steps,
                exclude_step_indices=excluded_a11y_indices,
            )
            if a11y_dir
            else ""
        )
        logger.debug(
            f"[verifier] screenshots@steps={sorted(shot_step_indices)} "
            f"excluded_a11y@steps={sorted(excluded_a11y_indices)} "
            f"a11y_chars={len(a11y_summary)}"
        )

        final_text = final_state or ""
        # 只告诉 Verifier 成败二值，不给具体原因——让它自己从证据中找 root cause
        oracle_outcome: str | None = None
        if ground_truth_score is not None:
            oracle_outcome = "SUCCESS" if ground_truth_score >= 1.0 else "FAILED"
            logger.debug(
                f"[verifier] oracle_outcome={oracle_outcome} "
                f"(score={ground_truth_score}, reason hidden from LLM)"
            )

        user_text = VERIFIER_USER_PROMPT_TEMPLATE.render(
            instruction=instruction,
            actions=actions,
            a11y_summary=a11y_summary,
            final_state=final_text,
            previous_assertions=self.previous_assertions,
            oracle_outcome=oracle_outcome,
        )

        user_content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
        for shot in screenshots:
            try:
                from PIL import Image as _Image

                img = _Image.open(shot).convert("RGB")
                img, _, _ = pil_adaptive_resize(img, self.screenshot_max_dim)
                b64 = pil_to_base64(img)
                user_content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    }
                )
            except Exception as e:
                logger.warning(f"Verifier failed to attach screenshot {shot}: {e}")

        messages = [
            {"role": "system", "content": VERIFIER_SYSTEM_PROMPT},
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
        # qwen36-35b-a3b 的 thinking 链在 verifier 场景经常撑爆 max_tokens
        # 导致 content 为空（finish_reason=length）。这里只针对该模型显式关闭
        # thinking，避免影响其他 qwen 模型的默认行为。
        if "qwen36-35b-a3b" in self.model_name.lower():
            extra = kwargs.setdefault("extra_body", {})
            extra.setdefault("chat_template_kwargs", {})["enable_thinking"] = False

        # Retry with exponential backoff for rate limits / transient errors
        max_retries = 4
        raw = ""
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    timeout=300,
                    **kwargs,
                )
                raw = response.choices[0].message.content or ""
                break
            except Exception as e:
                err_str = str(e).lower()
                if "429" in str(e) or "rate" in err_str or "timeout" in err_str:
                    wait = 2 ** attempt * 5  # 5s, 10s, 20s, 40s
                    logger.warning(
                        f"Verifier LLM call failed (attempt {attempt+1}/{max_retries}): {e}; "
                        f"retrying in {wait}s"
                    )
                    import time
                    time.sleep(wait)
                else:
                    logger.error(f"Verifier LLM call failed (non-retryable): {e}")
                    raise
        else:
            logger.error(f"Verifier LLM call failed after {max_retries} retries")
            raw = ""

        try:
            payload = self._parse_json(raw)
        except Exception as e:
            logger.warning(f"Verifier output is not parseable JSON ({e}); raw=\n{raw}")
            payload = {
                "task_success": False,
                "failure_type": "other",
                "failed_step": None,
                "diagnosis": raw[:500],
                "root_cause": "verifier_parse_error",
                "suggestions": [],
                "state_assertions": [],
            }

        feedback = VerifierFeedback.from_payload(payload, raw=raw)
        # 留作下一轮上下文
        self.previous_assertions = list(feedback.state_assertions)
        return feedback

    @staticmethod
    def _parse_json(raw: str) -> dict:
        text = (raw or "").strip()
        if not text:
            raise ValueError("Empty verifier response")
        try:
            return parse_json_markdown(text)
        except Exception:
            pass
        start = text.find("{")
        if start == -1:
            raise ValueError("No JSON object detected")
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[start : i + 1])
        raise ValueError("Unbalanced JSON")
