from loguru import logger

from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.app_helpers.system import enable_auto_time_sync, reset_chrome
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SearchTopInfoAskUserTask(BaseTask):
    """Search for top information in a specific field and send email with the information."""

    task_tags = {"agent-user-interaction", "lang-en"}

    goal = (
        "Search for the recent news in the field I am interested, "
        "and send an email to Kevin with a subject line that includes the field name "
        "and the following message:\n"
        "Here is the recent news in the [field name] field:\n"
        "[One sentence summary of the recent news you found]"
    )

    # Expected email details - will be provided by user agent
    correct_recipient = "kevin@example.com"
    interest_field = "gui agent"
    expected_phrase = f"Here is the recent news in the {interest_field} field"

    app_names = {"Chrome", "Mail"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        try:
            if not enable_auto_time_sync(controller):
                return False

            reset_chrome(controller)

            self.relevant_information = (
                f"The field I am interested in is {self.interest_field}. "
                f"Kevin's email address is {self.correct_recipient}."
                f"I do not have any preferences for the news content. Just search for the most top information in the field recently."
            )
            return True
        except Exception as e:
            logger.error(f"Initialize Chrome task failed: {e}")
            return False

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        logger.info("Checking for sent email...")
        email = get_sent_email_info()

        if email is None:
            logger.info("No email found")
            return 0.0, "No email found"

        logger.info(f"Found email - To: {email.get('to')}, Subject: {email.get('subject')}")

        if email["to"].lower() != self.correct_recipient.lower():
            logger.info(f"Email sent to wrong recipient: {email['to']}")
            logger.info(f"Expected recipient: {self.correct_recipient}")
            return 0.0, f"Email sent to wrong recipient: {email['to']}"

        email_subject = email.get("subject", "")
        field_keywords = self.interest_field.lower().split()
        subject_lower = email_subject.lower()
        if not all(keyword in subject_lower for keyword in field_keywords):
            logger.info(f"Email subject does not contain required keywords: {self.interest_field}")
            logger.info(f"Email subject: {email_subject}")
            return (
                0.0,
                f"Email subject does not contain required keywords: {self.interest_field}",
            )

        email_body = email.get("body", "")
        logger.info(f"Email body: {email_body}")

        if not email_body or len(email_body.strip()) < 10:
            logger.info("Email body is empty or too short")
            return 0.0, "Email body is empty or too short"

        if self.expected_phrase.lower() not in email_body.lower():
            logger.info(f"Email body does not contain expected phrase: '{self.expected_phrase}'")
            return 0.0, f"Email body does not contain expected phrase: '{self.expected_phrase}'"

        return 1.0, "Success"
