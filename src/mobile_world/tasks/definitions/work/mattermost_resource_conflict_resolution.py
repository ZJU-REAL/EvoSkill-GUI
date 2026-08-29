"""Cross-platform resource conflict resolution - identify and resolve scheduling conflicts across requests."""

import re
import time
from datetime import datetime, timedelta

from mobile_world.runtime.app_helpers import mattermost
from mobile_world.runtime.app_helpers.fossify_calendar import (
    get_calendar_events,
    insert_calendar_event,
)
from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.app_helpers.mattermost import DEFAULT_PASSWORD, USERS
from mobile_world.runtime.app_helpers.system import time_sync_to_now
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


def _compute_dates() -> dict:
    """Compute dynamic dates for resource conflict task."""
    today = datetime.now().date()
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    base_date = today + timedelta(days=days_until_monday)

    return {
        "monday": base_date.strftime("%Y-%m-%d"),
        "tuesday": (base_date + timedelta(days=1)).strftime("%Y-%m-%d"),
        "wednesday": (base_date + timedelta(days=2)).strftime("%Y-%m-%d"),
        "thursday": (base_date + timedelta(days=3)).strftime("%Y-%m-%d"),
        "friday": (base_date + timedelta(days=4)).strftime("%Y-%m-%d"),
    }


