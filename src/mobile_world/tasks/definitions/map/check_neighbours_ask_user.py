from loguru import logger

from mobile_world.runtime.app_helpers.system import enable_auto_time_sync, reset_maps
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class GoogleMapsAlibabaSouthNeighborAskUserTask(BaseTask):
    """Use Google Maps to find the company directly south of Alibaba Hangzhou headquarters."""

    goal = (
        "Open Google Maps and find which company is directly south of my company. "
        "ONLY output the company name in English."
    )

    correct_answer = "netease"

    task_tags = {"lang-en", "agent-user-interaction"}

    app_names = {
        "Maps",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        self.relevant_information = (
            "My company is Alibaba Hangzhou headquarters in Binjiang District."
        )

        try:
            reset_maps(controller)
            return True
        except Exception as e:
            logger.error(f"Initialize Google Maps task failed: {e}")
            return False

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        answer = (controller.interaction_cache or "").strip()
        logger.info(f"answer: {answer}")

        if not answer:
            return 0.0, "no answer provided"

        normalized = answer.lower().strip()

        if self.correct_answer in normalized:
            return 1.0, "success"
        else:
            return 0.0, "incorrect answer, correct answer is {self.correct_answer}"
