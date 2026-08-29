"""Post a new content on Mastodon."""

import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonNewPostTask(BaseTask):
    goal = "Open Mastodon app and post a new toot with the content 'Hello from AI agent!'"

    EXPECTED_CONTENT = "Hello from AI agent!"
    EXPECTED_USERNAME = "test"

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
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()
        time.sleep(1)

        toots = mastodon.get_latest_toots_by_username(self.EXPECTED_USERNAME, limit=1)
        if not toots:
            return 0.0, f"No toots found for user: {self.EXPECTED_USERNAME}"

        # get the latest toot
        toot = toots[0]
        text = toot["text"]

        if self.EXPECTED_CONTENT not in text:
            return 0.0, f"Expected content not found in the latest toot: {self.EXPECTED_CONTENT}"

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        try:
            mastodon.stop_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to stop Mastodon backend: {e}")
            return False
        return True
