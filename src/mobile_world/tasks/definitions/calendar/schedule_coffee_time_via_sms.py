"""Schedule coffee time invitation from SMS to calendar task implementation."""

import time

from loguru import logger

from mobile_world.runtime.app_helpers.system import check_sms_via_adb
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class ScheduleCoffeeTimeViaSmsTask(BaseTask):
    """Receive coffee time invitation via SMS and schedule it on calendar."""

    goal = (
        "I've received a coffee time invitation via text message; please check the calendar."
        'If I am available in this time slot, reply "OK" and schedule a corresponding event on my calendar.'
        'Otherwise reply "Not available in this time slot."'
    )

    # SMS sender and content
    sender_name = "Marry"
    sender_phone = "+15051234567"
    sms_content = "Hi! Would you like to join me for a coffee time on October 20th at 9:10 AM? It will be about an hour. Looking forward to it!"

    # Expected reply message
    expected_reply = "Not available in this time slot"

    task_tags = {"lang-en"}

    app_names = {"Calendar", "Messages"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        try:
            logger.info(f"Injecting SMS from {self.sender_name} ({self.sender_phone})")
            result = controller.simulate_sms(self.sender_phone, self.sms_content)

            if not result.success:
                logger.error(f"Failed to inject SMS: {result.error}")
                return False

            time.sleep(1)

            logger.info("Successfully injected coffee time invitation SMS")

            return True

        except Exception as e:
            logger.error(f"Initialize task failed: {e}")
            return False

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        sms_sent = check_sms_via_adb(
            controller,
            phone_number=self.sender_phone,
            content=self.expected_reply,
        )

        if not sms_sent:
            logger.info(
                f"SMS reply '{self.expected_reply}' to Marry ({self.sender_phone}) not found"
            )
            return (
                0.0,
                f"SMS reply '{self.expected_reply}' to Marry ({self.sender_phone}) not found",
            )

        logger.info(
            f"SMS reply '{self.expected_reply}' to Marry ({self.sender_phone}) verified successfully"
        )
        return 1.0, "Success"
