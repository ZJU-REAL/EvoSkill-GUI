"""Check depart time task implementation."""

import time

from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.app_helpers.system import get_sms_list_via_adb
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SMSManagement(BaseTask):
    goal = "Check all unread sms messages, delete spams, and provide a summary of recruitment messages to me via email by sending to dylan@gmail.com. Note I'm only interested in open data scientist role."

    key_numbers_to_delete = [
        "78901",  # paypal
        "56789",  # personal loan
        "34567",  # amazon
        "88999",  # walmart
    ]
    key_numbers_not_to_delete = [
        "AMAZON",
    ]

    task_tags = {"lang-en"}

    app_names = {"Messages", "Mail"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        time.sleep(3)
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """Check if the task was completed successfully."""
        self._check_is_initialized()

        sms_list = get_sms_list_via_adb(controller)
        addresses = [s.split("address=")[1].split(",")[0] for s in sms_list]
        for key_number in self.key_numbers_to_delete:
            if key_number in addresses:
                return 0.0, "Spam message found!"
        for key_number in self.key_numbers_not_to_delete:
            if key_number not in addresses:
                return 0.0, "Non-spam message accidentally deleted!"

        email_info = get_sent_email_info()
        if email_info is None:
            return 0.0, "Email was not sent!"
        if not (email_info["to"] == "dylan@gmail.com"):
            return 0.0, "Email was not sent to dylan@gmail.com"
        if "meta" not in email_info["body"].lower():
            return 0.0, "Email body does not contain recruitment information from Meta"
        if "data scientist" not in email_info["body"].lower():
            return 0.0, "Email body does not contain data scientist information"

        return 1.0
