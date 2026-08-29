import json
import os
import random
import threading
import time
from queue import Queue

from dotenv import load_dotenv
from joblib import Parallel, delayed
from loguru import logger

from mobile_world.agents.base import BaseAgent, MCPAgent
from mobile_world.agents.registry import create_agent
from mobile_world.runtime.client import (
    AndroidEnvClient,
    AndroidMCPEnvClient,
    scan_finished_tasks,
)
from mobile_world.runtime.utils.docker import (
    discover_backends,
)
from mobile_world.runtime.utils.models import ANSWER, ENV_FAIL, FINISHED, UNKNOWN
from mobile_world.runtime.utils.trajectory_logger import TrajLogger

load_dotenv()


def _execute_single_task(
    env: AndroidEnvClient,
    agent: BaseAgent,
    task_name: str,
    max_step: int,
    traj_logger: TrajLogger,
    enable_mcp: bool = False,
) -> tuple[int, float]:
    """Execute a single task and return the number of steps and score.

    Returns:
        tuple[int, float]: (number of steps, score)
    """

    logger.debug(f"max_step: {max_step}")

    if enable_mcp and not isinstance(agent, MCPAgent):
        logger.error(
            "MCP is enabled but agent type is not a MCP agent. Please use a MCP agent type."
        )

    if enable_mcp:
        traj_logger.log_tools(env.tools)
    task_goal = env.get_task_goal(task_type=task_name)

    logger.debug(f"task_goal: {task_goal}")

    step = 0
    obs = env.initialize_task(task_name=task_name)
    agent.initialize(task_goal)

    while True:
        step += 1

        logger.debug(f"Screenshot captured in step {step}")

        prediction, action = agent.predict(
            {
                "screenshot": obs.screenshot,
                "tool_call": obs.tool_call,
                "ask_user_response": obs.ask_user_response,
            }
        )  # for backward compatibility
        traj_logger.log_traj(
            task_name,
            task_goal,
            step,
            prediction,
            action.model_dump(exclude_none=True),
            obs,
            agent.get_total_token_usage(),
        )
        if prediction is None:
            logger.warning(f"Agent prediction failed in step {step}")
            break

        terminate = False
        logger.debug(f"current step {step}")

        if action.action_type in [ENV_FAIL, FINISHED, UNKNOWN]:
            logger.debug(f"task terminated in step {step} with action {action.action_type}")
            terminate = True
        elif action.action_type in [ANSWER]:
            logger.debug(f"answer triggered, execution action {action}")
            obs = env.execute_action(action)
            terminate = True
        else:
            logger.debug(f"execution action {action}")
            obs = env.execute_action(action)
        if terminate:
            break

        if step >= max_step:
            logger.debug("task steps reach max step, terminate")
            break

    score, reason = env.get_task_score(task_type=task_name)
    logger.debug(f"task_score: {score}, reason: {reason}")
    traj_logger.log_score(score=score, reason=reason)

    res = env.tear_down_task(task_type=task_name)
    agent.done()
    logger.debug(f"tear_down_task response: {res}")

    return step, score


def _execute_single_task_with_evolution(
    env: AndroidEnvClient,
    agent: BaseAgent,
    task_name: str,
    max_step: int,
    traj_logger: TrajLogger,
    *,
    skills_store: str,
    max_evolution_iterations: int,
    retrieval_threshold: float,
    enable_a11y_for_verifier: bool,
    a11y_log_dir: str | None,
    inject_a11y_to_agent: bool = False,
) -> tuple[int, float]:
    """使用 EvolutionLoop 替代单次 rollout。"""

    from mobile_world.skills.evolution_loop import build_evolution_loop

    # Duck-typing: 任意实现了 set_skill / refine_skill_with_feedback /
    # active_skill / skill_edit_log 的 agent 都可以接入自进化循环。
    # 目前内置实现：EvoSkillAgent (general_e2e 风格) 和 MaiUIEvoSkillAgent。
    required_attrs = (
        "set_skill",
        "clear_skill",
        "active_skill",
        "skill_edit_log",
        "refine_skill_with_feedback",
    )
    missing = [a for a in required_attrs if not hasattr(agent, a)]
    if missing:
        raise TypeError(
            f"--enable_evolution requires an evo-skill capable agent (missing: {missing}); "
            f"got {type(agent).__name__}. Use --agent_type=evo_skill or "
            "--agent_type=mai_ui_evo_skill."
        )

    # 注入 a11y 给 agent 时，verifier 也需要这个目录（共享同一份 wrap_env 数据）
    a11y_dir_for_verifier = (
        a11y_log_dir if (enable_a11y_for_verifier or inject_a11y_to_agent) else None
    )

    loop = build_evolution_loop(
        env=env,
        agent=agent,
        traj_logger=traj_logger,
        skills_store=skills_store,
        max_step=max_step,
        max_iterations=max_evolution_iterations,
        retrieval_threshold=retrieval_threshold,
        a11y_log_dir_for_verifier=a11y_dir_for_verifier,
        inject_a11y_to_agent=inject_a11y_to_agent,
    )

    result = loop.run(task_name)

    summary_path = os.path.join(traj_logger.log_file_dir, "evolution_summary.json")
    try:
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Failed to write evolution summary {summary_path}: {e}")

    total_steps = sum(it.steps for it in result.iterations)
    return total_steps, result.final_score


