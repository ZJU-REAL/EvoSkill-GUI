"Report harmful toot on Mastodon."

import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonReportTask(BaseTask):
    goal = (
        "Report Frank’s post about “the gas leak event” for spam, "
        "include the whole post content as the report reason, and block Frank after submitting the report."
    )

    EXPECTED_REPORTER_USERNAME = "test"
    EXPECTED_BLOCKED_USERNAME = "frank"
    EXPECTED_TOOT_ID = 115383686318250006
    EXPECTED_CATEGORY = 1000  # spam
    CATEGORY_MAP = {
        1: "dont like",  # this one not confirmed
        1000: "spam",
        1500: "illegal",
        0: "other",
    }

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
        - The report reason is the same as the toot content
        - The report category is the same as the expected category
        - The reporter is the same as the expected reporter
        - The informer has blocked the blocked user
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()
        time.sleep(2)  # wait for the report to be submitted

        report_info = mastodon.get_report_info(self.EXPECTED_TOOT_ID)
        if not report_info:
            return 0.0, f"The report info for toot {self.EXPECTED_TOOT_ID} is not found"

        toot_info = mastodon.get_toot_by_status_id(self.EXPECTED_TOOT_ID)
        if not toot_info:
            return 0.0, f"The toot {self.EXPECTED_TOOT_ID} is not found"

        # check if the report reason is content
        toot_content = toot_info.get("content")
        report_reason = report_info.get("comment")
        if toot_content != report_reason:
            return (
                0.0,
                f"The report reason is not the same as the toot content: toot_content={toot_content} != report_reason={report_reason}",
            )

        # check if the category is correct
        print(report_info.get("category"))
        if report_info.get("category") != self.EXPECTED_CATEGORY:
            return (
                0.0,
                f"The report category is not the same as the expected category: report_category={report_info.get('category')} != expected_category={self.EXPECTED_CATEGORY}",
            )

        # check if the reporter is correct
        if report_info.get("reporter_username") != self.EXPECTED_REPORTER_USERNAME:
            return (
                0.0,
                f"The reporter is not the same as the expected reporter: reporter_username={report_info.get('reporter_username')} != expected_reporter_username={self.EXPECTED_REPORTER_USERNAME}",
            )

        # check if the informer has blocked the blocked user
        blocked_users = mastodon.get_blocked_users(self.EXPECTED_REPORTER_USERNAME)
        if not blocked_users:
            return (
                0.0,
                f"The blocked users for reporter {self.EXPECTED_REPORTER_USERNAME} is not found",
            )

        blocked_users_set = set(user.get("blocked_username") for user in blocked_users)
        if self.EXPECTED_BLOCKED_USERNAME not in blocked_users_set:
            return (
                0.0,
                f"The informer {self.EXPECTED_REPORTER_USERNAME} has not blocked the blocked user {self.EXPECTED_BLOCKED_USERNAME}",
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
