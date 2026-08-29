"""Mattermost email task implementation - send contract via email and create calendar event."""

import json

from PIL import Image, ImageChops

from mobile_world.runtime.app_helpers import mattermost
from mobile_world.runtime.controller import AndroidController
from mobile_world.runtime.utils.helpers import execute_adb
from mobile_world.tasks.base import BaseTask


class MattermostSendFileTask(BaseTask):
    """Mattermost send file task - send a file to a channel on Mattermost."""

    goal = "It's alex's 21st birthday today. Send a birthday message to him privately on mattermost. Upload a birthday cake image to the message."
    snapshot_tag = "init_state"

    task_tags = {"lang-en"}

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
        channel_info = mattermost.get_channel_info(message[5])
        if channel_info[13] != mattermost.ALEX_ID:
            return 0.0, "Message not sent to alex privately"
        if "birthday" not in message[8].lower():
            return 0.0, "Message not sent with birthday message"
        file_id_list = json.loads(message[13])
        if len(file_id_list) != 1:
            return 0.0, "Birthday cake image not uploaded or too many files uploaded"
        file_path = mattermost.get_file_info(file_id_list[0], return_path=True)
        execute_adb("adb pull /sdcard/Pictures/21bd-1.jpg /tmp/21bd-1.jpg")

        img1 = Image.open("/tmp/21bd-1.jpg")
        try:
            img2 = Image.open(file_path)
        except Exception as e:
            return 0.0, f"Error opening image: {e}"

        diff = ImageChops.difference(img1, img2)
        if diff.getbbox() is not None:
            return 0.0, "Wrong image uploaded"
        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        mattermost.stop_mattermost_backend()
