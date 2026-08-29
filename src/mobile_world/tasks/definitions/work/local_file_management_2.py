"""Mattermost email task implementation - send contract via email and create calendar event."""

from mobile_world.runtime.app_helpers import system
from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.controller import AndroidController
from mobile_world.runtime.utils.helpers import execute_adb
from mobile_world.tasks.base import BaseTask


class LocalFileManagementTask2(BaseTask):
    """Local file management task - handle local file management."""

    task_tags = {"lang-en"}
    goal = "There are too many files in my download folder, can you check my files and compress files that are older than 1 year in a single `old_files.zip` file. Delete the files after compression. Send myself an email with the list of deleted files just for record"
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

    app_names = {"Files", "Mail"}

    def initialize_task_hook(self, controller: AndroidController) -> None:
        # nothing to do for this task
        pass

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        existing_files = system.get_file_list("/sdcard/Download")
        for file in self.filenames:
            if file in existing_files:
                return 0.0, f"File {file} is not deleted"

        if "old_files.zip" not in existing_files:
            return 0.0, "old_files.zip is not in the download folder"

        content = execute_adb("adb shell unzip -l /sdcard/Download/old_files.zip")
        if not content.success:
            return 0.0, f"Failed to unzip the zip file: {content.stderr}"

        for file in self.filenames:
            if file not in content.output:
                return 0.0, f"File {file} is not in the zip file"
        extra_lines = 5
        if len(content.output.splitlines()) - extra_lines != len(self.filenames):
            return 0.0, f"Extra lines in the zip file: {len(content.splitlines()) - extra_lines}"
        email_info = get_sent_email_info()
        if email_info is None:
            return 0.0, "No email found"
        if not (email_info["to"] == "test@gmail.com"):
            return 0.0, "Last message is not sent to myself"
        for file in self.filenames:
            if file not in email_info["body"]:
                return 0.0, f"File {file} is not in the email body"

        return 1.0
