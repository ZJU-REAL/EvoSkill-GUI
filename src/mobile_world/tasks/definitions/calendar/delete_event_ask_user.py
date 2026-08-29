"""Delete calendar event task implementation - agent asks user which event to delete."""

from loguru import logger

from mobile_world.runtime.app_helpers.fossify_calendar import get_calendar_events
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class DeleteEventAskUserTask(BaseTask):
    """Delete calendar event ask user task - agent asks user which event to delete."""

    task_tags = {"agent-user-interaction", "lang-en"}
    goal = "My schedule on 10/20 is a bit full, please remove a few events."

    # Event that should be deleted
    # Using partial match to handle variations like "Meet with Sam", "meeting with sam", etc.
    target_event_keyword = "sam"
    events_to_keep = ["morning run", "personal time off", "team standup"]

    app_names = {
        "Calendar",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        self.relevant_information = (
            f"When the agent asks you which event to delete, you must first wait for the agent to list all events on 10/20. "
            f"Before the agent lists all events, you should pretend you don't know which specific event needs to be deleted and ask the agent to show you the schedule first. "
            f"Once the agent shows you all the events on 10/20/2025, you should tell the agent to delete the event related to '{self.target_event_keyword}'"
            f"Do not suggest deleting any other events."
        )

        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        events = get_calendar_events(time_range=["2025-10-20 00:00:00", "2025-10-20 23:59:59"])

        logger.info(f"Found {len(events)} events on 10/20/2025")

        event_titles = [event["title"].lower() for event in events]
        logger.info(f"Current events on 10/20: {event_titles}")

        if any(event_to_keep not in event_titles for event_to_keep in self.events_to_keep):
            return 0.0, f"Events to keep: {self.events_to_keep} not found"

        target_events = [
            event["title"]
            for event in events
            if self.target_event_keyword.lower() in event["title"].lower()
        ]

        if target_events:
            logger.error(
                f"- Target event(s) containing '{self.target_event_keyword}' still exist: {target_events}"
            )
            return (
                0.0,
                f"Target event(s) containing '{self.target_event_keyword}' still exist: {target_events}",
            )
        else:
            logger.info(
                f"- No events containing '{self.target_event_keyword}' found - event was deleted"
            )
            return 1.0, "Success"

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        return True
