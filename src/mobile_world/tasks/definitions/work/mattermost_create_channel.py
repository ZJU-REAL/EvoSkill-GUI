"""Mattermost email task implementation - send contract via email and create calendar event."""

from mobile_world.runtime.app_helpers import mattermost
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MattermostCreateChannelTask(BaseTask):
    """Mattermost create channel task - create a channel on Mattermost."""

    goal = "Create a channel on Mattermost called 'reading' for paper reading. Add everyone to the channel and greet everyone with a welcome message."
    snapshot_tag = "init_state"

    task_tags = {"lang-en"}

    app_names = {
        "Mattermost",
    }

    def initialize_task_hook(self, controller: AndroidController) -> None:
        mattermost.start_mattermost_backend()

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()
        assert mattermost.is_mattermost_healthy()

        channel_info = mattermost.get_channel_info(channel_name="reading")
        if channel_info is None:
            return 0.0, "Channel not created"
        members = mattermost.get_users_in_channel(channel_info[0])
        if len(members) != 11:
            return 0.0, "Number of members in the channel is not correct"
        last_message = mattermost.get_latest_messages()[0]
        if last_message[5] != channel_info[0]:
            return 0.0, "Last message is not sent to the channel"
        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        mattermost.stop_mattermost_backend()
