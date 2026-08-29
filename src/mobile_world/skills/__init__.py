"""CoEvoSkill - 自进化 GUI Agent 技能包模块。

核心子模块：
- `skill_manager`：技能包元数据/文件管理
- `skill_retriever`：基于关键词/embedding 的技能包语义检索
- `skill_generator`：使用 VLM 生成初始技能包
- `file_tools`：执行模型可用的文件操作工具集
- `verifier`：信息隔离的轨迹验证器
- `evolution_loop`：自进化闭环控制器
"""

from mobile_world.skills.file_tools import FILE_TOOLS, dispatch_file_tool, get_file_tool_specs
from mobile_world.skills.skill_generator import SkillGenerator
from mobile_world.skills.skill_manager import SkillManager, SkillMeta, SkillPackage
from mobile_world.skills.skill_retriever import (
    KeywordSkillRetriever,
    SkillRetriever,
    make_default_retriever,
)
from mobile_world.skills.verifier import Verifier, VerifierFeedback

# evolution_loop 延迟导入，避免与 evo_skill_agent 循环依赖
# 使用方式：from mobile_world.skills.evolution_loop import build_evolution_loop

__all__ = [
    "SkillManager",
    "SkillPackage",
    "SkillMeta",
    "SkillRetriever",
    "KeywordSkillRetriever",
    "make_default_retriever",
    "FILE_TOOLS",
    "dispatch_file_tool",
    "get_file_tool_specs",
    "SkillGenerator",
    "Verifier",
    "VerifierFeedback",
]
