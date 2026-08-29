"""Set alarm task implementation."""

from loguru import logger

from mobile_world.runtime.app_helpers.system import (
    check_alarm_via_adb,
)
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SetAlarmTaskAskUser2(BaseTask):
    task_tags = {"agent-user-interaction", "lang-en"}

    goal = "Please set a wake-up alarm for my weekend, and choose my favorite ringtone."

    app_names = {
        "Clock",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize the alarm clock task by resetting the Clock app to clean state."""
        self.relevant_information = "The alarm should be set for 9:45 AM on weekend (Saturday and Sunday). My favorite ringtone is 'beebeep'."
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """Check if the alarm was set correctly via ADB."""
        self._check_is_initialized()

        alarm_info = check_alarm_via_adb(controller, hour=9, minute=45)

        if not alarm_info:
            logger.info("No alarm found at 9:45 AM")
            return 0.0, "No alarm found at 9:45 AM"

        if not alarm_info.get("enabled", False):
            logger.info("Alarm exists but is not enabled")
            return 0.0, "Alarm exists but is not enabled"

        # Weekend mask: Saturday(32) + Sunday(64) = 96
        weekend_mask = 96
        daysofweek = alarm_info.get("daysofweek", 0)

        if daysofweek != weekend_mask:
            logger.info(f"Days mismatch: expected {weekend_mask} (weekend), got {daysofweek}")
            return 0.0, f"Days mismatch: expected {weekend_mask} (weekend), got {daysofweek}"

        ringtone = alarm_info.get("ringtone", "").lower()
        if "beebeep" not in ringtone:
            logger.info(f"Ringtone mismatch: expected 'beebeep' in '{ringtone}'")
            return 0.0, f"Ringtone mismatch: expected 'beebeep' in '{ringtone}'"

        logger.info("All alarm conditions met successfully (via adb)")
        return 1.0, "success"
