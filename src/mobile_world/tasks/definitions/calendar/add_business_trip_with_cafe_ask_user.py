"""Add business trip calendar event with nearby cafe information."""

import datetime

from mobile_world.runtime.app_helpers import mcp as mcp_helper
from mobile_world.runtime.app_helpers.fossify_calendar import get_calendar_events
from mobile_world.runtime.app_helpers.system import get_device_datetime
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class AddBusinessTripAskUserTask(BaseTask):
    """Add business trip calendar event with nearby cafe address in description."""

    goal = (
        "我下周六10:00am-12:30am要上海虹桥火车站，"
        '你帮我找到离上海虹桥火车站10公里以内的景点，我周一上班前去参观下，添加事项到calender，事项为出差游玩，把找到的景点按照"景点名字：地址"放入calender事件的描述中，多个景点按逗号分隔'
    )
    task_tags = {"agent-mcp", "agent-user-interaction", "lang-cn"}

    EVENT_TITLE = "出差游玩"
    SEARCH_KEYWORDS = "景点"
    SEARCH_RADIUS = "10000"  # 10公里 = 10000米
    DESTINATION_LOCATION = "121.323774, 31.193241"

    app_names = {"MCP-Amap", "Calendar"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        self.relevant_information = "游玩的时间是周日早上9:00am-5:00pm"
        return True

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        landmark_list = await mcp_helper.search_nearby(
            location=self.DESTINATION_LOCATION,
            radius=self.SEARCH_RADIUS,
            keywords=self.SEARCH_KEYWORDS,
        )

        today = get_device_datetime()
        days_until_sunday = (6 - today.weekday()) % 7
        if days_until_sunday == 0:
            days_until_sunday = 7
        next_sunday_date = (today + datetime.timedelta(days=days_until_sunday)).date()

        start_time = datetime.datetime(
            next_sunday_date.year,
            next_sunday_date.month,
            next_sunday_date.day,
            9,
            0,
            0,
            tzinfo=datetime.UTC,
        )
        end_time = datetime.datetime(
            next_sunday_date.year,
            next_sunday_date.month,
            next_sunday_date.day,
            17,
            0,
            0,
            tzinfo=datetime.UTC,
        )

        expected_start_ts = int(start_time.timestamp())
        expected_end_ts = int(end_time.timestamp())

        events = get_calendar_events([expected_start_ts, expected_end_ts])

        for event in events:
            if self.EVENT_TITLE not in event.get("title", ""):
                continue

            description = event.get("description", "")
            percentage = sum(landmark in description for landmark in landmark_list) / len(
                landmark_list
            )

            if percentage < 0.8:
                return (
                    0.0,
                    "Event description does not contain correct format.",
                )

            event_start_ts = event.get("start_ts", 0)
            event_end_ts = event.get("end_ts", 0)

            if event_start_ts != expected_start_ts or event_end_ts != expected_end_ts:
                return (
                    0.0,
                    f"Event time incorrect. Expected: {start_time.strftime('%Y-%m-%d %H:%M:%S')} - {end_time.strftime('%Y-%m-%d %H:%M:%S')} UTC (start_ts={expected_start_ts}, end_ts={expected_end_ts}), Got: start_ts={event_start_ts}, end_ts={event_end_ts}",
                )

            return 1.0

        return (
            0.0,
            f"Calendar event not found with title '{self.EVENT_TITLE}' containing attractions",
        )

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        return True
