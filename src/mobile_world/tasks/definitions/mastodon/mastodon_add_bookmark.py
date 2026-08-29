"""Add some bookmark on Mastodon."""

import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonAddBookmarkTask(BaseTask):
    goal = "In Mastodon, add all posts of user kitty that have #cats tag to bookmarks."

    EXPECTED_USERNAME = "test"
    EXPECTED_STATUS_ID = {115359670141158913, 115342692663348018}

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
        - bookmarks for user 'test' contains all expected status ids
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()
        time.sleep(1)

        bookmarks = mastodon.get_bookmarks_by_username(self.EXPECTED_USERNAME)

        if bookmarks is None:
            return 0.0, f"Bookmarks for user '{self.EXPECTED_USERNAME}' is empty"
        else:
            bookmark_status_ids = {bookmark.get("status_id") for bookmark in bookmarks}
            if not self.EXPECTED_STATUS_ID.issubset(bookmark_status_ids):
                return (
                    0.0,
                    f"Expected status id {self.EXPECTED_STATUS_ID} not found in bookmarks for user '{self.EXPECTED_USERNAME}'",
                )

        return 1.0

    def tear_down(self, controller: AndroidController):
        super().tear_down(controller)
        try:
            mastodon.stop_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to stop Mastodon backend: {e}")
            return False
        return True
