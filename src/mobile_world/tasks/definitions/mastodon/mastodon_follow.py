"""Follow a user on Mastodon."""

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonFollowTask(BaseTask):
    goal = "Find Robert's nickname in Contacts, then search it on Mastodon, and follow him."

    EXPECTED_USERNAME = "test"
    EXPECTED_TARGET_USERNAME = "rainbow123"  # Robert

    task_tags = {"lang-en"}

    app_names = {"Mastodon", "Contacts"}

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

        following_users = mastodon.get_following_users(self.EXPECTED_USERNAME)
        if not following_users:
            return 0.0, f"No following users found for {self.EXPECTED_USERNAME}"

        target_usernames = [user.get("target_username") for user in following_users]
        if self.EXPECTED_TARGET_USERNAME not in target_usernames:
            return (
                0.0,
                f"Target username {self.EXPECTED_TARGET_USERNAME} not found in following users for {self.EXPECTED_USERNAME}",
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
