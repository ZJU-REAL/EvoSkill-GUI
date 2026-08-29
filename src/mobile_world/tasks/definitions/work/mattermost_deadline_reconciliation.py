"""Cross-platform deadline reconciliation task - verify deadlines mentioned in chat have calendar events."""

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
    """Compute dynamic dates based on current date."""
    today = datetime.now().date()
    # Start from next Monday
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    base_date = today + timedelta(days=days_until_monday)

    return {
        # Deadlines: day 3, 8, 13, 18 from base
        "deadline_1": (base_date + timedelta(days=3)).strftime("%Y-%m-%d"),
        "deadline_2": (base_date + timedelta(days=8)).strftime("%Y-%m-%d"),
        "deadline_3": (base_date + timedelta(days=13)).strftime("%Y-%m-%d"),
        "deadline_4": (base_date + timedelta(days=18)).strftime("%Y-%m-%d"),
        # Calendar events: matches deadline_1, matches deadline_2 (within ±2 days), untracked
        "calendar_1": (base_date + timedelta(days=3)).strftime("%Y-%m-%d"),  # exact match
        "calendar_2": (base_date + timedelta(days=7)).strftime(
            "%Y-%m-%d"
        ),  # within ±2 of deadline_2
        "calendar_untracked": (base_date + timedelta(days=10)).strftime("%Y-%m-%d"),  # no match
        # Range for calendar query
        "range_start": base_date.strftime("%Y-%m-%d"),
        "range_end": (base_date + timedelta(days=30)).strftime("%Y-%m-%d"),
    }


