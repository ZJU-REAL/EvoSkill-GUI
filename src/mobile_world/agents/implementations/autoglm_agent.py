"""AutoGLM-Phone agent implementation for MobileWorld.

The action grammar matches the upstream Open-AutoGLM project
(https://github.com/zai-org/Open-AutoGLM): the model emits a single
``<think>...</think><answer>...</answer>`` block and the answer body is a
Python-style ``do(action=..., **kwargs)`` or ``finish(message=...)`` call.

Reference implementations:
- Action handler: ``Open-AutoGLM/phone_agent/actions/handler.py`` (parse_action)
- Streaming client: ``Open-AutoGLM/phone_agent/model/client.py``
- Prompts: ``Open-AutoGLM/phone_agent/config/prompts_{en,zh}.py``

We deliberately keep the externally observable behaviour (action names, scaling,
streaming, frequency penalty) close to upstream so that ``AutoGLM-Phone-9B`` and
``AutoGLM-Phone-9B-Multilingual`` checkpoints can be evaluated as-is.
"""

import ast
import json
import os
import re
import time
from typing import Any

from loguru import logger
from PIL import Image

from mobile_world.agents.base import MCPAgent
from mobile_world.agents.utils.helpers import pil_to_base64
from mobile_world.agents.utils.prompts.autoglm import (
    AUTOGLM_SYSTEM_PROMPT_EN,
    AUTOGLM_SYSTEM_PROMPT_ZH,
    AUTOGLM_USER_HEADER_TEMPLATE,
)
from mobile_world.runtime.utils.helpers import pretty_print_messages
from mobile_world.runtime.utils.models import (
    ANSWER,
    ASK_USER,
    CLICK,
    DOUBLE_TAP,
    DRAG,
    INPUT_TEXT,
    LONG_PRESS,
    MCP,
    NAVIGATE_BACK,
    NAVIGATE_HOME,
    OPEN_APP,
    UNKNOWN,
    WAIT,
    JSONAction,
)


# AutoGLM uses a 0-999 normalised coordinate space (see prompts).
AUTOGLM_SCALE_FACTOR = 1000


def _strip_answer_wrapper(action_text: str) -> str:
    """Strip surrounding ``<answer>...</answer>`` tags if present."""
    text = action_text.strip()
    text = re.sub(r"^<answer>\s*", "", text)
    text = re.sub(r"\s*</answer>$", "", text)
    return text.strip()


def _parse_thinking_action(raw_response: str) -> tuple[str, str]:
    """Split the raw model output into ``(thinking, action_call)``.

    Mirrors ``Open-AutoGLM/phone_agent/model/client.py::_parse_response``: prefer
    the first ``finish(message=`` / ``do(action=`` marker, fall back to
    ``<think>``/``<answer>`` XML tags.
    """
    if raw_response is None:
        return "", ""

    content = raw_response.strip()

    # Rule 1: explicit pseudo-code anchors.
    for marker in ("finish(message=", "do(action="):
        if marker in content:
            head, tail = content.split(marker, 1)
            thinking = head
            # Drop a trailing "<answer>" if the model emitted both forms.
            thinking = re.sub(r"<answer>\s*$", "", thinking).strip()
            thinking = re.sub(r"<think>", "", thinking)
            thinking = re.sub(r"</think>", "", thinking).strip()
            action = marker + tail
            # 只取第一个完整的 do(...) / finish(...)，忽略后续内容
            # 匹配到最外层右括号结束
            paren_depth = 0
            end_idx = 0
            for i, ch in enumerate(action):
                if ch == "(":
                    paren_depth += 1
                elif ch == ")":
                    paren_depth -= 1
                    if paren_depth == 0:
                        end_idx = i + 1
                        break
            if end_idx > 0:
                action = action[:end_idx]
            action = _strip_answer_wrapper(action)
            return thinking, action

    # Rule 2: XML tag fallback.
    if "<answer>" in content:
        head, tail = content.split("<answer>", 1)
        thinking = head.replace("<think>", "").replace("</think>", "").strip()
        action = tail.split("</answer>", 1)[0].strip()
        return thinking, action

    return "", content


