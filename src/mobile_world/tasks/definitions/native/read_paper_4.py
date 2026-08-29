import time
from pathlib import Path

from loguru import logger

from mobile_world.runtime.app_helpers.system import reset_chrome
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class ReadQwen3PaperTask4(BaseTask):
    """Read the Qwen3-Omini paper and answer a question about Vision encoder size."""

    goal = "Read the downloaded Qwen3-Omni paper and tell me the size of Vision encoder in Qwen3-Omni-30B-A3B model. Please provide only the numeric value in millions of parameters."

    # The correct answer for validation
    CORRECT_ANSWERS = [540, 543]
    PDF_FILENAME = "qwen3-omni.pdf"

    task_tags = {"lang-en"}

    app_names = {"Docreader", "Files"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize task by pushing the Qwen3 PDF to the device."""
        try:
            # Reset Chrome first
            reset_chrome(controller)

            # Get path to the PDF in assets directory
            root_path = Path(__file__).resolve().parent
            local_pdf_path = root_path / "assets" / self.PDF_FILENAME

            logger.info(f"Looking for PDF at: {local_pdf_path}")

            # Check if PDF exists
            if not local_pdf_path.exists():
                logger.error(f"PDF file not found: {local_pdf_path}")
                return False

            # Define remote path on device (in Download directory for easy access)
            remote_pdf_path = f"/sdcard/Download/{self.PDF_FILENAME}"

            logger.info(f"Pushing PDF: {self.PDF_FILENAME} to {remote_pdf_path}")

            # Push the PDF to device
            result = controller.push_file(str(local_pdf_path), remote_pdf_path)

            if not result.success:
                logger.error(f"Failed to push PDF to device: {result.error}")
                return False

            # Wait a moment for file to be written
            time.sleep(0.5)

            # Trigger media scanner to make the PDF visible in file managers
            logger.info(f"Triggering media scan for {self.PDF_FILENAME}")
            controller.refresh_media_scan(remote_pdf_path)

            # Store the remote path for potential cleanup
            self._remote_pdf_path = remote_pdf_path

            logger.info("Successfully pushed PDF to device")
            return True

        except Exception as e:
            logger.error(f"Initialize task failed: {e}")
            return False

    def is_successful(self, controller: AndroidController) -> tuple[float, str]:
        """Check if the user provided the correct answer (540)."""
        self._check_is_initialized()

        answer = controller.interaction_cache

        logger.info(f"User answer: {answer}")

        try:
            # Try to parse as float to handle decimal answers
            answer_float = float(answer)
        except (ValueError, TypeError):
            logger.warning(f"Could not parse answer as number: {answer}")
            return 0.0, f"could not parse answer as number: {answer}"

        if answer_float in self.CORRECT_ANSWERS:
            return 1.0, "success"
        else:
            return 0.0, f"incorrect. Expected: {self.CORRECT_ANSWERS}, Got: {answer_float}"
