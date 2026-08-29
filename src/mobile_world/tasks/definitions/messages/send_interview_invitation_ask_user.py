"""Send interview invitation task implementation."""

from loguru import logger

from mobile_world.runtime.app_helpers.system import check_sms_via_adb
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SendInterviewInvitationAskUserTask(BaseTask):
    task_tags = {"agent-user-interaction", "lang-en"}
    goal = 'Send a message to Kevin to information him "Your interview is scheduled for tomorrow morning at 10:30 AM".'

    correct_phone_number = "15551234567"
    expected_message_partial = "Your interview is scheduled for tomorrow morning at 10:30 AM"

    app_names = {
        "Messages",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize the messages task by resetting the Messages app and setting up contacts."""

        self.relevant_information = f"The phone number of Kevin is {self.correct_phone_number}. "
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """
        Check if task is successful - SMS should be sent to Kevin (phone: 15551234567) with content:
        "Your interview is scheduled for tomorrow morning at 10:30 AM."

        Uses ADB to check the SMS database directly.
        """
        self._check_is_initialized()

        # Check if SMS with expected content was sent to the correct phone number
        result = check_sms_via_adb(
            controller,
            phone_number=self.correct_phone_number,
            content=self.expected_message_partial,
        )

        if result:
            logger.info(
                f"Successfully found SMS to {self.correct_phone_number} with correct content"
            )
            return 1.0, "success"
        else:
            return 0.0, f"SMS to {self.correct_phone_number} with correct content not found"
