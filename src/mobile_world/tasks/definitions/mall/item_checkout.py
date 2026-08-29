from typing import Any

from mobile_world.runtime.app_helpers.mall import clear_callback_files, get_recent_callback_content
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class ItemCheckoutTask(BaseTask):
    """Checkout an item from a mall."""

    goal = "帮我在淘店下单购物车里的iphone 15 pro，寄到浙江省杭州市余杭区阿里巴巴西溪C区，收件人张先生，收件人电话13800138000。如需登录，可以通过短信验证码。在支付页面让我操作"

    task_tags = {"lang-cn"}

    app_names = {
        "Taodian",
    }

    @classmethod
    def generate_random_params(cls) -> dict[str, Any]:
        return {}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        data = get_recent_callback_content(1)
        if len(data) == 0:
            return 0.0, "No callback data found"
        data = data[0]
        if data["task_name"] != "提交订单":
            return 0.0, "Conducted action type on taodian is wrong "
        if len(data["product_info"]) != 1:
            return 0.0, "Product info length does not match"
        if data["product_info"][0]["prodId"] != "11":
            return 0.0, "Product id does not match"
        if data["product_info"][0]["prodName"] != "iPhone 15 Pro":
            return 0.0, "Product name does not match"
        if (
            data["address_info"]["mobile"] != "13800138000"
            or data["address_info"]["receiver"] != "张先生"
            or data["address_info"]["addr"] != "阿里巴巴西溪C区"
            or data["address_info"]["province"] != "浙江省"
            or data["address_info"]["city"] != "杭州市"
            or data["address_info"]["area"] != "余杭区"
        ):
            return 0.0, "Address info does not match"
        return 1.0, "Success"

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        clear_callback_files(controller.device)
        return True
