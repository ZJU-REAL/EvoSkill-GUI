"""a11y (Accessibility Tree) 数据格式化工具。

提供两个面向不同消费者的格式化函数：
- collect_a11y_summary: 给 Verifier 用，多步互补采样，精简文本
- format_step_a11y_for_agent: 给执行 Agent 用，单步，含坐标和完整状态
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


def _step_index_from_name(name: str) -> int:
    """从文件名解析 step 索引。

    支持两种命名风格：
    - 截图：'TaskName-0-12.png' → 12
    - a11y：'step_001.json' → 1
    """
    stem = name.rsplit(".", 1)[0]
    if stem.startswith("step_"):
        tail = stem[len("step_"):]
        if tail.isdigit():
            return int(tail)
    parts = stem.split("-")
    try:
        return int(parts[-1])
    except (ValueError, IndexError):
        return 0


def collect_a11y_summary(
    a11y_dir: str | Path | None,
    *,
    max_per_step: int = 12,
    max_steps: int = 12,
    exclude_step_indices: Optional[set[int] | list[int]] = None,
) -> str:
    """将 wrap_env 保存的逐步 a11y JSON 汇成一份精简摘要文本（给 Verifier）。

    Args:
        a11y_dir: a11y_traces 目录
        max_per_step: 每步保留的元素上限
        max_steps: a11y 摘要保留的步数上限
        exclude_step_indices: 截图已覆盖的 step indices；这些步骤会被排除，
            避免与截图信息重叠。优先用 a11y 补充截图未覆盖的步骤。

    设计：a11y 与截图采用"互补覆盖"策略——
        - 截图采样 N 步（视觉信息）
        - a11y 在【截图未覆盖的步骤】中再等距采样 M 步（文本/状态信息）
        - 这样总覆盖率 ≈ N+M，远高于两者独立采样时的重叠覆盖。
    """
    if not a11y_dir:
        return ""
    d = Path(a11y_dir)
    if not d.exists():
        return ""
    files = sorted(d.glob("step_*.json"))
    if not files:
        return ""

    # 排除截图已覆盖的步骤，让 a11y 专注于补充截图的"空隙"
    excluded: set[int] = set(exclude_step_indices or [])
    if excluded:
        candidate_files = [
            f for f in files if _step_index_from_name(f.name) not in excluded
        ]
        # 如果排除后空了（截图覆盖了全部步），退回到全量列表
        if not candidate_files:
            candidate_files = files
    else:
        candidate_files = files

    # 在剩余候选步骤中等距采样
    if len(candidate_files) > max_steps:
        n = len(candidate_files)
        idxs = sorted(
            {0, n - 1, *[round(i * (n - 1) / (max_steps - 1)) for i in range(max_steps)]}
        )
        candidate_files = [candidate_files[i] for i in sorted(set(idxs))[:max_steps]]

    snippets: list[str] = []
    for f in candidate_files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        elements = data.get("elements", []) or []
        kept: list[str] = []
        for elem in elements:
            label = elem.get("text") or elem.get("content_description")
            if not label:
                continue
            cls = (elem.get("class_name") or "").rsplit(".", 1)[-1]
            extras: list[str] = []
            for key in ("checked", "selected"):
                v = elem.get(key)
                if v is True:
                    extras.append(f"{key}=true")
            ri = elem.get("range_info") or {}
            if isinstance(ri, dict) and ri:
                cur = ri.get("current")
                mn = ri.get("min")
                mx = ri.get("max")
                if cur is not None or mx is not None:
                    extras.append(
                        f"range={cur if cur is not None else '?'}/"
                        f"{mx if mx is not None else '?'}"
                        f"{f' min={mn}' if mn not in (None, 0) else ''}"
                    )
            extra_str = f" ({', '.join(extras)})" if extras else ""
            kept.append(f'{cls}:"{label}"{extra_str}')
            if len(kept) >= max_per_step:
                break
        if kept:
            step_idx = _step_index_from_name(f.name)
            snippets.append(f"### step {step_idx}\n" + ", ".join(kept))
    return "\n\n".join(snippets)


def format_step_a11y_for_agent(
    a11y_dir: str | Path | None,
    *,
    step_index: Optional[int] = None,
    max_elements: int = 40,
    header_label: Optional[str] = None,
) -> str:
    """把指定 step 的 a11y JSON 格式化为给【执行 Agent】看的文本。

    与 :func:`collect_a11y_summary` 的关键区别：
    - 单步而非多步采样（agent 关心的是"当前屏幕"）
    - 保留 bounds 坐标（agent 需要点击坐标）
    - 保留更多状态字段（clickable/scrollable/checked/range_info...）
    - 上限 max_elements 默认 40，更慷慨

    Args:
        a11y_dir: wrap_env 写入的 step_NNN.json 目录
        step_index: 想要的 step 编号；None 代表"取目录中最新的一个"
        max_elements: 单步最多输出多少个元素
        header_label: 自定义 header 标题；None 时使用默认中性表述。
            建议调用方传入 rollout 的实际 step 序号（而不是 a11y 文件
            内部编号），以免误导模型——因为 a11y 文件名表示 "上一步动作
            执行后的状态"，索引会比 agent 当前步号小 1。
    """
    if not a11y_dir:
        return ""
    d = Path(a11y_dir)
    if not d.exists():
        return ""
    files = sorted(d.glob("step_*.json"), key=lambda p: _step_index_from_name(p.name))
    if not files:
        return ""

    target: Optional[Path] = None
    if step_index is not None:
        for f in files:
            if _step_index_from_name(f.name) == step_index:
                target = f
                break
    if target is None:
        target = files[-1]

    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return ""
    elements = data.get("elements", []) or []

    lines: list[str] = []
    for elem in elements:
        label = elem.get("text") or elem.get("content_description")
        cls = (elem.get("class_name") or "").rsplit(".", 1)[-1] or "?"
        if not label:
            if not (elem.get("clickable") or elem.get("editable") or elem.get("scrollable")):
                continue

        bounds = elem.get("bounds_in_screen") or elem.get("bounds")
        bounds_str = ""
        if isinstance(bounds, dict):
            l, t = bounds.get("left"), bounds.get("top")
            r, b = bounds.get("right"), bounds.get("bottom")
            if all(v is not None for v in (l, t, r, b)):
                bounds_str = f" @[{l},{t},{r},{b}]"
        elif isinstance(bounds, (list, tuple)) and len(bounds) == 4:
            bounds_str = f" @[{bounds[0]},{bounds[1]},{bounds[2]},{bounds[3]}]"

        state_bits: list[str] = []
        for k in ("clickable", "scrollable", "editable", "checked", "selected"):
            if elem.get(k) is True:
                state_bits.append(k)
        if elem.get("enabled") is False:
            state_bits.append("disabled")
        ri = elem.get("range_info") or {}
        if isinstance(ri, dict) and ri:
            cur, mx = ri.get("current"), ri.get("max")
            if cur is not None or mx is not None:
                state_bits.append(
                    f"range={cur if cur is not None else '?'}/"
                    f"{mx if mx is not None else '?'}"
                )
        state_str = f" ({', '.join(state_bits)})" if state_bits else ""
        text_part = f'"{label}"' if label else "(no_text)"
        lines.append(f"- {cls}:{text_part}{bounds_str}{state_str}")
        if len(lines) >= max_elements:
            break

    if not lines:
        return ""
    if header_label:
        header = f"Accessibility tree ({header_label})"
    else:
        header = "Accessibility tree (current screen)"
    return f"{header}\n" + "\n".join(lines)
