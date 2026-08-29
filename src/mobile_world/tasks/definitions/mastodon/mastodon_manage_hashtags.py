"""Manage hashtags on Mastodon."""

import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonManageHashtagsTask(BaseTask):
    goal = "In Mastodon, unfollow the hashtags I followed before related to animals."

    EXPECTED_USERNAME = "test"
    EXPECTED_NO_FOLLOWED_HASHTAGS = ["dogs", "cats"]

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
        - no followed hashtags are found in the hashtags
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()
        time.sleep(1)

        hashtags = mastodon.get_hashtags_by_username(self.EXPECTED_USERNAME)
        if not hashtags:
            return 0.0, f"No hashtags found for user {self.EXPECTED_USERNAME}"

        followed_hashtags = [hashtag.get("tag_name") for hashtag in hashtags]
        # check
        for hashtag in self.EXPECTED_NO_FOLLOWED_HASHTAGS:
            if hashtag in followed_hashtags:
                return (
                    0.0,
                    f"Expected no followed hashtags {hashtag} found in followed hashtags {followed_hashtags}",
                )

        return 1.0

    def tear_down_hook(self, controller: AndroidController) -> bool:
        super().tear_down_hook(controller)
        try:
            mastodon.stop_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to stop Mastodon backend: {e}")
            return False
        return True
