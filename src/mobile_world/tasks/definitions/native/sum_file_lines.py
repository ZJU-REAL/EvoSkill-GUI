"""Count file lines task implementation - count lines in a file inside a zip archive."""

from loguru import logger

from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SumFileLinesTask(BaseTask):
    """Count file lines task - find and count lines in all files inside earliest July zip file."""

    goal = "Check the all files inside the earliest zip file from July in the Downloads directory and count how many lines it contains in total. Respond only with an integer representing the line count, with no other text."

    CORRECT_ANSWER = 29 + 39 + 45 + 47 + 23 + 44 + 32 + 10 + 44

    task_tags = {"lang-en"}

    app_names = {
        "Files",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize task - prepare zip files with test data."""
        return True

    def is_successful(self, controller: AndroidController) -> tuple[float, str]:
        """Check if the count file lines task was completed successfully."""
        self._check_is_initialized()

        answer = controller.interaction_cache

        logger.info(f"Agent answer: {answer}")

        if answer is None:
            return 0.0, "No answer provided"

        # Strip whitespace and convert to string for comparison
        answer_str = str(answer).strip()

        try:
            # Try to parse as integer to handle numeric answers
            answer_int = int(answer_str)
        except (ValueError, TypeError):
            logger.warning(f"Could not parse answer as integer: {answer_str}")
            return 0.0, f"Invalid answer format: {answer_str} (expected integer)"

        if answer_int == self.CORRECT_ANSWER:
            return 1.0, "Task completed successfully"
        else:
            return 0.0, f"Incorrect answer: {answer_int} (expected: {self.CORRECT_ANSWER})"
