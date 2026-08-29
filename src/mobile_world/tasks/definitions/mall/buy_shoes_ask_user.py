"""Buy black tennis shoes for brother and ship to school dormitory address."""

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


class BuyBlackTennisShoesBrotherAddressAskUserTask(BaseTask):
    """Buy black tennis shoes for brother and ship to school dormitory address."""

    task_tags = {"agent-user-interaction", "lang-en"}

    goal = "I want to buy a pair of black tennis shoes for my brother on TaoDian app and ship them directly to his school dormitory."
    snapshot_tag = "init_state"

    CONFIG = MallConfig(showSplashAd=True, requireLogin=False)

    # Expected address information
    EXPECTED_PROVINCE = "浙江省"
    EXPECTED_CITY = "杭州市"
    EXPECTED_AREA = "西湖区"
    EXPECTED_ADDR = "余杭塘路866号"

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

        self.relevant_information = (
            f"My brother's name is {self.EXPECTED_RECEIVER} and his mobile number is {self.EXPECTED_MOBILE}. "
            f"His school dormitory address is {self.EXPECTED_PROVINCE} {self.EXPECTED_CITY} {self.EXPECTED_AREA} {self.EXPECTED_ADDR}."
            f"No perference about shoes size, style or color, just buy a pair of black tennis shoes."
        )

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
        if "网球鞋" not in product.get("prodName", ""):
            return 0.0, "Product name does not contain '网球鞋'"

        if product.get("prodCount", 0) != 1:
            return 0.0, "Product count does not match"

        address_info = data.get("address_info")
        if address_info is None:
            return 0.0, "Address info is missing"

        if address_info.get("province") != self.EXPECTED_PROVINCE:
            return 0.0, "Address province does not match"
        if address_info.get("city") != self.EXPECTED_CITY:
            return 0.0, "Address city does not match"
        if address_info.get("area") != self.EXPECTED_AREA:
            return 0.0, "Address area does not match"
        if address_info.get("addr") != self.EXPECTED_ADDR:
            return 0.0, "Address does not match"

        if address_info.get("receiver", "").lower() != self.EXPECTED_RECEIVER.lower():
            return 0.0, "Receiver name does not match"
        if address_info.get("mobile") != self.EXPECTED_MOBILE:
            return 0.0, "Mobile number does not match"

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        clear_config()
        clear_callback_files(controller.device)
        return True
