"Create a new memo on Mastodon."

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.app_helpers.fossify_calendar import get_calendar_events
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonCreateMemoTask(BaseTask):
    goal = (
        "Find information under #openTalk on Mastodon about the topic of Urban Mobility lectures, "
        "then create a event on my calendar with time, location, and topic as title, and set a reminder 1 day before."
    )

    EXPECTED_EVENT_START_TIME = (
        1761318000  # 2025-10-24 15:00:00 (GMT+0, greenwich mean time, linux time +1h)
    )
    EXPECTED_EVENT_END_TIME = (
        1761323400  # 2025-10-24 16:30:00 (GMT+0, greenwich mean time, linux time +1h)
    )
    EXPECTED_TITLE = "AI-Powered Urban Mobility"
    EXPECTED_LOCATION = "Auditorium 2-A, Innovation Building"
    EXPECTED_REMINDER_TIME = 1440  # 1 day in minutes

    task_tags = {"lang-en"}

    app_names = {"Mastodon", "Calendar"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        try:
            mastodon.start_mastodon_backend()
            return True
        except Exception as e:
            logger.error(f"Failed to start Mastodon backend: {e}")
            return False

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """
        check:
        - event exists
        - event title is the expected title
        - event location is the expected location
        - event reminder time is the expected reminder time
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()

        memo_events = get_calendar_events()

        events = [
            event
            for event in memo_events
            if event["start_ts"] == self.EXPECTED_EVENT_START_TIME
            and event["end_ts"] == self.EXPECTED_EVENT_END_TIME
        ]

        # check if the event exists
        if len(events) == 0:
            return (
                0.0,
                f"Event not found: {self.EXPECTED_EVENT_START_TIME} - {self.EXPECTED_EVENT_END_TIME}",
            )
        event = events[0]

        # check title
        if self.EXPECTED_TITLE.lower() not in event["title"].lower():
            return 0.0, f"Title mismatch: {event['title']} does not contain {self.EXPECTED_TITLE}"

        # check location
        if self.EXPECTED_LOCATION.lower() not in event["location"].lower():
            return (
                0.0,
                f"Location mismatch: {event['location']} does not contain {self.EXPECTED_LOCATION}",
            )

        # check reminder time
        if event["reminder_1_minutes"] != self.EXPECTED_REMINDER_TIME:
            return (
                0.0,
                f"Reminder time mismatch: {event['reminder_1_minutes']} != {self.EXPECTED_REMINDER_TIME}",
            )

        return 1.0

    def tear_down(self, controller: AndroidController):
        super().tear_down(controller)
        try:
            mastodon.stop_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to stop Mastodon backend: {e}")
            return False
        return True
