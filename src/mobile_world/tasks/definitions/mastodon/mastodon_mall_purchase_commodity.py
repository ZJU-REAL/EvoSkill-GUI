"""get purchase info from Mastodon and buy the commodity in the mall app."""

import time

from loguru import logger

from mobile_world.runtime.app_helpers import mall, mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonMallPurchaseCommodityTask(BaseTask):
    goal = "我在mastodon上关注的jack分享了一个商品,请你在淘店app下单购买2双同款，收货地址为：广东省广州市天河区华景新城，收货人李四，收货人电话13800139999。"

    EXPECTED_PRODUCT_NAME = "运动休闲鞋"
    EXPECTED_PRODUCT_COUNT = 2
    EXPECTED_RECEIVER_NAME = "李四"
    EXPECTED_RECEIVER_PHONE = "13800139999"
    EXPECTED_RECEIVER_PROVINCE = "广东省"
    EXPECTED_RECEIVER_CITY = "广州市"
    EXPECTED_RECEIVER_AREA = "天河区"
    EXPECTED_RECEIVER_ADDRESS = "华景新城"

    task_tags = {"lang-cn"}

    app_names = {"Mastodon", "Taodian"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        try:
            mastodon.start_mastodon_backend()
            return True
        except Exception as e:
            logger.error(f"Failed to start Mastodon backend: {e}")
            return False

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """
        Check:
        - product name
        - product count
        - receiver name
        - receiver phone
        - receiver province
        - receiver city
        - receiver area
        - receiver address
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()
        time.sleep(1)

        try:
            callback_records = mall.get_recent_callback_content(1)
        except Exception:
            return 0.0, "Failed to retrieve callback content"

        if not callback_records:
            return 0.0, "No callback records were found."

        callback = callback_records[0]
        if callback.get("task_name") != "提交订单":
            return 0.0, "Unexpected task name in callback: expected '提交订单', got {task_name}"

        product_info = callback.get("product_info") or []
        if len(product_info) != 1:
            return 0.0, "Unexpected product info length: expected 1, got {length}"

        # check product name
        product = product_info[0]
        if product.get("prodName") != self.EXPECTED_PRODUCT_NAME:
            return (
                0.0,
                f"Product name mismatch: expected {self.EXPECTED_PRODUCT_NAME}, got {product.get('prodName')}",
            )

        # check product count
        prod_count = product.get("prodCount")
        try:
            prod_count_value = int(prod_count)
        except (TypeError, ValueError):
            prod_count_value = None

        if prod_count_value != self.EXPECTED_PRODUCT_COUNT:
            return (
                0.0,
                f"Product count mismatch: expected {self.EXPECTED_PRODUCT_COUNT}, got {prod_count}",
            )

        address = callback.get("address_info") or {}
        if not address:
            return 0.0, "Address info is missing from callback."

        # check receiver name
        if address.get("receiver") != self.EXPECTED_RECEIVER_NAME:
            return (
                0.0,
                f"Receiver name mismatch: expected {self.EXPECTED_RECEIVER_NAME}, got {address.get('receiver')}",
            )

        # check receiver phone
        if address.get("mobile") != self.EXPECTED_RECEIVER_PHONE:
            return (
                0.0,
                f"Receiver phone mismatch: expected {self.EXPECTED_RECEIVER_PHONE}, got {address.get('mobile')}",
            )

        # check receiver province
        if address.get("province") != self.EXPECTED_RECEIVER_PROVINCE:
            return (
                0.0,
                f"Receiver province mismatch: expected {self.EXPECTED_RECEIVER_PROVINCE}, got {address.get('province')}",
            )

        # check receiver city
        if address.get("city") != self.EXPECTED_RECEIVER_CITY:
            return (
                0.0,
                f"Receiver city mismatch: expected {self.EXPECTED_RECEIVER_CITY}, got {address.get('city')}",
            )

        # check receiver area
        if address.get("area") != self.EXPECTED_RECEIVER_AREA:
            return (
                0.0,
                f"Receiver area mismatch: expected {self.EXPECTED_RECEIVER_AREA}, got {address.get('area')}",
            )

        # check receiver detailed address
        if self.EXPECTED_RECEIVER_ADDRESS not in address.get("addr"):
            return (
                0.0,
                f"Receiver address mismatch: expected {self.EXPECTED_RECEIVER_ADDRESS}, got {address.get('addr')}",
            )

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        try:
            mastodon.stop_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to stop Mastodon backend: {e}")
            return False
        return True
