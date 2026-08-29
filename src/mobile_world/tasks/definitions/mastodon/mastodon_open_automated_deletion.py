"""Open automated post deletions setting on Mastodon."""

import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonOpenAutomatedDeletionTask(BaseTask):
    goal = (
        "In Mastodon, enable automatically delete old posts, "
        "only set pinned posts as expected, and set the age threshold to 7 days, "
        "Keep posts with at least 20 favs or 20 reblogs."
    )

    EXPECTED_USERNAME = "test"
    EXPECTED_ENABLED = True
    EXPECTED_MIN_STATUS_AGE = 604800  # 7 days
    EXPECTED_KEEP_DIRECT = False
    EXPECTED_KEEP_PINNED = True
    EXPECTED_KEEP_POLLS = False
    EXPECTED_KEEP_MEDIA = False
    EXPECTED_KEEP_SELF_FAV = False
    EXPECTED_KEEP_SELF_BOOKMARK = False
    EXPECTED_MIN_FAVS = 20
    EXPECTED_MIN_REBLOGS = 20

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
        Check:
        - Enabled
        - Minimum status age (7 days)
        - Do not keep direct posts
        - Keep pinned posts
        - Do not keep polls
        - Do not keep media
        - Do not keep self fav
        - Do not keep self bookmark
        - Minimum number of favs (20)
        - Minimum number of reblogs (20)
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()
        time.sleep(1)

        automated_post_deletions_setting = mastodon.get_automated_post_deletions_setting(
            self.EXPECTED_USERNAME
        )
        if not automated_post_deletions_setting:
            return (
                0.0,
                f"No automated post deletions setting found for user: {self.EXPECTED_USERNAME}",
            )

        # check enabled
        enabled = automated_post_deletions_setting.get("enabled")
        if enabled != self.EXPECTED_ENABLED:
            return (
                0.0,
                f"Enabled mismatch: enabled={enabled} != expected_enabled={self.EXPECTED_ENABLED}",
            )

        # check expiration time
        min_status_age = automated_post_deletions_setting.get("min_status_age")
        if min_status_age != self.EXPECTED_MIN_STATUS_AGE:
            return (
                0.0,
                f"Min status age mismatch: min_status_age={min_status_age} != expected_min_status_age={self.EXPECTED_MIN_STATUS_AGE}",
            )

        # check toot types to be kept
        keep_direct = automated_post_deletions_setting.get("keep_direct")
        if keep_direct != self.EXPECTED_KEEP_DIRECT:
            return (
                0.0,
                f"Keep direct mismatch: keep_direct={keep_direct} != expected_keep_direct={self.EXPECTED_KEEP_DIRECT}",
            )

        keep_pinned = automated_post_deletions_setting.get("keep_pinned")
        if keep_pinned != self.EXPECTED_KEEP_PINNED:
            return (
                0.0,
                f"Keep pinned mismatch: keep_pinned={keep_pinned} != expected_keep_pinned={self.EXPECTED_KEEP_PINNED}",
            )

        keep_polls = automated_post_deletions_setting.get("keep_polls")
        if keep_polls != self.EXPECTED_KEEP_POLLS:
            return (
                0.0,
                f"Keep polls mismatch: keep_polls={keep_polls} != expected_keep_polls={self.EXPECTED_KEEP_POLLS}",
            )

        keep_media = automated_post_deletions_setting.get("keep_media")
        if keep_media != self.EXPECTED_KEEP_MEDIA:
            return (
                0.0,
                f"Keep media mismatch: keep_media={keep_media} != expected_keep_media={self.EXPECTED_KEEP_MEDIA}",
            )

        keep_self_fav = automated_post_deletions_setting.get("keep_self_fav")
        if keep_self_fav != self.EXPECTED_KEEP_SELF_FAV:
            return (
                0.0,
                f"Keep self fav mismatch: keep_self_fav={keep_self_fav} != expected_keep_self_fav={self.EXPECTED_KEEP_SELF_FAV}",
            )

        keep_self_bookmark = automated_post_deletions_setting.get("keep_self_bookmark")
        if keep_self_bookmark != self.EXPECTED_KEEP_SELF_BOOKMARK:
            return (
                0.0,
                f"Keep self bookmark mismatch: keep_self_bookmark={keep_self_bookmark} != expected_keep_self_bookmark={self.EXPECTED_KEEP_SELF_BOOKMARK}",
            )

        # check minimum number of favs and reblogs
        min_favs = automated_post_deletions_setting.get("min_favs")
        if min_favs != self.EXPECTED_MIN_FAVS:
            return (
                0.0,
                f"Min favs mismatch: min_favs={min_favs} != expected_min_favs={self.EXPECTED_MIN_FAVS}",
            )

        min_reblogs = automated_post_deletions_setting.get("min_reblogs")
        if min_reblogs != self.EXPECTED_MIN_REBLOGS:
            return (
                0.0,
                f"Min reblogs mismatch: min_reblogs={min_reblogs} != expected_min_reblogs={self.EXPECTED_MIN_REBLOGS}",
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
