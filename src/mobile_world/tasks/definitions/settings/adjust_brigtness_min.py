"""Adjust screen brightness task implementation."""

from loguru import logger

from mobile_world.runtime.app_helpers.system import (
    get_screen_brightness,
)
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class AdjustBrightnessMinimumTask(BaseTask):
    """Adjust screen brightness to minimum level task."""

    goal = "Set the brightness to the minimum level."
    min_brightness = 1

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
        """Check if task is successful - brightness should be at minimum level."""
        self._check_is_initialized()

        current_brightness = get_screen_brightness(controller)
        logger.info(f"Current brightness: {current_brightness}")

        # Check if brightness is at minimum
        brightness_at_min = current_brightness <= self.min_brightness
        if brightness_at_min:
            logger.info(
                f"- Brightness is at minimum level ({current_brightness}/{self.min_brightness}) - task successful"
            )
            return 1.0, "Success"
        else:
            logger.info(
                f"- Brightness not at minimum (current: {current_brightness}/{self.min_brightness}) - task failed"
            )
            return (
                0.0,
                f"Brightness is not at minimum level, current: {current_brightness}/{self.min_brightness}",
            )
