import re
import time
from pathlib import Path

import requests
from loguru import logger

from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.app_helpers.system import reset_chrome
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SendInvoiceWithInfoTask(BaseTask):
    """Send invoice PDF with exchange rate information via email."""

    goal = (
        "Send the invoice PDF file in the download directory to Mia. "
        "And attach the following information to the email: the total amount of the invoice and exchange to RMB according to the latest exchange rate. "
        "The format is total amount: xxx, exchange rate: xxx, total amount in RMB: xxx."
    )

    PDF_FILENAME = "invoice.pdf"

    # Mia's contact information (from contacts.vcf)
    RECIPIENT_NAME = "Mia Scott"
    RECIPIENT_EMAIL = "mia.scott@summitcloud.com"

    # Expected invoice total amount (from invoice.pdf)
    EXPECTED_TOTAL_AMOUNT = 102120.0  # USD

    task_tags = {"lang-en", "agent-user-interaction"}

    app_names = {"Docreader", "Files", "Mail", "Chrome"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize task by pushing the invoice PDF to the device."""

        self.relevant_information = (
            "Mia's email address can be found in the Contacts app. "
            "You can use Chrome browser to search for real-time exchange rates from USD to RMB/CNY. "
        )

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

            # Get current exchange rate for validation (required)
            try:
                self._current_exchange_rate = self._get_real_time_exchange_rate()
                if self._current_exchange_rate is None:
                    logger.error("Failed to get real-time exchange rate - task cannot proceed")
                    return False
                logger.info(f"Current USD to CNY exchange rate: {self._current_exchange_rate}")
            except Exception as e:
                logger.error(f"Failed to get current exchange rate: {e}")
                return False

            logger.info("Successfully pushed PDF to device")
            return True

        except Exception as e:
            logger.error(f"Initialize task failed: {e}")
            return False

    def _get_real_time_exchange_rate(self) -> float:
        """
        Get real-time USD to CNY exchange rate using a free API.
        Returns the exchange rate as a float.
        """
        try:
            # Try multiple free exchange rate APIs
            apis = [
                {"url": "https://api.exchangerate-api.com/v4/latest/USD", "path": ["rates", "CNY"]},
                {"url": "https://open.er-api.com/v6/latest/USD", "path": ["rates", "CNY"]},
            ]

            for api in apis:
                try:
                    response = requests.get(api["url"], timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        rate = data
                        for key in api["path"]:
                            rate = rate.get(key)
                            if rate is None:
                                break
                        if rate is not None:
                            return float(rate)
                except Exception as e:
                    logger.warning(f"Failed to get rate from {api['url']}: {e}")
                    continue

            # If all APIs fail, return None
            logger.warning("All exchange rate APIs failed")
            return None

        except Exception as e:
            logger.error(f"Error getting exchange rate: {e}")
            return None

    def is_successful(self, controller: AndroidController) -> tuple[float, str]:
        """
        Check if the task is successful.

        Validation criteria:
        1. Email was sent
        2. Email sent to correct address (mia.scott@summitcloud.com)
        3. Email has invoice.pdf attachment
        4. Email body contains the required format: "total amount: xxx, exchange rate: xxx, total amount in RMB: xxx"
        5. Exchange rate is reasonable (within expected range)
        6. Calculation is correct (amount * rate = RMB amount)
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
        if email_to.lower() != self.RECIPIENT_EMAIL.lower():
            logger.info(
                f"Email sent to wrong address: {email_to} (expected: {self.RECIPIENT_EMAIL})"
            )
            return (
                0.0,
                f"Email sent to wrong address: {email_to} (expected: {self.RECIPIENT_EMAIL})",
            )

        # ===== CHECK 3: Email has invoice.pdf attachment =====
        attachments = sent_email_info.get("attachments", [])
        logger.info(f"Email attachments: {attachments}")

        invoice_attached = False
        for attachment in attachments:
            # Handle both string and dict formats
            if isinstance(attachment, dict):
                attachment_name = attachment.get("name", "")
            else:
                attachment_name = str(attachment)

            if self.PDF_FILENAME.lower() in attachment_name.lower():
                invoice_attached = True
                break

        if not invoice_attached:
            logger.info(f"Email does not have {self.PDF_FILENAME} attachment")
            return 0.0, f"Email does not have {self.PDF_FILENAME} attachment"

        # ===== CHECK 4: Email body contains required format =====
        email_body = sent_email_info.get("body", "")
        logger.info(f"Email body: {email_body}")

        # Normalize the body text (remove extra spaces, newlines, etc.)
        body_normalized = email_body.lower().replace("\n", " ").replace("\r", " ")

        # Try to extract the required information using regex
        # Pattern: total amount: xxx, exchange rate: xxx, total amount in RMB: xxx
        # More flexible pattern to handle variations

        # Extract total amount (USD)
        amount_patterns = [
            r"total\s+amount[:\s]+(\$?\s*[\d,]+\.?\d*)",
            r"amount[:\s]+(\$?\s*[\d,]+\.?\d*)",
        ]

        total_amount = None
        for pattern in amount_patterns:
            match = re.search(pattern, body_normalized)
            if match:
                amount_str = match.group(1).replace("$", "").replace(",", "").strip()
                try:
                    total_amount = float(amount_str)
                    break
                except ValueError:
                    continue

        # Extract exchange rate
        rate_patterns = [
            r"exchange\s+rate[:\s]+([\d,]+\.?\d*)",
            r"rate[:\s]+([\d,]+\.?\d*)",
        ]

        exchange_rate = None
        for pattern in rate_patterns:
            match = re.search(pattern, body_normalized)
            if match:
                rate_str = match.group(1).replace(",", "").strip()
                try:
                    exchange_rate = float(rate_str)
                    break
                except ValueError:
                    continue

        # Extract RMB amount
        rmb_patterns = [
            r"(?:total\s+amount\s+in\s+rmb|in\s+rmb|rmb)[:\s]+([¥￥]?\s*[\d,]+\.?\d*)",
            r"rmb[:\s]+([¥￥]?\s*[\d,]+\.?\d*)",
            r"cny[:\s]+([¥￥]?\s*[\d,]+\.?\d*)",
        ]

        rmb_amount = None
        for pattern in rmb_patterns:
            match = re.search(pattern, body_normalized)
            if match:
                rmb_str = match.group(1).replace("¥", "").replace("￥", "").replace(",", "").strip()
                try:
                    rmb_amount = float(rmb_str)
                    break
                except ValueError:
                    continue

        logger.info(
            f"Extracted: total_amount={total_amount}, exchange_rate={exchange_rate}, rmb_amount={rmb_amount}"
        )

        if total_amount is None or exchange_rate is None or rmb_amount is None:
            missing = []
            if total_amount is None:
                missing.append("total amount")
            if exchange_rate is None:
                missing.append("exchange rate")
            if rmb_amount is None:
                missing.append("RMB amount")

            logger.info(f"Email body missing required information: {', '.join(missing)}")
            return 0.0, f"Email body missing required information: {', '.join(missing)}"

        # ===== CHECK 4.5: Total amount is correct =====
        # Verify the total amount matches the invoice
        amount_diff_percent = (
            abs(total_amount - self.EXPECTED_TOTAL_AMOUNT) / self.EXPECTED_TOTAL_AMOUNT * 100
        )

        if amount_diff_percent > 0.1:  # Allow 0.1% tolerance for minor variations
            logger.info(
                f"Total amount is incorrect: {total_amount} "
                f"(expected: {self.EXPECTED_TOTAL_AMOUNT}, difference: {amount_diff_percent:.2f}%)"
            )
            return (
                0.0,
                f"Total amount is incorrect: {total_amount} (expected: {self.EXPECTED_TOTAL_AMOUNT})",
            )

        # ===== CHECK 5: Exchange rate matches real-time rate =====
        # Allow small tolerance (0.05) for timing differences or rounding
        rate_diff = abs(exchange_rate - self._current_exchange_rate)
        if rate_diff > 0.05:
            logger.info(
                f"Exchange rate does not match real-time rate: {exchange_rate} "
                f"(current rate: {self._current_exchange_rate}, difference: {rate_diff:.4f})"
            )
            return (
                0.0,
                f"Exchange rate does not match real-time rate: {exchange_rate} "
                f"(current rate: {self._current_exchange_rate})",
            )

        # ===== CHECK 6: Calculation is correct based on real-time rate =====
        # Calculate expected RMB using the real-time exchange rate
        expected_rmb = total_amount * self._current_exchange_rate
        rmb_diff_percent = abs(rmb_amount - expected_rmb) / expected_rmb * 100

        # Allow 1% tolerance for rounding differences
        if rmb_diff_percent > 1.0:
            logger.info(
                f"RMB calculation error: {rmb_amount} != {expected_rmb:.2f} "
                f"(using real-time rate {self._current_exchange_rate}, difference: {rmb_diff_percent:.2f}%)"
            )
            return (
                0.0,
                f"RMB calculation error: {rmb_amount} != {expected_rmb:.2f} "
                f"(difference: {rmb_diff_percent:.2f}%)",
            )

        return 1.0, "success"
