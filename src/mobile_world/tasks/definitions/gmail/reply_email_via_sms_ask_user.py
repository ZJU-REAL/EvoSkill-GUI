"""Reply email via SMS task implementation."""

from loguru import logger

from mobile_world.runtime.app_helpers.system import check_sms_via_adb
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class ReplyEmailViaSmsAskUserTask(BaseTask):
    task_tags = {"agent-user-interaction", "lang-en"}

    goal = "I received an email about the Next.js Conf. Please check my calendar. If I'm available, send the sender an SMS saying, 'I can attend the conference.' If not, reply with, 'Sorry, I can't attend.'"

    correct_phone_number = "17771234567"
    expected_message = "I can attend the conference"
    sender_name = "Vercel"

    app_names = {"Mail", "Calendar", "Messages"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Set up phone number information for user agent."""
        self.relevant_information = f"The phone number of the email sender is {self.correct_phone_number}. The sender name is {self.sender_name}. "
        logger.info("Successfully set up task information.")
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """
        Check if task is successful - SMS should be sent to the sender (phone: 17771234567)
        with content: "I can attend the conference."

        Uses ADB to check the SMS database directly.
        Note: Phone number matching is flexible to handle different formats (with/without country code).
        """
        self._check_is_initialized()

        # Try multiple phone number formats for matching
        # Format 1: Full number with country code (17771234567)
        # Format 2: Without country code (7771234567)
        phone_formats = [
            self.correct_phone_number,  # "17771234567"
            self.correct_phone_number[1:],  # "7771234567" (without leading 1)
        ]

        # Try each phone number format
        for phone_format in phone_formats:
            result = check_sms_via_adb(
                controller,
                phone_number=phone_format,
                content=self.expected_message,
            )

            if result:
                logger.info(f"Successfully found SMS to {phone_format} with correct content")
                return 1.0, "success"

        logger.info(
            f"SMS to {self.correct_phone_number} (or variants) with correct content not found"
        )
        return (
            0.0,
            f"SMS to {self.correct_phone_number} (or variants) with correct content not found",
        )
