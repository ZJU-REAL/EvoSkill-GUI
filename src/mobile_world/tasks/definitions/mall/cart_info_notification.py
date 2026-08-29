from loguru import logger

from mobile_world.runtime.app_helpers.mall import (
    MallConfig,
    clear_callback_files,
    clear_config,
    set_config,
)
from mobile_world.runtime.app_helpers.system import check_sms_via_adb
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class CartInfoNotificationTask(BaseTask):
    """Find items awaiting shipment and send SMS notification to recipient."""

    goal = "Find the items awaiting shipment in TaoDian and send an SMS reminder to the recipient, including the product name and order number, with no other text."

    recipient_phone = "13800138888"

    order_number = "639281475036294"

    product_names = ["经典白色T恤", "保湿面霜套装"]

    CONFIG = MallConfig(showSplashAd=True, requireLogin=False)

    task_tags = {"lang-en"}

    app_names = {"Taodian", "Messages"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        set_config(self.CONFIG)
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """
        Check if SMS was sent to the recipient with correct content.
        SMS should contain product names and order number.
        """
        self._check_is_initialized()

        try:
            result = check_sms_via_adb(
                controller,
                phone_number=self.recipient_phone,
                content=self.order_number,
            )

            if not result:
                return (
                    0.0,
                    f"SMS to {self.recipient_phone} with order number not found",
                )

            # Check if SMS content contains all product names
            for product_name in self.product_names:
                result = check_sms_via_adb(
                    controller,
                    phone_number=self.recipient_phone,
                    content=product_name,
                )
                if not result:
                    return (
                        0.0,
                        f"Product name '{product_name}' not found in SMS to {self.recipient_phone}",
                    )

            return (
                1.0,
                "Successfully found SMS to {self.recipient_phone} with order number and all product names",
            )

        except Exception as e:
            logger.error(f"Error checking SMS status via ADB: {e}")
            return 0.0, f"Error checking SMS status via ADB: {e}"

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        clear_config()
        clear_callback_files(controller.device)
        return True
