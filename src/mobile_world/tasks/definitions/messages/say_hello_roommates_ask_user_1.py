"""Say hello to roommates task implementation."""

from loguru import logger

from mobile_world.runtime.app_helpers.system import check_contact_starred_via_adb, check_sms_via_adb
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SayHelloRoommatesAskUserTask1(BaseTask):
    task_tags = {"agent-user-interaction", "lang-en"}
    goal = "Add my new roommates contacts to favorites and text 'hello' to each of them."

    # Roommates information: name -> phone number mapping
    roommates = {
        "Ella King": "14676741503",
        "Grace Hall": "17746937409",
        "Sophia White": "16854269375",
    }
    expected_message_partial = "hello"

    app_names = {"Messages", "Contacts"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize the messages task by providing roommates information."""

        # Create relevant information string with all roommates' phone numbers
        roommate_info = []
        for name, phone in self.roommates.items():
            roommate_info.append(f"The phone number of {name} is {phone}.")

        self.relevant_information = "My roommates information: " + " ".join(roommate_info)
        self.relevant_information += "The contacts of my roommates are in the Contacts app."
        logger.info(f"Task initialized with roommates: {', '.join(self.roommates.keys())}")
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """
        Check if task is successful - ALL of the following must be true:
        1. ALL roommates' contacts are added to favorites (starred)
        2. SMS containing "hello" is sent to ALL roommates

        Current roommates and their phone numbers:
        - Ella: 14676741503
        - Grace: 17746937409
        - Sophia: 16854269375

        Uses ADB to check both contacts starred status and SMS database.
        Returns 1.0 if ALL requirements are met, 0.0 otherwise (all-or-nothing scoring).
        """
        self._check_is_initialized()

        all_starred = True
        all_sms_sent = True

        # Check each roommate
        for name, phone_number in self.roommates.items():
            # Check 1: Is contact starred (favorite)?
            is_starred = check_contact_starred_via_adb(controller, phone_number=phone_number)

            if not is_starred:
                all_starred = False

            # Check 2: Was SMS sent?
            sms_sent = check_sms_via_adb(
                controller,
                phone_number=phone_number,
                content=self.expected_message_partial,
            )

            if not sms_sent:
                all_sms_sent = False

        if all_starred and all_sms_sent:
            return 1.0, "success"
        else:
            return (
                0.0,
                "task failed, not all roommates are starred or not all roommates received 'hello' message",
            )
