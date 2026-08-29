"""Set up a new filter rule on Mastodon."""

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonNewFilterTask(BaseTask):
    goal = (
        "In Mastodon, add a new filter called “Anti-Spoiler-BCS”, "
        "use all the words from the text file named filter_BCS in the documents "
        "folder as blocked keywords, and set it to expire 5 days from today."
    )

    EXPECTED_TITLE = "Anti-Spoiler-BCS"
    EXPECTED_KEYWORDS = {
        "Better Call Saul",
        "saul goodman",
        "kim wexler",
        "season 6",
        "finale",
    }
    EXPECTED_USERNAME = "test"
    EXPECTED_REMAINING_DAYS = 5
    CASE_INSENSITIVE = True

    task_tags = {"lang-en"}

    app_names = {"Mastodon", "Files"}

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
        - The filter is added successfully
        - The filter keywords are the expected keywords
        - The filter expiry days are the expected expiry days
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()

        filters = mastodon.get_filters_by_username(self.EXPECTED_USERNAME)
        if not filters:
            return 0.0, f"No filters found for {self.EXPECTED_USERNAME}"

        filter_target = next(
            (filter for filter in filters if filter.get("phrase") == self.EXPECTED_TITLE), None
        )
        if not filter_target:
            return (
                0.0,
                f"Filter not found: phrase={self.EXPECTED_TITLE}, username={self.EXPECTED_USERNAME}",
            )

        # check keywords
        filter_keywords = filter_target.get("keywords")
        if not filter_keywords:
            return (
                0.0,
                f"No keywords found for filter: phrase={self.EXPECTED_TITLE}, username={self.EXPECTED_USERNAME}",
            )

        filter_keywords_set = {keyword.get("keyword") for keyword in filter_keywords}

        def _norm(s: str) -> str:
            s = (s or "").strip()
            return s.lower() if self.CASE_INSENSITIVE else s

        got_set = {_norm(k) for k in filter_keywords_set}
        exp_set = {_norm(k) for k in self.EXPECTED_KEYWORDS}

        if got_set != exp_set:
            return 0.0, f"Keyword mismatch. expected={sorted(exp_set)}, got={sorted(got_set)}"

        # check expiry
        expires_at = mastodon.parse_dt(filter_target.get("expires_at"))
        created_at = mastodon.parse_dt(filter_target.get("created_at"))
        if expires_at is None and created_at is None:
            return (
                0.0,
                f"Invalid expires_at and created_at in filter: phrase={self.EXPECTED_TITLE}, username={self.EXPECTED_USERNAME}",
            )
        elif expires_at is None:  # never expires
            if self.EXPECTED_REMAINING_DAYS is not None:
                return (
                    0.0,
                    f"Expiry days mismatch. expected={self.EXPECTED_REMAINING_DAYS}, got=never expires",
                )
        elif created_at is None:
            return (
                0.0,
                f"Invalid created_at in filter: phrase={self.EXPECTED_TITLE}, username={self.EXPECTED_USERNAME}",
            )
        else:
            delta_days = (expires_at.date() - created_at.date()).days
            if delta_days != self.EXPECTED_REMAINING_DAYS:
                return (
                    0.0,
                    f"Expiry days mismatch. expected={self.EXPECTED_REMAINING_DAYS}, got={delta_days}",
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
