"""解析 uiautomator dump 的 XML 输出为 UIElement 列表。"""

import xml.etree.ElementTree as ET
from typing import Optional
from a11y_tool.models import BoundingBox, UIElement


def parse_bounds(bounds_str: str) -> Optional[BoundingBox]:
    """解析 '[x1,y1][x2,y2]' 格式的 bounds 字符串。"""
    if not bounds_str:
        return None
    try:
        coords = list(map(int, bounds_str.strip("[]").replace("][", ",").split(",")))
        return BoundingBox(x_min=coords[0], x_max=coords[2],
                           y_min=coords[1], y_max=coords[3])
    except (ValueError, IndexError):
        return None


def _bool(val: Optional[str]) -> bool:
    return val == "true"


def _text_or_none(val: Optional[str]) -> Optional[str]:
    return val if val else None


def xml_node_to_element(node: ET.Element, depth: int = 0) -> UIElement:
    bbox = parse_bounds(node.get("bounds", ""))
    children = [xml_node_to_element(child, depth + 1) for child in node]
    return UIElement(
        text=_text_or_none(node.get("text")),
        content_description=_text_or_none(node.get("content-desc")),
        class_name=_text_or_none(node.get("class")),
        bbox=bbox,
        resource_id=_text_or_none(node.get("resource-id")),
        package_name=_text_or_none(node.get("package")),
        is_clickable=_bool(node.get("clickable")),
        is_scrollable=_bool(node.get("scrollable")),
        is_editable=_bool(node.get("editable")),
        is_checkable=_bool(node.get("checkable")),
        is_checked=_bool(node.get("checked")),
        is_enabled=_bool(node.get("enabled")),
        is_focused=_bool(node.get("focused")),
        is_focusable=_bool(node.get("focusable")),
        is_long_clickable=_bool(node.get("long-clickable")),
        is_selected=_bool(node.get("selected")),
        is_visible=True,
        depth=depth,
        children=children,
    )


def parse_xml_dump(xml_string: str) -> list[UIElement]:
    """将 uiautomator dump 的 XML 解析为扁平的 UIElement 列表。"""
    root = ET.fromstring(xml_string)
    elements: list[UIElement] = []

    def flatten(node: ET.Element, depth: int = 0):
        elem = xml_node_to_element(node, depth)
        elem.children = []
        elements.append(elem)
        for child in node:
            flatten(child, depth + 1)

    for child in root:
        flatten(child, depth=0)
    return elements


def parse_xml_dump_as_tree(xml_string: str) -> list[UIElement]:
    """将 uiautomator dump 的 XML 解析为树形 UIElement 结构。"""
    root = ET.fromstring(xml_string)
    return [xml_node_to_element(child) for child in root]
