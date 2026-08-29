"""自进化技能包闭环控制器。

替代 ``runner._execute_single_task`` 的循环执行版本：

1. Stage 1：根据 instruction 检索现有技能包（KeywordSkillRetriever），
   命中阈值则复用，否则用 SkillGenerator 现场生成。
2. Stage 2：把技能包注入 EvoSkillAgent，跑一次 rollout，记录轨迹。
3. Stage 3：让隔离 Verifier 阅读轨迹，输出诊断；若失败则让同一个
   EvoSkillAgent 用 file tools 修改技能包，环境 tear_down + reinit 后再跑。
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

# EvoSkillAgent 延迟导入，避免循环依赖
# 在类型注解中用 TYPE_CHECKING，在运行时用函数内 import
from typing import TYPE_CHECKING, Any

from loguru import logger
from openai import OpenAI

from mobile_world.runtime.client import AndroidEnvClient
from mobile_world.runtime.utils.models import ANSWER, ENV_FAIL, FINISHED, UNKNOWN
from mobile_world.runtime.utils.trajectory_logger import TrajLogger
from mobile_world.skills.a11y_utils import format_step_a11y_for_agent
from mobile_world.skills.skill_generator import SkillGenerator
from mobile_world.skills.skill_manager import SkillManager, SkillPackage
from mobile_world.skills.skill_retriever import (
    SkillRetriever,
    make_default_retriever,
)
from mobile_world.skills.verifier import (
    Verifier,
    VerifierFeedback,
)

if TYPE_CHECKING:
    from mobile_world.agents.implementations.evo_skill_agent import EvoSkillAgent


@dataclass
class IterationRecord:
    iteration: int
    score: float
    reason: str
    steps: int
    skill_id: str
    skill_root: str
    feedback: dict | None = None
    skill_edits: list[dict] = field(default_factory=list)


@dataclass
class EvolutionResult:
    task_name: str
    final_score: float
    iterations_used: int
    skill_id: str
    iterations: list[IterationRecord] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "task_name": self.task_name,
            "final_score": self.final_score,
            "iterations_used": self.iterations_used,
            "skill_id": self.skill_id,
            "iterations": [asdict(it) for it in self.iterations],
        }


class EvolutionLoop:
    """对单个任务做技能包自进化的执行器。"""

    def __init__(
        self,
        agent: EvoSkillAgent,
        env: AndroidEnvClient,
        manager: SkillManager,
        retriever: SkillRetriever,
        skill_generator: SkillGenerator,
        verifier: Verifier,
        traj_logger: TrajLogger,
        max_step: int,
        max_iterations: int = 3,
        retrieval_threshold: float = 0.6,
        a11y_log_dir_for_verifier: str | None = None,
        inject_a11y_to_agent: bool = False,
    ):
        self.agent = agent
        self.env = env
        self.manager = manager
        self.retriever = retriever
        self.skill_generator = skill_generator
        self.verifier = verifier
        self.traj_logger = traj_logger
        self.max_step = max_step
        self.max_iterations = max_iterations
        self.retrieval_threshold = retrieval_threshold
        self.a11y_log_dir_for_verifier = a11y_log_dir_for_verifier
        self.inject_a11y_to_agent = inject_a11y_to_agent

    # ------------------------------------------------------------------
    # Stage 1
    # ------------------------------------------------------------------

    def _retrieve_or_generate(
        self,
        task_name: str,
        instruction: str,
        initial_screenshot,
        initial_a11y: str | None,
    ) -> SkillPackage:
        match = self.retriever.best_match(instruction, threshold=self.retrieval_threshold)
        if match is not None:
            logger.info(
                f"[evolution_loop] Re-use existing skill {match.skill.skill_id} "
                f"(score={match.score:.3f})"
            )
            return match.skill

        logger.info(
            f"[evolution_loop] No skill above threshold {self.retrieval_threshold}; "
            "generating a new one."
        )
        try:
            return self.skill_generator.generate(
                task_name=task_name,
                instruction=instruction,
                initial_screenshot=initial_screenshot,
                initial_a11y=initial_a11y,
            )
        except Exception as e:
            logger.warning(f"Skill generation failed: {e}; using minimal fallback")
            payload = self.skill_generator._fallback_payload(task_name, instruction)
            return self.skill_generator._materialize(task_name, instruction, payload)

    # ------------------------------------------------------------------
    # Stage 2
    # ------------------------------------------------------------------

    def _clean_a11y_dir(self) -> None:
        """每个 rollout 开始前清空 a11y 目录并把 wrap_env 的 step_counter 归零。

        如果只删文件不重置 counter，那么第 2 轮以后写出的文件名会从更高的
        编号开始（如 step_011..020 而不是 step_001..010），导致：
        - Verifier 用 screenshot 索引去重 a11y 时索引完全对不上
        - format_step_a11y_for_agent 的 header 显示的 step 号与 rollout
          实际 step 号严重不一致，干扰模型判断。
        """
        if not self.a11y_log_dir_for_verifier:
            return
        d = Path(self.a11y_log_dir_for_verifier)
        try:
            if d.exists():
                for f in d.glob("step_*.json"):
                    try:
                        f.unlink()
                    except Exception:
                        pass
            else:
                d.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Failed to clean a11y dir {d}: {e}")

        # 重置 wrap_env 闭包里的 step_counter 与 save_dir，保证文件编号从 1 开始
        state = getattr(self.env, "_a11y_state", None)
        if isinstance(state, dict):
            state["step_counter"] = 0
            state["save_dir"] = self.a11y_log_dir_for_verifier

    def _capture_initial_a11y(self) -> None:
        """在 initialize_task 之后主动抓取一次 a11y，落盘为 step_000.json。

        wrap_env 只 patch 了 ``execute_action``，没有 patch ``initialize_task``，
        所以初始屏永远不会自动产生 a11y 文件。这就让 step 1 时
        ``inject_a11y_to_agent`` 拿不到任何 a11y 信息。这里在初始化结束后
        显式触发一次抓取，把初始屏存为 ``step_000.json``，以便：

        - 执行 agent 在 step 1 也能看到 a11y（与初始截图对应）
        - Verifier 的 a11y 摘要包含初始屏
        """
        if not self.a11y_log_dir_for_verifier:
            return
        capture = getattr(self.env, "capture_a11y_now", None)
        if capture is None:
            return
        state = getattr(self.env, "_a11y_state", None)
        if isinstance(state, dict):
            state["step_counter"] = 0  # 让本次抓取写到 step_000.json
        try:
            capture(advance_counter=False)
        except Exception as e:
            logger.warning(f"capture initial a11y failed: {e}")

    def _execute_rollout(
        self,
        task_name: str,
        task_goal: str,
        skill: SkillPackage,
    ) -> tuple[int, float, str]:
        """跑一遍任务，返回 (steps, score, reason)。"""
        # 重置 traj logger（保留之前的 backup）
        self.traj_logger.reset_traj()
        self._clean_a11y_dir()

        self.agent.set_skill(skill)
        self.agent.reset()

        obs = self.env.initialize_task(task_name=task_name)
        # initialize_task 不会触发 wrap_env 的 patched execute_action，所以
        # 初始屏没有 a11y。这里主动抓取一次落到 step_000.json，让 step 1
        # 也能享受 inject_a11y_to_agent 的辅助。
        self._capture_initial_a11y()
        self.agent.initialize(task_goal)

        step = 0
        while True:
            step += 1
            logger.debug(f"[evolution_loop] step {step}")

            # 可选：把当前页面的 a11y tree 注入给 agent 作为执行参考
            a11y_for_agent: str | None = None
            if self.inject_a11y_to_agent and self.a11y_log_dir_for_verifier:
                try:
                    # rollout step N 看到的屏幕 = step N-1 的动作执行后的状态
                    # = a11y step_{N-1}.json（step 1 时取 step_000.json，
                    # 即 _capture_initial_a11y 写入的初始屏快照）。
                    target_a11y_step = step - 1
                    a11y_for_agent = format_step_a11y_for_agent(
                        self.a11y_log_dir_for_verifier,
                        step_index=target_a11y_step,
                        header_label=f"current screen, before rollout step {step}",
                    ) or None
                    if a11y_for_agent is None:
                        # 回落到"取最新"，避免因为索引不一致而完全没有 a11y
                        a11y_for_agent = format_step_a11y_for_agent(
                            self.a11y_log_dir_for_verifier,
                            header_label=f"current screen, before rollout step {step}",
                        ) or None
                except Exception as e:
                    logger.warning(f"a11y inject failed at step {step}: {e}")

            prediction, action = self.agent.predict(
                {
                    "screenshot": obs.screenshot,
                    "tool_call": obs.tool_call,
                    "ask_user_response": obs.ask_user_response,
                    "accessibility_tree": a11y_for_agent,
                }
            )
            self.traj_logger.log_traj(
                task_name,
                task_goal,
                step,
                prediction,
                action.model_dump(exclude_none=True),
                obs,
                self.agent.get_total_token_usage(),
            )
            if prediction is None:
                logger.warning(f"Agent prediction failed at step {step}")
                break

            if action.action_type in [ENV_FAIL, FINISHED, UNKNOWN]:
                logger.debug(f"task terminated at step {step} with {action.action_type}")
                break
            if action.action_type == ANSWER:
                obs = self.env.execute_action(action)
                break
            obs = self.env.execute_action(action)
            if step >= self.max_step:
                logger.debug("max_step reached")
                break

        score, reason = self.env.get_task_score(task_type=task_name)
        return step, score, reason

    # ------------------------------------------------------------------
    # Stage 3
    # ------------------------------------------------------------------

    def _diagnose(
        self,
        instruction: str,
        score: float,
        reason: str,
    ) -> VerifierFeedback:
        traj_json = Path(self.traj_logger.log_file_dir) / self.traj_logger.log_file_name
        screenshots_dir = Path(self.traj_logger.log_file_dir) / self.traj_logger.screenshots_dir

        return self.verifier.diagnose(
            instruction=instruction,
            traj_json_path=traj_json,
            screenshots_dir=screenshots_dir,
            a11y_dir=self.a11y_log_dir_for_verifier,
            final_state=None,
            ground_truth_score=score,
            ground_truth_reason=reason,
        )

    def _refine_skill(
        self,
        skill: SkillPackage,
        feedback: VerifierFeedback,
    ) -> list[dict[str, Any]]:
        feedback_text = json.dumps(feedback.to_dict(), ensure_ascii=False, indent=2)
        edits = self.agent.refine_skill_with_feedback(feedback_text)
        # 同步元信息
        skill.meta.failure_history_summary = (
            (skill.meta.failure_history_summary or "")
            + f"\n[iter] {feedback.failure_type}: {feedback.root_cause[:120]}"
        ).strip()
        skill.save_meta()
        return edits

    # ------------------------------------------------------------------
    # Public entry
    # ------------------------------------------------------------------

    def run(self, task_name: str) -> EvolutionResult:
        task_goal = self.env.get_task_goal(task_type=task_name)
        logger.info(f"[evolution_loop] task={task_name} | goal={task_goal!r}")

        # 用一次"轻量初始化"获取首屏截图供生成器使用，然后立即 tear_down
        # 避免污染正式 rollout 的初始环境
        initial_obs = None
        try:
            initial_obs = self.env.initialize_task(task_name=task_name)
        except Exception as e:
            logger.warning(f"Pre-init for skill generation failed: {e}")
        finally:
            try:
                self.env.tear_down_task(task_type=task_name)
            except Exception as e:
                logger.warning(f"Pre-init tear_down failed: {e}")

        initial_screenshot = getattr(initial_obs, "screenshot", None) if initial_obs else None
        initial_a11y_text = None  # a11y 在 wrap_env 接管时会得到，预初始化阶段先跳过

        skill = self._retrieve_or_generate(
            task_name=task_name,
            instruction=task_goal,
            initial_screenshot=initial_screenshot,
            initial_a11y=initial_a11y_text,
        )

        self.verifier.reset()
        result = EvolutionResult(
            task_name=task_name,
            final_score=0.0,
            iterations_used=0,
            skill_id=skill.skill_id,
        )

        last_score = 0.0
        for it in range(1, self.max_iterations + 1):
            logger.info(f"[evolution_loop] iteration {it}/{self.max_iterations}")

            try:
                steps, score, reason = self._execute_rollout(task_name, task_goal, skill)
            except Exception as e:
                err_str = str(e)
                # If device is unhealthy, wait and retry once
                if "not healthy" in err_str or "Device" in err_str:
                    logger.warning(
                        f"[evolution_loop] iter {it}: device unhealthy, waiting 60s and retrying..."
                    )
                    time.sleep(60)
                    try:
                        steps, score, reason = self._execute_rollout(task_name, task_goal, skill)
                    except Exception as e2:
                        logger.exception(f"Rollout failed after retry at iteration {it}: {e2}")
                        steps, score, reason = 0, 0.0, f"rollout_error: {e2}"
                else:
                    logger.exception(f"Rollout failed at iteration {it}: {e}")
                    steps, score, reason = 0, 0.0, f"rollout_error: {e}"

            last_score = score
            self.traj_logger.log_score(score=score, reason=reason)

            success = score > 0.0
            # ⚠️ 信息隔离：reason 是环境 oracle 的"为什么判 0/1"详细说明，
            # 绝对不能写进 skill 包（执行 agent 通过 file_tools 能直接
            # read_file 读到 meta_info.json，会让 ground-truth 细节泄露）。
            # 只在 disk-only 的 evolution_summary.json / result.txt 里保留 reason。
            skill.record_iteration(
                iteration=it,
                success=success,
                summary=f"score={score}",
            )

            iter_record = IterationRecord(
                iteration=it,
                score=score,
                reason=reason,
                steps=steps,
                skill_id=skill.skill_id,
                skill_root=str(skill.root),
            )

            if success:
                logger.info(
                    f"[evolution_loop] iter {it} succeeded (score={score}); stop refinement"
                )
                result.iterations.append(iter_record)
                result.iterations_used = it
                result.final_score = score
                # tear down to leave env clean
                try:
                    self.env.tear_down_task(task_type=task_name)
                except Exception:
                    pass
                self.agent.done()
                return result

            # 失败：诊断 + 修改 + 环境重置
            feedback = self._diagnose(task_goal, score, reason)
            iter_record.feedback = feedback.to_dict()

            if it >= self.max_iterations:
                # 最后一轮失败，不再 refine
                result.iterations.append(iter_record)
                logger.info(
                    f"[evolution_loop] iter {it} failed; reached max_iterations, stopping"
                )
                break

            logger.info(
                f"[evolution_loop] iter {it} failed; verifier diagnosis="
                f"{feedback.failure_type} root_cause={feedback.root_cause[:120]!r}"
            )
            edits = self._refine_skill(skill, feedback)
            iter_record.skill_edits = edits
            result.iterations.append(iter_record)

            # 把失败案例落到 failure_examples/ 供下次复用
            try:
                skill.add_failure_example(
                    f"# Iteration {it} failure\n\n"
                    f"- score: {score}\n\n"
                    f"## Verifier diagnosis\n{feedback.diagnosis}\n\n"
                    f"## Suggestions applied\n"
                    + "\n".join(f"- {s}" for s in feedback.suggestions)
                )
            except Exception as e:
                logger.warning(f"Failed to write failure example: {e}")

            # 环境复位：关闭当前任务（_execute_rollout 内部已经 init_task；
            # 这里 tear_down 让下一轮重新 init）
            try:
                self.env.tear_down_task(task_type=task_name)
            except Exception as e:
                logger.warning(f"tear_down between iterations failed: {e}")

            time.sleep(2)

        result.iterations_used = len(result.iterations)
        result.final_score = last_score
        try:
            self.env.tear_down_task(task_type=task_name)
        except Exception:
            pass
        self.agent.done()
        return result


# ----------------------------------------------------------------------
# Convenience builder
# ----------------------------------------------------------------------


def build_evolution_loop(
    *,
    env: AndroidEnvClient,
    agent: EvoSkillAgent,
    traj_logger: TrajLogger,
    skills_store: str | os.PathLike,
    max_step: int,
    max_iterations: int = 3,
    retrieval_threshold: float = 0.6,
    verifier_model_name: str | None = None,
    a11y_log_dir_for_verifier: str | None = None,
    inject_a11y_to_agent: bool = False,
) -> EvolutionLoop:
    """根据 agent 已有的 OpenAI client 复用同一个模型的客户端搭建闭环。"""
    manager = SkillManager(skills_store)
    retriever = make_default_retriever(
        manager,
        threshold=retrieval_threshold,
    )

    client: OpenAI = agent.openai_client
    model_name = verifier_model_name or agent.model_name

    skill_generator = SkillGenerator(
        client=client,
        model_name=model_name,
        manager=manager,
    )
    verifier = Verifier(client=client, model_name=model_name)

    return EvolutionLoop(
        agent=agent,
        env=env,
        manager=manager,
        retriever=retriever,
        skill_generator=skill_generator,
        verifier=verifier,
        traj_logger=traj_logger,
        max_step=max_step,
        max_iterations=max_iterations,
        retrieval_threshold=retrieval_threshold,
        a11y_log_dir_for_verifier=a11y_log_dir_for_verifier,
        inject_a11y_to_agent=inject_a11y_to_agent,
    )
