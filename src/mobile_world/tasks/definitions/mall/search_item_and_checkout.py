from typing import Any

from mobile_world.runtime.app_helpers.mall import (
    MallConfig,
    clear_callback_files,
    clear_config,
    get_recent_callback_content,
    set_config,
)
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SearchItemAndCheckoutTask(BaseTask):
    """Checkout an item from a mall."""

    goal = "万圣节快到了，帮我在淘店下单买一套临时纹身，在支付页面让我操作"

    CONFIG = MallConfig(showSplashAd=True, requireLogin=False)

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
        self._check_is_initialized()

        data = get_recent_callback_content(1)
        if len(data) == 0:
            return 0.0, "No callback data found"
        data = data[0]
        if data["task_name"] != "提交订单":
            return 0.0, "Conducted action type on taodian is wrong "
        if (
            "万圣节" not in data["product_info"][0]["prodName"]
            or "临时纹身" not in data["product_info"][0]["prodName"]
        ):
            return 0.0, "Product name does not match"

        return 1.0, "Success"

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        clear_config()
        clear_callback_files(controller.device)
        return True