def _process_task_on_env(
    task_name: str,
    env_queue: Queue,
    agent_type: str,
    model_name: str,
    llm_base_url: str,
    api_key: str | None,
    log_file_root: str,
    max_step: int,
    retry_on_device_unhealthy: int = 2,
    enable_mcp: bool = False,
    enable_evolution: bool = False,
    skills_store: str | None = None,
    max_evolution_iterations: int = 3,
    retrieval_threshold: float = 0.6,
    enable_a11y_for_verifier: bool = False,
    inject_a11y_to_agent: bool = False,
    **kwargs,
) -> dict:
    """Process a single task on a specific environment.

    Args:
        task_name: Name of the task to execute
        env_url: URL of the environment to use
        agent_type: Type of agent to create
        model_name: Model name for the agent
        llm_base_url: LLM service base URL
        api_key: API key for LLM service
        log_file_root: Root directory for log files
        max_step: Maximum steps for task execution
        **kwargs: Additional kwargs for agent creation

    Returns:
        dict: Task result containing task_name, success, score, steps, duration_seconds
    """
    # Create thread-specific log file
    thread_id = threading.current_thread().ident
    thread_log_file = os.path.join(log_file_root, task_name, f"thread_{thread_id}.log")
    os.makedirs(os.path.dirname(thread_log_file), exist_ok=True)
    traj_logger = TrajLogger(log_file_root, task_name)

    def thread_filter(record):
        return record["extra"].get("thread_id") == thread_id

    thread_handler_id = logger.add(
        thread_log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | container: {extra[container_name]} | {message}",
        level="DEBUG",
        enqueue=True,
        filter=thread_filter,
    )
    env, container_name = env_queue.get()

    try:
        with logger.contextualize(thread_id=thread_id, container_name=container_name):
            logger.info("Processing task '{}' on environment {}", task_name, env.base_url)
            if enable_mcp:
                assert isinstance(env, AndroidMCPEnvClient), (
                    f"env must be a AndroidMCPEnvClient, but got {type(env)}"
                )
                try:
                    env.reset_tools(task_type=task_name)
                except Exception as e:
                    logger.exception(f"Error resetting tools for task {task_name}: {e}")
                    return None

            agent_kwargs = dict(kwargs)
            if enable_evolution and agent_type in ("evo_skill", "mai_ui_evo_skill"):
                agent_kwargs.setdefault("enable_user_interaction", False)

            agent = create_agent(
                agent_type, model_name, llm_base_url, api_key, env=env, **agent_kwargs
            )

            need_a11y_capture = enable_a11y_for_verifier or inject_a11y_to_agent
            a11y_log_dir = (
                os.path.join(log_file_root, task_name, "a11y_traces")
                if need_a11y_capture
                else None
            )
            if need_a11y_capture:
                _maybe_wrap_env_with_a11y(env, container_name, a11y_log_dir)

            task_start_time = time.time()
            while True:
                try:
                    if enable_evolution:
                        task_steps, task_score = _execute_single_task_with_evolution(
                            env,
                            agent,
                            task_name,
                            max_step,
                            traj_logger=traj_logger,
                            skills_store=skills_store
                            or os.path.join(log_file_root, "_skills_store"),
                            max_evolution_iterations=max_evolution_iterations,
                            retrieval_threshold=retrieval_threshold,
                            enable_a11y_for_verifier=enable_a11y_for_verifier,
                            a11y_log_dir=a11y_log_dir,
                            inject_a11y_to_agent=inject_a11y_to_agent,
                        )
                    else:
                        task_steps, task_score = _execute_single_task(
                            env,
                            agent,
                            task_name,
                            max_step,
                            traj_logger=traj_logger,
                            enable_mcp=enable_mcp,
                        )
                    break
                except Exception as e:
                    if "Device is not healthy" in str(e) and retry_on_device_unhealthy > 0:
                        logger.warning("Device is not healthy, retrying...")
                        time.sleep(20)
                        retry_on_device_unhealthy -= 1
                        traj_logger.reset_traj()
                        continue
                    else:
                        logger.exception(f"Error executing task {task_name}")
                        return None

            task_duration = time.time() - task_start_time
            task_success = task_score > 0.0

            logger.info(
                "Task '{}' completed on {}: success={}, score={}, steps={}, duration={:.1f}s",
                task_name,
                env.base_url,
                task_success,
                task_score,
                task_steps,
                task_duration,
            )

            return {
                "task_name": task_name,
                "score": task_score,
            }
    finally:
        # Remove the thread-specific handler
        logger.remove(thread_handler_id)
        env_queue.put((env, container_name))


