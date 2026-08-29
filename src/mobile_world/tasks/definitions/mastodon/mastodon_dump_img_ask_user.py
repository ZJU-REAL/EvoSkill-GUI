"""Download images from Mastodon post - save pupper's earliest post images to specified path."""

import os
from typing import Any

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
from mobile_world.runtime.utils.helpers import execute_adb
from mobile_world.tasks.base import BaseTask

# Task constants
SOURCE_USERNAME = "pupper"
TARGET_PATH = "/sdcard/mastodon_img"
REQUIRED_IMAGES = ["image1.jpeg", "image2.jpeg", "image3.jpeg", "image4.jpeg"]
ASSETS_PATH = "/app/service/src/mobile_world/tasks/definitions/mastodon/assets/flowerPhotos"

# For local development:
# ASSETS_PATH = "/home/admin/zhangxu/mobile_world/src/mobile_world/tasks/definitions/mastodon/assets/flowerPhotos"


def _get_earliest_toot_images(username: str) -> tuple[str | None, list[dict]]:
    """
    Get images from the earliest toot of a user.

    Args:
        username: Username to get toots from

    Returns:
        Tuple of (toot_id, list of image info dicts) or (None, []) if no toots/images found
    """
    try:
        # Get all toots from the user
        toots = get_latest_toots_by_username(username, limit=100)
        if not toots:
            logger.warning(f"No toots found for user: {username}")
            return None, []

        # Find the earliest toot (last in the list)
        earliest_toot = toots[-1]
        toot_id = earliest_toot.get("id")

        logger.info(f"Found earliest toot from {username}: ID={toot_id}")

        # Get images from the toot
        images = get_images_by_status_id(toot_id)
        if not images:
            logger.warning(f"No images found in earliest toot: {toot_id}")
            return toot_id, []

        logger.info(f"Found {len(images)} images in earliest toot")
        return toot_id, images

    except Exception as e:
        logger.error(f"Error getting earliest toot images: {e}")
        return None, []


