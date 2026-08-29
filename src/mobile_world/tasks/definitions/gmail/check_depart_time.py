"""Check depart time task implementation."""

from pathlib import Path

from loguru import logger

from mobile_world.runtime.app_helpers.system import check_sms_via_adb
from mobile_world.runtime.controller import AndroidController
from mobile_world.runtime.utils.helpers import execute_adb
from mobile_world.tasks.base import BaseTask


class CheckDepartTimeTask(BaseTask):
    goal = (
        "Check if I've received an email about the depart time for the CoolHacks hackathon."
        "If not, text Carl (345 6784 3456) 'Do you know what time we're leaving tomorrow?'"
    )
    correct_phone_number = "34567843456"
    expected_message_partial = "Do you know what time we're leaving tomorrow?"

    task_tags = {"lang-en"}

    app_names = {"Messages", "Mail"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Inject test email and reset Mail app."""
        root_path = Path(__file__).resolve().parent
        local_json_path = root_path / "assets" / "checkDepartTime.json"

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
        """Check if the correct SMS was sent to Susan."""
        self._check_is_initialized()

        result = check_sms_via_adb(
            controller,
            phone_number=self.correct_phone_number,
            content=self.expected_message_partial,
        )

        if result:
            logger.info(
                f"Successfully found SMS to {self.correct_phone_number} with correct content"
            )
            return 1.0, "success"
        else:
            return 0.0, f"SMS to {self.correct_phone_number} with correct content not found"
