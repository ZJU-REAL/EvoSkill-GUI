"""Add featured hashtags on Mastodon."""

import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonAddFeaturedHashtagsTask(BaseTask):
    goal = "On Mastodon, add some hashtags as my featured hashtags in my profile, add the hashtags: summerrain, nature, and photography."

    EXPECTED_HASHTAGS = {"summerrain", "nature", "photography"}
    EXPECTED_USERNAME = "test"
    task_tags = {"lang-en"}

    app_names = {
        "Mastodon",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        try:
            mastodon.start_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to start Mastodon backend: {e}")
            return False
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """
        check:
        - featured hashtags are the expected hashtags
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()
        time.sleep(1)

        featured_tags = mastodon.get_featured_tags_by_username(self.EXPECTED_USERNAME)
        if not featured_tags:
            return 0.0, f"Featured tags for user {self.EXPECTED_USERNAME} not found"

        featured_tags = set(tag["name"] for tag in featured_tags)
        if featured_tags != set(self.EXPECTED_HASHTAGS):
            return (
                0.0,
                f"Featured tags for user {self.EXPECTED_USERNAME} are not the expected hashtags: {featured_tags} != {self.EXPECTED_HASHTAGS}",
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
