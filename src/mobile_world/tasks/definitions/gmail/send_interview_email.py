"""Send interview email task implementation."""

from pathlib import Path

from loguru import logger

from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SendInterviewEmailTask(BaseTask):
    goal = (
        "Find Kevin's resume and send an email to Kevin saying: "
        '"Your interview is scheduled for tomorrow morning at 10:30 AM."'
    )
    correct_recipient = "kevin.zhang@example.com"
    expected_message_partial = "Your interview is scheduled for tomorrow morning at 10:30 AM"
    file_name = "Kevin_CV.pdf"

    task_tags = {"lang-en"}

    app_names = {"Mail", "Files"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize the gmail task by pushing Kevin's resume to the device."""
        current_file = Path(__file__).resolve()
        logger.info(f"Current file: {current_file}")
        logger.info(f"Current file parent: {current_file.parent}")

        root_path = Path(__file__).resolve().parent
        logger.info(f"Calculated project root: {root_path}")

        local_pdf_path = root_path / "assets" / self.file_name
        logger.info(f"Looking for PDF at: {local_pdf_path}")

        remote_pdf_path = f"/sdcard/Download/{self.file_name}"

        if not local_pdf_path.exists():
            logger.error(f"PDF file not found: {local_pdf_path}")
            return False

        result = controller.push_file(str(local_pdf_path), remote_pdf_path)

        if not result.success:
            logger.error(f"Failed to push PDF file to emulator: {result.error}")
            return False

        controller.refresh_media_scan(remote_pdf_path)

        self.relevant_information = "Kevin's email can be found in his resume."

        logger.info("Successfully initialized task with resume file")
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """
        Check if task is successful - Email should be sent to Kevin (kevin.zhang@example.com) with content:
        "Your interview is scheduled for tomorrow morning at 10:30 AM."

        Uses get_sent_email_info to check the sent email.
        """
        self._check_is_initialized()

        email = get_sent_email_info()

        if email is None:
            logger.info("No email found")
            return 0.0, "no email found"

        # Check recipient
        if email["to"].lower() != self.correct_recipient.lower():
            logger.info(f"Email sent to wrong recipient: {email['to']}")
            return 0.0, "email sent to wrong recipient"

        # Check if email body contains the expected message
        email_body = email.get("body", "")
        if self.expected_message_partial.lower() not in email_body.lower():
            logger.info("Email body does not contain expected message")
            return 0.0, "email body does not contain expected message"

        logger.info(f"Successfully found email to {self.correct_recipient} with correct content")
        return 1.0, "success"
