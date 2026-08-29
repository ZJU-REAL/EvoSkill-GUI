"""Check meal event and ask user for contact information task implementation."""

from loguru import logger

from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class CheckMealEventAskUserTask(BaseTask):
    """Check calendar for meal events and email to ask if it can be canceled."""

    task_tags = {"agent-user-interaction", "lang-en"}

    goal = "Check next week's schedule. If there is a meal with someone, email them to ask if it can be canceled."

    # Contact information from the provided image
    correct_recipient = "sarah.martinez@greenfield.com"  # Sarah Martinez's email
    contact_name = "Sarah Martinez"

    app_names = {"Calendar", "Mail", "Contacts"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        self.relevant_information = (
            f"The contact information for Sarah Martinez can be found in the Contacts app."
        )

    def is_successful(self, controller: AndroidController) -> tuple[float, str]:
        self._check_is_initialized()

        email = get_sent_email_info()

        if email is None:
            logger.info("No email found")
            return 0.0, "No email found"

        email_to = email.get("to", "").lower()
        expected_recipient = self.correct_recipient.lower()
        message_content = email.get("body", "").lower()

        if email_to == expected_recipient and len(message_content) > 0:
            logger.info(f"Successfully found email sent to {self.correct_recipient}")
            return 1.0, "Success"
        else:
            logger.info(
                f"Email sent to wrong recipient: {email_to}, expected: {expected_recipient}"
            )
            return 0.0, f"Email sent to wrong recipient: {email_to}, expected: {expected_recipient}"
