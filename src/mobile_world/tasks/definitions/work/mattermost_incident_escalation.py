"""Incident escalation task - monitor support tickets and escalate critical issues."""

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


class MattermostIncidentEscalationTask(BaseTask):
    """Monitor support channel for critical tickets and perform escalation procedures."""

    task_tags = {"lang-en"}
    goal = (
        "Monitor the 'support-tickets' channel for CRITICAL incidents. "
        "If a critical ticket is found:\n"
        "1. Create a dedicated channel named 'incident-<ticket_id>' (e.g., incident-ticket-123).\n"
        "2. Add user 'sam.oneill@neuralforge.ai' to this new channel.\n"
        "3. Email 'cto@company.com' with subject 'CRITICAL INCIDENT: <ticket_id>' and the issue description.\n"
        "4. Schedule a 'Discussion on <ticket_id>' meeting for tomorrow at 09:00 AM in the calendar."
    )
    snapshot_tag = "init_state"

    EMAIL_ADDRESS = "cto@company.com"
    SUPPORT_CHANNEL = "support-tickets"
    CRITICAL_TICKET_ID = "TICKET-500"

    def __init__(self):
        super().__init__()
        self._tomorrow = (datetime.now().date() + timedelta(days=1)).strftime("%Y-%m-%d")

    app_names = {"Mattermost", "Calendar", "Mail"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        mattermost.start_mattermost_backend()
        time.sleep(5)

        cli = mattermost.MattermostCLI()
        cli.login(USERS["alex"], DEFAULT_PASSWORD)

        # Create support channel
        cli.create_channel(
            team=mattermost.TEAM_NAME,
            channel_name=self.SUPPORT_CHANNEL,
            display_name="Support Tickets",
            private=False,
        )
        cli.add_users_to_channel(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            users=["harry.kong@neuralforge.ai", USERS["sofia"], USERS["mike"], USERS["sam"]],
        )

        # Wave 1: Early morning tickets from Alex
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            message="TICKET-490 [Low]: Footer links not aligned on Safari.",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            message="TICKET-491 [Low]: Tooltip text truncated on hover.",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            message="Good morning team! Please prioritize TICKET-491 if you have time.",
        )

        # Wave 2: Sofia joins with more tickets
        cli.logout()
        cli.login(USERS["sofia"], DEFAULT_PASSWORD)
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            message="TICKET-492 [Medium]: Export CSV missing headers.",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            message="TICKET-493 [High]: Password reset email delayed by 10+ minutes.",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            message="@alex Can you check TICKET-493? Users are complaining.",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            message="TICKET-494 [Low]: Favicon not showing on Firefox.",
        )

        # Wave 3: Mike with mixed priority
        cli.logout()
        cli.login(USERS["mike"], DEFAULT_PASSWORD)
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            message="TICKET-495 [Medium]: Search autocomplete not working.",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            message="I'll take TICKET-493, looks like an SMTP config issue.",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            message="TICKET-496 [High]: User profile images not loading.",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            message="TICKET-497 [Low]: Typo in Terms of Service page.",
        )

        # Wave 4: More discussion and tickets from Alex
        cli.logout()
        cli.login(USERS["alex"], DEFAULT_PASSWORD)
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            message="Thanks @mike! Let me know if you need help with TICKET-493.",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            message="TICKET-498 [Medium]: Dashboard charts not rendering on IE11.",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            message="Note: We're dropping IE11 support next quarter anyway.",
        )

        # Wave 5: Sofia with more noise
        cli.logout()
        cli.login(USERS["sofia"], DEFAULT_PASSWORD)
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            message="TICKET-499 [Low]: Mobile menu animation stutters.",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            message="Reminder: Weekly support review meeting at 3pm today.",
        )

        # CRITICAL TICKET buried in the middle of conversation
        cli.logout()
        cli.login(USERS["mike"], DEFAULT_PASSWORD)
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            message=(
                f"{self.CRITICAL_TICKET_ID} [CRITICAL]: Database connection timeout. "
                "All systems down. Immediate attention required."
            ),
        )

        # Wave 6: Immediate follow-up noise to bury the critical ticket
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            message="TICKET-501 [Low]: Newsletter signup confirmation unclear.",
        )

        cli.logout()
        cli.login(USERS["alex"], DEFAULT_PASSWORD)
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            message="TICKET-502 [Medium]: API rate limiting too aggressive.",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            message="Just merged fix for TICKET-491, please verify.",
        )

        cli.logout()
        cli.login(USERS["sofia"], DEFAULT_PASSWORD)
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            message="TICKET-503 [Low]: Date picker shows wrong timezone.",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            message="@alex Verified TICKET-491, looks good!",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            message="TICKET-504 [Medium]: Notification badge count off by one.",
        )

        # Wave 7: More end-of-day chatter
        cli.logout()
        cli.login(USERS["mike"], DEFAULT_PASSWORD)
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            message="TICKET-505 [Low]: Help docs link returns 404.",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            message="EOD update: TICKET-493 fixed, was a misconfigured SMTP relay.",
        )

        cli.logout()
        cli.login(USERS["alex"], DEFAULT_PASSWORD)
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            message="Great work everyone! See you at the 3pm review.",
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.SUPPORT_CHANNEL,
            message="TICKET-506 [Low]: Cookie consent banner overlaps on mobile.",
        )

        if not time_sync_to_now():
            return False

        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()
        assert mattermost.is_mattermost_healthy()

        expected_channel = f"incident-{self.CRITICAL_TICKET_ID}".lower()

        # Check 1: Channel created
        channel_info = mattermost.get_channel_info(channel_name=expected_channel)
        if not channel_info:
            return 0.0, f"Incident channel '{expected_channel}' not found"

        # Check 2: Sam added to channel
        channel_id = channel_info[0]
        sam_id = mattermost.get_user_id_by_email(USERS["sam"])

        if sam_id is None:
            return 0.0, "Could not find Sam's user ID"

        if not mattermost.is_user_in_channel(sam_id, channel_id):
            return 0.0, "Sam not added to incident channel"

        # Check 3: Email sent
        email = get_sent_email_info()
        if email is None:
            return 0.0, "No escalation email sent"

        if email.get("to", "").lower() != self.EMAIL_ADDRESS.lower():
            return 0.0, f"Email sent to wrong address: {email.get('to')}"

        if self.CRITICAL_TICKET_ID not in email.get("subject", ""):
            return 0.0, f"Ticket ID not in email subject: {email.get('subject')}"

        if (
            "timeout" not in email.get("body", "").lower()
            or "database" not in email.get("body", "").lower()
        ):
            return 0.0, "Description not in email body"

        # Check 4: Calendar event
        events = get_calendar_events(
            time_range=[self._tomorrow, self._tomorrow], format_timestamp=True
        )
        post_mortem_found = False
        for event in events:
            title = event["title"].lower()
            if "discussion" in title and self.CRITICAL_TICKET_ID.lower() in title:
                post_mortem_found = True
                break

        if not post_mortem_found:
            return 0.0, "Post-mortem meeting not found in calendar for tomorrow"

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        mattermost.stop_mattermost_backend()
        return True
