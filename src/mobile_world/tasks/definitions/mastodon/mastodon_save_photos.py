"""Save photos to gallery"""

import os
import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonSavePhotosTask(BaseTask):
    goal = "Find the post that Alice published on October 5th on Mastodon, and save all the images to the phone."

    EXPECTED_TOOT_ID = 115319571928036858
    EXPECTED_PHOTO_NAME = ["21bd-1.jpg", "21bd-2.jpeg", "21bd-3.jpg"]
    ASSETS_PATH = "/app/service/src/mobile_world/tasks/definitions/mastodon/assets/savePhotos"
    TEMP_LOCAL_PATH = "/app/temp"

    task_tags = {"lang-en"}

    app_names = {"Mastodon", "Gallery"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        try:
            mastodon.start_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to start Mastodon backend: {e}")
            return False
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """
        Check:
        - The photos are saved correctly
        - The photos are the expected photos
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()
        time.sleep(2)  # wait for the photos to be saved

        images = mastodon.get_images_by_status_id(self.EXPECTED_TOOT_ID)
        if not images:
            return 0.0, f"No images found for toot: {self.EXPECTED_TOOT_ID}"
        images_set = set(image.get("file_name") for image in images)
        expected_images_set = set(self.EXPECTED_PHOTO_NAME)

        # check the number of images
        if len(images_set) != len(expected_images_set):
            return (
                0.0,
                f"Wrong number of images in the toot: {len(images_set)} != {len(expected_images_set)}",
            )

        # get the device address by the name in images_set
        image_device_paths = []
        for image in images_set:
            image_device_path = mastodon.get_device_file_path(controller, image)
            if not image_device_path:
                return 0.0, f"Image not found on device: {image}"
            image_device_paths.append(image_device_path)

        expected_image_paths = []
        for image in expected_images_set:
            expected_image_path = os.path.join(self.ASSETS_PATH, image)
            if not os.path.exists(expected_image_path):
                return 0.0, f"Expected image not found: {expected_image_path}"
            expected_image_paths.append(expected_image_path)

        # create the temporary directory
        os.makedirs(self.TEMP_LOCAL_PATH, exist_ok=True)

        # save the device images to the local temporary directory
        device_local_paths = []
        for i, device_path in enumerate(image_device_paths):
            local_filename = f"device_image_{i}.jpg"
            local_path = os.path.join(self.TEMP_LOCAL_PATH, local_filename)
            if not mastodon.save_file_to_local(controller, device_path, local_path):
                logger.error(f"Failed to save device image {device_path} to local")
                # remove the saved files
                for path in device_local_paths:
                    if os.path.exists(path):
                        os.remove(path)
                return 0.0, f"Failed to save device image {device_path} to local"
            device_local_paths.append(local_path)

        # for each device image, find the best matching expected image
        matched_expected_indices = set()

        for device_local_path in device_local_paths:
            best_match_idx = -1
            best_match_score = float("inf")

            # compute the hash of the device image
            device_md5 = mastodon.compute_md5(device_local_path)
            device_phash = mastodon.compute_phash(device_local_path)

            # compare with each expected image
            for i, expected_path in enumerate(expected_image_paths):
                if i in matched_expected_indices:
                    continue  # this expected image has been matched

                expected_md5 = mastodon.compute_md5(expected_path)
                expected_phash = mastodon.compute_phash(expected_path)

                # compare the MD5
                if device_md5 == expected_md5:
                    best_match_idx = i
                    best_match_score = 0  # perfect match
                    break

                # if the MD5 does not match, compare the perceptual hash
                phash_diff = abs(device_phash - expected_phash)
                if phash_diff < best_match_score:
                    best_match_score = phash_diff
                    best_match_idx = i

            # check the matching result
            if best_match_idx == -1:
                return 0.0, f"No matching expected image found for device image {device_local_path}"

            if best_match_score > 5:  # the perceptual hash difference is too large
                return (
                    0.0,
                    f"Device image {device_local_path} does not match expected image {expected_image_paths[best_match_idx]} (phash diff: {best_match_score})",
                )

            matched_expected_indices.add(best_match_idx)

        # remove the temporary files
        for path in device_local_paths:
            if os.path.exists(path):
                os.remove(path)

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        try:
            mastodon.stop_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to stop Mastodon backend: {e}")
            return False
        return True
