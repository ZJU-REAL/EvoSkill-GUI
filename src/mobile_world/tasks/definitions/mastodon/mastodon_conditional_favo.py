"""Conditional favorite toots on Mastodon."""

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonConditionalFavoTask(BaseTask):
    goal = "favorite all toots tagged “#dogs” on Mastodon, but do not add them to my favorite list if they are already in my favorite list or bookmark list."

    task_tags = {"lang-en"}

    EXPECTED_USERNAME = "test"
    EXPECTED_FAVORITE_TOOTS = {
        115410810887077411,
        115410813905484454,
    }

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
        - all expected toots are favorited
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()

        # Check favorites
        favorites = mastodon.get_favorites_by_username(self.EXPECTED_USERNAME)
        if not favorites:
            return 0.0, f"No favorites found for user '{self.EXPECTED_USERNAME}'"

        favorited_toot_ids = {favorite.get("status_id") for favorite in favorites}
        if not favorited_toot_ids:
            return 0.0, f"No favorited toots found for user '{self.EXPECTED_USERNAME}'"

        if not set(self.EXPECTED_FAVORITE_TOOTS).issubset(set(favorited_toot_ids)):
            missing = self.EXPECTED_FAVORITE_TOOTS - favorited_toot_ids
            return (
                0.0,
                f"Not all expected toots are favorited. Expected: {self.EXPECTED_FAVORITE_TOOTS}, Missing: {missing}",
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
