"""Adjust the toots on Mastodon."""

import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonAdjustTootsTask(BaseTask):
    goal = "On Mastodon, remove all bookmarks and add them as favorites, and boost all of them."
    task_tags = {"lang-en"}
    EXPECTED_USERNAME = "test"
    EXPECTED_FAVORITE_AND_BOOST_TOOTS = {
        115348102480027134,
        115410818912936581,
        115410836820181445,
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
        - all expected status ids are removed from bookmarks
        - all expected status ids are added as favorites
        - all expected status ids are boosted (reblogged) - verified by checking latest toots
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()
        time.sleep(1)  # wait for operations to complete

        # 1. Check that bookmarks are removed
        bookmarks = mastodon.get_bookmarks_by_username(self.EXPECTED_USERNAME)
        if bookmarks:
            bookmark_status_ids = {bookmark.get("status_id") for bookmark in bookmarks}
            # Check if any expected status ids are still in bookmarks
            still_bookmarked = self.EXPECTED_FAVORITE_AND_BOOST_TOOTS & bookmark_status_ids
            if still_bookmarked:
                return 0.0, (
                    f"Expected status ids are still in bookmarks. "
                    f"Still bookmarked: {still_bookmarked}"
                )

        # 2. Check that all expected status ids are added as favorites
        favorites = mastodon.get_favorites_by_username(self.EXPECTED_USERNAME)
        if not favorites:
            return 0.0, f"No favorites found for user '{self.EXPECTED_USERNAME}'"

        favorited_status_ids = {favorite.get("status_id") for favorite in favorites}
        if not favorited_status_ids:
            return 0.0, f"No favorited status ids found for user '{self.EXPECTED_USERNAME}'"

        missing_favorites = self.EXPECTED_FAVORITE_AND_BOOST_TOOTS - favorited_status_ids
        if missing_favorites:
            return 0.0, (
                f"Not all expected toots are favorited. "
                f"Expected: {self.EXPECTED_FAVORITE_AND_BOOST_TOOTS}, "
                f"Missing: {missing_favorites}, "
                f"Found: {favorited_status_ids}"
            )

        # 3. Check that all expected status ids are boosted (reblogged)
        # Get latest toots (at least as many as expected toots)
        num_expected = len(self.EXPECTED_FAVORITE_AND_BOOST_TOOTS)
        toots = mastodon.get_latest_toots_by_username(
            self.EXPECTED_USERNAME, limit=num_expected * 2
        )
        if not toots:
            return 0.0, f"No toots found for user '{self.EXPECTED_USERNAME}'"

        # Extract reblog_of_id from latest toots (filter out None values)
        reblogged_status_ids = {
            toot.get("reblog_of_id") for toot in toots if toot.get("reblog_of_id") is not None
        }

        # Check if all expected status ids are in the reblogged list
        missing_reblogs = self.EXPECTED_FAVORITE_AND_BOOST_TOOTS - reblogged_status_ids
        if missing_reblogs:
            return 0.0, (
                f"Not all expected toots are boosted (reblogged). "
                f"Expected: {self.EXPECTED_FAVORITE_AND_BOOST_TOOTS}, "
                f"Missing: {missing_reblogs}, "
                f"Found reblogged: {reblogged_status_ids}"
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
