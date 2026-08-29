"""执行 Agent 用于读写技能包的 tool_call 工具集。

所有写操作都被沙箱化在一个由调用方传入的 ``base_dir`` 内（默认是技能包
根目录），防止 LLM 越权修改其他文件。

工具规范遵循 OpenAI tool/function 调用约定，可直接传给 ``tools=[...]``。
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

# ---------------------------------------------------------------------------
# Tool schema (OpenAI tool/function 格式)
# ---------------------------------------------------------------------------

FILE_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取技能包内的文件，返回完整文本内容。仅允许读取技能包根目录下的文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "相对技能包根目录的路径，如 'docs/plan.md'",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "将内容写入技能包文件（覆盖式）。如果文件不存在会自动创建。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "相对技能包根目录的路径"},
                    "content": {"type": "string", "description": "完整文件内容"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "append_file",
            "description": "在技能包文件末尾追加内容。文件不存在则会创建。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "列出技能包内某个目录的文件和子目录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "相对技能包根目录的路径，留空表示根目录",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_file",
            "description": "在技能包内对指定文件做正则/字面量搜索，返回命中行（带行号）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "pattern": {"type": "string"},
                    "is_regex": {
                        "type": "boolean",
                        "description": "是否将 pattern 视为正则表达式，默认 false",
                    },
                },
                "required": ["path", "pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_failure_example",
            "description": "在 failure_examples/ 文件夹下创建一份失败案例 markdown，用于积累经验。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "案例文件名（不含扩展名），可留空让系统自动编号"},
                    "content": {"type": "string", "description": "Markdown 正文"},
                },
                "required": ["content"],
            },
        },
    },
]


def get_file_tool_specs() -> list[dict]:
    """返回 OpenAI tool 规范副本，避免外部修改污染常量。"""
    import copy

    return copy.deepcopy(FILE_TOOLS)


# ---------------------------------------------------------------------------
# Sandbox 实现
# ---------------------------------------------------------------------------


@dataclass
class FileToolResult:
    ok: bool
    output: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return {"ok": self.ok, "output": self.output, "error": self.error}


def _resolve(
    base_dir: Path,
    rel_path: str,
) -> Path:
    """解析并校验路径在 base_dir 之内。"""
    base = base_dir.resolve()
    p = (base / rel_path.strip()).resolve() if rel_path else base
    try:
        p.relative_to(base)
    except ValueError as e:
        raise PermissionError(
            f"Path '{rel_path}' escapes the skill sandbox '{base}'"
        ) from e
    return p


def _read_file(
    base_dir: Path,
    path: str,
) -> FileToolResult:
    try:
        target = _resolve(base_dir, path)
        if not target.exists():
            return FileToolResult(ok=False, error=f"File not found: {path}")
        if target.is_dir():
            return FileToolResult(ok=False, error=f"Path is a directory: {path}")
        text = target.read_text(encoding="utf-8")
        if len(text) > 200_000:
            text = text[:200_000] + "\n... [truncated]"
        return FileToolResult(ok=True, output=text)
    except Exception as e:
        return FileToolResult(ok=False, error=str(e))


def _write_file(
    base_dir: Path,
    path: str,
    content: str,
) -> FileToolResult:
    try:
        target = _resolve(base_dir, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return FileToolResult(ok=True, output=f"wrote {len(content)} bytes to {path}")
    except Exception as e:
        return FileToolResult(ok=False, error=str(e))


def _append_file(
    base_dir: Path,
    path: str,
    content: str,
) -> FileToolResult:
    try:
        target = _resolve(base_dir, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as f:
            if target.stat().st_size and not content.startswith("\n"):
                f.write("\n")
            f.write(content)
        return FileToolResult(ok=True, output=f"appended {len(content)} bytes to {path}")
    except Exception as e:
        return FileToolResult(ok=False, error=str(e))


def _list_dir(
    base_dir: Path,
    path: str = "",
) -> FileToolResult:
    try:
        target = _resolve(base_dir, path)
        if not target.exists():
            return FileToolResult(ok=False, error=f"Directory not found: {path}")
        if not target.is_dir():
            return FileToolResult(ok=False, error=f"Not a directory: {path}")
        entries = []
        for child in sorted(target.iterdir()):
            kind = "dir" if child.is_dir() else "file"
            size = child.stat().st_size if child.is_file() else "-"
            entries.append(f"[{kind}] {child.name} (size={size})")
        return FileToolResult(ok=True, output="\n".join(entries) or "(empty)")
    except Exception as e:
        return FileToolResult(ok=False, error=str(e))


def _search_file(
    base_dir: Path,
    path: str,
    pattern: str,
    is_regex: bool = False,
) -> FileToolResult:
    try:
        target = _resolve(base_dir, path)
        if not target.exists():
            return FileToolResult(ok=False, error=f"File not found: {path}")
        if target.is_dir():
            return FileToolResult(ok=False, error=f"Path is a directory: {path}")
        regex = re.compile(pattern) if is_regex else re.compile(re.escape(pattern))
        hits: list[str] = []
        with target.open(encoding="utf-8") as f:
            for i, line in enumerate(f, start=1):
                if regex.search(line):
                    hits.append(f"{i}: {line.rstrip()}")
                    if len(hits) >= 200:
                        hits.append("... (more matches truncated)")
                        break
        return FileToolResult(ok=True, output="\n".join(hits) or "(no matches)")
    except Exception as e:
        return FileToolResult(ok=False, error=str(e))


def _create_failure_example(
    base_dir: Path,
    content: str,
    title: str | None = None,
) -> FileToolResult:
    try:
        examples_dir = base_dir / "failure_examples"
        examples_dir.mkdir(parents=True, exist_ok=True)
        existing = sorted(p.name for p in examples_dir.iterdir() if p.is_file())
        if title:
            slug = re.sub(r"[^A-Za-z0-9_-]+", "_", title).strip("_") or f"failure_{len(existing) + 1:03d}"
            name = f"{slug}.md"
        else:
            name = f"failure_{len(existing) + 1:03d}.md"
        target = examples_dir / name
        target.write_text(content, encoding="utf-8")
        return FileToolResult(ok=True, output=f"created failure_examples/{name}")
    except Exception as e:
        return FileToolResult(ok=False, error=str(e))


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def dispatch_file_tool(
    name: str,
    arguments: dict[str, Any],
    base_dir: str | os.PathLike,
) -> FileToolResult:
    """执行一次工具调用。

    Args:
        name: 工具名（read_file / write_file / ...）
        arguments: 工具参数 dict
        base_dir: 沙箱根目录（一般为技能包根目录）
    """
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)
    args = arguments or {}

    handlers: dict[str, Callable[..., FileToolResult]] = {
        "read_file": lambda: _read_file(base, args.get("path", "")),
        "write_file": lambda: _write_file(
            base, args.get("path", ""), args.get("content", "")
        ),
        "append_file": lambda: _append_file(
            base, args.get("path", ""), args.get("content", "")
        ),
        "list_dir": lambda: _list_dir(base, args.get("path", "") or ""),
        "search_file": lambda: _search_file(
            base,
            args.get("path", ""),
            args.get("pattern", ""),
            bool(args.get("is_regex", False)),
        ),
        "create_failure_example": lambda: _create_failure_example(
            base, args.get("content", ""), args.get("title") or None
        ),
    }
    handler = handlers.get(name)
    if handler is None:
        return FileToolResult(ok=False, error=f"Unknown tool: {name}")
    try:
        result = handler()
        logger.debug(
            f"[file_tool] {name}({args}) -> ok={result.ok} "
            f"output_len={len(result.output)} error={result.error!r}"
        )
        return result
    except Exception as e:
        logger.exception(f"file_tool {name} failed")
        return FileToolResult(ok=False, error=str(e))
