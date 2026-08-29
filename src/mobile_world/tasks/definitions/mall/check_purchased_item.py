from typing import Any

from loguru import logger

from mobile_world.runtime.app_helpers.mall import (
    MallConfig,
    clear_callback_files,
    clear_config,
    set_config,
)
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class CheckPuchasedItem(BaseTask):
    """Find items awaiting shipment and send SMS notification to recipient."""

    goal = "之前我给朋友在淘店上买了一双鞋，帮我看一下他脚多少尺码。请只回答一个整数, 不要返回任何其他文本."

    CORRECT_ANSWER = 42

    CONFIG = MallConfig(
        showSplashAd=True,
        requireLogin=False,
        mockOrders=[
            {
                "orderNumber": "639281475036294",
                "userId": "mashu001",
                "status": 3,
                "totalMoney": 1999.00,
                "actualTotal": 1999.00,
                "createTime": "2025-9-05 09:30:00",
                "orderItemDtos": [
                    {
                        "prodId": "11",
                        "prodName": "iPhone 15 Pro",
                        "pic": "/static/images/items2/unsplash-1695048133142-1a20484d2569.jpg",
                        "skuName": "256GB 原色钛金属",
                        "price": 1999.00,
                        "prodCount": 1,
                    }
                ],
            },
            {
                "orderNumber": "274958163074928",
                "userId": "mashu001",
                "status": 5,
                "totalMoney": 299.00,
                "actualTotal": 299.00,
                "createTime": "2025-09-27 15:20:00",
                "orderItemDtos": [
                    {
                        "prodId": "14",
                        "prodName": "运动休闲鞋",
                        "pic": "/static/images/items2/unsplash-1549298916-b41d501d3772.jpg",
                        "skuName": "42码 棕色",
                        "price": 299.00,
                        "prodCount": 1,
                    }
                ],
            },
        ],
    )

    task_tags = {"lang-cn"}

    app_names = {
        "Taodian",
    }

    @classmethod
    def generate_random_params(cls) -> dict[str, Any]:
        return {}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        set_config(self.CONFIG)
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """
        Check if SMS was sent to the recipient with correct content.
        SMS should contain product names and order number.
        """

        answer = controller.interaction_cache

        logger.info(f"Agent answer: {answer}")

        if answer is None:
            return 0.0, "No answer provided"

        # Strip whitespace and convert to string for comparison
        answer_str = str(answer).strip()

        try:
            # Try to parse as integer to handle numeric answers
            answer_int = int(answer_str)
        except (ValueError, TypeError):
            logger.warning(f"Could not parse answer as integer: {answer_str}")
            return 0.0, f"Invalid answer format: {answer_str} (expected integer)"

        if answer_int == self.CORRECT_ANSWER:
            return 1.0, "Task completed successfully"
        else:
            return 0.0, f"Incorrect answer: {answer_int} (expected: {self.CORRECT_ANSWER})"

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        clear_config()
        clear_callback_files(controller.device)
        return True