def parse_autoglm_action(action_str: str) -> dict[str, Any]:
    """Parse an AutoGLM ``do(...)`` / ``finish(...)`` call into a dict.

    Adapted from ``Open-AutoGLM/phone_agent/actions/handler.py::parse_action``
    but more tolerant of whitespace and stray wrappers, since MobileWorld
    serves slightly different prompts.
    """
    if not action_str:
        raise ValueError("Empty action string")

    response = _strip_answer_wrapper(action_str)

    # Special-case Type / Type_Name: text may legitimately contain commas,
    # quotes, etc., so we parse manually instead of relying on AST.
    type_match = re.match(
        r'^do\(\s*action\s*=\s*"(Type|Type_Name)"\s*,\s*text\s*=\s*"(.*)"\s*\)\s*$',
        response,
        re.DOTALL,
    )
    if type_match:
        return {
            "_metadata": "do",
            "action": type_match.group(1),
            "text": type_match.group(2),
        }

    if response.startswith("do"):
        # Escape characters that would break ``ast.parse``.
        normalised = (
            response.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
        )
        try:
            tree = ast.parse(normalised, mode="eval")
            if not isinstance(tree.body, ast.Call):
                raise ValueError("Expected a function call")
            call = tree.body
            action: dict[str, Any] = {"_metadata": "do"}
            for keyword in call.keywords:
                key = keyword.arg
                value = ast.literal_eval(keyword.value)
                action[key] = value
            return action
        except (SyntaxError, ValueError) as exc:
            raise ValueError(f"Failed to parse do() action: {exc}; raw={response}")

    if response.startswith("finish"):
        # ``finish(message="...")`` - extract message robustly.
        msg_match = re.match(
            r'^finish\(\s*message\s*=\s*"(.*)"\s*\)\s*$', response, re.DOTALL
        )
        if msg_match:
            return {"_metadata": "finish", "message": msg_match.group(1)}
        # Fall back to AST parsing.
        try:
            tree = ast.parse(response, mode="eval")
            if isinstance(tree.body, ast.Call):
                kwargs = {kw.arg: ast.literal_eval(kw.value) for kw in tree.body.keywords}
                return {"_metadata": "finish", **kwargs}
        except (SyntaxError, ValueError):
            pass
        return {"_metadata": "finish", "message": response}

    raise ValueError(f"Unrecognised AutoGLM action: {response!r}")


def _to_pixel(value: Any, dimension: int) -> int:
    """Convert a 0-999 normalised coordinate to absolute pixels."""
    try:
        coord = float(value)
    except (TypeError, ValueError):
        coord = 0.0
    return int(coord / AUTOGLM_SCALE_FACTOR * dimension)


def _parse_duration(raw: Any, default: float = 1.0) -> float:
    """Parse strings like ``'2 seconds'`` or numeric values to seconds."""
    if raw is None:
        return default
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip().lower()
    text = text.replace("seconds", "").replace("second", "").replace("s", "").strip()
    try:
        return float(text)
    except ValueError:
        return default


def transform_autoglm_action(
    action: dict[str, Any], image_width: int, image_height: int
) -> dict[str, Any]:
    """Map a parsed AutoGLM action dict to a MobileWorld JSONAction dict."""

    metadata = action.get("_metadata")

    if metadata == "finish":
        return {"action_type": ANSWER, "text": str(action.get("message", "")).strip() or "done"}

    if metadata != "do":
        return {"action_type": UNKNOWN, "text": f"Unknown metadata: {metadata}"}

    name = action.get("action")
    if not name:
        return {"action_type": UNKNOWN, "text": "Missing action name"}

    if name == "Tap":
        element = action.get("element") or [0, 0]
        return {
            "action_type": CLICK,
            "x": _to_pixel(element[0], image_width),
            "y": _to_pixel(element[1], image_height),
        }

    if name == "Double Tap":
        element = action.get("element") or [0, 0]
        return {
            "action_type": DOUBLE_TAP,
            "x": _to_pixel(element[0], image_width),
            "y": _to_pixel(element[1], image_height),
        }

    if name == "Long Press":
        element = action.get("element") or [0, 0]
        return {
            "action_type": LONG_PRESS,
            "x": _to_pixel(element[0], image_width),
            "y": _to_pixel(element[1], image_height),
        }

    if name in ("Type", "Type_Name"):
        return {"action_type": INPUT_TEXT, "text": str(action.get("text", ""))}

    if name == "Swipe":
        start = action.get("start") or [0, 0]
        end = action.get("end") or [0, 0]
        return {
            "action_type": DRAG,
            "start_x": _to_pixel(start[0], image_width),
            "start_y": _to_pixel(start[1], image_height),
            "end_x": _to_pixel(end[0], image_width),
            "end_y": _to_pixel(end[1], image_height),
        }

    if name == "Launch":
        return {"action_type": OPEN_APP, "app_name": str(action.get("app", ""))}

    if name == "Back":
        return {"action_type": NAVIGATE_BACK}

    if name == "Home":
        return {"action_type": NAVIGATE_HOME}

    if name == "Wait":
        # MobileWorld's WAIT does not take a duration argument, but downstream
        # consumers happily ignore extras; keep the field for traceability.
        return {"action_type": WAIT}

    if name in ("Take_over", "Interact"):
        return {
            "action_type": ASK_USER,
            "text": str(action.get("message", "")) or f"{name} requested",
        }

    if name in ("Note", "Call_API"):
        # No direct MobileWorld equivalent; emit a no-op WAIT so the loop keeps
        # going and the trajectory still records the model's intent.
        logger.info(f"AutoGLM produced a {name} action; treating as a no-op WAIT.")
        return {"action_type": WAIT}

    # Anything else is interpreted as an MCP tool invocation. The argument
    # convention follows the prompt: ``do(action="<tool>", arguments={...})``.
    arguments = action.get("arguments")
    if arguments is None:
        arguments = {k: v for k, v in action.items() if k not in ("_metadata", "action")}
    if not isinstance(arguments, dict):
        arguments = {"value": arguments}
    return {
        "action_type": MCP,
        "action_name": name,
        "action_json": arguments,
    }


