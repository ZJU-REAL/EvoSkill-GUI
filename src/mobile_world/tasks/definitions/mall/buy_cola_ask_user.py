"""Buy sugar-free cola and ship to work address task."""

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


class BuySugarFreeColaWorkAddressAskUserTask(BaseTask):
    """Buy a box of sugar-free cola and ship to work address (not home address)."""

    task_tags = {"agent-user-interaction", "lang-cn"}

    goal = "帮我在淘店上买一箱无糖可乐，寄到我这次上班的地址，不要寄错到家里"
    snapshot_tag = "init_state"

    CONFIG = MallConfig(showSplashAd=True, requireLogin=False)

    # Expected work address information
    EXPECTED_PROVINCE = "浙江省"
    EXPECTED_CITY = "杭州市"
    EXPECTED_AREA = "余杭区"
    EXPECTED_ADDR = "阿里巴巴西溪C园区"

    # Expected recipient information
    EXPECTED_RECEIVER = "dylan"
    EXPECTED_MOBILE = "04785907777"

    def __init__(self, params: dict[str, Any] = None):
        super().__init__(params)

    app_names = {
        "Taodian",
    }

    def initialize_task_hook(self, controller: AndroidController) -> None:
        """Initialize task - set mall config."""

        # Use Chinese for user-facing information (since template is in Chinese)
        self.relevant_information = f"我的姓名是{self.EXPECTED_RECEIVER}，手机号是{self.EXPECTED_MOBILE}。我这次上班的地址是{self.EXPECTED_PROVINCE}{self.EXPECTED_CITY}{self.EXPECTED_AREA}{self.EXPECTED_ADDR}。"

        set_config(self.CONFIG)

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        data = get_recent_callback_content(1)
        if len(data) == 0:
            return 0.0, "No callback data found"
        data = data[0]

        if data.get("task_name") != "提交订单":
            return 0.0, "Conducted action type on taodian is wrong "

        product_info = data.get("product_info", [])
        if len(product_info) != 1:
            return 0.0, "Product info length does not match"

        product = product_info[0]
        prod_name = product.get("prodName", "")
        if "无糖可乐" not in prod_name:
            return 0.0, "Product name does not contain '无糖可乐'"

        sku_name = product.get("skuName", "")
        if "箱" not in prod_name and "箱" not in sku_name:
            return 0.0, "Product is not a box (一箱)"

        if product.get("prodCount", 0) != 1:
            return 0.0, "Product count is invalid"

        address_info = data.get("address_info")
        if address_info is None:
            return 0.0, "Address info is missing"

        if address_info.get("province") != self.EXPECTED_PROVINCE:
            return 0.0, "Address province does not match"
        if address_info.get("city") != self.EXPECTED_CITY:
            return 0.0, "Address city does not match"
        if address_info.get("area") != self.EXPECTED_AREA:
            return 0.0, "Address area does not match"

        addr = address_info.get("addr", "")
        if "阿里巴巴西溪" not in addr or ("C园区" not in addr and "C区" not in addr):
            return 0.0, "Address does not match work address"

        if address_info.get("receiver") != self.EXPECTED_RECEIVER:
            return 0.0, "Receiver name does not match"
        if address_info.get("mobile") != self.EXPECTED_MOBILE:
            return 0.0, "Mobile number does not match"

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        clear_config()
        clear_callback_files(controller.device)
        return True
