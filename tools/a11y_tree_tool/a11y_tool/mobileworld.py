"""MobileWorld 评测集成 - 在每步 action 后自动获取 a11y tree。

用法:
    from a11y_tool.mobileworld import wrap_env

    env = wrap_env(env, container="mobile_world_env_0", save_dir="./a11y_logs")
    # 之后正常使用，每步 action 后 a11y tree 自动保存到文件
    # 也可以通过 env.get_a11y_tree() 手动获取

可重入语义（v2）:
    多次调用 ``wrap_env(env, ...)`` 不会再叠加 patch。第一次调用真正
    安装钩子；后续调用只更新 save_dir / fmt / step_counter，并复用
    同一个 ``A11yTreeClient``。这样可以安全地把同一个 env 在不同任
    务/不同 rollout 之间复用，而不会产生：

    1. 多层补丁串成 chain，导致每次 execute_action 触发 N 次 a11y 抓取
    2. 旧任务的 save_dir 被持续写入污染
    3. ``A11yTreeClient`` 资源泄漏

外部可以通过 ``env._a11y_state`` 访问/修改：

    env._a11y_state["save_dir"]      # 切换写盘目录（None 表示停止写盘）
    env._a11y_state["step_counter"]  # 重置计数（每个新 rollout 应清零）
    env._a11y_state["fmt"]           # "json" 或 "text"
    env._a11y_state["last_tree"]     # 最近一次抓到的 A11yTree
    env._a11y_state["client"]        # 底层 A11yTreeClient
"""

from __future__ import annotations
import logging
import os
from typing import Any, Optional

from a11y_tool.client import A11yTreeClient
from a11y_tool.models import A11yTree

logger = logging.getLogger(__name__)


_A11Y_STATE_ATTR = "_a11y_state"


def _capture_and_save(state: dict, *, advance_counter: bool = True) -> Optional[A11yTree]:
    """根据 state 抓取一次 a11y tree，按 save_dir/fmt 写盘。

    Args:
        state: env._a11y_state 引用。
        advance_counter: True 时使用 step_counter+1 命名文件（用于 patched
            execute_action 的逐步抓取）；False 时使用当前 step_counter
            （用于"补抓初始屏" 的 step_000 场景，调用方负责先把 counter
            置为 0 再调用）。
    """
    try:
        tree = state["client"].get_tree()
    except Exception as e:  # pragma: no cover - 网络/容器不可用
        state["last_tree"] = None
        logger.warning(
            "获取 a11y tree 失败 (step %d): %s",
            state.get("step_counter", -1),
            e,
        )
        return None

    state["last_tree"] = tree

    if advance_counter:
        state["step_counter"] = int(state.get("step_counter", 0)) + 1

    save_dir = state.get("save_dir")
    if save_dir:
        try:
            os.makedirs(save_dir, exist_ok=True)
            fmt = state.get("fmt", "json")
            path = os.path.join(save_dir, f"step_{state['step_counter']:03d}.{fmt}")
            content = tree.to_json() if fmt == "json" else tree.to_text()
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.debug("a11y tree saved to %s", path)
        except Exception as e:  # pragma: no cover - 磁盘/权限故障
            logger.warning(
                "写入 a11y tree 失败 (step %d, save_dir=%s): %s",
                state["step_counter"], save_dir, e,
            )

    return tree


def wrap_env(
    env: Any,
    container: Optional[str] = None,
    mode: str = "uiautomator",
    save_dir: Optional[str] = None,
    fmt: str = "json",
) -> Any:
    """包装 AndroidEnvClient，使每步 action 后自动获取 a11y tree 并保存。

    幂等/可重入：多次调用同一个 env 不会叠加 patch，只会原地更新 save_dir、
    fmt 与 step_counter（counter 会被重置为 0）。

    Args:
        env: AndroidEnvClient 或 AndroidMCPEnvClient 实例
        container: Docker 容器名（如 "mobile_world_env_0"）
        mode: 获取模式 "uiautomator" 或 "grpc"
        save_dir: 保存目录（如 "./a11y_logs"），None 则不保存文件
        fmt: 保存格式 "json" 或 "text"

    Returns:
        包装后的 env（原地修改）
    """
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)

    existing_state = getattr(env, _A11Y_STATE_ATTR, None)
    if existing_state is not None:
        # 已经 wrap 过：原地更新 save_dir / fmt / counter，复用 client
        existing_state["save_dir"] = save_dir
        existing_state["fmt"] = fmt
        existing_state["step_counter"] = 0
        # mode/container 切换不在重入路径里支持（这通常意味着换了 env）
        if existing_state.get("mode") != mode or existing_state.get("container") != container:
            logger.warning(
                "wrap_env re-entry with different mode/container "
                "(was mode=%s container=%s, now mode=%s container=%s); "
                "keeping the existing client. Create a new env if you really "
                "need to switch backends.",
                existing_state.get("mode"), existing_state.get("container"),
                mode, container,
            )
        return env

    # 第一次 wrap：真正安装 patch
    client = A11yTreeClient(mode=mode, docker_container=container)
    state: dict = {
        "client": client,
        "save_dir": save_dir,
        "fmt": fmt,
        "step_counter": 0,
        "last_tree": None,
        "mode": mode,
        "container": container,
    }
    setattr(env, _A11Y_STATE_ATTR, state)

    original_execute = env.execute_action

    def patched_execute_action(action):
        obs = original_execute(action)
        # 抓取并按当前 save_dir 写盘；counter 会前进一格
        _capture_and_save(state, advance_counter=True)
        return obs

    def get_a11y_tree() -> Optional[A11yTree]:
        """获取最近一步的 a11y tree（不会重新抓取）。"""
        return state["last_tree"]

    def get_fresh_a11y_tree() -> A11yTree:
        """立即获取当前屏幕的 a11y tree（不写盘、不前进 counter）。"""
        tree = state["client"].get_tree()
        state["last_tree"] = tree
        return tree

    def capture_a11y_now(advance_counter: bool = False) -> Optional[A11yTree]:
        """主动抓取一次 a11y 并按 save_dir 落盘。

        典型用途：在 ``initialize_task`` 之后捕获初始屏，命名为
        ``step_000.json``。调用方应先把 ``step_counter`` 置 0：

            env._a11y_state["step_counter"] = 0
            env.capture_a11y_now(advance_counter=False)  # 写 step_000.json
        """
        return _capture_and_save(state, advance_counter=advance_counter)

    env.execute_action = patched_execute_action
    env.get_a11y_tree = get_a11y_tree
    env.get_fresh_a11y_tree = get_fresh_a11y_tree
    env.capture_a11y_now = capture_a11y_now

    # 兼容旧字段（外部代码可能 hasattr 检查）
    env._a11y_client = client

    original_close = getattr(env, "close", None)

    def patched_close(*args, **kwargs):
        try:
            state["client"].close()
        except Exception:  # pragma: no cover
            pass
        if original_close:
            return original_close(*args, **kwargs)

    env.close = patched_close

    return env
