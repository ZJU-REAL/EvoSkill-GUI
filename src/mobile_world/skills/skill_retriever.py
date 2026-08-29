"""技能包语义检索。"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from loguru import logger

from mobile_world.skills.skill_manager import SkillManager, SkillPackage

# 简单的中英文分词：按非 \w 字符切分，并丢弃过短 token
_TOKEN_RE = re.compile(r"[\w']+", re.UNICODE)
_STOPWORDS = {
    "the", "a", "an", "to", "of", "in", "on", "for", "and", "or",
    "is", "be", "with", "by", "at", "from", "as", "this", "that",
    "task", "user", "用户", "请", "帮我", "进行", "完成",
}


def _tokenize(text: str | None) -> list[str]:
    if not text:
        return []
    tokens = [t.lower() for t in _TOKEN_RE.findall(text)]
    return [t for t in tokens if len(t) >= 2 and t not in _STOPWORDS]


@dataclass
class RetrievalResult:
    skill: SkillPackage
    score: float

    def __post_init__(self) -> None:
        # 防止极小负分混入
        if self.score < 0:
            self.score = 0.0


class SkillRetriever(ABC):
    """技能包检索抽象基类。"""

    def __init__(self, manager: SkillManager, threshold: float = 0.75):
        self.manager = manager
        self.threshold = threshold

    @abstractmethod
    def score(self, query: str, skill: SkillPackage) -> float: ...

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        threshold: float | None = None,
    ) -> list[RetrievalResult]:
        """返回得分由高到低的候选技能包。"""
        skills = self.manager.list_skills()
        results: list[RetrievalResult] = []
        for s in skills:
            try:
                sc = self.score(query, s)
            except Exception as e:
                logger.warning(f"Failed to score skill {s.skill_id}: {e}")
                continue
            results.append(RetrievalResult(skill=s, score=sc))
        results.sort(key=lambda r: r.score, reverse=True)

        thr = self.threshold if threshold is None else threshold
        # 注意：top_k 截断后再施加阈值过滤
        return [r for r in results[:top_k] if r.score >= thr]

    def best_match(self, query: str, threshold: float | None = None) -> RetrievalResult | None:
        """返回最佳匹配，若不满足阈值则返回 None。"""
        results = self.retrieve(query, top_k=1, threshold=threshold)
        return results[0] if results else None


class KeywordSkillRetriever(SkillRetriever):
    """基于关键词与 BM25-lite 的检索器（无外部依赖）。"""

    def __init__(self, manager: SkillManager, threshold: float = 0.6, k1: float = 1.5, b: float = 0.75):
        super().__init__(manager, threshold)
        self.k1 = k1
        self.b = b

    def _build_doc(self, skill: SkillPackage) -> list[str]:
        parts = [
            skill.meta.task_intent,
            " ".join(skill.meta.keywords or []),
            " ".join(skill.meta.domain_app or []),
        ]
        return _tokenize(" ".join(p for p in parts if p))

    def score(self, query: str, skill: SkillPackage) -> float:
        q_tokens = _tokenize(query)
        if not q_tokens:
            return 0.0

        doc_tokens = self._build_doc(skill)
        if not doc_tokens:
            return 0.0

        q_set = set(q_tokens)
        d_set = set(doc_tokens)
        overlap = q_set & d_set
        if not overlap:
            return 0.0

        # Jaccard 系数 + 命中关键词比例的加权（更偏 query 命中率）
        jaccard = len(overlap) / len(q_set | d_set)
        recall = len(overlap) / max(1, len(q_set))

        # 域应用直接命中给 +0.15 加成
        domain_bonus = 0.0
        for app in skill.meta.domain_app or []:
            if app and app.lower() in (query or "").lower():
                domain_bonus = 0.15
                break

        # 关键词出现的精确加成
        keyword_bonus = 0.0
        kws = [k for k in (skill.meta.keywords or []) if k]
        if kws:
            hits = sum(1 for k in kws if k.lower() in (query or "").lower())
            if hits:
                keyword_bonus = min(0.2, hits * 0.05)

        # 组合：以 recall 为主（更看重 query 是否被覆盖），辅以 jaccard
        base = 0.6 * recall + 0.4 * jaccard
        return min(1.0, base + domain_bonus + keyword_bonus)


def make_default_retriever(
    manager: SkillManager,
    threshold: float = 0.6,
) -> SkillRetriever:
    """构造默认的关键词检索器。"""
    logger.info(f"[skill_retriever] threshold={threshold}")
    return KeywordSkillRetriever(manager=manager, threshold=threshold)
