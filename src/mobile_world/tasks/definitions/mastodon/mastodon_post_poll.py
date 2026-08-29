"""Post a poll on Mastodon."""

import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonPostPollTask(BaseTask):
    goal = (
        "Search on Google for the '2025 Nobel Prize in Economics' and use the names of the winners "
        "as the poll options. Post a poll on Mastodon with the hashtag '#vote2025', allowing multiple "
        "selections and lasting for one week."
    )

    EXPECTED_USERNAME = "test"
    EXPECTED_POLL_TAG = ["vote2025"]  # caution! case-insensitive in the database
    EXPECTED_POLL_OPTIONS_COUNT = 3
    EXPECTED_POLL_EXPIRATION_DAYS = 7
    EXPECTED_MULTIPLE_VOTES = True  # True: multiple votes allowed, False: single vote only
    EXPECTED_POLL_OPTIONS_NAMES = ["Joel Mokyr", "Philippe Aghion", "Peter Howitt"]

    task_tags = {"lang-en"}

    app_names = {"Mastodon", "Chrome"}

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
        - The poll is posted successfully
        - The poll has the expected tags
        - The poll has the expected number of options
        - The poll allows multiple selections
        - The poll duration is expected
        - The poll option names are expected
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()
        time.sleep(1)

        toots = mastodon.get_latest_toots_by_username(self.EXPECTED_USERNAME, limit=1)
        if not toots:
            return 0.0, f"No toots found for user: {self.EXPECTED_USERNAME}"
        toot = toots[0]
        poll_id = toot["poll_id"]
        if not poll_id:
            return 0.0, f"No poll ID found for toot: {toot}"
        poll = mastodon.get_polls(poll_id)

        options = poll["options"]
        multiple = poll["multiple"]
        expires_at = poll["expires_at"]
        created_at = poll["created_at"]
        toot_id = toot["id"]
        tags = mastodon.get_toot_tags(toot_id)
        if not tags:
            return 0.0, f"No tags found for toot: {toot_id}"

        # Check 1: Poll tags contains expected tags
        tags_set = set(tag.lower() for tag in tags)
        expected_tags_set = set(tag.lower() for tag in self.EXPECTED_POLL_TAG)
        if tags_set != expected_tags_set:
            return 0.0, f"Wrong tags in the toot: {tags_set} != {expected_tags_set}"

        # Check 2: Number of options
        if not options or len(options) != self.EXPECTED_POLL_OPTIONS_COUNT:
            actual_count = len(options) if options else 0
            return (
                0.0,
                f"Expected {self.EXPECTED_POLL_OPTIONS_COUNT} options, but found {actual_count}",
            )

        # Check 3: Multiple selection allowed
        if multiple != self.EXPECTED_MULTIPLE_VOTES:
            return (
                0.0,
                f"Expected multiple={self.EXPECTED_MULTIPLE_VOTES}, but found multiple={multiple}",
            )

        # Check 4: Poll duration (expires_at should be approximately expected_days from created_at)
        created_dt = mastodon.parse_dt(created_at)
        expires_dt = mastodon.parse_dt(expires_at)

        if not created_dt or not expires_dt:
            return 0.0, "Could not parse poll timestamps for duration check"

        delta_days = (expires_dt.date() - created_dt.date()).days
        if delta_days != self.EXPECTED_POLL_EXPIRATION_DAYS:
            return (
                0.0,
                f"Expected poll duration of {self.EXPECTED_POLL_EXPIRATION_DAYS} days, but found {delta_days} days",
            )

        # Check 5: Poll option names
        if self.EXPECTED_POLL_OPTIONS_NAMES:
            if not options:
                return 0.0, "No poll options found to check names"
            else:
                # case-insensitive comparison
                expected_names_lower = {
                    name.lower().strip() for name in self.EXPECTED_POLL_OPTIONS_NAMES
                }
                actual_options_lower = {opt.lower().strip() for opt in options}

                if actual_options_lower != expected_names_lower:
                    return (
                        0.0,
                        f"Expected options: {expected_names_lower}, Actual options: {actual_options_lower}",
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
