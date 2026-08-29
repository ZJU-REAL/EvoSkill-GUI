"""Take selfie and share task implementation."""

import os
import re

from loguru import logger

from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.controller import AndroidController
from mobile_world.runtime.utils.helpers import execute_adb
from mobile_world.tasks.base import BaseTask


def get_mediastore_images(controller: AndroidController) -> dict[str, dict]:
    """
    Get all images from MediaStore with their metadata.

    Returns:
        dict: {id: {name, path, date_added}} mapping
    """
    try:
        query_cmd = (
            f"adb -s {controller.device} shell content query "
            f"--uri content://media/external/images/media "
            f"--projection _id:_display_name:_data:date_added"
        )

        result = execute_adb(query_cmd, output=False)

        images_dict = {}
        if result.success and result.output:
            rows = [line for line in result.output.split("\n") if line.strip().startswith("Row:")]
            for row in rows:
                # Extract fields
                match_id = re.search(r"_id=(\d+)", row)
                match_name = re.search(r"_display_name=([^,\s]+)", row)
                match_path = re.search(r"_data=([^,\s]+)", row)
                match_added = re.search(r"date_added=(\d+)", row)

                if match_id and match_name:
                    image_id = match_id.group(1)
                    images_dict[image_id] = {
                        "name": match_name.group(1),
                        "path": match_path.group(1) if match_path else "",
                        "date_added": int(match_added.group(1)) if match_added else 0,
                    }

        logger.debug(f"Found {len(images_dict)} images in MediaStore")
        return images_dict
    except Exception as e:
        logger.warning(f"Error querying MediaStore: {e}")
        import traceback

        logger.debug(f"Traceback: {traceback.format_exc()}")
        return {}


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
        # Convert timestamp to milliseconds
        timestamp_ms = int(timestamp * 1000)

        # Query MediaStore for recent images with file paths
        # date_added is in seconds, date_modified is in seconds
        query_cmd = (
            f"adb -s {controller.device} shell content query "
            f"--uri content://media/external/images/media "
            f"--projection _id:_display_name:_data:date_added:date_modified "
            f'--where "date_added>{int(timestamp)}"'
        )

        result = execute_adb(query_cmd, output=False)

        photo_paths = []
        if result.success and result.output:
            # Parse rows to extract file paths
            rows = [line for line in result.output.split("\n") if line.strip().startswith("Row:")]
            logger.info(f"MediaStore query found {len(rows)} row(s)")
            for i, row in enumerate(rows):
                logger.debug(f"Row {i}: {row}")
                # Extract _data field which contains file path
                match_path = re.search(r"_data=([^,\s]+)", row)
                match_added = re.search(r"date_added=(\d+)", row)

                if match_path:
                    path = match_path.group(1)
                    # Double check the date_added timestamp
                    if match_added:
                        date_added = int(match_added.group(1))
                        logger.debug(
                            f"  Path: {path}, date_added: {date_added}, threshold: {int(timestamp)}"
                        )
                        # Strict filtering: only include if date_added is strictly greater than start timestamp
                        if date_added > int(timestamp):
                            photo_paths.append(path)
                    else:
                        # If can't verify timestamp, include it anyway
                        photo_paths.append(path)

            count = len(photo_paths)
            if count > 0:
                logger.info(f"Found {count} new photo(s) in MediaStore after timestamp {timestamp}")
                logger.info(f"New photo paths: {[os.path.basename(p) for p in photo_paths]}")
            else:
                logger.info(f"No new photos found in MediaStore after timestamp {timestamp}")
            return count, photo_paths

        logger.info("MediaStore query returned no results")
        return 0, []

    except Exception as e:
        logger.warning(f"Error querying MediaStore: {e}")
        import traceback

        logger.debug(f"Traceback: {traceback.format_exc()}")
        return 0, []


