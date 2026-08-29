"""Filter language on Mastodon."""

import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonFilterLanguageTask(BaseTask):
    goal = "On Mastodon, set up filters to only show posts in English, Japanese, and Chinese Simplified."

    task_tags = {"lang-en"}
    EXPECTED_USERNAME = "test"
    EXPECTED_LANGUAGE = {"en", "zh-CN", "ja"}

    app_names = {
        "Mastodon",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        try:
            mastodon.start_mastodon_backend()
            return True
        except Exception as e:
            logger.error(f"Failed to start Mastodon backend: {e}")
            return False

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """
        check:
        - chosen languages are the expected languages (English, Japanese, and Chinese Simplified)
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()
        time.sleep(1)  # wait for the language to be changed

        user_info = mastodon.get_user_info(self.EXPECTED_USERNAME)
        if not user_info:
            return 0.0, f"User info for {self.EXPECTED_USERNAME} not found"

        chosen_languages = set(user_info.get("chosen_languages"))
        if not chosen_languages:
            return 0.0, f"Chosen languages for user {self.EXPECTED_USERNAME} not found"

        if chosen_languages != self.EXPECTED_LANGUAGE:
            return (
                0.0,
                f"Chosen languages for user {self.EXPECTED_USERNAME} are not the expected language: {chosen_languages} != {self.EXPECTED_LANGUAGE}",
            )

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        try:
            mastodon.stop_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to stop Mastodon backend: {e}")
            return False
        return True
