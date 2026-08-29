"""Send phone number via email task implementation."""

from loguru import logger

from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SendPhoneNumberAskUserTask(BaseTask):
    task_tags = {"agent-user-interaction", "lang-en"}

    goal = "Send Kevin's phone number (in message body) to Grace via email. "
    correct_recipient = "grace.hall@urbanedge.com"
    expected_phone_number = "15551234567"

    app_names = {"Mail", "Contacts"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize the task - no special setup needed for this task."""
        self.relevant_information = (
            f"The phone number of Kevin is {self.expected_phone_number}. "
            f"The Grace's email address can be found in the contacts app."
        )
        logger.info("Initializing send phone number task")
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """
        Check if task is successful - Email should be sent to Grace (grace.hall@urbanedge.com)
        with Kevin's phone number (15551234567) in the content.

        Uses get_sent_email_info to check the sent email.
        """
        self._check_is_initialized()

        email = get_sent_email_info()

        if email is None:
            logger.info("No email found")
            return 0.0, "no email found"

        # Check recipient
        if email["to"].lower() != self.correct_recipient.lower():
            logger.info(
                f"Email sent to wrong recipient: {email['to']}, expected: {self.correct_recipient}"
            )
            return 0.0, "email sent to wrong recipient"

        # Check if email body contains the phone number
        email_body = email.get("body", "")
        # Remove any formatting characters from both the body and expected number
        normalized_body = (
            email_body.replace("-", "").replace("(", "").replace(")", "").replace(" ", "")
        )
        normalized_phone = (
            self.expected_phone_number.replace("-", "")
            .replace("(", "")
            .replace(")", "")
            .replace(" ", "")
        )

        if normalized_phone not in normalized_body:
            logger.info(
                f"Email body does not contain expected phone number: {self.expected_phone_number}"
            )
            logger.info(f"Email body: {email_body}")
            return 0.0, "email body does not contain expected phone number"

        logger.info(
            f"Successfully found email to {self.correct_recipient} with correct phone number"
        )
        return 1.0, "success"