def check_email_with_attachment_sent(
    controller: AndroidController, recipient_email: str
) -> tuple[bool, list[str]]:
    """
    Check if an email with attachment (photo) was sent to a specific email address.

    Args:
        controller: AndroidController instance
        recipient_email: Email address to check (e.g., "jimmy.wang@example.com")

    Returns:
        tuple: (bool: email sent successfully, list: attachment filenames)
    """
    try:
        # Get sent email information using the mail helper
        email = get_sent_email_info()

        if email is None:
            logger.info("No sent email found")
            return False, []

        # Debug: Print full email structure
        logger.info(f"Email data keys: {list(email.keys())}")
        logger.info(f"Email data: {email}")

        # Check if email was sent to the correct recipient
        email_to = email.get("to", "").lower()
        if email_to != recipient_email.lower():
            logger.info(f"Email sent to wrong recipient: {email_to}, expected: {recipient_email}")
            return False, []

        # Collect attachment filenames for analysis
        attachment_filenames = []

        # Check if email has attachments (indicating a photo was shared)
        # Try multiple possible keys for attachments
        attachments = email.get("attachments", None)
        if attachments is None:
            attachments = email.get("attachment", None)
        if attachments is None:
            attachments = email.get("files", None)

        if not attachments:
            # Sometimes attachments might be indicated by a boolean flag
            has_attachment = email.get("hasAttachment", False) or email.get("has_attachment", False)
            if has_attachment:
                logger.info("Email has attachment flag set (assuming photo was sent)")
                return True, []

            logger.info(
                f"Email sent but no attachments field found. Available keys: {list(email.keys())}"
            )
            # Check if any key suggests attachments
            for key in email.keys():
                if "attach" in key.lower() or "file" in key.lower():
                    logger.info(f"Found potential attachment key: {key} = {email[key]}")
                    return True, []

            return False, []

        logger.info(f"Found attachments field: {attachments} (type: {type(attachments)})")

        # If attachments is a list, check each item
        if isinstance(attachments, list):
            if len(attachments) == 0:
                logger.info("Attachments list is empty")
                return False, []

            # Check if any attachment is an image
            has_image = False
            for i, attachment in enumerate(attachments):
                logger.info(f"Checking attachment {i}: {attachment} (type: {type(attachment)})")

                if isinstance(attachment, dict):
                    filename = attachment.get("filename", attachment.get("name", "")).lower()
                    content_type = attachment.get("contentType", attachment.get("type", "")).lower()
                    logger.info(f"  filename: {filename}, contentType: {content_type}")

                    # Collect filename for later analysis
                    if filename:
                        attachment_filenames.append(filename)
                else:
                    filename = str(attachment).lower()
                    content_type = ""
                    logger.info(f"  attachment string: {filename}")
                    if filename:
                        attachment_filenames.append(filename)

                # Check if it's an image file
                if any(
                    ext in filename for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]
                ) or any(
                    img_type in content_type
                    for img_type in ["image/jpeg", "image/png", "image/gif", "image/"]
                ):
                    has_image = True

            if has_image:
                return True, attachment_filenames
            else:
                return False, []
        else:
            # Attachments is not a list, might be a count or boolean
            logger.info(
                f"Attachments is not a list (type: {type(attachments)}, value: {attachments})"
            )
            if attachments:  # If truthy, assume it indicates attachments exist
                logger.info("Attachments field is truthy, assuming photo was sent")
                return True, []
            return False, []

    except Exception as e:
        logger.error(f"Error checking email: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        return False, []


class TakeSelfieAskUserTask1(BaseTask):
    task_tags = {"agent-user-interaction", "lang-en"}

    goal = "Take a selfie, and share it with Jimmy via email."

    correct_email = "jimmy.wang@example.com"

    app_names = {"Camera", "Mail", "Gallery"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize the camera task by resetting the Camera app and recording initial state."""
        # Set up information for user agent
        self.relevant_information = f"Jimmy's email address is {self.correct_email}. "

        # Record current timestamp for queries
        import time as time_module

        self._start_timestamp = time_module.time()
        logger.info(f"Task start timestamp: {self._start_timestamp}")

        # Record initial images in MediaStore
        self._initial_mediastore_images = get_mediastore_images(controller)
        logger.info(f"Initial MediaStore images: {len(self._initial_mediastore_images)} images")
        if self._initial_mediastore_images:
            sample_names = [
                img["name"] for img in list(self._initial_mediastore_images.values())[:5]
            ]
            logger.debug(f"Sample initial images: {sample_names}")

        return True

    def is_successful(self, controller: AndroidController) -> tuple[float, str]:
        """Check if the selfie task was completed successfully."""
        self._check_is_initialized()

        # Wait a bit for photo to be saved and email to be sent
        import time as time_module

        logger.info("Waiting for photos to be saved and email to be sent...")
        time_module.sleep(3)

        # Trigger media scan to ensure MediaStore is updated
        scan_cmd = f"adb -s {controller.device} shell am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file:///sdcard/Pictures"
        execute_adb(scan_cmd, output=False)
        time_module.sleep(0.5)

        # Initialize checking
        check_1_passed = False
        check_2_passed = False
        failure_reasons = []
        new_photo_names = []  # Store names of new photos

        # Get current images from MediaStore
        current_mediastore_images = get_mediastore_images(controller)
        logger.info(f"Current MediaStore images: {len(current_mediastore_images)} images")
        logger.info(f"Initial MediaStore images: {len(self._initial_mediastore_images)} images")

        # Find new images by comparing IDs
        new_image_ids = set(current_mediastore_images.keys()) - set(
            self._initial_mediastore_images.keys()
        )

        logger.info(f"New image IDs: {new_image_ids}")

        # Also check for images with date_added > start_timestamp
        for image_id, image_info in current_mediastore_images.items():
            if image_info["date_added"] > int(self._start_timestamp):
                if image_id not in new_image_ids:
                    logger.info(
                        f"Found image with recent date_added: {image_info['name']} (date_added={image_info['date_added']} > {int(self._start_timestamp)})"
                    )
                    new_image_ids.add(image_id)

        # Extract information about new images
        for image_id in new_image_ids:
            if image_id in current_mediastore_images:
                image_info = current_mediastore_images[image_id]
                new_photo_names.append(image_info["name"])

        if len(new_photo_names) > 0:
            check_1_passed = True
        else:
            failure_reasons.append("No new photo detected")

        email_sent, attachment_filenames = check_email_with_attachment_sent(
            controller, self.correct_email
        )

        if email_sent:
            match_found = False

            if attachment_filenames and new_photo_names:
                for attachment_name in attachment_filenames:
                    attachment_base = os.path.splitext(attachment_name)[0].lower()

                    for new_photo_name in new_photo_names:
                        new_photo_base = os.path.splitext(new_photo_name)[0].lower()

                        if attachment_name.lower() == new_photo_name.lower():
                            match_found = True
                            break

                        elif attachment_base == new_photo_base:
                            match_found = True
                            break

                        elif len(new_photo_base) > 5 and (
                            new_photo_base in attachment_base or attachment_base in new_photo_base
                        ):
                            match_found = True
                            break

                    if match_found:
                        break

                # Method 4: Check if attachment filename matches new image ID
                # (photo picker uses ID-based names like "1000000108.jpg")
                if not match_found:
                    for attachment_name in attachment_filenames:
                        attachment_base = os.path.splitext(attachment_name)[0].lower()
                        if attachment_base in new_image_ids:
                            match_found = True
                            logger.info(f"Matched attachment by image ID: {attachment_name} -> {attachment_base}")
                            break

                if match_found:
                    check_2_passed = True
                else:
                    failure_reasons.append("Email attachment does not match new photo")

            elif not attachment_filenames:
                if check_1_passed:
                    check_2_passed = True
                else:
                    failure_reasons.append("Cannot verify email attachment")

            elif not new_photo_names:
                failure_reasons.append("No new photos found")
        else:
            failure_reasons.append(f"No email sent to {self.correct_email}")

        if check_1_passed and check_2_passed:
            return 1.0, "Success: Photo taken and shared via email"
        else:
            reason = "Failed: " + "; ".join(failure_reasons)
            return 0.0, reason
