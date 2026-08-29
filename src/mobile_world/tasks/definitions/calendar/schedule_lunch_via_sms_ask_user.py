"""Schedule lunch invitation from SMS to calendar task implementation."""

import datetime
import time

from loguru import logger

from mobile_world.runtime.app_helpers.fossify_calendar import get_calendar_events
from mobile_world.runtime.app_helpers.system import check_sms_via_adb
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class ScheduleLunchViaSmsAskUserTask(BaseTask):
    """Receive lunch invitation via SMS and schedule it on calendar."""

    task_tags = {"lang-en", "agent-user-interaction"}
    goal = 'I\'ve received a lunch invitation via text message; please reply "OK" and schedule a lunch event ranging from 11 a.m. to 12 a.m. on Oct 16.'

    # SMS sender and content
    sender_name = "Marry"
    sender_phone = "+15051234567"
    sms_content = "Hi! Would you like to join me for lunch tomorrow at 11 AM? It will be about an hour. Looking forward to it!"

    # Expected reply message
    expected_reply = "OK"

    # Expected calendar event details (in UTC)
    # Tomorrow is Oct 17, so today is Oct 16
    # Note: Calendar stores times in UTC directly (11:00 UTC, not local time)
    expected_date = datetime.date(2025, 10, 17)
    expected_start_hour = 11
    expected_start_minute = 0
    expected_duration_hours = 1  # 1 hour lunch

    app_names = {"Calendar", "Messages"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        self.relevant_information = "I just gave the incorrect information by mistake, the time range should be 11 a.m. to 12 p.m. on Oct 17."

        try:
            logger.info(f"Injecting SMS from {self.sender_name} ({self.sender_phone})")
            result = controller.simulate_sms(self.sender_phone, self.sms_content)

            if not result.success:
                logger.error(f"Failed to inject SMS: {result.error}")
                return False

            time.sleep(1)
            logger.info("Successfully injected lunch invitation SMS")

            return True

        except Exception as e:
            logger.error(f"Initialize task failed: {e}")
            return False

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        sms_sent = check_sms_via_adb(
            controller,
            phone_number=self.sender_phone,
            content=self.expected_reply,
        )

        if not sms_sent:
            logger.info(
                f"SMS reply '{self.expected_reply}' to Marry ({self.sender_phone}) not found"
            )
            return (
                0.0,
                f"SMS reply '{self.expected_reply}' to Marry ({self.sender_phone}) not found",
            )

        calendar_info = get_calendar_events()

        start_time = datetime.datetime(
            self.expected_date.year,
            self.expected_date.month,
            self.expected_date.day,
            self.expected_start_hour,
            self.expected_start_minute,
            0,
            tzinfo=datetime.UTC,
        )
        end_time = start_time + datetime.timedelta(hours=self.expected_duration_hours)

        start_ts = int(start_time.timestamp())
        end_ts = int(end_time.timestamp())

        logger.info(
            f"Looking for calendar event on {self.expected_date} from {self.expected_start_hour}:00 to {self.expected_start_hour + self.expected_duration_hours}:00 UTC"
        )
        logger.info(
            f"Expected timestamps: start={start_ts} ({start_time}), end={end_ts} ({end_time})"
        )

        calendar_event_found = False
        for event in calendar_info:
            if event["start_ts"] == start_ts and event["end_ts"] == end_ts:
                calendar_event_found = True
                break

        if not calendar_event_found:
            logger.info(
                f"Calendar event not found for Oct 17, 2025 11:00-12:00. Found {len(calendar_info)} total events."
            )
            if calendar_info:
                for event in calendar_info:
                    logger.debug(
                        f"Event: {event.get('title', 'Untitled')} - start: {event['start_ts']}, end: {event['end_ts']}"
                    )
            return (
                0.0,
                f"Calendar event not found for Oct 17, 2025 11:00-12:00. Found {len(calendar_info)} total events.",
            )

        return 1.0, "Success"
