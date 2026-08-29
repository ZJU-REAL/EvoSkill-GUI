from typing import Any

from loguru import logger

from mobile_world.runtime.app_helpers.mall import (
    MallConfig,
    clear_callback_files,
    clear_config,
    set_config,
)
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class CheckCartPriceTask(BaseTask):
    """Check the total price of the three most expensive items in the shopping cart."""

    goal = "Find the three most expensive items in the TaoDian app shopping cart and calculate their total price. Respond only with an integer representing the total price, with no other text."

    CORRECT_ANSWER = 13186

    CONFIG = MallConfig(showSplashAd=True, requireLogin=False)

    task_tags = {"lang-en"}

    app_names = {
        "Taodian",
    }

    @classmethod
    def generate_random_params(cls) -> dict[str, Any]:
        return {}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        set_config(self.CONFIG)
        return True

    def is_successful(self, controller: AndroidController) -> tuple[float, str]:
        """
        Check if the user provided the correct answer.

        The agent must respond with exactly "10000" (the correct total price)
        No other text should be included in the response.
        """
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

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        clear_config()
        clear_callback_files(controller.device)
        return True
