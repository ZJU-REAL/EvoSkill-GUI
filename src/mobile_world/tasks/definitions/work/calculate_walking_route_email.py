"""Calculate walking route and send email with distance and duration."""

import re

from mobile_world.runtime.app_helpers import mcp as mcp_helper
from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class CalculateWalkingRouteEmailTask(BaseTask):
    """Calculate walking route from home to park and send email with distance and duration."""

    goal = (
        "我想每天晚饭后从阿里巴巴西溪园区散步到西溪湿地。"
        "我家在「浙江省杭州市余杭区文一西路阿里巴巴西溪园区C区三号楼」，"
        "公园在「西溪国家湿地公园周家村主入口」，"
        "评估把总距离（公里）和预计时长(分钟)email到我的生活邮箱dylan@gmail.com，标题为daily walking"
    )
    task_tags = {"agent-mcp", "lang-cn"}

    EMAIL_ADDRESS = "dylan@gmail.com"
    EMAIL_SUBJECT = "daily walking"
    DISTANCE_TOLERANCE = 1.0  # 1km tolerance
    DURATION_TOLERANCE = 20.0  # 20min tolerance

    ORIGIN_LOCATION = "120.023164,30.283370"
    DESTINATION_LOCATION = "120.060816,30.256190"

    app_names = {"MCP-Amap", "Mail"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        return True

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        route_info = await mcp_helper.plan_walking_route(
            origin=self.ORIGIN_LOCATION, destination=self.DESTINATION_LOCATION
        )

        distance = route_info["route"]["route"]["paths"][0]["distance"]
        duration_seconds = route_info["route"]["route"]["paths"][0]["duration"]
        assert distance is not None, "Failed to extract distance from route"
        assert duration_seconds is not None, "Failed to extract duration from route"

        distance_km = distance / 1000

        email = get_sent_email_info()
        if email is None:
            return 0.0, "No email sent"

        if email.get("to", "").lower() != self.EMAIL_ADDRESS.lower():
            return (
                0.0,
                f"Email sent to wrong address: {email.get('to')} (expected: {self.EMAIL_ADDRESS})",
            )

        if email.get("subject", "") != self.EMAIL_SUBJECT:
            return (
                0.0,
                f"Email subject incorrect: {email.get('subject')} (expected: {self.EMAIL_SUBJECT})",
            )

        email_body = email.get("body", "").strip()

        distance_values = [float(match) for match in re.findall(r"\d+\.?\d*", email_body)]
        distance_found = any(
            abs(val - distance_km) <= self.DISTANCE_TOLERANCE for val in distance_values
        )

        if not distance_found:
            return 0.0, f"Distance not found in email body. Expected around {distance_km:.2f} km"

        # Verify duration (allow tolerance, compare values in minutes)
        duration_minutes = duration_seconds / 60
        duration_values = [float(match) for match in re.findall(r"\d+\.?\d*", email_body)]
        duration_found = any(
            abs(val - duration_minutes) <= self.DURATION_TOLERANCE for val in duration_values
        )

        if not duration_found:
            return (
                0.0,
                f"Duration not found in email body. Expected around {duration_minutes:.1f} minutes",
            )

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        return True
