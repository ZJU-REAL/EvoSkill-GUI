"""Send zip files task implementation - compress files and send via email."""

from loguru import logger

from mobile_world.runtime.app_helpers import mail
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SendZipFilesAskUserTask2(BaseTask):
    """Send zip files task - compress files from past three months and send via email."""

    task_tags = {"agent-user-interaction", "lang-en"}
    goal = 'Compress the earliest 5 downloaded files into a single file, renamed as "documents.zip", email it to Kevin using `Mail` app with the list of compressed files, seprated by comma. No other text.'

    EMAIL_ADDRESS = "kevin_zhang@example.com"
    # Email should contain list of compressed files, comma separated
    EXPECTED_EMAIL_FILES = [
        "15_camera_backup_20231116.zip",
        "17_archive_20231229.zip",
        "02_music_collection_20240125.zip",
        "08_photos_vacation_sydney_20240130.zip",
        "19_documents_20240305.zip",
    ]
    # Expected zip file name
    EXPECTED_ZIP_NAME = "documents.zip"

    app_names = {"Files", "Mail"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize task - set up user agent for answering questions about Kevin's email."""

        self.relevant_information = f"The email address of Kevin is {self.EMAIL_ADDRESS}. The zip files are in the 'Download' folder."
        return True

    def is_successful(self, controller: AndroidController) -> tuple[float, str]:
        """Check if the send zip files task was completed successfully."""
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

        # Check 2: Email body contains all file names (comma separated)
        email_body = sent_email_info["body"].strip()
        logger.info(f"Email body: {email_body}")

        # Check if all required file names are mentioned in the email body
        missing_files = []
        for filename in self.EXPECTED_EMAIL_FILES:
            if filename not in email_body:
                missing_files.append(filename)

        if missing_files:
            return 0.0, f"Email body missing file names: {missing_files}"

        # Check 3: Email has at least one attachment
        if len(sent_email_info["attachments"]) == 0:
            return 0.0, "No attachments found in email"

        # Check 4: Verify attachment is named "documents.zip"
        documents_zip_found = False

        for attachment in sent_email_info["attachments"]:
            att_name = attachment["name"]
            logger.info(f"Found attachment: {att_name}")

            # Check if attachment name matches expected name
            if att_name == self.EXPECTED_ZIP_NAME:
                documents_zip_found = True
                return 1.0, "success"

        if not documents_zip_found:
            attachment_names = [att["name"] for att in sent_email_info["attachments"]]
            return (
                0.0,
                f"Attachment not named '{self.EXPECTED_ZIP_NAME}'. Found: {attachment_names}",
            )
