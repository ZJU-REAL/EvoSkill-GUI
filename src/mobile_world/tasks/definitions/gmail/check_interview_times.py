"""Check upcoming interviews and set calendar task implementation."""

import datetime
from pathlib import Path

import pytz
from loguru import logger

from mobile_world.runtime.app_helpers.fossify_calendar import get_calendar_events
from mobile_world.runtime.controller import AndroidController
from mobile_world.runtime.utils.helpers import execute_adb
from mobile_world.tasks.base import BaseTask


class CheckInterviewTimesTask(BaseTask):
    goal = (
        "Check my email for any job interviews I have in November."
        "Set calendar events for each of them. Use the company name as the title and the interview time as the start and end time."
    )

    task_tags = {"lang-en"}

    app_names = {"Mail", "Calendar"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Inject test email and reset Mail app."""
        root_path = Path(__file__).resolve().parent
        local_json_path = root_path / "assets" / "checkInterviewTimes.json"

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
        count = 0

        # Check calendar
        calendar_info = get_calendar_events()
        time_zone = pytz.timezone("UTC")
        meet_times = {
            1: time_zone.localize(datetime.datetime(2025, 11, 12, 14, 0, 0)),
            2: time_zone.localize(datetime.datetime(2025, 11, 3,  17, 30, 0)),
            3: time_zone.localize(datetime.datetime(2025, 11, 20, 15, 0, 0)),
        }
        meet_titles = {"Google": 1, "Meta": 2, "Amazon": 3}
        start_ts = {
            1: int(meet_times[1].timestamp()),
            2: int(meet_times[2].timestamp()),
            3: int(meet_times[3].timestamp()),
        }
        end_ts = {
            1: int(meet_times[1].timestamp()) + 3600,
            2: int(meet_times[2].timestamp()) + 2700,
            3: int(meet_times[3].timestamp()) + 5400,
        }

        for event in calendar_info:
            if event["title"] in meet_titles:
                index = meet_titles[event["title"]]
                if event["start_ts"] == start_ts[index] and event["end_ts"] == end_ts[index]:
                    count += 1

        if count == 3:
            logger.info("Correct calendar events")
            return 1.0, "success"

        logger.info("Incorrect calendar events")
        return 0.0, "incorrect calendar events"