class MattermostResourceConflictResolutionTask(BaseTask):
    """Identify resource booking conflicts from multiple channels and propose resolutions."""

    task_tags = {"lang-en"}
    goal = (
        "Check the 'resource-booking' channel on Mattermost for resource requests. "
        "Cross-reference each request with the calendar to determine status. "
        "Send a report email to 'facilities@company.com' with subject 'Resource Booking Conflicts' "
        "in the following format:\n"
        "APPROVED: <resource>, <resource>, ... (no calendar conflict)\n"
        "CONFLICT: <resource>, <resource>, ... (overlaps existing booking)\n"
        "For approved requests, add calendar events titled 'BOOKED: [resource] - [requester]'. "
        "For conflicts, DM the requester about the issue."
    )
    snapshot_tag = "init_state"

    # Expected categorization based on calendar state
    APPROVED_ITEMS = ["Conf Room B", "Conf Room C", "Projector", "Video Camera"]
    CONFLICT_ITEMS = ["Conf Room A"]

    EMAIL_ADDRESS = "facilities@company.com"
    EMAIL_SUBJECT = "Resource Booking Conflicts"
    CHANNEL_NAME = "resource-booking"

    def __init__(self):
        super().__init__()
        self._dates = _compute_dates()

    app_names = {"Mattermost", "Calendar", "Mail"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        mattermost.start_mattermost_backend()
        time.sleep(5)

        dates = self._dates
        cli = mattermost.MattermostCLI()
        cli.login(USERS["sam"], DEFAULT_PASSWORD)

        # Create resource-booking channel
        cli.create_channel(
            team=mattermost.TEAM_NAME,
            channel_name=self.CHANNEL_NAME,
            display_name="Resource Booking",
            private=False,
            purpose="Request meeting rooms and equipment",
        )

        # Add all users to the channel
        cli.add_users_to_channel(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            users=list(USERS.values()) + ["harry.kong@neuralforge.ai"],
        )

        # Sam requests Conf Room B (no conflict)
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message=(
                f"Resource Request:\n"
                f"- Resource: Conf Room B\n"
                f"- Date: {dates['wednesday']}\n"
                f"- Time: 14:00-15:00\n"
                f"- Purpose: Client Demo\n"
                f"- Requester: Sam"
            ),
        )

        # Alex requests Conf Room A (will conflict with existing booking)
        cli.logout()
        cli.login(USERS["alex"], DEFAULT_PASSWORD)

        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message=(
                f"Resource Request:\n"
                f"- Resource: Conf Room A\n"
                f"- Date: {dates['wednesday']}\n"
                f"- Time: 10:00-12:00\n"
                f"- Purpose: Sprint Planning\n"
                f"- Requester: Alex"
            ),
        )

        # Sofia requests Conf Room C (no conflict)
        cli.logout()
        cli.login(USERS["sofia"], DEFAULT_PASSWORD)

        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message=(
                f"Resource Request:\n"
                f"- Resource: Conf Room C\n"
                f"- Date: {dates['tuesday']}\n"
                f"- Time: 11:00-12:00\n"
                f"- Purpose: Design Review\n"
                f"- Requester: Sofia"
            ),
        )

        cli.logout()
        cli.login(USERS["mike"], DEFAULT_PASSWORD)

        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message=(
                f"Resource Request:\n"
                f"- Resource: Video Camera\n"
                f"- Date: {dates['friday']}\n"
                f"- Time: 13:00-15:00\n"
                f"- Purpose: Product Recording\n"
                f"- Requester: Mike"
            ),
        )

        cli.logout()
        cli.login(USERS["sam"], DEFAULT_PASSWORD)

        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message=(
                f"Resource Request:\n"
                f"- Resource: Projector\n"
                f"- Date: {dates['thursday']}\n"
                f"- Time: 09:00-10:00\n"
                f"- Purpose: Training Session\n"
                f"- Requester: Sam"
            ),
        )

        insert_calendar_event(
            title="Team Standup - Conf Room A",
            start_time=f"{dates['wednesday']} 10:00:00",
            end_time=f"{dates['wednesday']} 11:00:00",
            description="Daily standup meeting",
        )

        insert_calendar_event(
            title="Projector - Morning Presentation",
            start_time=f"{dates['thursday']} 08:00:00",
            end_time=f"{dates['thursday']} 08:30:00",
            description="Quick presentation",
        )

        if not time_sync_to_now():
            return False

        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()
        assert mattermost.is_mattermost_healthy()

        # Check 1: Email sent with correct recipient and subject
        email = get_sent_email_info()
        if email is None:
            return 0.0, "No email sent"

        if email.get("to", "").lower() != self.EMAIL_ADDRESS.lower():
            return 0.0, f"Email sent to wrong address: {email.get('to')}"

        if self.EMAIL_SUBJECT.lower() not in email.get("subject", "").lower():
            return 0.0, f"Email subject incorrect: {email.get('subject')}"

        # Check email body format with regex
        email_body = email.get("body", "").lower()

        approved_match = re.search(r"approved[^:]*:\s*([^\n]+)", email_body, re.IGNORECASE)
        conflict_match = re.search(r"conflict[^:]*:\s*([^\n]+)", email_body, re.IGNORECASE)

        if not approved_match:
            return 0.0, "APPROVED section not found in email"
        if not conflict_match:
            return 0.0, "CONFLICT section not found in email"

        approved_section = approved_match.group(1).lower()
        conflict_section = conflict_match.group(1).lower()

        # Verify items are in correct sections
        for item in self.APPROVED_ITEMS:
            if item.lower() not in approved_section:
                return 0.0, f"'{item}' not in APPROVED section"

        for item in self.CONFLICT_ITEMS:
            if item.lower() not in conflict_section:
                return 0.0, f"'{item}' not in CONFLICT section"

        # Check 2: Calendar events created for approved requests
        dates = self._dates
        events = get_calendar_events(
            time_range=[dates["monday"], dates["friday"]], format_timestamp=True
        )
        event_titles = [e["title"].lower() for e in events]

        for item in self.APPROVED_ITEMS:
            item_lower = item.lower()
            if not any("booked" in t and item_lower in t for t in event_titles):
                return 0.0, f"Calendar event for {item} not created"

        # Check 3: DM sent to Alex about Conf Room A conflict
        dm_messages = mattermost.get_latest_messages()[:20]
        alex_dm_found = False

        for msg in dm_messages:
            channel = mattermost.get_channel_info(msg[5])
            if channel is None:
                continue
            channel_name = channel[7] if len(channel) > 7 else ""
            if (
                mattermost.HARRY_ID in channel_name
                and mattermost.ALEX_ID in channel_name
                and msg[4] == mattermost.HARRY_ID
            ):
                alex_dm_found = True
                break

        if not alex_dm_found:
            return 0.0, "DM to Alex not sent"

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        mattermost.stop_mattermost_backend()
        return True
