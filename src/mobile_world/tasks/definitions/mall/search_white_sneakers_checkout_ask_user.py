"""Search and checkout white sneakers task with user interaction for shoe size."""

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


class SearchWhiteSneakersCheckoutAskUserTask(BaseTask):
    """Search and checkout white sneakers for daily commute with user-provided shoe size."""

    task_tags = {"agent-user-interaction", "lang-cn"}
    goal = "帮我在淘店上找一双白色的鞋，日常通勤穿的，按我平时穿的码下单，默认收件人和地址"
    snapshot_tag = "init_state"

    CONFIG = MallConfig(showSplashAd=True, requireLogin=False)

    # Expected shoe size from user (will be set during initialization)
    EXPECTED_SIZE = "39"  # Default value, user will provide this

    def __init__(self, params: dict[str, Any] = None):
        super().__init__(params)
        self.shoe_size = self.EXPECTED_SIZE

    app_names = {
        "Taodian",
    }

    def initialize_task_hook(self, controller: AndroidController) -> None:
        """Initialize task - set mall config and configure user agent."""
        set_config(self.CONFIG)

        self.relevant_information = f"If anyone asks you about your shoe size or what size you wear, you need to answer '{self.shoe_size}'. "
        return True

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
        if "白色" not in prod_name:
            return 0.0, "Product name does not contain '白色'"
        sku_name = product.get("skuName", "")
        if self.shoe_size not in sku_name:
            return 0.0, "SKU name (size) does not match user-provided size"

        if product.get("prodCount", 0) != 1:
            return 0.0, "Product count does not match"

        address_info = data.get("address_info")
        if address_info is None:
            return 0.0, "Address info is missing"

        required_fields = ["receiver", "mobile", "addr", "province", "city", "area"]
        missing_fields = [field for field in required_fields if not address_info.get(field)]
        if missing_fields:
            return 0.0, f"Address info is incomplete. Missing fields: {missing_fields}"

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        clear_config()
        clear_callback_files(controller.device)
        return True
