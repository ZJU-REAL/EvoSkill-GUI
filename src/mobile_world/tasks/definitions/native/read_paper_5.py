import time
from pathlib import Path

from loguru import logger

from mobile_world.runtime.app_helpers.system import reset_chrome
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class ReadQwen3PaperTask5(BaseTask):
    """Read the Qwen3-Omini paper and answer a question about Vision encoder size."""

    goal = (
        "Read the downloaded Qwen3 paper and tell me what kind of Austroasiatic language is supported by Qwen3 in Belebele Benchmark."
        "The answer should be a list of languages separated by comma."
        "No other text."
    )

    # The correct answer for validation
    CORRECT_ANSWER = "vie Latn,khm Khmr"
    PDF_FILENAMES = ["qwen3.pdf", "qwen3-omni.pdf"]

    task_tags = {"lang-en"}

    app_names = {"Docreader", "Files"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize task by pushing the Qwen3 PDFs to the device."""
        try:
            # Reset Chrome first
            reset_chrome(controller)

            # Get path to the PDF in assets directory
            root_path = Path(__file__).resolve().parent

            # Store remote paths for potential cleanup
            self._remote_pdf_paths = []

            # Push all PDF files
            for pdf_filename in self.PDF_FILENAMES:
                local_pdf_path = root_path / "assets" / pdf_filename

                logger.info(f"Looking for PDF at: {local_pdf_path}")

                # Check if PDF exists
                if not local_pdf_path.exists():
                    logger.error(f"PDF file not found: {local_pdf_path}")
                    return False

                # Define remote path on device (in Download directory for easy access)
                remote_pdf_path = f"/sdcard/Download/{pdf_filename}"

                logger.info(f"Pushing PDF: {pdf_filename} to {remote_pdf_path}")

                # Push the PDF to device
                result = controller.push_file(str(local_pdf_path), remote_pdf_path)

                if not result.success:
                    logger.error(f"Failed to push PDF to device: {result.error}")
                    return False

                # Wait a moment for file to be written
                time.sleep(0.5)

                # Trigger media scanner to make the PDF visible in file managers
                logger.info(f"Triggering media scan for {pdf_filename}")
                controller.refresh_media_scan(remote_pdf_path)

                # Store the remote path for potential cleanup
                self._remote_pdf_paths.append(remote_pdf_path)

            logger.info("Successfully pushed all PDFs to device")
            return True

        except Exception as e:
            logger.error(f"Initialize task failed: {e}")
            return False

    def is_successful(self, controller: AndroidController) -> tuple[float, str]:
        """Check if the user provided the correct answer (exact string match)."""
        self._check_is_initialized()

        answer = controller.interaction_cache

        logger.info(f"User answer: {answer}")

        # Normalize answer by stripping whitespace
        answer_normalized = answer.strip() if isinstance(answer, str) else str(answer)
        # Normalize spaces around commas (e.g., "vie Latn, khm Khmr" -> "vie Latn,khm Khmr")
        answer_normalized = ",".join(part.strip() for part in answer_normalized.split(","))

        if answer_normalized == self.CORRECT_ANSWER:
            return 1.0, "success"
        else:
            return 0.0, f"incorrect. Expected: {self.CORRECT_ANSWER}, Got: {answer_normalized}"
