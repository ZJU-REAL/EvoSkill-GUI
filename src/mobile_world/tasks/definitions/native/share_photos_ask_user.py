"""Share photos task implementation - find flowers pictures and send via email."""

import time
from pathlib import Path

from loguru import logger

from mobile_world.runtime.app_helpers import mail
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SharePhotosAskUserTask(BaseTask):
    """Share photos ask user task - find flowers pictures in gallery and send via email."""

    task_tags = {"agent-user-interaction", "lang-en"}

    goal = 'Send some photos to Kevin via email, with text "Here are some pictures for you." '

    # Required image files (flowers pictures)
    REQUIRED_IMAGES = ["image1.jpeg", "image2.jpeg", "image3.jpeg", "image4.jpeg"]
    EMAIL_ADDRESS = "kevin_zhang@example.com"
    EMAIL_TEXT = "Here are some pictures for you."

    app_names = {"Gallery", "Mail"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize task - push all images from assets to device."""

        self.relevant_information = (
            f"Kevin's email address is {self.EMAIL_ADDRESS}. His full name is Kevin Zhang."
            f"The photos can be found in the Gallery app."
            f"You want to send all flowers pictures to Kevin via email."
            f"Once GUI agent let you determine the photos to send, you must require the agent to first summarize all photos categories in the Gallery app."
            f"Before the agent describe the photos categories, you must pretend you don't know which photos should be sent."
            f"If the agent provide the list of photos categories, you must answer to agent you will send all flowers pictures to Kevin via email."
        )
        # Get path to assets directory
        current_dir = Path(__file__).parent
        assets_dir = current_dir / "assets"

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
        required_set = set(self.REQUIRED_IMAGES)
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
        """Check if the share photos task was completed successfully."""
        self._check_is_initialized()

        # Check if email was sent
        sent_email_info = mail.get_sent_email_info()

        if sent_email_info is None:
            return 0.0, "No email sent"

        # Check 1: Email sent to correct address
        if sent_email_info["to"] != self.EMAIL_ADDRESS:
            return (
                0.0,
                f"Email sent to wrong address: {sent_email_info['to']} (expected: {self.EMAIL_ADDRESS})",
            )

        # Check 2: Email body contains required text
        if self.EMAIL_TEXT.lower() not in sent_email_info["body"].lower():
            return 0.0, f"Email body does not contain required text: '{self.EMAIL_TEXT}'"

        # Check 3: Email has all required attachments
        if len(sent_email_info["attachments"]) != len(self.REQUIRED_IMAGES):
            return (
                0.0,
                f"Wrong number of attachments: {len(sent_email_info['attachments'])} (expected: {len(self.REQUIRED_IMAGES)})",
            )

        # Check that all required images are attached
        attachment_names = {att["name"] for att in sent_email_info["attachments"]}
        required_names = set(self.REQUIRED_IMAGES)

        if attachment_names != required_names:
            missing = required_names - attachment_names
            extra = attachment_names - required_names
            msg = "Attachment mismatch."
            if missing:
                msg += f" Missing: {missing}."
            if extra:
                msg += f" Extra: {extra}."
            return 0.0, msg

        return 1.0, "success"
