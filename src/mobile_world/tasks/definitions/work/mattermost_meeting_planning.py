"""Calendar-aware meeting planning task with route constraints via Mattermost coordination."""

import re
import time
from datetime import datetime, timedelta

from mobile_world.runtime.app_helpers import mattermost
from mobile_world.runtime.app_helpers.fossify_calendar import (
    get_calendar_events,
    insert_calendar_event,
)
from mobile_world.runtime.app_helpers.system import time_sync_to_now
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


def _compute_meeting_dates() -> dict:
    """Compute dynamic dates for meeting planning based on current date."""
    today = datetime.now().date()
    # Start from next Monday
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    base_date = today + timedelta(days=days_until_monday)

    # Week days: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4
    monday = base_date
    tuesday = base_date + timedelta(days=1)
    wednesday = base_date + timedelta(days=2)
    thursday = base_date + timedelta(days=3)
    friday = base_date + timedelta(days=4)

    return {
        "week_start": monday.strftime("%Y-%m-%d"),
        "week_end": friday.strftime("%Y-%m-%d"),
        "monday": monday.strftime("%Y-%m-%d"),
        "tuesday": tuesday.strftime("%Y-%m-%d"),
        "wednesday": wednesday.strftime("%Y-%m-%d"),
        "thursday": thursday.strftime("%Y-%m-%d"),
        "friday": friday.strftime("%Y-%m-%d"),
        # Expected meeting date: Thursday 14:00-16:00
        "expected_date": thursday.strftime("%Y-%m-%d"),
    }


