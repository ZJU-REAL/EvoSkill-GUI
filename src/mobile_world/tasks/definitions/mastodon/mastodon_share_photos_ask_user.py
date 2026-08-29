"""Share photos via Mastodon - find flowers pictures and post with caption."""

import os
import time
from pathlib import Path

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.app_helpers.mastodon import (
    compute_md5,
    compute_phash,
    get_images_by_status_id,
    get_latest_toots_by_username,
    get_toot_images_path,
)
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask

# Task constants
EXPECTED_USERNAME = "test"
EXPECTED_CAPTION = "Here are some beautiful flowers."
REQUIRED_IMAGES = ["image1.jpeg", "image2.jpeg", "image3.jpeg", "image4.jpeg"]
ASSETS_PATH = "/app/service/src/mobile_world/tasks/definitions/mastodon/assets/flowerPhotos"

# For local development:
# ASSETS_PATH = "/home/admin/zhangxu/mobile_world/src/mobile_world/tasks/definitions/mastodon/assets/flowerPhotos"


def _check_consistency(
    username: str, expected_caption: str, expected_images: list[str], assets_path: str
) -> bool:
    """
    Check if the Mastodon post contains the correct caption and images.

    Args:
        username: Username to check for the post
        expected_caption: Expected caption text in the post
        expected_images: List of expected image filenames
        assets_path: Path to the assets directory with expected images

    Returns:
        True if post contains correct caption and all images match, False otherwise
    """
    try:
        # Get the latest toot from the user
        toots = get_latest_toots_by_username(username, limit=1)
        if not toots:
            logger.warning(f"No toots found for user: {username}")
            return False

        toot = toots[0]
        toot_id = toot.get("id")
        toot_text = toot.get("text", "")

        if expected_caption.lower() not in toot_text.lower():
            logger.warning(f"Caption mismatch: '{toot_text}' does not contain '{expected_caption}'")
            return False

        images = get_images_by_status_id(toot_id)
        if not images:
            logger.warning(f"No images found for toot: {toot_id}")
            return False

        if len(images) != len(expected_images):
            logger.warning(
                f"Wrong number of images: {len(images)} (expected: {len(expected_images)})"
            )
            return False

        expected_image_paths = []
        for image_name in expected_images:
            expected_path = os.path.join(assets_path, image_name)
            if not os.path.exists(expected_path):
                logger.warning(f"Expected image not found: {expected_path}")
                return False
            expected_image_paths.append(expected_path)

        # Get toot image paths
        toot_image_paths = []
        for image in images:
            image_id = image.get("media_attachment_id")
            image_name = image.get("file_name")
            toot_image_path = get_toot_images_path(image_id, image_name)
            if not os.path.exists(toot_image_path):
                logger.warning(f"Toot image not found: {toot_image_path}")
                return False
            toot_image_paths.append(toot_image_path)

        # Match toot images with expected images using MD5 and perceptual hash
        matched_expected_indices = set()

        for toot_image_path in toot_image_paths:
            best_match_idx = -1
            best_match_score = float("inf")

            # Compute hash for toot image
            try:
                toot_md5 = compute_md5(toot_image_path)
                toot_phash = compute_phash(toot_image_path)
            except Exception as e:
                logger.error(f"Error computing hash for toot image {toot_image_path}: {e}")
                return False

            for i, expected_path in enumerate(expected_image_paths):
                if i in matched_expected_indices:
                    continue

                try:
                    expected_md5 = compute_md5(expected_path)
                    expected_phash = compute_phash(expected_path)

                    if toot_md5 == expected_md5:
                        best_match_idx = i
                        best_match_score = 0
                        break

                    phash_diff = abs(toot_phash - expected_phash)
                    if phash_diff < best_match_score:
                        best_match_score = phash_diff
                        best_match_idx = i

                except Exception as e:
                    logger.error(f"Error computing hash for expected image {expected_path}: {e}")
                    continue

            if best_match_idx == -1:
                logger.warning(f"No matching expected image found for toot image {toot_image_path}")
                return False

            if best_match_score > 5:
                logger.warning(
                    f"Toot image {toot_image_path} does not match expected image "
                    f"{expected_image_paths[best_match_idx]} (phash diff: {best_match_score})"
                )
                return False

            matched_expected_indices.add(best_match_idx)

        return True

    except Exception as e:
        logger.error(f"Error checking consistency: {e}")
        return False


