"""Search benchmark tasks count and send SMS."""

from mobile_world.runtime.app_helpers.system import check_sms_via_adb
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SearchBenchmarkTasksSmsTask(BaseTask):
    """Search benchmark tasks count in repository and send SMS."""

    goal = "帮我在google-research/android_world里搜一下该benchmark构建任务的数量，短信给16655342。"
    task_tags = {"agent-mcp", "lang-cn"}

    RECIPIENT_PHONE = "16655342"
    EXPECTED_NUMBER = "116"

    app_names = {"MCP-Github", "Messages"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize task - no special setup needed."""
        return True

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        # Verify SMS contains the expected number (fixed content: 116)
        if not check_sms_via_adb(
            controller, phone_number=self.RECIPIENT_PHONE, content=self.EXPECTED_NUMBER
        ):
            return (
                0.0,
                f"SMS not found sent to {self.RECIPIENT_PHONE} with content containing: {self.EXPECTED_NUMBER}",
            )

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        return True
