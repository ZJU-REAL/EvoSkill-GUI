"""Careful email reading task implementation."""

from pathlib import Path

from loguru import logger

from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.controller import AndroidController
from mobile_world.runtime.utils.helpers import execute_adb
from mobile_world.tasks.base import BaseTask


class CheckRegistrationTask(BaseTask):
    goal = (
        "Check my email for Putnam registration confirmation."
        "If no such email exists, email kathy@gmail.com asking about it with the subject 'Putnam Registration Confirmation'"
    )

    correct_recipient = "kathy@gmail.com"

    task_tags = {"lang-en"}

    app_names = {
        "Mail",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Inject test email and reset Mail app."""
        root_path = Path(__file__).resolve().parent
        local_json_path = root_path / "assets" / "checkRegistration.json"

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
        """Check if the task succeeded by verifying the check registration email was sent."""
        self._check_is_initialized()

        email = get_sent_email_info()

        if email is None:
            return 0.0, "No email found"
        if email.get("body", "") == "":
            return 0.0, "No email body found"
        if (
            email["to"].lower() == self.correct_recipient.lower()
            and email["subject"].lower() == "Putnam Registration Confirmation".lower()
        ):
            return 1.0, "success"
        return 0.0, "Wrong email sent"
