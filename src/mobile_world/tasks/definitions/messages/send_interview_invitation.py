"""Send interview invitation task implementation."""

from pathlib import Path

from loguru import logger

from mobile_world.runtime.app_helpers.system import check_sms_via_adb
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SendInterviewInvitationTask(BaseTask):
    goal = (
        "Find Kevin's resume and send a text message to Kevin saying: "
        '"Your interview is scheduled for tomorrow morning at 10:30 AM."'
    )
    correct_phone_number = "15551234567"
    expected_message_partial = "Your interview is scheduled for tomorrow morning at 10:30 AM"

    task_tags = {"lang-en"}

    app_names = {"Messages", "Files"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize the messages task by resetting the Messages app to clean state."""
        current_file = Path(__file__).resolve()
        logger.info(f"Current file: {current_file}")
        logger.info(f"Current file parent: {current_file.parent}")

        root_path = Path(__file__).resolve().parent
        logger.info(f"Calculated project root: {root_path}")

        local_pdf_path = root_path / "assets" / "Kevin_CV.pdf"
        logger.info(f"Looking for PDF at: {local_pdf_path}")

        remote_pdf_path = "/sdcard/Download/Kevin_CV.pdf"

        if not local_pdf_path.exists():
            logger.error(f"PDF file not found: {local_pdf_path}")
            return False

        result = controller.push_file(str(local_pdf_path), remote_pdf_path)

        if not result.success:
            logger.error(f"Failed to push PDF file to emulator: {result.error}")
            return False

        controller.refresh_media_scan(remote_pdf_path)

        logger.info("Successfully initialized task with resume file")
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """
        Check if task is successful - SMS should be sent to Kevin (phone: 15551234567) with content:
        "Your interview is scheduled for tomorrow morning at 10:30 AM."

        Uses ADB to check the SMS database directly.
        """
        self._check_is_initialized()

        # Check if SMS with expected content was sent to the correct phone number
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
