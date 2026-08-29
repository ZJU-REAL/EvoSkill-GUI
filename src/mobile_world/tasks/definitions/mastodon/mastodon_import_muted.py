"""Import muted users from Mastodon."""
import os
import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonImportMutedUsersTask(BaseTask):
    goal = "In Mastodon, import my muted list from the file named 'muted_accounts.csv' in the Downloads directory."
    task_tags = {"lang-en"}
    EXPECTED_USERNAME = "test"
    EXPECTED_MUTED_USERS = ["olivia"]
    EXPECTED_FILE_NAME = "muted_accounts.csv"
    ASSETS_PATH = "/app/service/src/mobile_world/tasks/definitions/mastodon/assets/importMuted"


    app_names = {
        "Mastodon",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        # push the image to the gallery
        file_path = os.path.join(self.ASSETS_PATH, self.EXPECTED_FILE_NAME)
        if not os.path.exists(file_path):
            return 0.0, f"File path not found: {file_path}"
        controller.push_file(file_path, f"/sdcard/Download/{self.EXPECTED_FILE_NAME}")
        controller.refresh_media_scan("/sdcard/Download/")
        
        try:
            mastodon.start_mastodon_backend()
            return True
        except Exception as e:
            logger.error(f"Failed to start Mastodon backend: {e}")
            return False

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """
        check:
        - all expected users are muted
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()
        time.sleep(1)  # wait for the muted list to be imported

        # Check muted users
        muted_users = mastodon.get_muted_users(self.EXPECTED_USERNAME)
        if not muted_users:
            return 0.0, f"No muted users found for user '{self.EXPECTED_USERNAME}'"

        muted_usernames = {
            user.get("muted_username").lower() for user in muted_users if user.get("muted_username")
        }

        expected_muted_usernames = {username.lower() for username in self.EXPECTED_MUTED_USERS}

        if expected_muted_usernames != muted_usernames:
            return (
                0.0,
                f"Not all expected users are muted. Expected: {expected_muted_usernames}, Found: {muted_usernames}",
            )

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        try:
            mastodon.stop_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to stop Mastodon backend: {e}")
            return False
        return True