class AutoGLMAgent(MCPAgent):
    """End-to-end agent that drives MobileWorld with an AutoGLM-Phone model.

    Args:
        model_name: served model name (e.g. ``autoglm-phone-9b-multilingual``).
        llm_base_url: OpenAI-compatible base URL (vLLM, z.ai, Novita, etc.).
        api_key: API key for the LLM endpoint, ``"empty"`` for self-hosted.
        runtime_conf: optional overrides for sampling parameters and history.
        lang: ``"en"`` (default) or ``"cn"`` to mirror the upstream prompt set.
        tools: MCP tool descriptors injected by the runner.
    """

    def __init__(
        self,
        model_name: str,
        llm_base_url: str,
        api_key: str = "empty",
        runtime_conf: dict[str, Any] | None = None,
        lang: str = "en",
        tools: list[dict] | None = None,
        enable_user_interaction: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(tools=tools or [], **kwargs)

        default_conf: dict[str, Any] = {
            "history_n_images": 3,
            "max_tokens": 3000,
            "temperature": 0.0,
            "top_p": 0.85,
            "frequency_penalty": 0.2,
        }
        self.runtime_conf: dict[str, Any] = {**default_conf, **(runtime_conf or {})}

        self.model_name = model_name
        self.llm_base_url = llm_base_url
        self.api_key = api_key
        self.lang = lang.lower()
        self.enable_user_interaction = enable_user_interaction

        self.history_n_images = self.runtime_conf.pop("history_n_images", 3)
        if os.getenv("HISTORY_N_IMAGES") is not None:
            try:
                self.history_n_images = int(os.environ["HISTORY_N_IMAGES"])
            except ValueError:
                logger.warning(
                    "Invalid HISTORY_N_IMAGES env var: %s",
                    os.environ.get("HISTORY_N_IMAGES"),
                )

        self.build_openai_client(self.llm_base_url, self.api_key)
        logger.debug(
            f"AutoGLM agent ready model={self.model_name} base_url={self.llm_base_url} "
            f"history_n_images={self.history_n_images} lang={self.lang}"
        )

        # Per-task state (mirrors GeneralE2EAgentMCP).
        self.history_images: list[tuple[Image.Image, Any, Any]] = []
        self.history_responses: list[str] = []
        self.actions: list[dict[str, Any]] = []

    def initialize_hook(self, instruction: str) -> None:
        logger.info(f"Initializing AutoGLM agent with instruction: {instruction}")
        self.reset()

    def reset(self) -> None:
        self.history_images = []
        self.history_responses = []
        self.actions = []

    def _system_prompt(self) -> str:
        template = (
            AUTOGLM_SYSTEM_PROMPT_ZH if self.lang.startswith("cn") else AUTOGLM_SYSTEM_PROMPT_EN
        )
        rendered_tools = ""
        if self.tools:
            rendered_tools = "\n".join(
                json.dumps(tool, ensure_ascii=False) for tool in self.tools
            )
        return template.render(
            tools=rendered_tools,
            enable_user_interaction=self.enable_user_interaction,
        )

    def _build_user_message(
        self,
        screenshot_b64: str,
        tool_call_res: Any,
        ask_user_res: Any,
        is_first: bool,
    ) -> dict[str, Any]:
        content: list[dict[str, Any]] = []

        if is_first:
            screen_info = json.dumps({"current_app": "unknown"}, ensure_ascii=False)
            header = AUTOGLM_USER_HEADER_TEMPLATE.render(
                instruction=self.instruction,
                screen_info=screen_info,
            )
            content.append({"type": "text", "text": header})

        if tool_call_res is not None:
            tool_text = (
                json.dumps(tool_call_res, ensure_ascii=False)
                if isinstance(tool_call_res, (dict, list))
                else str(tool_call_res)
            )
            content.append({"type": "text", "text": f"Tool call result: {tool_text}"})
        elif ask_user_res is not None:
            content.append({"type": "text", "text": f"User reply: {ask_user_res}"})

        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"},
            }
        )

        if not is_first:
            # Mimic Open-AutoGLM, which sends ``** Screen Info **`` between turns.
            content.append({"type": "text", "text": "** Screen Info **"})

        return {"role": "user", "content": content}

    def _build_messages(self) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._system_prompt()}
        ]

        for idx, (img, tool_res, ask_res) in enumerate(self.history_images):
            screenshot_b64 = pil_to_base64(img)
            user_msg = self._build_user_message(
                screenshot_b64=screenshot_b64,
                tool_call_res=tool_res,
                ask_user_res=ask_res,
                is_first=(idx == 0),
            )
            messages.append(user_msg)
            if idx < len(self.history_responses):
                messages.append(
                    {"role": "assistant", "content": self.history_responses[idx]}
                )

        return self._hide_history_images(messages)

    def _hide_history_images(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keep only the most recent ``history_n_images`` image attachments."""
        kept = 0
        for message in reversed(messages):
            if message.get("role") != "user":
                continue
            content = message.get("content")
            if not isinstance(content, list):
                continue
            new_content: list[dict[str, Any]] = []
            for item in content:
                if item.get("type") == "image_url":
                    if kept < self.history_n_images:
                        new_content.append(item)
                        kept += 1
                    else:
                        new_content.append(
                            {"type": "text", "text": "(Previous turn, screen not shown)"}
                        )
                else:
                    new_content.append(item)
            message["content"] = new_content
        return messages

    def predict(self, observation: dict[str, Any]) -> tuple[str, JSONAction]:
        screenshot = observation.get("screenshot")
        if not isinstance(screenshot, Image.Image):
            raise ValueError("AutoGLM agent expects a PIL Image screenshot")

        tool_call = observation.get("tool_call")
        ask_user_response = observation.get("ask_user_response")

        self.history_images.append((screenshot, tool_call, ask_user_response))
        assert len(self.history_images) == len(self.history_responses) + 1

        messages = self._build_messages()
        pretty_print_messages(messages, max_messages=6)

        try_times = 3
        raw_response: str | None = None
        while try_times > 0:
            try:
                raw_response = self.openai_chat_completions_create(
                    model=self.model_name,
                    messages=messages,
                    retry_times=1,
                    max_tokens=self.runtime_conf.get("max_tokens", 3000),
                    temperature=self.runtime_conf.get("temperature", 0.0),
                    top_p=self.runtime_conf.get("top_p", 0.85),
                    frequency_penalty=self.runtime_conf.get("frequency_penalty", 0.2),
                )
                if raw_response is not None:
                    break
            except Exception as exc:  # pragma: no cover - network errors
                logger.warning(f"AutoGLM LLM call failed: {exc}")
                try_times -= 1
                time.sleep(1)
                continue
            try_times -= 1

        if raw_response is None:
            self.history_responses.append("")
            return "AutoGLM LLM failed", JSONAction(
                action_type=UNKNOWN, text="AutoGLM LLM failed"
            )

        logger.info(f"AutoGLM raw response:\n{raw_response}")
        thinking, action_call = _parse_thinking_action(raw_response)
        logger.debug(f"AutoGLM thinking={thinking!r} action_call={action_call!r}")

        try:
            parsed = parse_autoglm_action(action_call)
        except ValueError as exc:
            logger.error(f"Failed to parse AutoGLM action: {exc}")
            self.history_responses.append(raw_response)
            return raw_response, JSONAction(action_type=UNKNOWN, text=str(exc))

        try:
            json_action_dict = transform_autoglm_action(
                parsed, image_width=screenshot.width, image_height=screenshot.height
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(f"Failed to transform AutoGLM action: {exc}")
            self.history_responses.append(raw_response)
            return raw_response, JSONAction(action_type=UNKNOWN, text=str(exc))

        self.history_responses.append(raw_response)
        self.actions.append(json_action_dict)
        logger.info(f"AutoGLM dispatched action: {json_action_dict}")

        return raw_response, JSONAction(**json_action_dict)