def _init_env(
    env_url: str, device: str, step_wait_time: float, suite_family: str, enable_mcp: bool
) -> AndroidEnvClient:
    """Initialize the environment."""
    if enable_mcp:
        env = AndroidMCPEnvClient(env_url, device, step_wait_time=step_wait_time)
    else:
        env = AndroidEnvClient(env_url, device, step_wait_time=step_wait_time)
    env.switch_suite_family(suite_family)
    return env


def _maybe_wrap_env_with_a11y(
    env: AndroidEnvClient,
    container_name: str | None,
    save_dir: str | None,
) -> None:
    """Best-effort：给 env 打上每步获取 a11y tree 的钩子。

    a11y_tool.wrap_env 是幂等的：第一次调用真正安装 patch；同一 env 的
    后续调用只会切换 save_dir 并重置 step_counter，**不会叠加多层补丁**。
    这避免了之前每次重新 wrap 都给 execute_action 加一层、导致 N 倍 a11y
    抓取以及历史任务目录被串扰污染的 bug。
    """
    if save_dir is None:
        return
    try:
        from a11y_tool.mobileworld import wrap_env  # type: ignore

        wrap_env(
            env,
            container=container_name,
            mode="uiautomator",
            save_dir=save_dir,
            fmt="json",
        )
        logger.info(f"a11y wrapper attached: container={container_name} save_dir={save_dir}")
    except Exception as e:
        logger.warning(f"Failed to attach a11y wrapper: {e}")


