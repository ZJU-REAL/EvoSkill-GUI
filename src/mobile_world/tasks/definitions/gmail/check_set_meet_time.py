"""Check meeting time and set calendar task implementation."""

import datetime
from pathlib import Path

import pytz
from loguru import logger

from mobile_world.runtime.app_helpers.fossify_calendar import get_calendar_events
from mobile_world.runtime.controller import AndroidController
from mobile_world.runtime.utils.helpers import execute_adb
from mobile_world.tasks.base import BaseTask


class CheckSetMeetTimeTask(BaseTask):
    goal = (
        "Check my email for the date and time of my meeting with Carl."
        "Then, set a one hour calendar event titled 'Board Meeting'"
    )

    task_tags = {"lang-en"}

    app_names = {"Mail", "Calendar"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Inject test email and reset Mail app."""
        root_path = Path(__file__).resolve().parent
        local_json_path = root_path / "assets" / "checkSetMeetTime.json"

        remote_json_path = "/sdcard/Android/data/com.gmailclone/files/state.json"

        if not local_json_path.exists():
            logger.error(f"Email state file not found: {local_json_path}")
            return False

        result = execute_adb(f"push {local_json_path} {remote_json_path}")
        if not result.success:
            logger.error(f"Failed to push email JSON to emulator: {result.error}")
            return False

        result1 = execute_adb("shell am force-stop com.gmailclone")
        result2 = execute_adb("shell am start -n com.gmailclone/.MainActivity")
        if not result1.success or not result2.success:
            logger.warning(
                f"Failed to restart Mail app: {result1.error if not result1.success else result2.error}"
            )

        logger.info("Successfully injected emails and restarted Mail app.")
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        # Check calendar
        calendar_info = get_calendar_events()
        time_zone = pytz.timezone("UTC")
        meet_time = time_zone.localize(datetime.datetime(2025, 11, 15, 15, 0, 0))
        meet_title = "Board Meeting"
        start_ts = int(meet_time.timestamp())
        end_ts = start_ts + 3600

        for event in calendar_info:
            if event["title"].lower() == meet_title.lower():
                if event["start_ts"] == start_ts and event["end_ts"] == end_ts:
                    return 1.0, "success"

        logger.info("Incorrect calendar event")
        return 0.0, "incorrect calendar event"
