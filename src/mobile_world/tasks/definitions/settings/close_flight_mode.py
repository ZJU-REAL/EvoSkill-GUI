"""Close flight mode task implementation."""

import time

from loguru import logger

from mobile_world.runtime.app_helpers.system import get_flight_mode_status, set_flight_mode
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class CloseFlightModeTask(BaseTask):
    """Close flight mode task."""

    goal = "Turn off device flight mode"

    task_tags = {"lang-en"}

    app_names = {
        "Settings",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize task - ensure flight mode is enabled so we have something to turn off."""
        # Check current flight mode status
        current_status = get_flight_mode_status(controller)
        logger.info(f"Current flight mode status: {'Enabled' if current_status else 'Disabled'}")

        # If flight mode is already disabled, we need to enable it first
        if not current_status:
            logger.info(
                "Flight mode is currently disabled, enabling it to test the disable function..."
            )

            # Try to enable using original method
            set_flight_mode(controller, True)
            time.sleep(1)

            # Check if successfully enabled, if not use backup method
            if not get_flight_mode_status(controller):
                logger.info("Failed to enable flight mode")
                return False
            else:
                return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """Check if task is successful - flight mode should be disabled."""
        self._check_is_initialized()

        # First check if flight mode is enabled
        status = get_flight_mode_status(controller)
        logger.info(
            f"Starting to execute flight mode disable task, current status: {'Enabled' if status else 'Disabled'}"
        )

        # If flight mode is already disabled, task is already completed
        if not status:
            logger.info("Flight mode is already disabled, task successful")
            return 1.0, "Success"
        else:
            logger.info("Flight mode not disabled, task failed")
            return 0.0, "Flight mode is still enabled"
