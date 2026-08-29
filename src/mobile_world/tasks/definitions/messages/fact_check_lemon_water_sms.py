"""Fact check statement and send SMS with result."""

from mobile_world.runtime.app_helpers.system import check_sms_via_adb
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class FactCheckLemonWaterSmsTask(BaseTask):
    """Fact check statement about lemon water and send SMS with result."""

    goal = (
        "帮我查一下这句话是不是靠谱：'每天喝柠檬水可以预防癌症。'"
        "可靠的话，编辑短信内容'每天喝柠檬水可以预防癌症'，"
        "不可靠的话编辑短信内容为'每天喝柠檬水不可以预防癌症'，"
        "发送给我妻子1665347803。"
    )
    task_tags = {"agent-mcp", "lang-cn"}

    STATEMENT = "每天喝柠檬水不可以预防癌症"
    RECIPIENT_PHONE = "1665347803"

    app_names = {"MCP-jina", "Messages"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize task - no special setup needed."""
        return True

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        if not check_sms_via_adb(
            controller, phone_number=self.RECIPIENT_PHONE, content=self.STATEMENT
        ):
            return (
                0.0,
                f"SMS not found sent to {self.RECIPIENT_PHONE} with content: {self.STATEMENT}",
            )

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        return True
