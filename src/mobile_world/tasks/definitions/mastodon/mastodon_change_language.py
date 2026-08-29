"""Change language on Mastodon."""

import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonChangeLanguageTask(BaseTask):
    goal = "In Mastodon, set the language of the account to Chinese Simplified."

    EXPECTED_USERNAME = "test"
    EXPECTED_LANGUAGE = "zh-CN"  # Chinese Simplified

    task_tags = {"lang-en"}

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
        - language is changed
        - language is the expected language
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()
        time.sleep(1)  # wait for the language to be changed

        user_info = mastodon.get_user_info(self.EXPECTED_USERNAME)
        if not user_info:
            return 0.0, f"User info not found for user: {self.EXPECTED_USERNAME}"

        actual_language = user_info.get("locale")
        if actual_language != self.EXPECTED_LANGUAGE:
            return (
                0.0,
                f"User language mismatch: actual_language={actual_language} != expected_language={self.EXPECTED_LANGUAGE}",
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
