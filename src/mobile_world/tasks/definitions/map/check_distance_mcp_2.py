"""Check distance using Amap MCP task with user interaction."""

from loguru import logger

from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class CheckDistanceMcpTask2(BaseTask):
    goal = "我的常用收货地址到杭州东站的直线距离是多少公里？只需要回答最终数字"
    task_tags = {"agent-mcp", "lang-cn", "agent-user-interaction"}

    distance = 8.878  # from Hangzhou East Station to 555 Wensan Road
    tolerance = 0.5

    app_names = {"MCP-Amap", "Taodian"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        self.relevant_information = "如果agent碰到了登录问题，可以让它尝试通过短信登录"
        return True

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        """Check if the task is successful."""
        self._check_is_initialized()
        answer = controller.interaction_cache
        logger.info(f"Got answer from interaction_cache: '{answer}'")
        try:
            distance = float(answer)
        except ValueError:
            return (
                0.0,
                f"Invalid answer: '{answer}'. Please answer with a number.",
            )

        score = 1.0 if abs(distance - self.distance) <= self.tolerance else 0.0
        return (
            score,
            f"Distance: {distance}, Expected: {self.distance}, Tolerance: {self.tolerance}",
        )
