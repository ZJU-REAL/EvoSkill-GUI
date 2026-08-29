import re
import time
from pathlib import Path

from loguru import logger

from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.app_helpers.system import reset_chrome
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class CheckInvoiceTask2(BaseTask):
    """Read the invoice PDF, calculate the total amount payable, and send via email."""

    goal = (
        "Read the invoice PDF file in the download directory. "
        "The customer has notified that payment will be made 45 days after the due date. "
        "Please recalculate the total amount payable and forward the result number to the customer via Email."
    )

    # The correct answer for validation
    CORRECT_ANSWER = 104417.7
    PDF_FILENAME = "invoice.pdf"
    EMAIL_ADDRESS = "accounting@globalent.com"

    task_tags = {"lang-en"}

    app_names = {"Docreader", "Files", "Mail"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize task by pushing the invoice PDF to the device."""
        try:
            # Reset Chrome first
            reset_chrome(controller)

            # Get path to the PDF in assets directory
            root_path = Path(__file__).resolve().parent
            local_pdf_path = root_path / "assets" / self.PDF_FILENAME

            logger.info(f"Looking for PDF at: {local_pdf_path}")

            # Check if PDF exists
            if not local_pdf_path.exists():
                logger.error(f"PDF file not found: {local_pdf_path}")
                return False

            # Define remote path on device (in Download directory for easy access)
            remote_pdf_path = f"/sdcard/Download/{self.PDF_FILENAME}"

            logger.info(f"Pushing PDF: {self.PDF_FILENAME} to {remote_pdf_path}")

            # Push the PDF to device
            result = controller.push_file(str(local_pdf_path), remote_pdf_path)

            if not result.success:
                logger.error(f"Failed to push PDF to device: {result.error}")
                return False

            # Wait a moment for file to be written
            time.sleep(0.5)

            # Trigger media scanner to make the PDF visible in file managers
            logger.info(f"Triggering media scan for {self.PDF_FILENAME}")
            controller.refresh_media_scan(remote_pdf_path)

            # Store the remote path for potential cleanup
            self._remote_pdf_path = remote_pdf_path

            logger.info("Successfully pushed PDF to device")
            return True

        except Exception as e:
            logger.error(f"Initialize task failed: {e}")
            return False

    def is_successful(self, controller: AndroidController) -> tuple[float, str]:
        """
        Check if the task is successful.

        Validation criteria:
        1. Email was sent
        2. Email sent to correct address (accounting@globalent.com)
        3. Email body contains the correct answer (104417.7)
        """
        self._check_is_initialized()

        # ===== CHECK 1: Email was sent =====
        logger.info("Checking for sent email...")
        sent_email_info = get_sent_email_info()

        if sent_email_info is None:
            logger.info("No email sent")
            return 0.0, "No email sent"

        # ===== CHECK 2: Email sent to correct address =====
        email_to = sent_email_info.get("to", "")
        if email_to.lower() != self.EMAIL_ADDRESS.lower():
            logger.info(f"Email sent to wrong address: {email_to} (expected: {self.EMAIL_ADDRESS})")
            return (
                0.0,
                f"Email sent to wrong address: {email_to} (expected: {self.EMAIL_ADDRESS})",
            )

        # ===== CHECK 3: Email body contains correct answer =====
        email_body = sent_email_info.get("body", "")
        logger.info(f"Email body: {email_body}")

        # Extract numbers from email body
        # Try to find the correct answer in various formats
        # Remove commas and spaces, then look for the number
        body_normalized = email_body.replace(",", "").replace(" ", "")

        # Try to extract all numbers with optional decimals
        numbers_found = re.findall(r"\d+\.?\d*", body_normalized)

        logger.info(f"Numbers found in email body: {numbers_found}")

        # Check if the correct answer appears in the email
        correct_answer_found = False
        for num_str in numbers_found:
            try:
                num_float = float(num_str)
                # Check with small tolerance for floating point comparison
                if num_float == self.CORRECT_ANSWER:
                    correct_answer_found = True
                    break
            except ValueError:
                continue

        if not correct_answer_found:
            logger.info(f"Email body does not contain correct answer: {self.CORRECT_ANSWER}")
            return (
                0.0,
                f"Email body does not contain correct answer: {self.CORRECT_ANSWER}",
            )

        return 1.0, "success"
