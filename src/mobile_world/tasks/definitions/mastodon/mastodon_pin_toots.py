"""Pin specific toots on Mastodon."""

import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonPinTootsTask(BaseTask):
    goal = "In Mastodon, pin the first post I published after creating the account to the top."

    EXPECTED_USERNAME = "test"
    EXPECTED_PINNED_TOOTS = {115338428767107750}

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
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()
        time.sleep(1)

        # Check if the toots are pinned
        pinned_toots = mastodon.get_pinned_toots_by_username(self.EXPECTED_USERNAME)

        if pinned_toots is None:
            return 0.0, f"Pinned toots for user '{self.EXPECTED_USERNAME}' is empty"
        else:
            pinned_toot_ids = {pinned_toot.get("status_id") for pinned_toot in pinned_toots}
            if not self.EXPECTED_PINNED_TOOTS.issubset(pinned_toot_ids):
                return (
                    0.0,
                    f"Expected toots {self.EXPECTED_PINNED_TOOTS} not found in pinned toots for user '{self.EXPECTED_USERNAME}'",
                )
            else:
                return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        try:
            mastodon.stop_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to stop Mastodon backend: {e}")
            return False
        return True
