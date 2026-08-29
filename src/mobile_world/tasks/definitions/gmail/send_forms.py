"""Task involving conditional searching for multiple emails."""

from pathlib import Path

from loguru import logger

from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.controller import AndroidController
from mobile_world.runtime.utils.helpers import execute_adb
from mobile_world.tasks.base import BaseTask


class SendFormsTask(BaseTask):
    goal = (
        "Please check my email for any field trip forms sent from October 3rd onward."
        "Download all of them and send them to principal@school.edu with the subject 'Field Trip Forms'. Then, tell me how many forms you found as a single number."
    )

    task_tags = {"lang-en"}

    app_names = {
        "Mail",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Inject test email and reset Mail app."""
        root_path = Path(__file__).resolve().parent
        local_json_path = root_path / "assets" / "sendForms.json"

        remote_json_path = "/sdcard/Android/data/com.gmailclone/files/state.json"
        remote_attachment_path = "/sdcard/Android/data/com.gmailclone/files/attachments"

        if not local_json_path.exists():
            logger.error(f"Email state file not found: {local_json_path}")
            return False

        result = execute_adb(f"push {local_json_path} {remote_json_path}")
        if not result.success:
            logger.error(f"Failed to push email JSON to emulator: {result.error}")
            return False

        for attachment in ["form1.jpg", "form2.jpg", "form3.jpg", "form4.jpg", "form5.jpg"]:
            result = execute_adb(
                f"push {root_path / 'assets' / attachment} {remote_attachment_path}/{attachment}",
                root_required=True,
            )
            if not result.success:
                logger.error(f"Failed to push attachment to emulator: {result.error}")
                return False

        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        # Check sent email
        email_info = get_sent_email_info()
        if email_info is None:
            return 0.0, "No email found"
        recipients = email_info["to"]
        attachments = email_info["attachments"]
        subject = email_info["subject"]
        files = {"form1.jpg", "form2.jpg", "form3.jpg"}

        # Validate email
        if not (
            len(attachments) == 3
            and subject == "Field Trip Forms"
            and recipients == "principal@school.edu"
        ):
            logger.info("Incorrect email")
            return 0.0, "incorrect email"

        # Check if all required files are in attachments
        if len(attachments) != len(files):
            logger.info("Incorrect email - wrong number of attachments")
            return 0.0, "incorrect email - wrong number of attachments"

        found = []
        for i in range(len(files)):
            if attachments[i]["name"] not in files:
                logger.info("Incorrect email - unexpected attachment found")
                return 0.0, "incorrect email - unexpected attachment found"
            found.append(attachments[i]["name"])

        if set(found) != files:
            logger.info("Incorrect email - missing attachments")
            return 0.0, "incorrect email - missing attachments"

        logger.info("Correct email sent")

        answer = (controller.interaction_cache or "").strip()

        if not answer:
            return 0.0, "no answer provided"

        normalized = answer.lower().strip()

        if "3" not in normalized:
            return 0.0, f"incorrect answer: {answer}"

        return 1.0, "correct answer"
