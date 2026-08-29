"""Adjust screen brightness task implementation."""

from loguru import logger

from mobile_world.runtime.app_helpers.system import (
    get_screen_brightness,
)
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class AdjustBrightnessMaximumTask(BaseTask):
    """Adjust screen brightness to maximum level task."""

    goal = "Set the brightness to the maximum level."
    max_brightness = 255

    task_tags = {"lang-en"}

    def __init__(self):
        super().__init__()

    app_names = {
        "Settings",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize task - no need to initialize anything."""
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """Check if task is successful - brightness should be at maximum level."""
        self._check_is_initialized()

        current_brightness = get_screen_brightness(controller)
        logger.info(f"Current brightness: {current_brightness}")

        # Check if brightness is at maximum
        brightness_at_max = current_brightness >= self.max_brightness
        if brightness_at_max:
            logger.info(
                f"- Brightness is at maximum level ({current_brightness}/{self.max_brightness}) - task successful"
            )
            return 1.0, "Success"
        else:
            logger.info(
                f"- Brightness not at maximum (current: {current_brightness}/{self.max_brightness}) - task failed"
            )
            return (
                0.0,
                f"Brightness is not at maximum level, current: {current_brightness}/{self.max_brightness}",
            )
