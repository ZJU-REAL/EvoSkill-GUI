"""Send weather information via SMS task implementation."""

from mobile_world.runtime.app_helpers import mcp as mcp_helper
from mobile_world.runtime.app_helpers.system import (
    check_sms_via_adb,
    enable_auto_time_sync,
)
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SendWeatherSmsTask(BaseTask):
    """Send weather information via SMS task."""

    goal = "明天下午我朋友要来杭州西溪这边，你帮我查一下杭州明天白天的天气和情况和温度发送给我的朋友，电话100077788236"
    task_tags = {"agent-mcp", "lang-cn"}

    CITY = "杭州"
    RECIPIENT_PHONE = "100077788236"

    app_names = {"MCP-Amap", "Messages"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        if not enable_auto_time_sync(controller):  # chrome needs auto time sync to work
            return False
        return True

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        weather_info = await mcp_helper.query_weather(city=self.CITY, date=None)

        forecast = weather_info["forecasts"][1]
        expected_dayweather = forecast.get("dayweather")
        expected_daytemp_float = forecast.get("daytemp")

        if not check_sms_via_adb(
            controller,
            phone_number=self.RECIPIENT_PHONE,
            content=[expected_dayweather, expected_daytemp_float],
        ):
            return (
                0.0,
                f"SMS not found sent to {self.RECIPIENT_PHONE} with content: {expected_dayweather, expected_daytemp_float}",
            )

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        return True
