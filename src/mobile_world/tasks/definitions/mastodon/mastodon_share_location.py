"""Share location on Mastodon."""

import os
import re
import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonShareLocationTask(BaseTask):
    goal = "Search for the location Eiffel Tower on Google Map, and share the link to Mastodon, add the Eiffel Tower image in my photo gallery, then post it."

    EXPECTED_USERNAME = "test"
    EXPECTED_URL = "https://maps.app.goo.gl/xxxxxx"
    EXPECTED_LOCATION = "Eiffel Tower"
    EXPECTED_IMAGE = "Eiffel_Tower.jpg"
    ASSETS_PATH = "/app/service/src/mobile_world/tasks/definitions/mastodon/assets/shareLocation"

    task_tags = {"lang-en"}

    app_names = {"Mastodon", "Maps", "Gallery"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        # push the image to the gallery
        image_path = os.path.join(self.ASSETS_PATH, self.EXPECTED_IMAGE)
        if not os.path.exists(image_path):
            return 0.0, f"Image path not found: {image_path}"
        controller.push_file(image_path, "/sdcard/Download/Eiffel_Tower.jpg")
        controller.refresh_media_scan("/sdcard/Download/")

        try:
            mastodon.start_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to start Mastodon backend: {e}")
            return False
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """
        Check:
        - The URL is shared correctly, regex: "https://maps.app.goo.gl/xxxxxx"
        - The location is shared correctly
        - The image is shared correctly, image is in the toot
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()
        time.sleep(1)

        toots = mastodon.get_latest_toots_by_username(self.EXPECTED_USERNAME, limit=1)
        if not toots:
            return 0.0, f"No toots found for user: {self.EXPECTED_USERNAME}"
        toot = toots[0]

        # check url, regex: "https://maps.app.goo.gl/xxxxxx"
        toot_text = toot.get("text")
        if not re.search(r"https://maps\.app\.goo\.gl/\w+", toot_text):
            return 0.0, f"URL mismatch: {toot_text} does not contain {self.EXPECTED_URL}"

        # check location, location is in the text
        if self.EXPECTED_LOCATION not in toot_text:
            return 0.0, f"Location mismatch: {toot_text} does not contain {self.EXPECTED_LOCATION}"

        # check image, image is in the toot
        status_id = toot.get("id")
        images = mastodon.get_images_by_status_id(status_id)
        if not images:
            return 0.0, f"No images found for toot: {status_id}"
        image_id = images[0].get("media_attachment_id")
        image_name = images[0].get("file_name")
        image_path = mastodon.get_toot_images_path(image_id, image_name)
        if not os.path.exists(image_path):
            return 0.0, f"Image path not found: {image_path}"

        expected_image_path = os.path.join(self.ASSETS_PATH, self.EXPECTED_IMAGE)
        if not os.path.exists(expected_image_path):
            return 0.0, f"Expected image path not found: {expected_image_path}"

        # compare the MD5 and perceptual hash
        image_md5 = mastodon.compute_md5(image_path)
        expected_md5 = mastodon.compute_md5(expected_image_path)
        if image_md5 != expected_md5:
            image_phash = mastodon.compute_phash(image_path)
            expected_phash = mastodon.compute_phash(expected_image_path)
            if abs(image_phash - expected_phash) > 5:
                return 0.0, f"Image perceptual hash mismatch: {image_phash} != {expected_phash}"

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        try:
            mastodon.stop_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to stop Mastodon backend: {e}")
            return False
        return True
