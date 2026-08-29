"""Send waiver task implementation."""

from pathlib import Path

from loguru import logger

from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SendWaiverTask(BaseTask):
    goal = (
        "Send the file 'waiver.jpg' as an email attachment to bob@gmail.com. "
        "Title the email 'Updated waiver'."
    )

    correct_recipient = "bob@gmail.com"
    file_name = "waiver.jpg"
    correct_subject = "Updated waiver"

    task_tags = {"lang-en"}

    app_names = {
        "Mail",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Prepare the task by resetting Mail and pushing the waiver file to the device."""
        root_path = Path(__file__).resolve().parent
        local_file_path = root_path / "assets" / self.file_name
        if not local_file_path.exists():
            logger.error(f"Waiver file not found: {local_file_path}")
            return False

        remote_file_path = f"/sdcard/Download/{self.file_name}"
        result = controller.push_file(str(local_file_path), remote_file_path)
        if not result.success:
            logger.error(f"Failed to push waiver file to emulator: {result.error}")
            return False

        controller.refresh_media_scan(remote_file_path)

        logger.info(f"Task initialized: '{self.file_name}' pushed to {remote_file_path}")
        self.initialized = True
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """Check if the task succeeded by verifying the waiver was sent to Bob."""
        self._check_is_initialized()

        email = get_sent_email_info()

        if email is None:
            return 0.0, "No email found"
        if email["to"].lower() == self.correct_recipient.lower():
            attachments = email.get("attachments", [])
            if len(attachments) == 1 and attachments[0]["name"] == self.file_name:
                if email["subject"].lower() == self.correct_subject.lower():
                    return 1.0, "success"
                else:
                    return 0.0, f"email subject is not '{self.correct_subject}'"
            else:
                return 0.0, "email has wrong attachments"
        else:
            return 0.0, "email sent to wrong recipient"
