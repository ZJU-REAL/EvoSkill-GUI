"""Add business trip calendar event with nearby cafe information."""

from mobile_world.runtime.app_helpers import mcp as mcp_helper
from mobile_world.runtime.app_helpers.fossify_calendar import get_calendar_events
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class AddBusinessTripWithCafeTask(BaseTask):
    """Add business trip calendar event with nearby cafe address in description."""

    goal = (
        "我下周六10:00am-12:30pm要去「上海虹桥火车站」，添加事项到calender，事项为出差，"
        '你帮我找到离上海虹桥火车站10公里以内的景点，我周一上班前去参观下，按照"景点名字：地址"放入calender事件的描述中，多个景点按逗号分隔'
    )
    task_tags = {"agent-mcp", "lang-cn"}

    EVENT_TITLE = "出差"
    SEARCH_KEYWORDS = "景点"
    SEARCH_RADIUS = "10000"  # 10公里 = 10000米
    DESTINATION_LOCATION = "121.323774, 31.193241"

    app_names = {"MCP-Amap", "Calendar"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        return True

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        landmark_list = await mcp_helper.search_nearby(
            location=self.DESTINATION_LOCATION,
            radius=self.SEARCH_RADIUS,
            keywords=self.SEARCH_KEYWORDS,
        )

        events = get_calendar_events()
        for event in events:
            if self.EVENT_TITLE not in event.get("title", ""):
                continue
            description = event.get("description", "")
            percentage = sum(landmark in description for landmark in landmark_list) / len(
                landmark_list
            )
            if percentage > 0.8:
                return 1.0
            else:
                return 0.0, "Event description does not contain correct format"
        return (
            0.0,
            f"Calendar event not found with title '{self.EVENT_TITLE}' containing attractions",
        )

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        return True
