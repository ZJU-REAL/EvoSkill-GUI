"""Cross-platform project status aggregation - collect updates from multiple channels and generate risk-assessed report."""

import re
import time
from datetime import datetime, timedelta

from mobile_world.runtime.app_helpers import mattermost
from mobile_world.runtime.app_helpers.fossify_calendar import (
    get_calendar_events,
    insert_calendar_event,
)
from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.app_helpers.system import time_sync_to_now
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


def _compute_dates() -> dict:
    """Compute dynamic dates for the status report task."""
    today = datetime.now().date()
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    base_date = today + timedelta(days=days_until_monday)

    return {
        "sprint_start": base_date.strftime("%Y-%m-%d"),
        "sprint_end": (base_date + timedelta(days=13)).strftime("%Y-%m-%d"),
        "milestone_1": (base_date + timedelta(days=4)).strftime("%Y-%m-%d"),  # On track
        "milestone_2": (base_date + timedelta(days=7)).strftime("%Y-%m-%d"),  # At risk
        "milestone_3": (base_date + timedelta(days=11)).strftime("%Y-%m-%d"),  # Blocked
        "review_date": (base_date + timedelta(days=6)).strftime("%Y-%m-%d"),
    }


class MattermostProjectStatusReportTask(BaseTask):
    """Aggregate status updates from multiple channels, assess risks, and generate comprehensive report."""

    task_tags = {"lang-en"}
    goal = (
        "I need a comprehensive project status report. Check these Mattermost channels: "
        "'backend-team', 'frontend-team', and 'qa-team' for status updates. "
        "For each team, identify items marked as 'blocked', 'at-risk', or 'on-track'. "
        "Cross-reference with calendar milestones to verify if timeline claims are accurate. "
        "Generate a risk matrix report in the following format: \n"
        "On Track (status=on-track AND milestone exists within 3 days): <item name>, <item name>, ... (and so on for all on-track items) \n"
        "At Risk (status=at-risk OR no milestone found): <item name>, <item name>, ... (and so on for all at-risk items) \n"
        "Blocked (explicitly marked blocked): <item name>, <item name>, ... (and so on for all blocked items) \n"
        "Email this report to 'pm@company.com' with subject 'Sprint Status Risk Matrix'. "
        "For any blocked items, create a calendar event titled '[ESCALATION] {item name}' "
        "on the next business day at 10:00-10:30. "
        "Post a summary in the 'project-sync' channel with the counts: X on-track, Y at-risk, Z blocked."
    )
    snapshot_tag = "init_state"

    # Expected categorization
    ON_TRACK_ITEMS = ["Authentication Module", "API Gateway Setup"]
    AT_RISK_ITEMS = ["Dashboard UI", "Performance Testing"]
    BLOCKED_ITEMS = ["Payment Integration", "Security Audit"]

    EMAIL_ADDRESS = "pm@company.com"
    EMAIL_SUBJECT = "Sprint Status Risk Matrix"
    SYNC_CHANNEL = "project-sync"

    def __init__(self):
        super().__init__()
        self._dates = _compute_dates()

    app_names = {"Mattermost", "Calendar", "Mail"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        mattermost.start_mattermost_backend()
        time.sleep(5)

        dates = self._dates
        cli = mattermost.MattermostCLI()
        cli.login(mattermost.SAM_ACCOUNT["username"], mattermost.SAM_ACCOUNT["password"])

        # Create team channels
        channels = [
            ("backend-team", "Backend Team"),
            ("frontend-team", "Frontend Team"),
            ("qa-team", "QA Team"),
            (self.SYNC_CHANNEL, "Project Sync"),
        ]

        for channel_name, display_name in channels:
            cli.create_channel(
                team=mattermost.TEAM_NAME,
                channel_name=channel_name,
                display_name=display_name,
                private=False,
            )
            cli.add_users_to_channel(
                team=mattermost.TEAM_NAME,
                channel=channel_name,
                users=["sam.oneill@neuralforge.ai", "harry.kong@neuralforge.ai"],
            )

        # Backend team updates - mix of statuses
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel="backend-team",
            message=(
                f"Status Update - Authentication Module: on-track\n"
                f"Expected completion: {dates['milestone_1']}\n"
                "All unit tests passing, ready for integration."
            ),
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel="backend-team",
            message=(
                "Status Update - Payment Integration: blocked\n"
                "Waiting on third-party API credentials from vendor.\n"
                "Cannot proceed until this is resolved."
            ),
        )

        # Frontend team updates
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel="frontend-team",
            message=(
                f"Status Update - Dashboard UI: at-risk\n"
                f"Original target: {dates['milestone_2']}\n"
                "Design changes requested, may need 2 extra days."
            ),
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel="frontend-team",
            message=(
                f"Status Update - API Gateway Setup: on-track\n"
                f"Completion target: {dates['milestone_1']}\n"
                "Routing configured, testing in progress."
            ),
        )

        # QA team updates
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel="qa-team",
            message=(
                "Status Update - Performance Testing: at-risk\n"
                "Load testing environment not yet provisioned.\n"
                "No calendar milestone assigned yet."
            ),
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel="qa-team",
            message=(
                "Status Update - Security Audit: blocked\n"
                "Dependency on Payment Integration completion.\n"
                "Cannot start until payment module is ready."
            ),
        )

        # Create calendar milestones for on-track items only
        insert_calendar_event(
            title="Authentication Module Complete",
            start_time=f"{dates['milestone_1']} 09:00:00",
            end_time=f"{dates['milestone_1']} 10:00:00",
            description="Backend authentication milestone",
        )
        insert_calendar_event(
            title="API Gateway Launch",
            start_time=f"{dates['milestone_1']} 14:00:00",
            end_time=f"{dates['milestone_1']} 15:00:00",
            description="Gateway setup completion",
        )

        if not time_sync_to_now():
            return False

        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()
        assert mattermost.is_mattermost_healthy()

        # Check 1: Email sent with correct subject
        email = get_sent_email_info()
        if email is None:
            return 0.0, "No email sent"

        if email.get("to", "").lower() != self.EMAIL_ADDRESS.lower():
            return 0.0, f"Email sent to wrong address: {email.get('to')}"

        if self.EMAIL_SUBJECT.lower() not in email.get("subject", "").lower():
            return 0.0, f"Email subject incorrect: {email.get('subject')}"

        email_body = email.get("body", "").lower()

        on_track_match = re.search(r"on[- ]?track[^:]*:\s*([^\n]+)", email_body, re.IGNORECASE)
        at_risk_match = re.search(r"at[- ]?risk[^:]*:\s*([^\n]+)", email_body, re.IGNORECASE)
        blocked_match = re.search(r"blocked[^:]*:\s*([^\n]+)", email_body, re.IGNORECASE)

        if not on_track_match:
            return 0.0, "On-track section not found in email"
        if not at_risk_match:
            return 0.0, "At-risk section not found in email"
        if not blocked_match:
            return 0.0, "Blocked section not found in email"

        on_track_section = on_track_match.group(1).lower()
        at_risk_section = at_risk_match.group(1).lower()
        blocked_section = blocked_match.group(1).lower()

        # Verify on-track items are in on-track section
        for item in self.ON_TRACK_ITEMS:
            if item.lower() not in on_track_section:
                return 0.0, f"On-track item '{item}' not in on-track section"

        # Verify at-risk items are in at-risk section
        for item in self.AT_RISK_ITEMS:
            if item.lower() not in at_risk_section:
                return 0.0, f"At-risk item '{item}' not in at-risk section"

        # Verify blocked items are in blocked section
        for item in self.BLOCKED_ITEMS:
            if item.lower() not in blocked_section:
                return 0.0, f"Blocked item '{item}' not in blocked section"

        today = datetime.now().date()
        next_bday = today + timedelta(days=1)
        while next_bday.weekday() >= 5:
            next_bday += timedelta(days=1)

        range_start = next_bday.strftime("%Y-%m-%d")
        range_end = (next_bday + timedelta(days=7)).strftime("%Y-%m-%d")

        events = get_calendar_events(time_range=[range_start, range_end], format_timestamp=True)
        event_titles = [e["title"].lower() for e in events]

        for blocked_item in self.BLOCKED_ITEMS:
            escalation_found = any(
                "[escalation]" in title and blocked_item.lower() in title for title in event_titles
            )
            if not escalation_found:
                return 0.0, f"Escalation event for '{blocked_item}' not created"

        channel_info = mattermost.get_channel_info(channel_name=self.SYNC_CHANNEL)

        messages = mattermost.get_latest_messages()[:10]
        channel_messages = [m for m in messages if m[5] == channel_info[0]]

        summary_found = False

        for msg in channel_messages:
            msg_content = msg[8].lower()
            if msg[4] == mattermost.HARRY_ID:
                if (
                    f"{len(self.ON_TRACK_ITEMS)} on-track, {len(self.AT_RISK_ITEMS)} at-risk, {len(self.BLOCKED_ITEMS)} blocked"
                    in msg_content
                ):
                    summary_found = True
                    break

        if not summary_found:
            return 0.0, "Summary with status counts not posted in project-sync channel"

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        mattermost.stop_mattermost_backend()
        return True
