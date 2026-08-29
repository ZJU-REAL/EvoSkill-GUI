"""Shift coverage task - manage shift swap requests via Mattermost and Calendar."""

import time
from datetime import datetime, timedelta

from mobile_world.runtime.app_helpers import mattermost
from mobile_world.runtime.app_helpers.fossify_calendar import (
    insert_calendar_event,
)
from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.app_helpers.mattermost import DEFAULT_PASSWORD, USERS
from mobile_world.runtime.app_helpers.system import time_sync_to_now
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


def _compute_dates() -> dict:
    """Compute dynamic dates for the shift task."""
    today = datetime.now().date()
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7

    next_monday = today + timedelta(days=days_until_monday)
    next_wednesday = next_monday + timedelta(days=2)

    return {
        "monday": next_monday.strftime("%Y-%m-%d"),
        "wednesday": next_wednesday.strftime("%Y-%m-%d"),
    }


class MattermostShiftCoverageTask(BaseTask):
    """Handle shift swap requests by checking calendar for conflicts."""

    task_tags = {"lang-en"}
    goal = (
        "Review shift swap requests in 'shift-requests' channel. "
        "Check the Calendar for any conflicts on the requested dates. "
        "If there is a conflict (e.g. 'All Hands' or 'Training'), reply to the request in the channel with 'Denied: [Reason]'. "
        "If there is no conflict, forward the request via email to 'hr@company.com' with subject 'Shift Swap Request' "
        "and reply to the user 'Request escalated to HR'."
    )
    snapshot_tag = "init_state"

    CHANNEL_NAME = "shift-requests"
    EMAIL_ADDRESS = "hr@company.com"

    def __init__(self):
        super().__init__()
        self._dates = _compute_dates()

    app_names = {"Mattermost", "Calendar", "Mail"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        mattermost.start_mattermost_backend()
        time.sleep(5)

        cli = mattermost.MattermostCLI()
        cli.login(USERS["alex"], DEFAULT_PASSWORD)

        # Create channel
        cli.create_channel(
            team=mattermost.TEAM_NAME,
            channel_name=self.CHANNEL_NAME,
            display_name="Shift Requests",
            private=False,
        )
        cli.add_users_to_channel(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            users=["harry.kong@neuralforge.ai", USERS["sofia"]],
        )

        # Create Conflict Event on Monday
        insert_calendar_event(
            title="All Hands Meeting - Mandatory",
            start_time=f"{self._dates['monday']} 09:00:00",
            end_time=f"{self._dates['monday']} 17:00:00",
            description="Full team attendance required",
        )

        # Request 1: Monday (Conflict)
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message=f"Requesting shift swap for {self._dates['monday']}. Family emergency.",
        )

        # Switch user to Sofia for second request
        cli.logout()
        cli.login(USERS["sofia"], DEFAULT_PASSWORD)

        # Request 2: Wednesday (No Conflict)
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message=f"Can I swap my shift on {self._dates['wednesday']}? Doctor appointment.",
        )

        if not time_sync_to_now():
            return False

        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()
        assert mattermost.is_mattermost_healthy()

        # Check messages
        messages = mattermost.get_latest_messages()[:20]
        channel_info = mattermost.get_channel_info(channel_name=self.CHANNEL_NAME)

        channel_messages = [m for m in messages if m[5] == channel_info[0]]

        denied_found = False
        escalated_found = False

        alex_msg_id = None
        sofia_msg_id = None
        for msg in channel_messages:
            if "Family emergency" in msg[8]:
                alex_msg_id = msg[0]
            if "Doctor appointment" in msg[8]:
                sofia_msg_id = msg[0]

        for msg in channel_messages:
            content = msg[8].lower()
            if (
                msg[4] == mattermost.HARRY_ID and msg[6] == alex_msg_id and "denied" in content
            ):  # Harry is the agent
                denied_found = True
            if msg[4] == mattermost.HARRY_ID and msg[6] == sofia_msg_id and "escalated" in content:
                escalated_found = True

        if not denied_found:
            return 0.0, "Did not find denial reply in channel"
        if not escalated_found:
            return 0.0, "Did not find escalation reply in channel"

        email = get_sent_email_info()
        if email is None:
            return 0.0, "No escalation email sent"

        if email.get("to", "").lower() != self.EMAIL_ADDRESS.lower():
            return 0.0, f"Email sent to wrong address: {email.get('to')}"

        if "shift swap request" not in email.get("subject", "").lower():
            return 0.0, "Email subject incorrect"

        if self._dates["wednesday"] not in email.get("body", ""):
            return 0.0, "Wednesday date not mentioned in email body"

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        mattermost.stop_mattermost_backend()
        return True
