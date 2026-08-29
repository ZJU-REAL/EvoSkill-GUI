from loguru import logger

from mobile_world.runtime.app_helpers.system import (
    check_contact_via_adb,
    enable_auto_time_sync,
    reset_maps,
)
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class GoogleMapsAlibabaPhoneContactAskUserTask(BaseTask):
    """Use Google Maps to find Alibaba's phone number and create a contact."""

    goal = "Find the Kevin's componany phone number using the google map, and based on that, create a new contact named Kevin Zhang with the company."

    expected_name = "Kevin Zhang"
    expected_phone = "+86 571 85022088"
    expected_company = "alibaba"

    task_tags = {"lang-en", "agent-user-interaction"}

    app_names = {"Maps", "Contacts"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        self.relevant_information = (
            "Kevin's company is Alibaba Hangzhou headquarters in Binjiang District."
        )

        try:
            reset_maps(controller)
            return True
        except Exception as e:
            logger.error(f"Initialize Google Maps task failed: {e}")
            return False

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        # Check if the contact exists with correct information
        if check_contact_via_adb(
            controller, self.expected_name, self.expected_phone, self.expected_company
        ):
            logger.info(
                f"Contact verification successful: {self.expected_name} with phone {self.expected_phone} and company containing {self.expected_company}"
            )
            return 1.0, "success"
        else:
            logger.warning(
                f"Contact verification failed: expected {self.expected_name}, {self.expected_phone}, company containing {self.expected_company}"
            )
            return 0.0, "contact verification failed"
