import re

from loguru import logger

from mobile_world.runtime.app_helpers.system import enable_auto_time_sync, reset_maps
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class CheckDistanceAskUserTask1(BaseTask):
    """Use Google Maps to check distance from Beijing to user's hometown."""

    task_tags = {"agent-user-interaction", "lang-en"}
    goal = "What is the driving distance in kilometers from Beijing to my hometown? Response as the following format: beijing to xxx: distance km. xxx denotes the name of the hometown."

    # Will be set during initialization
    hometown = "Hangzhou, Zhejiang, China"
    correct_answer = "1272"  # Distance from Beijing to Hangzhou in km
    distance_tolerance = 100  # Accept answers within ±100 km

    app_names = {
        "Maps",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        try:
            reset_maps(controller)
            self.relevant_information = f"My hometown is {self.hometown}. You need to use Google Maps to check the distance from Beijing to my hometown."
            logger.info(f"Task initialized with hometown: {self.hometown}")

            return True
        except Exception as e:
            logger.error(f"Initialize Google Maps task failed: {e}")
            return False

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        answer = (controller.interaction_cache or "").strip()
        logger.info(f"Agent answer: {answer}")

        if not answer:
            logger.warning("No answer provided")
            return 0.0, "no answer provided"

        try:
            pattern = r"beijing\s+to\s+([^:]+):\s*([\d,]+)\s*km"
            match = re.search(pattern, answer, re.IGNORECASE)

            if not match:
                logger.warning(
                    f"Answer does not match expected format 'beijing to xxx: distance km': {answer}"
                )
                return 0.0, "answer format incorrect"

            hometown_in_answer = match.group(1).strip()
            agent_distance = int(match.group(2).replace(",", ""))
            expected_distance = int(self.correct_answer)

            logger.info(f"Extracted hometown: {hometown_in_answer}")
            logger.info(f"Agent distance: {agent_distance} km")
            logger.info(f"Expected distance: {expected_distance} km")

            difference = abs(agent_distance - expected_distance)
            logger.info(f"Difference: {difference} km")

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