def _check_saved_images(
    target_path: str, expected_images: list[dict], assets_path: str
) -> tuple[bool, str]:
    """
    Check if images were saved correctly to the target path.

    Args:
        target_path: Path where images should be saved on device
        expected_images: List of expected image info from Mastodon
        assets_path: Path to the assets directory with original images

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        # Check if target directory exists
        result = execute_adb(f"shell ls -l {target_path}")
        if not result.success:
            return False, f"Target directory does not exist: {target_path}"

        lines = result.output.strip().split("\n")

        # Parse saved files
        saved_files = []
        for line in lines:
            if not line.strip() or line.startswith("total") or line.startswith("d"):
                continue

            parts = line.split()
            if len(parts) >= 8:
                filename = " ".join(parts[7:])
                saved_files.append(filename)

        logger.info(f"Files found in {target_path}: {saved_files}")

        # Check number of files
        if len(saved_files) != len(expected_images):
            return False, f"Expected {len(expected_images)} images, found {len(saved_files)}"

        # Get expected image paths from assets
        expected_image_paths = {}
        for image in expected_images:
            image_id = image.get("media_attachment_id")
            image_name = image.get("file_name")
            toot_image_path = get_toot_images_path(image_id, image_name)

            if os.path.exists(toot_image_path):
                expected_image_paths[image_name] = toot_image_path
            else:
                logger.warning(f"Expected toot image not found: {toot_image_path}")

        if not expected_image_paths:
            return False, "No expected images found in Mastodon backend"

        # Download saved files from device and compare
        import tempfile

        temp_dir = tempfile.mkdtemp()
        matched_count = 0

        try:
            for saved_file in saved_files:
                # Pull file from device
                remote_path = f"{target_path}/{saved_file}"
                local_path = os.path.join(temp_dir, saved_file)

                result = execute_adb(f"pull {remote_path} {local_path}")
                if not result.success:
                    logger.warning(f"Failed to pull {saved_file} from device")
                    continue

                # Compute hash for saved file
                try:
                    saved_md5 = compute_md5(local_path)
                    saved_phash = compute_phash(local_path)
                except Exception as e:
                    logger.error(f"Error computing hash for saved file {saved_file}: {e}")
                    continue

                # Compare with expected images
                matched = False
                for expected_name, expected_path in expected_image_paths.items():
                    try:
                        expected_md5 = compute_md5(expected_path)
                        expected_phash = compute_phash(expected_path)

                        if saved_md5 == expected_md5:
                            matched_count += 1
                            matched = True
                            break

                        phash_diff = abs(saved_phash - expected_phash)
                        if phash_diff <= 5:
                            matched_count += 1
                            matched = True
                            break

                    except Exception as e:
                        logger.error(f"Error comparing with {expected_name}: {e}")
                        continue

                if not matched:
                    logger.warning(f"{saved_file} does not match any expected image")

        finally:
            # Clean up temp directory
            for file in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, file))
            os.rmdir(temp_dir)

        # Check if all images matched
        if matched_count == len(expected_images):
            return True, f"All {matched_count} images saved correctly"
        else:
            return False, f"Only {matched_count}/{len(expected_images)} images matched"

    except Exception as e:
        logger.error(f"Error checking saved images: {e}")
        return False, f"Error during validation: {str(e)}"


class MastodonDumpImgAskUserTask(BaseTask):
    """Download images from Mastodon post - save pupper's earliest post images to specified path."""

    task_tags = {"agent-user-interaction", "lang-en"}

    goal = "Save the images from pupper's earliest post on Mastodon to the specified path."

    # Use constants defined at module level
    source_username = SOURCE_USERNAME
    target_path = TARGET_PATH
    required_images = REQUIRED_IMAGES
    assets_path = ASSETS_PATH

    def __init__(self, params: dict[str, Any] = None):
        super().__init__(params)
        self._earliest_toot_id = None
        self._expected_images = []

    app_names = {
        "Mastodon",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        # Set relevant_information to provide the target path to the agent
        self.relevant_information = f"Please save the images to {self.target_path}"
        try:
            mastodon.start_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to start Mastodon backend: {e}")
            return False

        # Get earliest toot from pupper and verify it has images
        toot_id, images = _get_earliest_toot_images(self.source_username)

        if not toot_id:
            logger.error(f"Could not find any toots from user: {self.source_username}")
            return False

        if not images:
            logger.error(f"Earliest toot from {self.source_username} has no images")
            return False

        # Store expected images for validation
        self._earliest_toot_id = toot_id
        self._expected_images = images

        logger.info(f"Found earliest toot (ID: {toot_id}) with {len(images)} images")
        logger.info(f"Task: Save these images to {self.target_path}")

        # Clean up target directory if it exists from previous runs
        result = execute_adb(f"shell ls {self.target_path}")
        if result.success:
            logger.info(f"Cleaning up existing target directory: {self.target_path}")
            execute_adb(f"shell rm -rf {self.target_path}")

        return True

    def is_successful(self, controller: AndroidController) -> tuple[float, str]:
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()

        # Verify we have expected images from initialization
        if not self._expected_images:
            return 0.0, "Task not properly initialized (no expected images)"

        success, message = _check_saved_images(
            target_path=self.target_path,
            expected_images=self._expected_images,
            assets_path=self.assets_path,
        )

        if success:
            return 1.0, message
        else:
            return 0.0, message

    def tear_down(self, controller: AndroidController) -> bool:
        """Clean up task - remove downloaded images and stop Mastodon backend."""
        super().tear_down(controller)

        try:
            # Remove target directory with downloaded images
            result = execute_adb(f"shell ls {self.target_path}")
            if result.success:
                logger.info(f"Cleaning up target directory: {self.target_path}")
                execute_adb(f"shell rm -rf {self.target_path}")
        except Exception as e:
            logger.error(f"Error cleaning up target directory: {e}")

        # Stop Mastodon backend
        try:
            mastodon.stop_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to stop Mastodon backend: {e}")
            return False

        return True
