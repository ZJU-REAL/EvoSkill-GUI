"""Open flight mode task implementation."""

import time

from loguru import logger

from mobile_world.runtime.app_helpers.system import get_flight_mode_status, set_flight_mode
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class OpenFlightModeTask(BaseTask):
    """Open flight mode task."""

    goal = "Turn on device flight mode"

    task_tags = {"lang-en"}

    app_names = {
        "Settings",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize task - ensure flight mode is disabled so we have something to turn on."""
        # Check current flight mode status
        current_status = get_flight_mode_status(controller)
        logger.info(f"Current flight mode status: {'Enabled' if current_status else 'Disabled'}")

        # If flight mode is already enabled, we need to disable it first
        if current_status:
            logger.info(
                "Flight mode is currently enabled, disabling it to test the enable function..."
            )

            # Try to disable using original method
            set_flight_mode(controller, False)
            time.sleep(1)

            # Check if successfully disabled
            if get_flight_mode_status(controller):
                logger.info("Failed to disable flight mode")
                return False
            else:
                return True
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """Check if task is successful - flight mode should be enabled."""
        self._check_is_initialized()

        # First check if flight mode is enabled
        status = get_flight_mode_status(controller)
        logger.info(
            f"Starting to execute flight mode enable task, current status: {'Enabled' if status else 'Disabled'}"
        )

        # If flight mode is enabled, task is successful
        if status:
            logger.info("Flight mode is enabled, task successful")
            return 1.0, "Success"
        else:
            logger.info("Flight mode not enabled, task failed")
            return 0.0, "Flight mode is still disabled"
