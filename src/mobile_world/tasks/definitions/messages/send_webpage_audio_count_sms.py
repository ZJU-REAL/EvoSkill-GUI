"""Send webpage audio word count via SMS task implementation."""

from mobile_world.runtime.app_helpers.system import check_sms_via_adb
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SendWebpageAudioCountSmsTask(BaseTask):
    """Send webpage audio word count via SMS task."""

    goal = (
        "Please count the occurrences of the word 'audio' on the page https://yenanliu.github.io/AVSS.github.io/ (case insensitive), "
        "and finally organize the final count with the summarized content into a text message and send it to 177663344"
    )
    task_tags = {"agent-mcp", "lang-en"}

    RECIPIENT_PHONE = "177663344"

    KEYWORDS = ["BAVS", "audio", "visual", "segmentation", "28"]

    app_names = {"MCP-jina", "Messages"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize task - no special setup needed."""
        return True

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        """Check if task is successful - verify SMS contains the expected count."""
        self._check_is_initialized()

        # Verify SMS contains the expected count (fixed content: 116)
        if not check_sms_via_adb(
            controller, phone_number=self.RECIPIENT_PHONE, content=self.KEYWORDS
        ):
            return (
                0.0,
                f"SMS not found sent to {self.RECIPIENT_PHONE} with content containing: {self.KEYWORDS}",
            )

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        return True
