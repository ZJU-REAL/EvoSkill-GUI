"""Estimate bicycling distance and time from origin to destination."""

import re

from mobile_world.runtime.app_helpers import mcp as mcp_helper
from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class EstimateBikeRouteTask(BaseTask):
    goal = (
        "我打算骑车上班，帮我估算萧山到阿里西溪C园区的距离(公里)和时间（分钟）"
        "把结果按`距离(公里),时间(分钟)`的格式发送到我的生活邮箱dylan@gmail.com，标题为`daily bike`"
    )

    task_tags = {"agent-mcp", "lang-cn"}

    EMAIL_ADDRESS = "dylan@gmail.com"
    EMAIL_SUBJECT = "daily bike"
    DISTANCE_TOLERANCE = 5.0
    DURATION_TOLERANCE = 30.0

    ORIGIN_LOCATION = "120.436328,30.234905"  # 机场出发
    DESTINATION_LOCATION = "120.015091,30.254659"  # 西溪园区 49.85km

    app_names = {"MCP-Amap", "Mail"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        return True

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        route_info = await mcp_helper.plan_bicycling_route(
            origin=self.ORIGIN_LOCATION, destination=self.DESTINATION_LOCATION
        )

        distance_meters = route_info.get("distance")
        duration_seconds = route_info.get("duration")
        assert distance_meters is not None, "Failed to extract distance from route"
        assert duration_seconds is not None, "Failed to extract duration from route"

        distance_km = distance_meters / 1000
        duration_minutes = duration_seconds / 60

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

        values = re.findall(r"\d+\.?\d*", email_body)
        if len(values) < 2:
            return (
                0.0,
                f"Email body should contain distance and duration. Found {len(values)} value(s)",
            )

        distance_value = float(values[0])
        duration_value = float(values[1])

        if abs(distance_value - distance_km) > self.DISTANCE_TOLERANCE:
            return (
                0.0,
                f"Distance mismatch. Expected around {distance_km:.2f} km, got {distance_value:.2f} km",
            )

        if abs(duration_value - duration_minutes) > self.DURATION_TOLERANCE:
            return (
                0.0,
                f"Duration mismatch. Expected around {duration_minutes:.1f} minutes, got {duration_value:.1f} minutes",
            )

        return 1.0
