"""Check email and set alarm task implementation."""

from pathlib import Path

from loguru import logger

from mobile_world.runtime.app_helpers.system import (
    check_alarm_via_adb,
)
from mobile_world.runtime.controller import AndroidController
from mobile_world.runtime.utils.helpers import execute_adb
from mobile_world.tasks.base import BaseTask


class CheckEventTimeTask(BaseTask):
    goal = (
        "Check my email for the time of the Christmas party today. "
        "Set an alarm for one hour before then."
    )

    task_tags = {"lang-en"}

    app_names = {"Clock", "Mail"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Inject test email and reset Mail app."""
        root_path = Path(__file__).resolve().parent
        local_json_path = root_path / "assets" / "checkEventTime.json"
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

        # Check 6:00 PM alarm
        alarm_info = check_alarm_via_adb(controller, hour=18, minute=0)
        if not alarm_info:
            logger.info("No alarm found at 6:00 PM")
            return 0.0, "No alarm found at 6:00 PM"
        if not alarm_info.get("enabled", False):
            logger.info("Alarm exists but is not enabled")
            return 0.0, "Alarm exists but is not enabled"

        # All conditions met
        logger.info("Alarm successfully set for 6:00 PM today")
        return 1.0, "success"
