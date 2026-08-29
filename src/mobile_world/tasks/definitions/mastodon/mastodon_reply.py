"""Reply to a mentioned toot on Mastodon."""

import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonReplyTask(BaseTask):
    goal = "Reply to the toot of gourmet user about Greek food Moussaka, and the reply content should be 'Nice sharing, i love it'."

    EXPECTED_USERNAME = "test"
    EXPECTED_BEING_REPLIED_TOOT_ID = 115342681979737543
    EXPECTED_REPLY_CONTENT = "Nice sharing, i love it"

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
        - The reply was posted to the expected toot
        - The reply content is the expected content
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()
        time.sleep(2)  # wait for the reply to be posted

        toots = mastodon.get_latest_toots_by_username(self.EXPECTED_USERNAME, limit=1)
        if not toots:
            return 0.0, f"No toots found for user: {self.EXPECTED_USERNAME}"

        toot = toots[0]
        # check if the toot is a reply to the expected toot
        in_reply_to_id = toot.get("in_reply_to_id")
        if in_reply_to_id is None or in_reply_to_id != self.EXPECTED_BEING_REPLIED_TOOT_ID:
            return (
                0.0,
                f"In reply to ID mismatch: in_reply_to_id={in_reply_to_id} != expected_toot_id={self.EXPECTED_BEING_REPLIED_TOOT_ID}",
            )

        # check if the reply content is the expected content, case insensitive
        reply_content = toot.get("text")
        if self.EXPECTED_REPLY_CONTENT.lower() not in reply_content.lower():
            return (
                0.0,
                f"Reply content does not contain expected content: reply_content={reply_content} != expected_reply_content={self.EXPECTED_REPLY_CONTENT}",
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