class MastodonSharePhotosAskUserTask(BaseTask):
    """Share photos via Mastodon - find flowers pictures and post with caption."""

    task_tags = {"agent-user-interaction", "lang-en"}

    goal = "Share all photos of flowers from the Pictures album (in Gallery app) via Mastodon, and add a caption."

    # Use constants defined at module level
    required_images = REQUIRED_IMAGES
    caption = EXPECTED_CAPTION
    username = EXPECTED_USERNAME
    assets_path = ASSETS_PATH

    app_names = {"Gallery", "Mastodon"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize task - push all images from assets to device and start Mastodon backend."""

        self.relevant_information = f"I want add the caption '{self.caption}' to the post."

        try:
            mastodon.start_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to start Mastodon backend: {e}")
            return False

        # Get path to assets directory (relative to this file)
        current_dir = Path(__file__).parent
        assets_dir = current_dir / "assets" / "flowerPhotos"

        # Check if assets directory exists
        if not assets_dir.exists():
            logger.error(f"Assets directory not found: {assets_dir}")
            return False

        # Find all image files in assets directory
        image_files = (
            list(assets_dir.glob("*.png"))
            + list(assets_dir.glob("*.jpeg"))
            + list(assets_dir.glob("*.jpg"))
        )

        if not image_files:
            logger.error(f"No image files found in {assets_dir}")
            return False

        logger.info(f"Found {len(image_files)} image files in assets directory")

        # Check that all required images are present
        image_filenames = {img.name for img in image_files}
        required_set = set(self.required_images)
        if not required_set.issubset(image_filenames):
            missing = required_set - image_filenames
            logger.error(f"Required images missing from assets: {missing}")
            return False

        # Store list of remote paths for cleanup
        self._remote_image_paths = []

        # Push all images to device
        for local_image_path in image_files:
            image_filename = local_image_path.name

            # Define remote path on device (in Pictures directory so Gallery can find it)
            remote_path = f"/sdcard/Pictures/{image_filename}"

            logger.info(f"Pushing image: {image_filename} to {remote_path}")

            # Push the image to device
            result = controller.push_file(str(local_image_path), remote_path)

            if not result.success:
                logger.error(f"Failed to push image {image_filename} to device: {result.error}")
                continue

            # Store the remote path for later cleanup
            self._remote_image_paths.append(remote_path)

            # Wait a moment for file to be written
            time.sleep(0.5)

            # Trigger media scanner to make the image visible in Gallery
            logger.info(f"Triggering media scan for {image_filename}")
            controller.refresh_media_scan(remote_path)

        if not self._remote_image_paths:
            logger.error("Failed to push any images to device")
            return False

        logger.info(f"Successfully pushed {len(self._remote_image_paths)} images to device")

        # Wait for media scan to complete
        time.sleep(2)

        return True

    def is_successful(self, controller: AndroidController) -> tuple[float, str]:
        """
        Check if the share photos task was completed successfully.

        Checks:
        - Mastodon post exists from the test user
        - Post contains caption "Here some beautiful flowers"
        - Post has all 4 flower images as attachments (image1.jpeg-image4.jpeg)
        """
        self._check_is_initialized()

        # Ensure Mastodon backend is running
        if not mastodon.is_mastodon_healthy():
            mastodon.start_mastodon_backend(self.MASTODON_STATUS_DIR)

        if _check_consistency(
            username=self.username,
            expected_caption=self.caption,
            expected_images=self.required_images,
            assets_path=self.assets_path,
        ):
            return 1.0, "Task completed successfully"
        else:
            return 0.0, "Task validation failed"

    def tear_down(self, controller: AndroidController) -> bool:
        """Clean up task - remove uploaded images and stop Mastodon backend."""
        super().tear_down(controller)

        try:
            # Remove all uploaded images
            if hasattr(self, "_remote_image_paths"):
                for remote_path in self._remote_image_paths:
                    controller.remove_file(remote_path)
                    logger.info(f"Removed image: {remote_path}")
        except Exception as e:
            logger.error(f"Error cleaning up images: {e}")

        # Stop Mastodon backend
        try:
            mastodon.stop_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to stop Mastodon backend: {e}")
            return False

        return True
