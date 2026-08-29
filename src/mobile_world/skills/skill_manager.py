"""技能包数据模型与文件管理。

每个技能包对应一个文件夹，结构如下::

    skills_store/<skill_id>/
        meta_info.json
        docs/
            plan.md
            backup.md
            recover.md
        a11y_utils/
            a11y_utils.py
            a11y_tree.json
        failure_examples/
            failure_001.md
            ...
"""

from __future__ import annotations

import json
import os
import re
import shutil
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

META_FILENAME = "meta_info.json"
DOCS_DIRNAME = "docs"
A11Y_UTILS_DIRNAME = "a11y_utils"
FAILURE_EXAMPLES_DIRNAME = "failure_examples"

PLAN_FILENAME = "plan.md"
BACKUP_FILENAME = "backup.md"
RECOVER_FILENAME = "recover.md"
A11Y_UTILS_PY_FILENAME = "a11y_utils.py"
A11Y_TREE_JSON_FILENAME = "a11y_tree.json"


# 默认 a11y_utils.py 模板（参考实现，供 Agent 阅读和按需扩展）
DEFAULT_A11Y_UTILS_TEMPLATE = '''"""技能包默认的 a11y_tree 解析工具参考。

提供一组面向 Android 无障碍树的查询函数，所有函数操作 a11y_tree.json
导出的扁平元素列表（参考 a11y_tool 的 UIElement.to_dict()）。
"""

from __future__ import annotations

import json
from typing import Any


def load_tree(path: str) -> list[dict]:
    """读取 a11y_tree.json 中的扁平元素列表。"""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("elements", [])


def filter_visible(elements: list[dict]) -> list[dict]:
    """过滤掉不可见 / 装饰性节点。"""
    return [
        e for e in elements
        if e.get("is_visible", True) and (e.get("text") or e.get("content_description") or e.get("is_clickable"))
    ]


def find_by_text(elements: list[dict], text: str, exact: bool = False) -> list[dict]:
    """按文本查找元素。"""
    out = []
    for e in elements:
        t = e.get("text") or ""
        d = e.get("content_description") or ""
        if exact:
            if t == text or d == text:
                out.append(e)
        else:
            if text.lower() in t.lower() or text.lower() in d.lower():
                out.append(e)
    return out


def find_by_role(elements: list[dict], class_suffix: str) -> list[dict]:
    """按 class_name 后缀查找（如 Button、ImageView）。"""
    return [e for e in elements if (e.get("class_name") or "").endswith(class_suffix)]


def find_clickable(elements: list[dict]) -> list[dict]:
    """返回所有可点击元素。"""
    return [e for e in elements if e.get("is_clickable")]


def get_bbox(elem: dict) -> tuple[int, int, int, int] | None:
    """获取元素的边界框 (x_min, y_min, x_max, y_max)。"""
    bbox = elem.get("bbox")
    if not bbox:
        return None
    return (bbox["x_min"], bbox["y_min"], bbox["x_max"], bbox["y_max"])


def get_center(elem: dict) -> tuple[int, int] | None:
    """获取元素中心坐标。"""
    bbox = get_bbox(elem)
    if not bbox:
        return None
    x_min, y_min, x_max, y_max = bbox
    return ((x_min + x_max) // 2, (y_min + y_max) // 2)
'''


def _slugify(text: str, max_length: int = 32) -> str:
    """将任意文本转为安全的目录名片段。"""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:max_length] or "skill"


