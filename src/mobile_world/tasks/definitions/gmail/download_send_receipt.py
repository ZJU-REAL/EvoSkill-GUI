"""Download receipt and send email task implementation."""

from pathlib import Path

from loguru import logger

from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.controller import AndroidController
from mobile_world.runtime.utils.helpers import execute_adb
from mobile_world.tasks.base import BaseTask


class DownloadSendReceiptTask(BaseTask):
    goal = (
        "Look for a file in my email titled 'receipts.jpg' and download it."
        "Then, send it to to treasurer@gmail.com with the subject 'Proof of purchase', the email should mention the total amount spent in the email."
    )

    correct_subjects = "Proof of purchase"
    correct_recipient = "treasurer@gmail.com"
    correct_attachment = "receipt.jpg"
    total_amount = "5.08"

    task_tags = {"lang-en"}

    app_names = {
        "Mail",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Inject test email and reset Mail app."""
        root_path = Path(__file__).resolve().parent
        local_json_path = root_path / "assets" / "downloadSendReceipt.json"
        local_attachment_path = root_path / "assets" / "receipt.jpg"

        remote_json_path = "/sdcard/Android/data/com.gmailclone/files/state.json"
        remote_attachment_path = "/sdcard/Android/data/com.gmailclone/files/attachments/receipt.jpg"

        if not local_json_path.exists():
            logger.error(f"Email state file not found: {local_json_path}")
            return False

        result = execute_adb(f"push {local_json_path} {remote_json_path}")
        if not result.success:
            logger.error(f"Failed to push email JSON to emulator: {result.error}")
            return False

        result1 = execute_adb(
            f"push {local_attachment_path} {remote_attachment_path}", root_required=True
        )
        if not result1.success:
            logger.error(f"Failed to push attachment to emulator: {result1.error}")
            return False

        result2 = execute_adb("shell am force-stop com.gmailclone")
        result3 = execute_adb("shell am start -n com.gmailclone/.MainActivity")
        if not result2.success or not result3.success:
            logger.warning(
                f"Failed to restart Mail app: {result2.error if not result2.success else result3.error}"
            )

        logger.info("Successfully injected emails and restarted Mail app.")
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        email_info = get_sent_email_info()
        if email_info is None:
            return 0.0, "No email found"
        attachments = email_info["attachments"]
        recipient = email_info["to"]
        subject = email_info["subject"]
        if len(attachments) != 1:
            return 0.0, "Incorrect number of attachments"

        if attachments[0]["name"] != self.correct_attachment:
            return 0.0, "Incorrect attachment"
        if recipient != self.correct_recipient:
            return 0.0, "Incorrect recipient"
        if subject not in self.correct_subjects:
            return 0.0, "Incorrect subject"
        if self.total_amount not in email_info["body"]:
            return 0.0, "Incorrect total amount"
        return 1.0, "success"
