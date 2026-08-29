"""Mattermost email task implementation - send contract via email and create calendar event."""

from mobile_world.runtime.app_helpers import mattermost
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MattermostReplyToMessageTask(BaseTask):
    """Mattermost reply to message task - reply to a message on Mattermost."""

    task_tags = {"lang-en"}
    goal = "I just got our OSWorld eval SR result (35.5). Reply to my own earlier message in AI-Research on mattermost with the result."
    snapshot_tag = "init_state"

    EARLIER_MSG_ID = "q1iiqx18bb8npdoiocr7ki5t1r"

    app_names = {
        "Mattermost",
    }

    def initialize_task_hook(self, controller: AndroidController) -> None:
        mattermost.start_mattermost_backend()

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()
        # to check if the task is successful, we need the mattermost backend to be running
        assert mattermost.is_mattermost_healthy()

        message = mattermost.get_latest_messages()[0]
        if message[6] != self.EARLIER_MSG_ID:
            return 0.0, "Message not replied to harry's own earlier message"
        if "35.5" not in message[8]:
            return 0.0, "Result not included in the reply"
        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        mattermost.stop_mattermost_backend()
