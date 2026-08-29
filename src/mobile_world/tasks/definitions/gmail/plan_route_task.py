"""Plan driving route and send to email."""

from mobile_world.runtime.app_helpers import mcp as mcp_helper
from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class PlanRouteTask(BaseTask):
    """Plan driving route from Alibaba Xixi C Campus to Xiaoshan Airport."""

    goal = (
        "帮我规划从杭州亲橙酒店到萧山机场之间规划一条驾车路线，"
        "把返回的路线信息组织成一段内容，instructions用逗号分隔，"
        "发送到我的生活邮箱dylan@gmail.com，标题为`daily travel`"
    )
    task_tags = {"agent-mcp", "lang-cn"}

    EMAIL_ADDRESS = "dylan@gmail.com"
    EMAIL_SUBJECT = "daily travel"

    ORIGIN_LOCATION = "120.021942,30.317023"
    DESTINATION_LOCATION = "120.432413,30.234708"

    app_names = {"MCP-Amap", "Mail"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize task - no special setup needed."""
        return True

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        # Get route information
        route_data = await mcp_helper.plan_route(
            origin=self.ORIGIN_LOCATION, destination=self.DESTINATION_LOCATION
        )

        route_info = route_data.get("route", [])
        assert len(route_info) > 0, "No route info"

        # Extract all instructions from route
        expected_instructions = []
        paths = route_info.get("paths", [])
        if paths:
            steps = paths[0].get("steps", [])
            for step in steps:
                if "instruction" in step:
                    instruction = str(step["instruction"]).strip()
                    if instruction:
                        expected_instructions.append(instruction)

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
        for instruction in expected_instructions:
            if instruction.lower().strip() not in email_body.lower().strip():
                return 0.0, f"Instruction {instruction} not found in email body"

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        return True
