"""Post a new content with edited photos on Mastodon."""

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonPostEditedPhotoTask(BaseTask):
    goal = "Select a random photo from the gallery, crop it to a 9:16 ratio, and post it with the tag #onePhoto. Post with the account @test."

    EXPECTED_USERNAME = "test"
    EXPECTED_TAG = ["onePhoto"]
    EXPECTED_PHOTO_ASPECT_RATIO = 0.5625  # 9:16

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
        Check:
        - The toot is posted successfully
        - The toot has the expected tags
        - The toot has the expected image aspect ratio
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()

        toots = mastodon.get_latest_toots_by_username(self.EXPECTED_USERNAME, limit=1)
        if not toots:
            return 0.0, f"No toots found for user: {self.EXPECTED_USERNAME}"

        toot = toots[0]
        toot_id = toot.get("id")
        images = mastodon.get_images_by_status_id(toot_id)
        if not images:
            return 0.0, f"No images found for toot: {toot_id}"

        # check tags
        tags = mastodon.get_toot_tags(toot_id)
        tags_set = set(tag.lower() for tag in tags)
        expected_tags_set = set(tag.lower() for tag in self.EXPECTED_TAG)
        if tags_set != expected_tags_set:
            return 0.0, f"Wrong tags in the toot: {tags_set} != {expected_tags_set}"

        # check images aspect ratio
        image_info = images[0]
        image_width = image_info.get("file_meta", {}).get("original", {}).get("width")
        image_height = image_info.get("file_meta", {}).get("original", {}).get("height")
        if image_width is None or image_height is None:
            return 0.0, "Image width or height missing in the image info"
        aspect_ratio = round(image_width / image_height, 2)
        if abs(aspect_ratio - self.EXPECTED_PHOTO_ASPECT_RATIO) > 0.02:
            return (
                0.0,
                f"Image aspect ratio {aspect_ratio} does not match expected {self.EXPECTED_PHOTO_ASPECT_RATIO}",
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
