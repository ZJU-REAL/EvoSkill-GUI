"""Remove a bookmark on Mastodon."""

import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonRemoveBookmarkTask(BaseTask):
    goal = "In Mastodon, remove the posts with #pets tag from bookmarks on my account."

    EXPECTED_USERNAME = "test"
    EXPECTED_STATUS_ID = {115410836820181445, 115410818912936581}

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
        Check:
        - The bookmark was removed for the expected username
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()
        time.sleep(1)

        # Check if the bookmark was removed
        bookmarks = mastodon.get_bookmarks_by_username(self.EXPECTED_USERNAME)
        if not bookmarks:
            return 0.0, f"No bookmarks found for user '{self.EXPECTED_USERNAME}'"

        bookmark_status_ids = {bookmark.get("status_id") for bookmark in bookmarks}
        if self.EXPECTED_STATUS_ID & bookmark_status_ids:
            return (
                0.0,
                f"Expected status id {self.EXPECTED_STATUS_ID} found in bookmarks for user '{self.EXPECTED_USERNAME}'",
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