class MattermostDeadlineReconciliationTask(BaseTask):
    """Cross-platform deadline reconciliation - verify chat deadlines have matching calendar events."""

    task_tags = {"lang-en"}
    goal = (
        "I suspect there's a discrepancy between what was discussed and what got documented. "
        "Please verify by checking the project-updates channel on Mattermost for any messages "
        "mentioning 'deadline' or 'milestone'. For each deadline mentioned, check if there's a "
        "corresponding calendar event within ±2 days of the mentioned date. "
        "Generate a reconciliation report showing: "
        "Deadlines with matching calendar events (PASS), "
        "Deadlines WITHOUT calendar events (- Missing), "
        "Calendar events not mentioned in chat (📅 Untracked). "
        "Email this report to dylan@gmail.com with subject 'Deadline Audit Report'. "
        "For each missing calendar event, create it with title '[AUTO] {deadline description}' "
        "and post confirmation in the project-updates channel listing the created event titles."
    )
    snapshot_tag = "init_state"

    MATCHED_DEADLINES = ["API Documentation Review", "Frontend MVP Launch"]
    MISSING_DEADLINES = ["Security Audit Completion", "Beta Testing Phase Start"]
    UNTRACKED_EVENTS = ["Team Building Event"]

    # Expected auto-created event titles for missing deadlines
    AUTO_EVENT_TITLES = [
        "[AUTO] Security Audit Completion",
        "[AUTO] Beta Testing Phase Start",
    ]

    EMAIL_ADDRESS = "dylan@gmail.com"
    EMAIL_SUBJECT = "Deadline Audit Report"
    CHANNEL_NAME = "project-updates"

    def __init__(self):
        super().__init__()
        self._dates = _compute_dates()

    app_names = {"Mattermost", "Calendar", "Mail"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        # Start mattermost backend
        mattermost.start_mattermost_backend()
        time.sleep(5)

        dates = self._dates

        # Create the project-updates channel and add messages with deadlines
        cli = mattermost.MattermostCLI()
        cli.login(mattermost.SAM_ACCOUNT["username"], mattermost.SAM_ACCOUNT["password"])

        cli.create_channel(
            team=mattermost.TEAM_NAME,
            channel_name=self.CHANNEL_NAME,
            display_name="Project Updates",
            private=False,
            purpose="Project milestone and deadline tracking",
            header="Track project progress here",
        )

        cli.add_users_to_channel(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            users=["sam.oneill@neuralforge.ai", "harry.kong@neuralforge.ai"],
        )

        # Post messages with deadline mentions (using dynamic dates)
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message="Hey team! Quick update on our project timeline.",
        )

        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message=(
                f"Reminder: The deadline for API Documentation Review is {dates['deadline_1']}. "
                "Please make sure all endpoints are documented by then."
            ),
        )

        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message=(
                f"Important milestone: Frontend MVP Launch scheduled for {dates['deadline_2']}. "
                "Let's make sure we're ready!"
            ),
        )

        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message=(
                f"Don't forget - Security Audit Completion deadline is {dates['deadline_3']}. "
                "We need all vulnerabilities addressed by then."
            ),
        )

        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message=(
                f"Final reminder: Beta Testing Phase Start milestone is {dates['deadline_4']}. "
                "@harry please coordinate with QA team."
            ),
        )

        # Create calendar events (some matching, some untracked)
        calendar_events = [
            # Matches "API Documentation Review" deadline (exact date)
            {"title": "API Docs Review Meeting", "date": dates["calendar_1"]},
            # Matches "Frontend MVP Launch" deadline (within ±2 days)
            {"title": "MVP Launch Party", "date": dates["calendar_2"]},
            # Does NOT match any deadline - untracked
            {"title": "Team Building Event", "date": dates["calendar_untracked"]},
        ]

        for event in calendar_events:
            insert_calendar_event(
                title=event["title"],
                start_time=f"{event['date']} 09:00:00",
                end_time=f"{event['date']} 10:00:00",
                description="Project event",
            )

        # Enable auto time sync for browser
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
            return (
                0.0,
                f"Email sent to wrong address: {email.get('to')} (expected: {self.EMAIL_ADDRESS})",
            )

        if self.EMAIL_SUBJECT.lower() not in email.get("subject", "").lower():
            return (
                0.0,
                f"Email subject incorrect: {email.get('subject')} (expected to contain: {self.EMAIL_SUBJECT})",
            )

        email_body = email.get("body", "").lower()

        # Check 2: Email mentions matched deadlines with PASS
        for deadline in self.MATCHED_DEADLINES:
            if deadline.lower() not in email_body:
                return 0.0, f"Matched deadline '{deadline}' not mentioned in email"

        # Check 3: Email mentions missing deadlines with
        for deadline in self.MISSING_DEADLINES:
            if deadline.lower() not in email_body:
                return 0.0, f"Missing deadline '{deadline}' not mentioned in email"

        # Check 4: Email mentions untracked events with 📅
        for event in self.UNTRACKED_EVENTS:
            if event.lower() not in email_body:
                return 0.0, f"Untracked event '{event}' not mentioned in email"

        # Check 5: Calendar events created for missing deadlines within ±2 days of actual deadline
        dates = self._dates
        # Map missing deadlines to their expected dates
        missing_deadline_dates = {
            "Security Audit Completion": dates["deadline_3"],
            "Beta Testing Phase Start": dates["deadline_4"],
        }

        for deadline, deadline_date in missing_deadline_dates.items():
            # Calculate ±2 day range for this specific deadline
            deadline_dt = datetime.strptime(deadline_date, "%Y-%m-%d")
            range_start = (deadline_dt - timedelta(days=2)).strftime("%Y-%m-%d")
            range_end = (deadline_dt + timedelta(days=2)).strftime("%Y-%m-%d")

            events = get_calendar_events(time_range=[range_start, range_end], format_timestamp=True)
            event_titles = [e["title"].lower() for e in events]

            # Check if [AUTO] event was created within ±2 days of the deadline
            auto_event_found = any(
                "[auto]" in title and deadline.lower() in title for title in event_titles
            )
            if not auto_event_found:
                return (
                    0.0,
                    f"Auto calendar event for '{deadline}' not created within ±2 days of {deadline_date}",
                )

        # Check 6: Confirmation posted in channel with event titles
        channel_info = mattermost.get_channel_info(channel_name=self.CHANNEL_NAME)
        messages = mattermost.get_latest_messages()[:10]
        channel_messages = [m for m in messages if m[5] == channel_info[0]]

        # Check if harry posted confirmation containing the auto-created event titles
        confirmation_found = False
        for msg in channel_messages:
            msg_content = msg[8]
            if msg[4] == mattermost.HARRY_ID:
                # Check if message contains the expected auto event titles
                titles_found = all(
                    title.lower() in msg_content.lower() for title in self.AUTO_EVENT_TITLES
                )
                if titles_found:
                    confirmation_found = True
                    break

        if not confirmation_found:
            return (
                0.0,
                f"No confirmation message with event titles {self.AUTO_EVENT_TITLES} posted in channel",
            )

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        mattermost.stop_mattermost_backend()
        return True
