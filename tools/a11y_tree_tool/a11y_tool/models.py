"""UI 元素数据模型和格式化输出。"""

from __future__ import annotations
import dataclasses
import json
from typing import Any, Optional


@dataclasses.dataclass
class BoundingBox:
    x_min: int
    x_max: int
    y_min: int
    y_max: int

    @property
    def center(self) -> tuple[float, float]:
        return (self.x_min + self.x_max) / 2.0, (self.y_min + self.y_max) / 2.0

    @property
    def width(self) -> int:
        return self.x_max - self.x_min

    @property
    def height(self) -> int:
        return self.y_max - self.y_min

    def to_dict(self) -> dict:
        return {"x_min": self.x_min, "x_max": self.x_max,
                "y_min": self.y_min, "y_max": self.y_max}


@dataclasses.dataclass
class UIElement:
    text: Optional[str] = None
    content_description: Optional[str] = None
    class_name: Optional[str] = None
    bbox: Optional[BoundingBox] = None
    resource_id: Optional[str] = None
    package_name: Optional[str] = None
    is_clickable: bool = False
    is_scrollable: bool = False
    is_editable: bool = False
    is_checkable: bool = False
    is_checked: bool = False
    is_enabled: bool = True
    is_focused: bool = False
    is_focusable: bool = False
    is_long_clickable: bool = False
    is_selected: bool = False
    is_visible: bool = True
    hint_text: Optional[str] = None
    tooltip: Optional[str] = None
    depth: int = 0
    children: list["UIElement"] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {}
        if self.text:
            d["text"] = self.text
        if self.content_description:
            d["content_description"] = self.content_description
        if self.class_name:
            d["class_name"] = self.class_name
        if self.bbox:
            d["bbox"] = self.bbox.to_dict()
        if self.resource_id:
            d["resource_id"] = self.resource_id
        if self.package_name:
            d["package_name"] = self.package_name
        for attr in ("is_clickable", "is_scrollable", "is_editable",
                      "is_checkable", "is_checked", "is_long_clickable",
                      "is_selected"):
            val = getattr(self, attr)
            if val:
                d[attr] = val
        if not self.is_enabled:
            d["is_enabled"] = False
        if not self.is_visible:
            d["is_visible"] = False
        if self.hint_text:
            d["hint_text"] = self.hint_text
        if self.children:
            d["children"] = [c.to_dict() for c in self.children]
        return d


@dataclasses.dataclass
class A11yTree:
    """完整的无障碍树结构。"""
    elements: list[UIElement]
    raw_xml: Optional[str] = None
    raw_forest: Any = None
    source: str = "unknown"
    timestamp: Optional[float] = None

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(
            {"source": self.source, "element_count": len(self.elements),
             "elements": [e.to_dict() for e in self.elements]},
            indent=indent, ensure_ascii=False,
        )

    def to_text(self, max_depth: Optional[int] = None) -> str:
        lines = [f"=== A11y Tree ({self.source}, {len(self.elements)} elements) ==="]
        for i, elem in enumerate(self.elements):
            lines.append(_format_element(i, elem, max_depth))
        return "\n".join(lines)

    def to_flat_list(self) -> list[dict]:
        return [e.to_dict() for e in self.elements]


def _format_element(idx: int, elem: UIElement, max_depth: Optional[int]) -> str:
    parts = [f"[{idx}]"]
    if elem.class_name:
        short = elem.class_name.rsplit(".", 1)[-1]
        parts.append(short)
    if elem.text:
        parts.append(f'"{elem.text}"')
    if elem.content_description:
        parts.append(f'(desc: "{elem.content_description}")')
    if elem.resource_id:
        parts.append(f'id={elem.resource_id}')

    flags = []
    if elem.is_clickable:
        flags.append("clickable")
    if elem.is_scrollable:
        flags.append("scrollable")
    if elem.is_editable:
        flags.append("editable")
    if elem.is_checkable:
        flags.append("checkable")
    if elem.is_checked:
        flags.append("checked")
    if flags:
        parts.append(f"[{','.join(flags)}]")

    if elem.bbox:
        b = elem.bbox
        parts.append(f"({b.x_min},{b.y_min})-({b.x_max},{b.y_max})")

    return " ".join(parts)
