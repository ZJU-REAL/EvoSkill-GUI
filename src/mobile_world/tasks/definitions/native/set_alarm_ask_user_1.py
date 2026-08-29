"""Set alarm task implementation."""

from loguru import logger

from mobile_world.runtime.app_helpers.system import (
    check_alarm_via_adb,
)
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SetAlarmTaskAskUser1(BaseTask):
    task_tags = {"agent-user-interaction", "lang-en"}

    goal = "Please set a wake-up alarm for me on Friday."

    app_names = {
        "Clock",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize the alarm clock task by resetting the Clock app to clean state."""
        self.relevant_information = "The alarm should be set for 1:20 PM on Friday."
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """Check if the alarm was set correctly via ADB."""
        self._check_is_initialized()

        try:
            alarm_info = check_alarm_via_adb(controller, hour=13, minute=20)

            if not alarm_info:
                logger.info("No alarm found at 1:20 PM")
                return 0.0, "No alarm found at 1:20 PM"

            if not alarm_info.get("enabled", False):
                logger.info("Alarm exists but is not enabled")
                return 0.0, "Alarm exists but is not enabled"

            # Friday mask: Friday(16) = 16
            friday_mask = 16
            daysofweek = alarm_info.get("daysofweek", 0)

            if daysofweek != friday_mask:
                logger.info(f"Days mismatch: expected {friday_mask} (Friday), got {daysofweek}")
                return 0.0, f"Days mismatch: expected {friday_mask} (Friday), got {daysofweek}"

            logger.info("All alarm conditions met successfully (via adb)")
            return 1.0, "All alarm conditions met successfully (via adb)"

        except Exception as e:
            logger.error(f"Error checking alarm via adb: {e}")
            return 0.0, f"Error checking alarm via adb: {e}"
