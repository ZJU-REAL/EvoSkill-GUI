"""Check distance using Amap MCP task."""

from loguru import logger

from mobile_world.runtime.app_helpers.system import enable_auto_time_sync
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class CheckDistanceMcpTask(BaseTask):
    """Check distance from Hangzhou East Station to a location using Amap MCP."""

    goal = "我在做一个咖啡连锁品牌发展史的研究，上次我去了Manner的全国首店，这次想实地考察Manner咖啡全国第二家店的选址。帮我用高德mcp查一下从杭州东站到它的直线距离？只需要回答数字。"
    task_tags = {"agent-mcp", "lang-cn"}

    distance = 157.254  # from Hangzhou East Station to Shanghai RÉEL Mall
    tolerance = 0.1

    app_names = {"MCP-Amap", "Chrome"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
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