def run_agent_with_evaluation(
    agent_type: str,
    model_name: str,
    llm_base_url: str,
    log_file_root: str,
    tasks: list[str],
    max_step: int = -1,
    aw_urls: list[str] | None = None,
    api_key: str | None = None,
    device: str = "emulator-5554",
    step_wait_time: float = 1.0,
    suite_family: str = "mobile_world",
    env_name_prefix: str = "mobile_world_env",
    env_image: str = "mobile_world",
    dry_run: bool = False,
    enable_mcp: bool = False,
    enable_user_interaction: bool = False,
    max_concurrency: int | None = None,
    shuffle_tasks: bool = False,
    auto_retry: int = 10,
    enable_evolution: bool = False,
    skills_store: str | None = None,
    max_evolution_iterations: int = 3,
    retrieval_threshold: float = 0.6,
    enable_a11y_for_verifier: bool = False,
    inject_a11y_to_agent: bool = False,
    **kwargs,
) -> list[dict]:
    """Run the agent and return the evaluation results.

    Args:
        agent_type: Type of agent to use
        model_name: Model name for the agent
        llm_base_url: LLM service base URL
        log_file_root: Root directory for log files
        tasks: List of task names to execute (empty list for all tasks)
        max_step: Maximum steps for task execution
        aw_urls: List of Android World backend URLs. If None, auto-discover from containers
        api_key: API key for LLM service
        device: Android device ID
        step_wait_time: Wait time after each step
        suite_family: Suite family to use
        **kwargs: Additional kwargs for agent creation

    Returns:
        list[dict]: The evaluation results for each task, containing task_name, success, score, steps, duration_seconds, env_url
    """

    container_names = None
    if aw_urls is None or len(aw_urls) == 0:
        logger.info("No backend URLs specified, auto-discovering from containers...")
        aw_urls, container_names = discover_backends(image_filter=env_image, prefix=env_name_prefix)
        logger.info("Container names: {}", container_names)
        if not aw_urls:
            logger.error("No backend URLs found. Please start containers or specify --aw-host")
            return [], []

    logger.info("Using {} backend URL(s): {}", len(aw_urls), aw_urls)

    envs = Parallel(
        n_jobs=min(max_concurrency if max_concurrency is not None else len(aw_urls), len(aw_urls)),
        backend="threading",
    )(
        delayed(_init_env)(env_url, device, step_wait_time, suite_family, enable_mcp)
        for env_url in aw_urls
    )

    if len(tasks) != 0:
        task_list = tasks
    else:
        task_list = envs[0].get_suite_task_list(enable_mcp=enable_mcp, enable_user_interaction=enable_user_interaction)

    logger.info("Task list: {} ({} tasks)", task_list, len(task_list))

    num_envs = len(envs)
    max_attempts = min(1 + auto_retry, 10)  # Cap at 10 to prevent infinite loops

    for attempt in range(max_attempts):
        # Scan finished tasks each iteration (picks up results from previous attempts)
        finished_task_list, finished_scores = scan_finished_tasks(log_file_root, task_list)
        logger.info("Finished task list: {} ({} tasks)", finished_task_list, len(finished_task_list))

        pending_tasks = [task for task in task_list if task not in finished_task_list]
        logger.info(
            "Attempt {}/{}: {} remaining tasks to execute",
            attempt + 1, max_attempts, len(pending_tasks),
        )

        if not pending_tasks:
            logger.info("All tasks finished, no retry needed")
            break

        env_queue = Queue[tuple[AndroidEnvClient, str | None]](maxsize=num_envs)
        for i, env in enumerate(envs):
            env_queue.put((env, container_names[i] if container_names else None))

        if shuffle_tasks:
            random.shuffle(pending_tasks)

        if not dry_run:
            task_results = Parallel(
                n_jobs=min(max_concurrency if max_concurrency is not None else num_envs, num_envs),
                backend="threading",
            )(
                delayed(_process_task_on_env)(
                    task_name=task_name,
                    env_queue=env_queue,
                    agent_type=agent_type,
                    model_name=model_name,
                    llm_base_url=llm_base_url,
                    api_key=api_key,
                    log_file_root=log_file_root,
                    max_step=max_step,
                    enable_mcp=enable_mcp,
                    enable_evolution=enable_evolution,
                    skills_store=skills_store,
                    max_evolution_iterations=max_evolution_iterations,
                    retrieval_threshold=retrieval_threshold,
                    enable_a11y_for_verifier=enable_a11y_for_verifier,
                    inject_a11y_to_agent=inject_a11y_to_agent,
                    **kwargs,
                )
                for task_name in pending_tasks
            )
        else:
            logger.info("Dry run mode, skipping task execution")
            task_results = []
            break

        # Identify failed tasks for potential retry
        failed_this_round = [
            task_name for task_name, task_result in zip(pending_tasks, task_results)
            if task_result is None
        ]

        logger.info(
            "Attempt {}/{} done: {} succeeded, {} failed/stale",
            attempt + 1, max_attempts,
            len(pending_tasks) - len(failed_this_round), len(failed_this_round),
        )

        if not failed_this_round or attempt >= max_attempts - 1:
            break

        logger.info("Auto-retrying {} failed tasks (retry {}/{})", len(failed_this_round), attempt + 1, auto_retry)

    # Final scan to get all finished results (including from retries)
    finished_task_list, finished_scores = scan_finished_tasks(log_file_root, task_list)
    # Build final results from scan (authoritative source)
    success_task_results = []
    for task_name, score in zip(finished_task_list, finished_scores):
        success_task_results.append({"task_name": task_name, "score": score})

    task_list_with_no_results = [task for task in task_list if task not in finished_task_list]
    logger.info(f"Final: {len(success_task_results)} tasks with results, {len(task_list_with_no_results)} with no results")

    return (success_task_results, task_list_with_no_results)
