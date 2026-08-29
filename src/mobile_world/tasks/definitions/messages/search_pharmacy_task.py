"""Search nearby pharmacies and send SMS."""

from mobile_world.runtime.app_helpers import mcp as mcp_helper
from mobile_world.runtime.app_helpers.system import check_sms_via_adb
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SearchPharmacyTask(BaseTask):
    """Search nearby pharmacies within 500 meters and send SMS."""

    goal = (
        "我现在的位置在西溪园区亲橙客栈，家里有人突然感冒，你帮我查500米范围内的药店，"
        "以`name：address`的格式，每个药店一行，帮我短信给我妻子1997777900"
    )
    task_tags = {"agent-mcp", "lang-cn"}

    RECIPIENT_PHONE = "1997777900"
    RADIUS = "500"
    KEYWORDS = "药店"
    CURRENT_LOCATION = "120.026783,30.286703"

    app_names = {"MCP-Amap", "Messages"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize task - no special setup needed."""
        return True

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        # Search nearby pharmacies
        pharmacy_list = await mcp_helper.search_nearby(
            location=self.CURRENT_LOCATION, radius=self.RADIUS, keywords=self.KEYWORDS
        )

        if not check_sms_via_adb(
            controller, phone_number=self.RECIPIENT_PHONE, content=pharmacy_list
        ):
            return (
                0.0,
                f"SMS not found sent to {self.RECIPIENT_PHONE} with content: {pharmacy_list}",
            )
        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        return True