@dataclass
class EvolutionStatus:
    usage_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    last_updated: str = field(default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%d"))
    iteration_history: list[dict] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.usage_count == 0:
            return 0.0
        return round(self.success_count / self.usage_count, 4)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["success_rate"] = self.success_rate
        return d


@dataclass
class SkillMeta:
    skill_id: str
    task_intent: str
    domain_app: list[str] = field(default_factory=list)
    platform: str = "Android"
    keywords: list[str] = field(default_factory=list)
    arguments: list[str] = field(default_factory=list)
    failure_history_summary: str = ""
    evolution_status: EvolutionStatus = field(default_factory=EvolutionStatus)

    def to_dict(self) -> dict:
        return {
            "skill_id": self.skill_id,
            "task_intent": self.task_intent,
            "domain_app": list(self.domain_app),
            "platform": self.platform,
            "keywords": list(self.keywords),
            "arguments": list(self.arguments),
            "evolution_status": self.evolution_status.to_dict(),
            "failure_history_summary": self.failure_history_summary,
        }

    @classmethod
    def from_dict(cls, d: dict) -> SkillMeta:
        es = d.get("evolution_status", {}) or {}
        if "success_rate" in es:
            es = dict(es)
            es.pop("success_rate", None)
        evolution_status = EvolutionStatus(**es) if es else EvolutionStatus()
        return cls(
            skill_id=d["skill_id"],
            task_intent=d.get("task_intent", ""),
            domain_app=list(d.get("domain_app", []) or []),
            platform=d.get("platform", "Android"),
            keywords=list(d.get("keywords", []) or []),
            arguments=list(d.get("arguments", []) or []),
            failure_history_summary=d.get("failure_history_summary", ""),
            evolution_status=evolution_status,
        )


@dataclass
class SkillPackage:
    """已加载的技能包。"""

    root: Path
    meta: SkillMeta

    @property
    def skill_id(self) -> str:
        return self.meta.skill_id

    @property
    def docs_dir(self) -> Path:
        return self.root / DOCS_DIRNAME

    @property
    def a11y_utils_dir(self) -> Path:
        return self.root / A11Y_UTILS_DIRNAME

    @property
    def failure_examples_dir(self) -> Path:
        return self.root / FAILURE_EXAMPLES_DIRNAME

    @property
    def plan_path(self) -> Path:
        return self.docs_dir / PLAN_FILENAME

    @property
    def backup_path(self) -> Path:
        return self.docs_dir / BACKUP_FILENAME

    @property
    def recover_path(self) -> Path:
        return self.docs_dir / RECOVER_FILENAME

    @property
    def a11y_tree_path(self) -> Path:
        return self.a11y_utils_dir / A11Y_TREE_JSON_FILENAME

    def read_doc(self, name: str) -> str:
        path = self.docs_dir / name
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def write_doc(self, name: str, content: str) -> None:
        path = self.docs_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def append_doc(self, name: str, content: str) -> None:
        path = self.docs_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            if not content.startswith("\n"):
                f.write("\n")
            f.write(content)

    def list_failure_examples(self) -> list[str]:
        if not self.failure_examples_dir.exists():
            return []
        return sorted(p.name for p in self.failure_examples_dir.iterdir() if p.is_file())

    def add_failure_example(self, content: str, name: str | None = None) -> Path:
        self.failure_examples_dir.mkdir(parents=True, exist_ok=True)
        existing = len(self.list_failure_examples())
        name = name or f"failure_{existing + 1:03d}.md"
        path = self.failure_examples_dir / name
        path.write_text(content, encoding="utf-8")
        return path

    def save_meta(self) -> None:
        path = self.root / META_FILENAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.meta.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def render_skill_context(
        self,
        max_chars_per_doc: int = 4000,
    ) -> str:
        """拼接技能包文档供执行 Agent 注入 prompt。"""
        sections: list[str] = []
        sections.append(f"## 技能包 ID: {self.skill_id}")
        sections.append(f"- 任务意图: {self.meta.task_intent}")
        if self.meta.domain_app:
            sections.append(f"- 适用应用: {', '.join(self.meta.domain_app)}")
        if self.meta.failure_history_summary:
            sections.append(f"- 历史失败教训: {self.meta.failure_history_summary}")

        for label, path in (
            ("plan.md (任务流程分解)", self.plan_path),
            ("backup.md (元素定位与后备方案)", self.backup_path),
            ("recover.md (失败恢复策略)", self.recover_path),
        ):
            if path.exists():
                content = path.read_text(encoding="utf-8").strip()
                if not content:
                    continue
                if len(content) > max_chars_per_doc:
                    content = content[:max_chars_per_doc] + "\n... [truncated]"
                sections.append(f"\n### {label}\n{content}")

        for fname in self.list_failure_examples()[:3]:
            fpath = self.failure_examples_dir / fname
            content = fpath.read_text(encoding="utf-8").strip()
            if len(content) > 1500:
                content = content[:1500] + "\n... [truncated]"
            sections.append(f"\n### failure_examples/{fname}\n{content}")

        return "\n".join(sections)

    def record_iteration(self, iteration: int, success: bool, summary: str) -> None:
        self.meta.evolution_status.usage_count += 1
        if success:
            self.meta.evolution_status.success_count += 1
        else:
            self.meta.evolution_status.fail_count += 1
        self.meta.evolution_status.last_updated = datetime.now(UTC).strftime("%Y-%m-%d")
        self.meta.evolution_status.iteration_history.append(
            {
                "iteration": iteration,
                "success": success,
                "summary": summary,
                "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
            }
        )
        self.save_meta()


class SkillManager:
    """技能包仓库管理器。"""

    def __init__(self, store_root: str | os.PathLike):
        self.store_root = Path(store_root)
        self.store_root.mkdir(parents=True, exist_ok=True)

    def list_skill_dirs(self) -> list[Path]:
        return [
            p for p in sorted(self.store_root.iterdir())
            if p.is_dir() and (p / META_FILENAME).exists()
        ]

    def list_skills(self) -> list[SkillPackage]:
        out: list[SkillPackage] = []
        for skill_dir in self.list_skill_dirs():
            try:
                out.append(self.load(skill_dir.name))
            except Exception as e:
                logger.warning(f"Failed to load skill {skill_dir.name}: {e}")
        return out

    def exists(self, skill_id: str) -> bool:
        return (self.store_root / skill_id / META_FILENAME).exists()

    def load(self, skill_id: str) -> SkillPackage:
        root = self.store_root / skill_id
        if not (root / META_FILENAME).exists():
            raise FileNotFoundError(f"Skill not found: {skill_id} ({root})")
        with (root / META_FILENAME).open(encoding="utf-8") as f:
            meta = SkillMeta.from_dict(json.load(f))
        return SkillPackage(root=root, meta=meta)

    def create(
        self,
        meta: SkillMeta,
        plan_md: str = "",
        backup_md: str = "",
        recover_md: str = "",
        a11y_tree: dict | None = None,
        a11y_utils_py: str | None = None,
        overwrite: bool = False,
    ) -> SkillPackage:
        root = self.store_root / meta.skill_id
        if root.exists():
            if overwrite:
                shutil.rmtree(root)
            else:
                raise FileExistsError(
                    f"Skill folder already exists: {root}. Pass overwrite=True to replace."
                )
        root.mkdir(parents=True, exist_ok=True)
        (root / DOCS_DIRNAME).mkdir(exist_ok=True)
        (root / A11Y_UTILS_DIRNAME).mkdir(exist_ok=True)
        (root / FAILURE_EXAMPLES_DIRNAME).mkdir(exist_ok=True)

        (root / DOCS_DIRNAME / PLAN_FILENAME).write_text(plan_md or "", encoding="utf-8")
        (root / DOCS_DIRNAME / BACKUP_FILENAME).write_text(backup_md or "", encoding="utf-8")
        (root / DOCS_DIRNAME / RECOVER_FILENAME).write_text(recover_md or "", encoding="utf-8")

        a11y_utils_content = a11y_utils_py or DEFAULT_A11Y_UTILS_TEMPLATE
        (root / A11Y_UTILS_DIRNAME / A11Y_UTILS_PY_FILENAME).write_text(
            a11y_utils_content, encoding="utf-8"
        )
        if a11y_tree is not None:
            (root / A11Y_UTILS_DIRNAME / A11Y_TREE_JSON_FILENAME).write_text(
                json.dumps(a11y_tree, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        pkg = SkillPackage(root=root, meta=meta)
        pkg.save_meta()
        logger.info(f"Created skill package: {root}")
        return pkg

    def update_a11y_tree(self, skill_id: str, a11y_tree: dict) -> None:
        pkg = self.load(skill_id)
        pkg.a11y_utils_dir.mkdir(parents=True, exist_ok=True)
        pkg.a11y_tree_path.write_text(
            json.dumps(a11y_tree, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def make_skill_id(self, task_intent: str, task_name: str | None = None) -> str:
        """根据任务意图生成唯一 skill_id。"""
        base = _slugify(task_name or task_intent or "task")
        ts_suffix = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        skill_id = f"skill_{base}_{ts_suffix}"
        # 防止极少数情况下并发碰撞
        idx = 0
        while self.exists(skill_id):
            idx += 1
            skill_id = f"skill_{base}_{ts_suffix}_{idx}"
        return skill_id

    def delete(self, skill_id: str) -> bool:
        root = self.store_root / skill_id
        if not root.exists():
            return False
        shutil.rmtree(root)
        return True

    def __iter__(self) -> Iterable[SkillPackage]:
        yield from self.list_skills()
