"""Mattermost email task implementation - send contract via email and create calendar event."""

from mobile_world.runtime.app_helpers import mattermost, system
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class LocalFileManagementTask(BaseTask):
    """Local file management task - handle local file management."""

    task_tags = {"lang-en"}
    goal = "I'm running out of space, can you check my files and delete zip files that are older than 1 year in my Download folder. Send myself on mattermost the list of deleted files just for record"
    snapshot_tag = "init_state"
    filenames = [
        "06_music_collection_20240929.zip",
        "01_archive_20240924.zip",
        "11_source_code_backup_20240909.zip",
        "03_screenshots_jun_2024.zip",
        "07_invoice_archive_mar_2024.zip",
        "18_receipts_mar_2024.zip",
        "19_documents_20240305.zip",
        "08_photos_vacation_sydney_20240130.zip",
        "02_music_collection_20240125.zip",
        "17_archive_20231229.zip",
        "15_camera_backup_20231116.zip",
    ]

    app_names = {"Files", "Mattermost"}

    def initialize_task_hook(self, controller: AndroidController) -> None:
        mattermost.start_mattermost_backend()

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()
        # to check if the task is successful, we need the mattermost backend to be running
        assert mattermost.is_mattermost_healthy()

        # check 1: the files are deleted
        existing_files = system.get_file_list("/sdcard/Download")
        for file in self.filenames:
            if file in existing_files:
                return 0.0, f"File {file} is not deleted"

        # check 2: no other files are deleted
        if len(existing_files) != 19:
            return 0.0, f"Other files are deleted: {existing_files}"
        # check 3: the last message is sent from harry to harry and contains the list of deleted files
        last_message = mattermost.get_latest_messages()[0]
        channel_info = mattermost.get_channel_info(last_message[5])
        if (
            last_message[4] != mattermost.HARRY_ID
            or channel_info[7] != f"{mattermost.HARRY_ID}__{mattermost.HARRY_ID}"
        ):
            return 0.0, "Last message is not sent to harry himeself"
        for file in self.filenames:
            if file not in last_message[8]:
                return 0.0, f"File {file} is not in the last message"
        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        mattermost.stop_mattermost_backend()