class MattermostMeetingPlanningTask(BaseTask):
    """Calendar-aware meeting planning - coordinate team schedules and find venue within walking distance."""

    task_tags = {"lang-en", "agent-mcp"}

    snapshot_tag = "init_state"

    # Expected venue and walking distance
    EXPECTED_VENUE = "杭州师范大学"
    EXPECTED_WALKING_DISTANCE = 1522  # meters
    DISTANCE_TOLERANCE = 300  # meters
    MAX_WALKING_TIME = 20  # minutes

    # Expected meeting time
    EXPECTED_START_HOUR = 14
    EXPECTED_END_HOUR = 16

    CHANNEL_NAME = "team-schedule"
    _dates = _compute_meeting_dates()

    goal = (
        "Our team (alex, sam, and I) need to schedule an offsite meeting next week. "
        "Check the team-schedule channel on Mattermost where alex and sam have posted their availability. "
        "Find a 2-hour overlapping free slot across all three people (my calendar is in the Calendar app). "
        "The meeting location should be reachable within 30 minutes walking from our office at "
        "'阿里巴巴西溪园区C区'. "
        "Evaluate these two venue options: "
        "1) '杭州师范大学' "
        "2) '浙江大学紫金港校区图书馆' "
        "Choose the venue that is reachable within 30 minutes walking. "
        "Create a calendar event named `Offsite Meeting` for the meeting at the first available slot. "
        "Post in the team-schedule channel announcing the meeting with: date, time, venue name, "
        "and estimated walking time. Use format: 'Meeting scheduled: [date] [time]-[end_time] at [venue], ~[X] min walk'. "
        "Send a separate private DM to alex with the walking distance in meters to the chosen venue."
    )

    app_names = {"Mattermost", "Calendar", "MCP-Amap", "Maps"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        # Start mattermost backend
        mattermost.start_mattermost_backend()
        time.sleep(5)

        dates = self._dates

        # Create the team-schedule channel
        cli = mattermost.MattermostCLI()
        cli.login(mattermost.SAM_ACCOUNT["username"], mattermost.SAM_ACCOUNT["password"])

        cli.create_channel(
            team=mattermost.TEAM_NAME,
            channel_name=self.CHANNEL_NAME,
            display_name="Team Schedule",
            private=False,
            purpose="Coordinate team schedules and meetings",
            header="Post your availability here",
        )

        cli.add_users_to_channel(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            users=[
                "sam.oneill@neuralforge.ai",
                "harry.kong@neuralforge.ai",
                "alex.rivera@neuralforge.ai",
            ],
        )

        # Sam posts availability (using dynamic dates)
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message=(
                f"Hey team! Here's my schedule for next week ({dates['monday']} to {dates['friday']}):\n"
                f"- Monday {dates['monday']}: Free all day\n"
                f"- Tuesday {dates['tuesday']}: Free all day\n"
                f"- Wednesday {dates['wednesday']}: Busy 09:00-13:00 (client call)\n"
                f"- Thursday {dates['thursday']}: Busy 10:00-14:00 (workshop)\n"
                f"- Friday {dates['friday']}: Free all day\n"
                "Let me know what works for the offsite!"
            ),
        )

        # Switch to Alex's account to post
        cli.logout()
        cli.login("alex.rivera@neuralforge.ai", "password")

        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message=(
                "Thanks Sam! My availability for next week:\n"
                f"- Monday {dates['monday']}: Busy 09:00-12:00 (team standup + reviews)\n"
                f"- Tuesday {dates['tuesday']}: Busy all day (offsite training)\n"
                f"- Wednesday {dates['wednesday']}: Busy 14:00-17:00 (sprint planning)\n"
                f"- Thursday {dates['thursday']}: Free all day\n"
                f"- Friday {dates['friday']}: Busy 09:00-11:00 (1:1s)\n"
                "Looking forward to the meeting!"
            ),
        )

        # Create Harry's calendar events (the user's own calendar) with dynamic dates
        # Monday: 9-11 meeting
        insert_calendar_event(
            title="Weekly Sync",
            start_time=f"{dates['monday']} 13:00:00",
            end_time=f"{dates['monday']} 18:00:00",
            description="Regular team sync",
        )

        # Tuesday: 15-17 meeting
        insert_calendar_event(
            title="Product Review",
            start_time=f"{dates['tuesday']} 15:00:00",
            end_time=f"{dates['tuesday']} 17:00:00",
            description="Q4 product review",
        )

        # Thursday: 9-12 meeting
        insert_calendar_event(
            title="Architecture Discussion",
            start_time=f"{dates['thursday']} 09:00:00",
            end_time=f"{dates['thursday']} 12:00:00",
            description="System architecture review",
        )

        # Enable auto time sync for browser/MCP
        if not time_sync_to_now():
            return False

        return True

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()
        assert mattermost.is_mattermost_healthy()

        dates = self._dates

        # Check 1: Calendar event created for the meeting with correct date and time
        events = get_calendar_events(
            time_range=[dates["week_start"], dates["week_end"]], format_timestamp=True
        )

        # Find the offsite meeting event
        offsite_event = None
        for event in events:
            title_lower = event["title"].lower()
            if (
                "offsite" in title_lower
                or "team meeting" in title_lower
                or "meeting" in title_lower
            ):
                # Exclude pre-existing events
                if title_lower not in ["weekly sync", "product review", "architecture discussion"]:
                    offsite_event = event
                    break

        if offsite_event is None:
            return 0.0, "No offsite meeting calendar event created"

        # Verify the event is on the expected date (Thursday) and time (14:00-16:00)
        event_start = offsite_event["start_ts"]  # format: "YYYY-MM-DD HH:MM:SS"
        event_end = offsite_event["end_ts"]

        expected_date = dates["expected_date"]
        if expected_date not in event_start:
            return 0.0, f"Meeting not scheduled on expected date {expected_date}, got {event_start}"

        # Check start time is 14:00
        start_hour_match = re.search(r"(\d{2}):(\d{2}):\d{2}$", event_start)
        if start_hour_match:
            start_hour = int(start_hour_match.group(1))
            if start_hour != self.EXPECTED_START_HOUR:
                return (
                    0.0,
                    f"Meeting start time incorrect: expected {self.EXPECTED_START_HOUR}:00, got {start_hour}:00",
                )

        # Check end time is 16:00
        end_hour_match = re.search(r"(\d{2}):(\d{2}):\d{2}$", event_end)
        if end_hour_match:
            end_hour = int(end_hour_match.group(1))
            if end_hour != self.EXPECTED_END_HOUR:
                return (
                    0.0,
                    f"Meeting end time incorrect: expected {self.EXPECTED_END_HOUR}:00, got {end_hour}:00",
                )

        # Check 2: Announcement posted in channel
        channel_info = mattermost.get_channel_info(channel_name=self.CHANNEL_NAME)
        if channel_info is None:
            return 0.0, "Team schedule channel not found"

        messages = mattermost.get_latest_messages()[:10]
        channel_messages = [m for m in messages if m[5] == channel_info[0]]

        announcement_found = False
        announcement_has_venue = False
        walking_time_estimated = False

        for msg in channel_messages:
            msg_content = msg[8].lower()
            if msg[4] == mattermost.HARRY_ID:
                if "meeting" in msg_content and (
                    "scheduled" in msg_content or expected_date in msg[8]
                ):
                    announcement_found = True
                    if "杭州师范大学" in msg[8] or "师范" in msg[8]:
                        announcement_has_venue = True
                    walking_time_matches = re.findall(r"(\d+) min walk", msg[8])
                    if walking_time_matches:
                        walking_time = float(walking_time_matches[0])
                        if walking_time <= self.MAX_WALKING_TIME:
                            walking_time_estimated = True
                            break
        if not announcement_found:
            return 0.0, "No meeting announcement posted in team-schedule channel"

        if not announcement_has_venue:
            return 0.0, "Meeting announcement missing venue name"

        if not walking_time_estimated:
            return 0.0, "Meeting announcement missing walking time estimate"

        # Check 3: Private DM sent to Alex with walking distance (use regex to extract and validate)
        dm_messages = mattermost.get_latest_messages()[:5]
        alex_dm_found = False

        for msg in dm_messages:
            channel = mattermost.get_channel_info(msg[5])
            if channel is None:
                continue
            # Check if it's a DM channel between Harry and Alex
            channel_name = channel[7] if len(channel) > 7 else ""
            if (
                mattermost.HARRY_ID in channel_name
                and mattermost.ALEX_ID in channel_name
                and msg[4] == mattermost.HARRY_ID
            ):
                msg_content = msg[8]
                distance_matches = re.findall(r"(\d+(?:\.\d+)?)\s*(?:meters?|m|米)?", msg_content)
                for match in distance_matches:
                    try:
                        distance = float(match)
                        if (
                            abs(distance - self.EXPECTED_WALKING_DISTANCE)
                            <= self.DISTANCE_TOLERANCE
                        ):
                            alex_dm_found = True
                            break
                    except ValueError:
                        continue
                if alex_dm_found:
                    break

        if not alex_dm_found:
            return (
                0.0,
                f"No private DM sent to Alex with valid walking distance "
                f"(expected ~{self.EXPECTED_WALKING_DISTANCE}m ± {self.DISTANCE_TOLERANCE}m)",
            )

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        mattermost.stop_mattermost_backend()
        return True
