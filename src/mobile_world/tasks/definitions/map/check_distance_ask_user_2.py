import re

from loguru import logger

from mobile_world.runtime.app_helpers.system import enable_auto_time_sync, reset_maps
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class CheckDistanceAskUserTask2(BaseTask):
    """Use Google Maps to check distance from Beijing to user's hometown."""

    task_tags = {"agent-user-interaction", "lang-en"}
    goal = "I want to drive to Tianjin, China from my hometown. Please check the driving distance in kilometers. Reponse only one integer number. No other text."

    # Will be set during initialization
    start_location = "Jinan, Shandong, China"
    end_location = "Tianjin"
    correct_answer = "331"  # Distance from Beijing to Hangzhou in km
    distance_tolerance = 100  # Accept answers within ±100 km

    app_names = {
        "Maps",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        try:
            reset_maps(controller)
            self.relevant_information = f"My hometown is {self.start_location}. I want to drive to {self.end_location}. You need to use Google Maps to check the distance."
            return True
        except Exception as e:
            logger.error(f"Initialize Google Maps task failed: {e}")
            return False

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """
        Check if task is successful by verifying the distance answer.
        The answer should be a number (integer) representing the distance in km.
        The distance should be within ±100 km of the correct distance.
        """
        self._check_is_initialized()

        # The agent should have written its final answer to interaction_cache
        answer = (controller.interaction_cache or "").strip()
        logger.info(f"Agent answer: {answer}")

        if not answer:
            logger.warning("No answer provided")
            return 0.0, "no answer provided"

        try:
            # Extract all numbers from the answer
            numbers = re.findall(r"\d+", answer)

            if not numbers:
                logger.warning(f"No number found in answer: {answer}")
                return 0.0, "no number found"

            # Use the first number found
            agent_distance = int(numbers[0])
            expected_distance = int(self.correct_answer)

            logger.info(f"Agent distance: {agent_distance} km")
            logger.info(f"Expected distance: {expected_distance} km")

            # Calculate the difference
            difference = abs(agent_distance - expected_distance)
            logger.info(f"Difference: {difference} km")

            # Check if within tolerance (±100 km)
            if difference <= self.distance_tolerance:
                logger.info(
                    f"- Distance is within {self.distance_tolerance} km tolerance. Score: 1.0"
                )
                return 1.0, "success"
            else:
                logger.warning(
                    f"- Distance difference ({difference} km) exceeds tolerance ({self.distance_tolerance} km). Score: 0.0"
                )
                return 0.0, "distance difference exceeds tolerance"

        except Exception as e:
            logger.error(f"Error parsing answer: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return 0.0, "error parsing answer"
