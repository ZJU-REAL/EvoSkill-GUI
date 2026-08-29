"""Take selfie task implementation."""

from loguru import logger

from mobile_world.runtime.app_helpers.system import get_file_list
from mobile_world.runtime.controller import AndroidController
from mobile_world.runtime.utils.helpers import execute_adb
from mobile_world.tasks.base import BaseTask


def get_camera_photos_count(controller: AndroidController) -> int:
    """
    Get the number of photos in Pictures directory.

    Checks /sdcard/Pictures directory only.
    """
    try:
        path = "/sdcard/Pictures"
        photos = get_file_list(path)
        # Filter for image files
        image_files = [f for f in photos if f.lower().endswith((".jpg", ".jpeg", ".png", ".dng"))]
        logger.debug(f"Found {len(image_files)} photos in {path}")
        return len(image_files)
    except Exception as e:
        logger.warning(f"Error getting camera photos count: {e}")
        return 0


def get_recent_photos_via_mediastore(
    controller: AndroidController, timestamp: float
) -> tuple[int, list[str]]:
    """
    Query MediaStore for photos taken after a given timestamp.

    Args:
        controller: AndroidController instance
        timestamp: Unix timestamp (seconds since epoch)

    Returns:
        Tuple of (count, list of file paths)
    """
    try:
        # Query MediaStore for recent images with file paths
        # date_added is in seconds, date_modified is in seconds
        query_cmd = (
            f"adb -s {controller.device} shell content query "
            f"--uri content://media/external/images/media "
            f"--projection _id:_display_name:_data:date_added "
            f'--where "date_added>{int(timestamp)}"'
        )

        result = execute_adb(query_cmd, output=False)

        photo_paths = []
        if result.success and result.output:
            # Parse rows to extract file paths
            rows = [line for line in result.output.split("\n") if line.strip().startswith("Row:")]
            for row in rows:
                # Extract _data field which contains file path
                import re

                match = re.search(r"_data=([^,\s]+)", row)
                if match:
                    photo_paths.append(match.group(1))

            count = len(rows)
            if count > 0:
                logger.info(f"Found {count} new photo(s) in MediaStore after timestamp {timestamp}")
                logger.debug(f"Photo paths: {photo_paths[:3]}")  # Show first 3
            return count, photo_paths

        return 0, []

    except Exception as e:
        logger.warning(f"Error querying MediaStore: {e}")
        return 0, []


class TakeSelfieTask(BaseTask):
    goal = "Take a photo."

    task_tags = {"lang-en"}

    app_names = {
        "Camera",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize the camera task by resetting the Camera app and recording initial state."""
        # Record the initial number of photos
        self._initial_photo_count = get_camera_photos_count(controller)
        logger.info(f"Initial photo count: {self._initial_photo_count}")

        # Record current timestamp for MediaStore queries
        import time as time_module

        self._start_timestamp = time_module.time()
        logger.info(f"Task start timestamp: {self._start_timestamp}")

        return True

    def is_successful(self, controller: AndroidController) -> tuple[float, str]:
        """Check if the selfie task was completed successfully."""
        self._check_is_initialized()

        import time as time_module

        logger.info("Waiting for photos to be saved...")
        time_module.sleep(2)

        # Trigger media scan to ensure MediaStore is updated
        scan_cmd = f"adb -s {controller.device} shell am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file:///sdcard/Pictures"
        execute_adb(scan_cmd, output=False)
        time_module.sleep(0.5)

        # Method 1: Check via MediaStore (most reliable for recent photos)
        new_photos_count, new_photo_paths = get_recent_photos_via_mediastore(
            controller, self._start_timestamp
        )
        logger.info(f"MediaStore check: {new_photos_count} new photo(s) since task start")

        # Method 2: Check file count in camera directories
        current_photo_count = get_camera_photos_count(controller)
        logger.info(
            f"File count check: Initial={self._initial_photo_count}, Current={current_photo_count}"
        )

        if new_photos_count > 0:
            return 1.0, f"Photo taken successfully ({new_photos_count} new photo(s))"
        elif current_photo_count > self._initial_photo_count:
            new_count = current_photo_count - self._initial_photo_count
            return 1.0, f"Photo taken successfully ({new_count} new photo(s))"
        else:
            return 0.0, "No new photo detected"
