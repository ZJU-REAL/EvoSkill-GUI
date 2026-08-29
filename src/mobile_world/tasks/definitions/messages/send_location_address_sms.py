"""Get address from coordinates and send SMS."""

from mobile_world.runtime.app_helpers.system import check_sms_via_adb
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SendLocationAddressSmsTask(BaseTask):
    """Get address from coordinates and send SMS with coordinate and address."""

    goal = (
        "我从高德复制了一段终点坐标 120.0351,30.2809（阿里西溪附近），"
        "帮我用它查出详细的行政区划地址，然后短信给1766242644，"
        '按照"坐标：地址"的格式编写短信内容'
    )
    task_tags = {"agent-mcp", "lang-cn"}

    LONGITUDE = 120.0351
    LATITUDE = 30.2809
    RECIPIENT_PHONE = "1766242644"
    ADDRESS_PARTS = ["浙江", "杭州", "余杭"]

    app_names = {"MCP-Amap", "Messages"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        return True

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        address_parts = [self.LONGITUDE, self.LATITUDE] + self.ADDRESS_PARTS
        if not check_sms_via_adb(
            controller, phone_number=self.RECIPIENT_PHONE, content=address_parts
        ):
            return (
                0.0,
                f"SMS not found sent to {self.RECIPIENT_PHONE} with content: {address_parts}",
            )

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        return True
