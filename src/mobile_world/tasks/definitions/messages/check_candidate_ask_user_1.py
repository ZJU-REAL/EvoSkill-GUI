"""Send interview invitation task implementation."""

from pathlib import Path

from loguru import logger

from mobile_world.runtime.app_helpers.system import check_sms_via_adb
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class CheckCandidateAskUserTask1(BaseTask):
    task_tags = {"agent-user-interaction", "lang-en"}

    goal = (
        "Find Kevin's resume and check whether his skills in database matches my job requirements. "
        "If yes, send a text message to HR: 'please kickoff the interview for Kevin.' "
        "If no, send a text message to HR: 'please reject the application for Kevin.'"
    )
    hr_name = "Mia Scott"
    hr_phone_number = "14058298746"
    expected_message_partial = "please kickoff the interview for Kevin"
    job_requirements = "Someone who is good at MongoDB or Redis."

    app_names = {"Messages", "Files"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize the messages task by resetting the Messages app to clean state."""

        self.relevant_information = (
            f"The HR name is {self.hr_name}. Her phone number can be found in the contacts app. "
            f"The job requirements are: {self.job_requirements}"
        )

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

    def is_successful(self, controller: AndroidController) -> tuple[float, str]:
        """
        Check if task is successful - SMS should be sent to HR with content containing:
        "please kickoff the interview for Kevin"

        Uses ADB to check the SMS database directly.
        """
        self._check_is_initialized()

        # Check if SMS with expected content was sent to the correct phone number
        result = check_sms_via_adb(
            controller,
            phone_number=self.hr_phone_number,
            content=self.expected_message_partial,
        )

        if result:
            logger.info(f"Successfully found SMS to {self.hr_phone_number} with correct content")
            return 1.0, "success"
        else:
            logger.info(f"SMS to {self.hr_phone_number} with correct content not found")
            return 0.0, f"SMS to {self.hr_phone_number} with correct content not found"
