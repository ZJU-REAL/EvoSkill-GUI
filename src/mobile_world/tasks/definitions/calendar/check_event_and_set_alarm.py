from loguru import logger

from mobile_world.runtime.app_helpers.system import (
    check_alarm_via_adb,
)
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class CheckEventAndSetAlarmAskUserTask(BaseTask):
    """Check calendar for meeting with Sam and set alarm to remind 5 minutes in advance."""

    goal = "Set an alarm in Clock app to remind me of my meeting with Sam 5 minutes in advance."
    alarm_hour = 8
    alarm_min = 55

    task_tags = {"lang-en", "agent-user-interaction"}

    app_names = {"Calendar", "Clock"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        self.relevant_information = "All the meetings are scheduled in the Calendar app."
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        alarm_info = check_alarm_via_adb(controller, hour=self.alarm_hour, minute=self.alarm_min)

        if not alarm_info:
            logger.info("No alarm found at 8:55 AM")
            return 0.0, "No alarm found at 8:55 AM"

        if not alarm_info.get("enabled", False):
            logger.info("Alarm exists but is not enabled")
            return 0.0, "Alarm exists but is not enabled"

        blackout_end = alarm_info.get("blackout_end", "")

        if blackout_end != "2025-10-19":  # Blackout end date is not 2025-10-20, but one day before
            logger.info(f"Blackout end date mismatch: expected 2025-10-19, got {blackout_end}")
            return 0.0, f"Blackout end date mismatch: expected 2025-10-19, got {blackout_end}"

        logger.info("All alarm conditions met successfully: Monday 8:55 AM alarm is set")
        return 1.0, "Success"
