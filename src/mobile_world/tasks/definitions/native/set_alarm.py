"""Set alarm task implementation."""

from loguru import logger

from mobile_world.runtime.app_helpers.system import (
    check_alarm_via_adb,
)
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SetAlarmTask(BaseTask):
    goal = 'Set a weekend alarm for 8:25 a.m. with the ringtone "beebeep" and vibration off. '

    task_tags = {"lang-en"}

    app_names = {
        "Clock",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize the alarm clock task by resetting the Clock app to clean state."""
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """Check if the alarm was set correctly via ADB."""
        self._check_is_initialized()

        alarm_info = check_alarm_via_adb(controller, hour=8, minute=25)

        if not alarm_info:
            logger.info("No alarm found at 8:25 AM")
            return 0.0, "No alarm found at 8:25 AM"

        if not alarm_info.get("enabled", False):
            logger.info("Alarm exists but is not enabled")
            return 0.0, "Alarm exists but is not enabled"

        # Weekend mask: Saturday(32) + Sunday(64) = 96
        weekend_mask = 96
        daysofweek = alarm_info.get("daysofweek", 0)

        if daysofweek != weekend_mask:
            logger.info(f"Days mismatch: expected {weekend_mask} (weekend), got {daysofweek}")
            return 0.0, f"Days mismatch: expected {weekend_mask} (weekend), got {daysofweek}"

        if alarm_info.get("vibrate", False):
            logger.info("Vibration is on, should be off")
            return 0.0, "Vibration is on, should be off"

        ringtone = alarm_info.get("ringtone", "").lower()
        if "beebeep" not in ringtone:
            logger.info(f"Ringtone mismatch: expected 'beebeep' in '{ringtone}'")
            return 0.0, f"Ringtone mismatch: expected 'beebeep' in '{ringtone}'"

        logger.info("All alarm conditions met successfully (via adb)")
        return 1.0, "success"
