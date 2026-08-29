"""Change header image on Mastodon profile."""

import os
import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonChangeHeaderTask(BaseTask):
    goal = "On Mastodon, replace my profile header with the tiger photo from my photo gallery."

    EXPECTED_USERNAME = "test"
    EXPECTED_SOURCE_IMAGE = "tiger.jpg"
    ASSETS_PATH = "/app/service/src/mobile_world/tasks/definitions/mastodon/assets/changeHeader"

    task_tags = {"lang-en"}

    app_names = {"Mastodon", "Gallery"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        try:
            mastodon.start_mastodon_backend()
            return True
        except Exception as e:
            logger.error(f"Failed to start Mastodon backend: {e}")
            return False

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """
        check:
        - header image is changed
        - header image is the expected image
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()
        time.sleep(2)  # wait for the header image to be changed

        # Get header path & device image path
        account_id = mastodon.get_user_account_info(self.EXPECTED_USERNAME).get("account_id")
        header_file_name = mastodon.get_user_account_info(self.EXPECTED_USERNAME).get(
            "header_file_name"
        )
        if not account_id or not header_file_name:
            return 0.0, "Account ID or header file name missing"

        header_path = mastodon.get_header_path(account_id, header_file_name)

        expected_image_path = os.path.join(self.ASSETS_PATH, self.EXPECTED_SOURCE_IMAGE)
        if not os.path.exists(expected_image_path):
            return 0.0, f"Expected image path not found: {expected_image_path}"

        # MD5 check
        expected_md5 = mastodon.compute_md5(expected_image_path)
        header_md5 = mastodon.compute_md5(header_path)
        if expected_md5 != header_md5:
            # then check perceptual hash
            expected_phash = mastodon.compute_phash(expected_image_path)
            header_phash = mastodon.compute_phash(header_path)
            if abs(expected_phash - header_phash) > 5:
                return 0.0, "Perceptual hash does not match, image not matched"

        return 1.0

    def tear_down(self, controller: AndroidController):
        super().tear_down(controller)
        try:
            mastodon.stop_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to stop Mastodon backend: {e}")
            return False
        return True
