"""Create multiple memos on Calendar from posts under #openTalk on Mastodon."""

import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.app_helpers.fossify_calendar import get_calendar_events
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonCalendarMultiMemosTask(BaseTask):
    goal = (
        "On Mastodon, find lectures in the #openTalk hashtag for the current month, "
        "then add the lecture information (time, location, topic) to the calendar events. "
        "If the start time is within 10 days, set the reminder time to 1 day before. "
        "Otherwise, set the reminder time to 3 days before the start time."
    )

    task_tags = {"lang-en"}

    EXPECTED_EVENTS_START_TIME_1 = (
        1761318000  # 2025-10-24 15:00:00 (GMT+0, greenwich mean time, linux time +1h)
    )
    EXPECTED_EVENTS_END_TIME_1 = (
        1761323400  # 2025-10-24 16:30:00 (GMT+0, greenwich mean time, linux time +1h)
    )
    EXPECTED_EVENTS_TITLE_1 = "AI-Powered Urban Mobility"
    EXPECTED_EVENTS_LOCATION_1 = "Auditorium 2-A, Innovation Building"
    EXPECTED_EVENTS_REMINDER_TIME_1 = 1440  # 1 day in minutes

    EXPECTED_EVENTS_START_TIME_2 = 1761575400  # 2025-10-27 14:30:00 (GMT+0)
    EXPECTED_EVENTS_END_TIME_2 = 1761580800  # 2025-10-27 16:00:00 (GMT+0)
    EXPECTED_EVENTS_TITLE_2 = "The Future of Edge Intelligence in Everyday Devices"
    EXPECTED_EVENTS_LOCATION_2 = "Room 401, Tech Innovation Center"
    EXPECTED_EVENTS_REMINDER_TIME_2 = 4320  # 3 days in minutes

    app_names = {"Mastodon", "Calendar"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        try:
            mastodon.start_mastodon_backend()
            return True
        except Exception as e:
            logger.error(f"Failed to start Mastodon backend: {e}")
            return False

    def _check_event(
        self,
        memo_events: list,
        start_time: int,
        end_time: int,
        title: str,
        location: str,
        reminder_time: int,
    ) -> tuple[bool, str]:
        """Helper method to check a single event."""
        events = [
            event
            for event in memo_events
            if event["start_ts"] == start_time and event["end_ts"] == end_time
        ]

        # check if the event exists
        if len(events) == 0:
            return False, f"Event not found: {start_time} - {end_time}"
        event = events[0]

        # check title
        if title.lower() not in event["title"].lower():
            return False, (f"Title mismatch: '{event['title']}' does not contain '{title}'")

        # check location
        if location.lower() not in event["location"].lower():
            return False, (
                f"Location mismatch: '{event['location']}' does not contain '{location}'"
            )

        # check reminder time
        if event["reminder_1_minutes"] != reminder_time:
            return False, (
                f"Reminder time mismatch: {event['reminder_1_minutes']} != {reminder_time}"
            )

        return True, ""

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """
        check:
        - event 1 exists
            - event title is the expected title
            - event location is the expected location
            - event reminder time is the expected reminder time
        - event 2 exists
            - event title is the expected title
            - event location is the expected location
            - event reminder time is the expected reminder time
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()
        time.sleep(1)

        memo_events = get_calendar_events()

        # Check event 1
        success_1, error_msg_1 = self._check_event(
            memo_events,
            self.EXPECTED_EVENTS_START_TIME_1,
            self.EXPECTED_EVENTS_END_TIME_1,
            self.EXPECTED_EVENTS_TITLE_1,
            self.EXPECTED_EVENTS_LOCATION_1,
            self.EXPECTED_EVENTS_REMINDER_TIME_1,
        )
        if not success_1:
            return 0.0, error_msg_1

        # Check event 2
        success_2, error_msg_2 = self._check_event(
            memo_events,
            self.EXPECTED_EVENTS_START_TIME_2,
            self.EXPECTED_EVENTS_END_TIME_2,
            self.EXPECTED_EVENTS_TITLE_2,
            self.EXPECTED_EVENTS_LOCATION_2,
            self.EXPECTED_EVENTS_REMINDER_TIME_2,
        )
        if not success_2:
            return 0.0, error_msg_2

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        try:
            mastodon.stop_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to stop Mastodon backend: {e}")
            return False
        return True
