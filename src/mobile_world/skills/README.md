# CoEvoSkill — Self-Evolving Skills for GUI Agents

Training-free 框架：执行 Agent 在解决 MobileWorld 任务时，先检索/生成
"技能包"，按 `plan.md / backup.md / recover.md` 行动；任务结束后由信息
隔离的 Verifier 给出诊断；执行 Agent 用文件操作 tool_call 修改技能包，
重新 rollout，最多 N 轮（默认 3）。

## 目录结构

```
mobile_world/skills/
├── __init__.py            # 公开 API
├── skill_manager.py       # SkillPackage / SkillManager / EvolutionStatus
├── skill_retriever.py     # KeywordSkillRetriever（BM25-lite）+ 抽象基类
├── skill_generator.py     # VLM 生成初始技能包
├── file_tools.py          # read_file / write_file / append_file / list_dir / search_file / create_failure_example
├── verifier.py            # 信息隔离的 Verifier
├── evolution_loop.py      # Stage 1-3 闭环控制器
└── README.md
```

技能包磁盘布局（每个技能包一个文件夹）：

```
<skills_store>/skill_<slug>_<timestamp>/
├── meta_info.json
├── docs/
│   ├── plan.md
│   ├── backup.md
│   └── recover.md
├── a11y_utils/
│   ├── a11y_utils.py
│   └── a11y_tree.json     # 可选，初始界面快照
└── failure_examples/      # 每次失败追加一份 markdown
    └── failure_001.md
```

## 信息隔离矩阵

| 数据                       | 执行 Agent | Verifier |
| -------------------------- | :--------: | :------: |
| 用户任务 instruction       | ✓          | ✓        |
| 截图序列                   | ✓          | ✓        |
| 动作日志                   | ✓          | ✓        |
| OCR / DOM / a11y           | ✓          | ✓        |
| URL / app / final state    | ✓          | ✓        |
| Verifier 自身历轮 assertions | ✗        | ✓        |
| 执行 Agent thought         | ✓          | ✗        |
| 技能包内容                 | ✓          | ✗        |
| 修改理由                   | ✓          | ✗        |

`Verifier` 在 `skills/verifier.py` 中通过 `ALLOWED_ACTION_KEYS` 白名单
和独立的 prompt 模板严格保证以上矩阵。

## CLI 用法

```bash
sudo HISTORY_N_IMAGES=3 mw eval \
    --agent_type evo_skill \
    --task ALL \
    --max_round 50 \
    --step_wait_time 3 \
    --model_name claude-sonnet-4-6-20260217 \
    --llm_base_url <openai-compatible-url> \
    --enable_mcp \
    --enable_evolution \
    --skills_store ./traj_logs/coevoskill/_skills_store \
    --max_evolution_iterations 3 \
    --retrieval_threshold 0.6 \
    --enable_a11y
```

或使用 `scripts/run_evo_skill_{claude,qwen}.sh`。两个脚本默认排除 12 个
需外部代理的 google 任务。

## 关键参数

| 参数                            | 含义                                 | 默认 |
| ------------------------------- | ------------------------------------ | ---- |
| `--enable_evolution`            | 开启自进化循环（依赖 `--agent_type=evo_skill`） | off |
| `--skills_store`                | 技能包根目录                         | `<log_root>/_skills_store` |
| `--max_evolution_iterations`    | 单任务最多 rollout × refine 次数     | 3 |
| `--retrieval_threshold`         | 命中阈值，低于则现场生成新技能包     | 0.6 |
| `--enable_a11y`                 | 启用 a11y_tree_tool wrap 环境（执行模型 + Verifier 均可使用） | off |

`EVOLUTION_SUMMARY_FILE` 会被写入 `<log_root>/<task>/evolution_summary.json`
记录每轮的 score / reason / verifier feedback / skill_edits。

## Python API

```python
from mobile_world.skills import (
    SkillManager,
    KeywordSkillRetriever,
    SkillGenerator,
    Verifier,
    build_evolution_loop,
)
```

执行 Agent 类：`mobile_world.agents.implementations.evo_skill_agent.EvoSkillAgent`
（已注册为 `"evo_skill"`）。

## 与 a11y_tree_tool 的集成

`runner.py` 中 `_maybe_wrap_env_with_a11y` 会在启用 `--enable_a11y_for_verifier`
时尝试 `from a11y_tool.mobileworld import wrap_env`，对每个 env 套上钩
子，把每步的 `step_NNN.json` 落到 `<log_root>/<task>/a11y_traces/`。
Verifier 通过同一目录读取 a11y 摘要。
