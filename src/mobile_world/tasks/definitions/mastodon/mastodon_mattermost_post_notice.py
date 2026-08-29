"""Post a notice from mattermost to mastodon."""

import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon, mattermost
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonMattermostPostNoticeTask(BaseTask):
    goal = (
        "Please help me sync the Security announcement from mike in the announcement channel on mattermost to mastodon, "
        "do not change the original content, the announcement is only visible to followers, and also @openCompany account."
    )

    EXPECTED_USERNAME = "test"
    EXPECTED_ANNOUNCEMENT = "Security: rotated API keys; check 1Password vault for updated entries."
    EXPECTED_VISIBILITY = 2  # 2: followers
    EXPECTED_MENTION_USERNAME = {"openCompany"}

    task_tags = {"lang-en"}

    app_names = {"Mastodon", "Mattermost"}

    def initialize_task_hook(self, controller: AndroidController) -> None:
        try:
            mastodon.start_mastodon_backend()
            mattermost.start_mattermost_backend()
            return True
        except Exception as e:
            logger.error(f"Failed to start Mastodon backend: {e}")
            return False

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """
        Check:
        - The toot text contains the expected announcement
        - The toot visibility is the expected visibility
        - The toot mentions the expected mention usernames
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()
        assert mattermost.is_mattermost_healthy()
        time.sleep(1)

        toots = mastodon.get_latest_toots_by_username(self.EXPECTED_USERNAME, limit=1)
        if not toots:
            return 0.0, f"No toots found for user: {self.EXPECTED_USERNAME}"

        toot = toots[0]
        # check content
        if self.EXPECTED_ANNOUNCEMENT not in toot.get("text"):
            return 0.0, f"Toot text mismatch: {toot.get('text')} != {self.EXPECTED_ANNOUNCEMENT}"

        # check visibility
        if toot.get("visibility") != self.EXPECTED_VISIBILITY:
            return (
                0.0,
                f"Toot visibility mismatch: {toot.get('visibility')} != {self.EXPECTED_VISIBILITY}",
            )

        # check mentions
        mentions = mastodon.get_mentions_by_status_id(status_id=toot.get("id"))
        if not mentions:
            return 0.0, f"No mentions found for status: {toot.get('id')}"
        mention_usernames = {mention.get("username") for mention in mentions}
        if mention_usernames != self.EXPECTED_MENTION_USERNAME:
            return (
                0.0,
                f"Mention usernames mismatch: {mention_usernames} != {self.EXPECTED_MENTION_USERNAME}",
            )

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        try:
            mastodon.stop_mastodon_backend()
            mattermost.stop_mattermost_backend()
        except Exception as e:
            logger.error(f"Failed to stop Mastodon and Mattermost backends: {e}")
            return False
        return True
