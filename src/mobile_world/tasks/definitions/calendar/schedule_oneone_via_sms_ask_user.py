"""Schedule coffee time invitation from SMS to calendar task implementation."""

import time

from loguru import logger

from mobile_world.runtime.app_helpers.system import check_sms_via_adb
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class ScheduleOneOneViaSmsAskUserTask(BaseTask):
    """Receive one-on-one meeting invitation via SMS and notify the person in the conflict event via SMS."""

    task_tags = {"agent-user-interaction", "lang-en"}

    goal = (
        "I've received a one-on-one meeting invitation from my boss. "
        "Please check my calendar and reply 'OK' if it's clear. "
        "If there's a scheduling conflict, please notify the person in the conflict event by SMS: "
        "'Sorry, I can't attend the meeting.'"
    )

    # SMS sender and content
    sender_name = "Marry"
    sender_phone = "+15051234567"
    sms_content = "Hi! Are you available for a one-on-one meeting with me on October 20th at 9:10 AM? I'd like to discuss the project progress."

    # Expected reply message
    expected_reply = "Sorry, I can't attend the meeting"
    correct_phone_number = "16854269375"
    contact_name = "Sam Smith"

    app_names = {"Calendar", "Messages"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        try:
            self.relevant_information = (
                f"The name of my boss is {self.sender_name}. His phone number is {self.sender_phone}."
                f"The name of the person in the conflict event is {self.contact_name}. His phone number is {self.correct_phone_number}."
                f"Only the GUI agent ask you for the phone number of the {self.contact_name}, you should answer the correct phone number."
                f"If the GUI agent do not mention the name of the {self.contact_name}, you should refuse to answer."
            )
            logger.info(f"Injecting SMS from my boss ({self.sender_phone})")
            result = controller.simulate_sms(self.sender_phone, self.sms_content)

            if not result.success:
                logger.error(f"Failed to inject SMS: {result.error}")
                return False

            time.sleep(1)

            logger.info("Successfully injected one-on-one meeting invitation SMS")

            return True

        except Exception as e:
            logger.error(f"Initialize task failed: {e}")
            return False

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        sms_sent = check_sms_via_adb(
            controller,
            phone_number=self.correct_phone_number,
            content=self.expected_reply,
        )

        if not sms_sent:
            logger.info(
                f"SMS reply '{self.expected_reply}' to the person in the conflict event ({self.correct_phone_number}) not found"
            )
            return (
                0.0,
                f"SMS reply '{self.expected_reply}' to the person in the conflict event ({self.correct_phone_number}) not found",
            )

        logger.info(
            f"SMS reply '{self.expected_reply}' to the person in the conflict event ({self.correct_phone_number}) verified successfully"
        )
        return 1.0, "Success"
