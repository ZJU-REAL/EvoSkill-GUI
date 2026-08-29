"""Customer feedback analysis task - aggregate feedback and schedule review."""

import time
from datetime import datetime, timedelta

from mobile_world.runtime.app_helpers import mattermost
from mobile_world.runtime.app_helpers.fossify_calendar import (
    get_calendar_events,
)
from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.app_helpers.mattermost import DEFAULT_PASSWORD, USERS
from mobile_world.runtime.app_helpers.system import time_sync_to_now
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


def _get_next_friday() -> str:
    today = datetime.now().date()
    days_ahead = 4 - today.weekday()
    if days_ahead <= 0:  # Target day already happened this week
        days_ahead += 7
    return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")


class MattermostCustomerFeedbackAnalysisTask(BaseTask):
    """Aggregate negative feedback from Mattermost and report to Product team."""

    task_tags = {"lang-en"}
    goal = (
        "Analyze the 'customer-feedback' channel. Identify all NEGATIVE feedback items (complaints, bugs, issues). "
        "1. Send a summary email to 'product@company.com' with subject 'Weekly Negative Feedback Digest' listing these items.\n"
        "2. Schedule a meeting 'Feedback Review' for next Friday at 14:00 in the Calendar.\n"
        "3. Reply to the channel with 'Feedback logged and meeting scheduled'."
    )
    snapshot_tag = "init_state"

    CHANNEL_NAME = "customer-feedback"
    EMAIL_ADDRESS = "product@company.com"

    NEGATIVE_ITEMS = [
        "Login page crashes on Android 10",
        "Billing dashboard is confusing",
        "Cannot export reports to PDF",
    ]

    def __init__(self):
        super().__init__()
        self._friday = _get_next_friday()

    app_names = {"Mattermost", "Calendar", "Mail"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        mattermost.start_mattermost_backend()
        time.sleep(5)

        cli = mattermost.MattermostCLI()
        cli.login(USERS["sofia"], DEFAULT_PASSWORD)

        # Create channel
        cli.create_channel(
            team=mattermost.TEAM_NAME,
            channel_name=self.CHANNEL_NAME,
            display_name="Customer Feedback",
            private=False,
        )
        cli.add_users_to_channel(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            users=["harry.kong@neuralforge.ai", USERS["alex"], USERS["mike"]],
        )

        # Post feedback items - mix of positive and negative from different users
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message="NEW Feedback: Love the new dark mode! Great job team. ⭐⭐⭐⭐⭐",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message="NEW Feedback: The onboarding tutorial was very helpful.",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message=f"NEW Feedback: {self.NEGATIVE_ITEMS[0]}",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message="NEW Feedback: Fast checkout process, very impressed!",
        )

        cli.logout()
        cli.login(USERS["alex"], DEFAULT_PASSWORD)
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message="NEW Feedback: App loads quickly on my iPhone 15.",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message=f"NEW Feedback: {self.NEGATIVE_ITEMS[1]}",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message="NEW Feedback: Customer support was very responsive.",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message="NEW Feedback: The new search feature is amazing!",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message="NEW Feedback: Easy to navigate, intuitive design.",
        )

        cli.logout()
        cli.login(USERS["mike"], DEFAULT_PASSWORD)
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message="NEW Feedback: Love the notification customization options.",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message=f"NEW Feedback: {self.NEGATIVE_ITEMS[2]}",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message="NEW Feedback: The new font is very readable. Thanks!",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message="NEW Feedback: Syncs perfectly across all my devices.",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message="NEW Feedback: Great value for the price!",
        )

        cli.logout()
        cli.login(USERS["sofia"], DEFAULT_PASSWORD)
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message="NEW Feedback: The widget on home screen is super useful.",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message="NEW Feedback: Smooth animations throughout the app.",
        )

        if not time_sync_to_now():
            return False

        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()
        assert mattermost.is_mattermost_healthy()

        # Check 1: Email sent
        email = get_sent_email_info()
        if email is None:
            return 0.0, "No summary email sent"

        if email.get("to", "").lower() != self.EMAIL_ADDRESS.lower():
            return 0.0, f"Email sent to wrong address: {email.get('to')}"

        if "negative feedback digest" not in email.get("subject", "").lower():
            return 0.0, "Email subject incorrect"

        body = email.get("body", "").lower()
        for item in self.NEGATIVE_ITEMS:
            if item.lower() not in body:
                return 0.0, f"Feedback item '{item}' likely missing from email"

        # Check 2: Calendar Event
        events = get_calendar_events(time_range=[self._friday, self._friday], format_timestamp=True)
        review_found = False
        for event in events:
            if "feedback review" in event["title"].lower():
                review_found = True
                break

        if not review_found:
            return 0.0, f"Feedback Review meeting not found for {self._friday}"

        # Check 3: Reply in channel
        messages = mattermost.get_latest_messages()[:10]
        channel_info = mattermost.get_channel_info(channel_name=self.CHANNEL_NAME)
        if not channel_info:
            return 0.0, "Channel not found"

        channel_messages = [m for m in messages if m[5] == channel_info[0]]
        reply_found = False

        for msg in channel_messages:
            content = msg[8].lower()
            if msg[4] == mattermost.HARRY_ID:
                if "feedback logged" in content and "meeting scheduled" in content:
                    reply_found = True
                    break

        if not reply_found:
            return 0.0, "Confirmation reply not found in channel"

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        mattermost.stop_mattermost_backend()
        return True
