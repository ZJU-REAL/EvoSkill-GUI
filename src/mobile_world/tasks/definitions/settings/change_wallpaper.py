"""Change wallpaper task implementation."""

import time
from pathlib import Path

from loguru import logger

from mobile_world.runtime.controller import AndroidController
from mobile_world.runtime.utils.helpers import execute_adb
from mobile_world.tasks.base import BaseTask


class ChangeWallpaperTask(BaseTask):
    """Change wallpaper to a sunflower photo task."""

    goal = "Change the wallpaper to a photo from the album that features sunflowers."
    target_image_name = "image1.jpeg"

    task_tags = {"lang-en"}

    app_names = {"Gallery", "Settings"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize task - push all wallpaper images from assets to device and record initial wallpaper state."""
        # Get path to assets directory
        current_dir = Path(__file__).parent
        assets_dir = current_dir / "assets"

        # Check if assets directory exists
        if not assets_dir.exists():
            logger.error(f"Assets directory not found: {assets_dir}")
            return False

        # Find all img files in assets directory
        image_files = (
            list(assets_dir.glob("*.png"))
            + list(assets_dir.glob("*.jpeg"))
            + list(assets_dir.glob("*.jpg"))
        )

        if not image_files:
            logger.error(f"No img files found in {assets_dir}")
            return False

        logger.info(f"Found {len(image_files)} image files in assets directory")

        # Store list of remote paths for cleanup
        self._remote_image_paths = []
        self._target_image_path = None

        # Push all images to device
        for local_image_path in image_files:
            image_filename = local_image_path.name
            # Define remote path on device (in Pictures directory so Gallery can find it)
            remote_path = f"/sdcard/Pictures/{image_filename}"

            logger.info(f"Pushing image: {local_image_path.name} to {remote_path}")

            # Push the image to device
            result = controller.push_file(str(local_image_path), remote_path)

            if not result.success:
                logger.error(f"Failed to push image {image_filename} to device: {result.error}")
                continue

            # Store the remote path for later cleanup
            self._remote_image_paths.append(remote_path)

            if image_filename.lower() == self.target_image_name.lower():
                self._target_image_path = remote_path
                logger.info(f"Target image: {self.target_image_name}")

            # Wait a moment for file to be written
            time.sleep(0.5)

            # Trigger media scanner to make the image visible in Gallery
            logger.info(f"Triggering media scan for {image_filename}")
            controller.refresh_media_scan(remote_path)

        if not self._remote_image_paths:
            logger.error("Failed to push any images to device")
            return False

        if not self._target_image_path:
            logger.error(f"Target image ({self.target_image_name}) not found in assets directory")
            return False

        logger.info(f"Successfully pushed {len(self._remote_image_paths)} images to device")

        # Wait for media scan to complete
        time.sleep(2)

        # Record initial wallpaper state (before user changes it)
        logger.info("\nRecording initial wallpaper state...")
        self._initial_wallpaper_state = self._get_wallpaper_state(controller)
        logger.info(f"Initial wallpaper state recorded: {self._initial_wallpaper_state}")

        return True

    def _get_wallpaper_state(self, controller: AndroidController) -> dict:
        """Get current wallpaper state (modification time or MD5)."""
        state = {}

        # Try to enable adb root first (only on first call to avoid repeated restarts)
        if not hasattr(self, "_adb_root_attempted"):
            root_cmd = f"adb -s {controller.device} root"
            execute_adb(root_cmd, output=False)
            time.sleep(1)
            self._adb_root_attempted = True

        # Check wallpaper files
        wallpaper_files = [
            "/data/system/users/0/wallpaper",
            "/data/system/users/0/wallpaper_orig",
        ]

        for wp_file in wallpaper_files:
            # Try to get file modification time
            stat_cmd = f"adb -s {controller.device} shell 'stat -c \"%Y\" {wp_file} 2>/dev/null'"
            result = execute_adb(stat_cmd, output=False)

            if result.success and result.output.strip() and result.output.strip().isdigit():
                state[wp_file] = result.output.strip()
                logger.info(f"  {wp_file}: mtime={result.output.strip()}")

        # If no wallpaper files found, use dumpsys wallpaper id
        if not state:
            dumpsys_cmd = f"adb -s {controller.device} shell dumpsys wallpaper"
            result = execute_adb(dumpsys_cmd, output=False)
            if result.success:
                # Extract wallpaper ID from dumpsys (more stable than full hash)
                import re

                # Look for wallpaper id in dumpsys output
                id_match = re.search(r"id=(\d+)", result.output)
                if id_match:
                    state["wallpaper_id"] = id_match.group(1)
                    logger.info(f"  wallpaper_id: {state['wallpaper_id']}")
                else:
                    # Fallback: use dimensions which are more stable
                    width_match = re.search(r"mWidth=(\d+)", result.output)
                    height_match = re.search(r"mHeight=(\d+)", result.output)
                    if width_match and height_match:
                        state["dimensions"] = f"{width_match.group(1)}x{height_match.group(1)}"
                        logger.info(f"  wallpaper dimensions: {state['dimensions']}")

        if not state:
            logger.warning("  ⚠ Warning: Could not determine wallpaper state")

        return state

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """Check if wallpaper has been changed."""
        self._check_is_initialized()

        # Wait a moment to ensure any changes are persisted
        time.sleep(2)

        # Compare with initial state
        if not hasattr(self, "_initial_wallpaper_state"):
            logger.error("Initial wallpaper state not recorded")
            return 0.0, "Initial wallpaper state not recorded"

        # Get current wallpaper state
        current_state = self._get_wallpaper_state(controller)

        # Check if empty states
        if not self._initial_wallpaper_state and not current_state:
            logger.warning("Both states are empty, cannot determine if wallpaper changed")
            return 0.0, "Both states are empty, cannot determine if wallpaper changed"

        # Check if wallpaper has changed
        if current_state != self._initial_wallpaper_state:
            return 1.0, "Success"

        return 0.0, "Wallpaper has not changed"
