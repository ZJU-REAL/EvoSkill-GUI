"""Update contacts on Mastodon."""

import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.app_helpers.system import check_sms_via_adb, get_contacts_via_adb
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonUpdateContactsTask(BaseTask):
    goal = (
        "My friend Olivia has left new phone and email information in the latest post on Mastodon, "
        "please update the information to my contacts, and send a text message to Olivia, the content of the "
        "text message should be 'Hello, how are you'. Remember to set the email label to internet."
    )

    EXPECTED_USERNAME = "test"
    EXPECTED_CONTACTS = "Olivia Taylor"
    EXPECTED_PHONE_NUMBER = "5551234567"
    EXPECTED_EMAIL = "olivia@gmail.com"
    EXPECTED_EMAIL_TYPE = "internet"
    EXPECTED_SMS_CONTENT = "Hello, how are you"
    task_tags = {"lang-en"}

    app_names = {"Mastodon", "Contacts"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        try:
            mastodon.start_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to start Mastodon backend: {e}")
            return False
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """
        Check:
        - Contacts are updated
        - SMS is sent
        - SMS content is correct
        """
        self._check_is_initialized()

        # Ensure Mastodon backend is running
        assert mastodon.is_mastodon_healthy()
        time.sleep(1)

        contacts = get_contacts_via_adb(controller, name=self.EXPECTED_CONTACTS)
        if not contacts:
            return 0.0, f"No contacts found for user: {self.EXPECTED_CONTACTS}"

        contact = contacts[0]
        # check phone number
        for phone in contact.get("phones"):
            if mastodon.phone_number_strip(phone.get("number")) == mastodon.phone_number_strip(
                self.EXPECTED_PHONE_NUMBER
            ):
                break
        else:
            return (
                0.0,
                f"Phone number mismatch: {contact.get('phones')} != {self.EXPECTED_PHONE_NUMBER}",
            )

        # check email and type
        for email in contact.get("emails"):
            if (
                email.get("address") == self.EXPECTED_EMAIL
                and email.get("label").lower() == self.EXPECTED_EMAIL_TYPE.lower()
            ):
                break
        else:
            return 0.0, f"Email mismatch: {contact.get('emails')} != {self.EXPECTED_EMAIL}"

        # check SMS content
        sms_consistency = check_sms_via_adb(
            controller, self.EXPECTED_PHONE_NUMBER, self.EXPECTED_SMS_CONTENT
        )
        if not sms_consistency:
            return 0.0, f"SMS content mismatch: {self.EXPECTED_SMS_CONTENT}"

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        try:
            mastodon.stop_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to stop Mastodon backend: {e}")
        return True
