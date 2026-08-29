"""Revise a poll on Mastodon."""

import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonRevisePollTask(BaseTask):
    goal = (
        "Edit my Mastodon poll about which country has the "
        "largest area by removing the option “USA” and changing the option “Brazil” to “Canada."
    )

    EXPECTED_USERNAME = "test"
    EXPECTED_TOOT_ID = 115433627788463436
    EXPECTED_POLL_OPTIONS_COUNT = 3
    EXPECTED_POLL_OPTIONS_NAMES = ["Russia", "China", "Canada"]

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
        - The poll options are the same as the expected poll options
        - The poll options count is the same as the expected poll options count
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()
        time.sleep(1)

        # Check if the poll revision meets all expected criteria
        toot = mastodon.get_toot_by_status_id(self.EXPECTED_TOOT_ID)
        if not toot:
            return 0.0, f"Toot with status ID {self.EXPECTED_TOOT_ID} not found"

        poll = mastodon.get_polls(toot["poll_id"])
        if not poll:
            return 0.0, f"Poll with status ID {toot['id']} not found"
        options = poll["options"]

        # Check 1: Number of options
        if not options or len(options) != self.EXPECTED_POLL_OPTIONS_COUNT:
            actual_count = len(options) if options else 0
            return (
                0.0,
                f"Expected {self.EXPECTED_POLL_OPTIONS_COUNT} options, but found {actual_count}",
            )

        # Check 2: Poll option names
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
                    f"Poll options do not match expected names. Expected: {self.EXPECTED_POLL_OPTIONS_NAMES}, Found: {options}",
                )

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        try:
            mastodon.stop_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to stop Mastodon backend: {e}")
        return True
