"""unfollow a user on Mastodon."""

import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonUnfollowTask(BaseTask):
    goal = "manage my following list on Mastodon, only keep the latest three users, and unfollow all other users."

    task_tags = {"lang-en"}
    EXPECTED_USERNAME = "test"
    EXPECTED_KEEP_FOLLOWING_USERS = ["openCompany", "gourmet", "kitty"]

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
        time.sleep(1)  # wait for the following list to be updated

        following_users = mastodon.get_following_users(self.EXPECTED_USERNAME)
        if not following_users:
            return 0.0, f"No following users found for {self.EXPECTED_USERNAME}"

        target_usernames = [user.get("target_username") for user in following_users]
        target_usernames_set = set(target_usernames)
        expected_set = set(self.EXPECTED_KEEP_FOLLOWING_USERS)

        # Check if the following list contains exactly the expected users
        if target_usernames_set != expected_set:
            unexpected_users = target_usernames_set - expected_set
            missing_users = expected_set - target_usernames_set
            error_msg = "Following list mismatch. "
            if unexpected_users:
                error_msg += f"Unexpected users: {unexpected_users}. "
            if missing_users:
                error_msg += f"Missing users: {missing_users}."
            return 0.0, error_msg

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        try:
            mastodon.stop_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to stop Mastodon backend: {e}")
            return False
        return True
