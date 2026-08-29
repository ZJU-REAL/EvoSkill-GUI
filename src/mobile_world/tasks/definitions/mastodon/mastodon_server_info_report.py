"""owner get server info report - count untackled reports and send email"""

import re
import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonServerInfoReportTask(BaseTask):
    goal = (
        "switch to owner account in mastodon, then go to account backend to "
        'find the number of reports not tackled yet, and send the number as an email content in the format: "Recent reports: xxx" '
        "to owner@mastodon_example.com by email, the number should be in Arabic numerals."
    )
    task_tags = {"lang-en"}

    EXPECTED_RECIPIENT = "owner@mastodon_example.com"
    EXPECTED_EMAIL_FORMAT_PREFIX = "Recent reports:"

    app_names = {"Mastodon", "Mail"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        try:
            mastodon.start_mastodon_backend()
            return True
        except Exception as e:
            logger.error(f"Failed to start Mastodon backend: {e}")
            return False

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()
        time.sleep(1)

        # Get all reports from the database
        all_reports = mastodon.get_all_reports_info()
        if all_reports is None:
            return 0.0, "Failed to get reports info from database"

        # Count reports where action_taken_by_account_id is null (not tackled yet)
        untackled_count = sum(
            1 for report in all_reports if report.get("action_taken_by_account_id") is None
        )

        logger.info(f"Found {untackled_count} untackled reports")

        # Check if email was sent
        email = get_sent_email_info()
        if email is None:
            return 0.0, "No email found"

        # Check recipient
        email_to = email.get("to", "").strip()
        if email_to.lower() != self.EXPECTED_RECIPIENT.lower():
            return (
                0.0,
                f"Email sent to wrong recipient. Expected: {self.EXPECTED_RECIPIENT}, Got: {email_to}",
            )

        # Check email body content
        email_body = email.get("body", "").strip()
        logger.info(f"Email body: {email_body}")

        # Check if the email body contains the expected format
        if self.EXPECTED_EMAIL_FORMAT_PREFIX.lower() not in email_body.lower():
            return (
                0.0,
                f"Email body does not contain expected format prefix '{self.EXPECTED_EMAIL_FORMAT_PREFIX}'. Actual: {email_body}",
            )

        # Extract the number from the email body
        # Look for pattern like "Recent reports: 123" or "Recent reports:123"
        pattern = rf"{re.escape(self.EXPECTED_EMAIL_FORMAT_PREFIX)}\s*(\d+)"
        match = re.search(pattern, email_body, re.IGNORECASE)

        if not match:
            return (
                0.0,
                f"Could not find number in email body with expected format. Actual: {email_body}",
            )

        email_number_str = match.group(1)
        try:
            email_number = int(email_number_str)
        except ValueError:
            return 0.0, f"Number in email is not a valid integer. Got: {email_number_str}"

        # Verify the number matches the actual count
        if email_number != untackled_count:
            return (
                0.0,
                f"Report count mismatch. Expected: {untackled_count}, Got in email: {email_number}",
            )

        logger.info(f"Successfully verified email with correct report count: {untackled_count}")
        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        try:
            mastodon.stop_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to stop Mastodon backend: {e}")
            return False
        return True
