"""Share a order info from mall to Mastodon."""

import os

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.app_helpers.mall import (
    MallConfig,
    clear_callback_files,
    clear_config,
    set_config,
)
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonMallShareOrderTask(BaseTask):
    goal = "在淘店中,找到我的订单中的手表商品,然后在mastodon发布一条推文介绍商品,内容包括商品名称,购买价格和商品图片。"

    EXPECTED_USERNAME = "test"
    EXPECTED_IMAGES = "watch.jpg"
    EXPECTED_PRODUCT_NAME = "智能手表"
    EXPECTED_PRICE = "1199"
    EXPECTED_IMAGES_PATH = (
        "/app/service/src/mobile_world/tasks/definitions/mastodon/assets/mallShare"
    )
    CONFIG = MallConfig(showSplashAd=True, requireLogin=False)
    task_tags = {"lang-cn"}

    app_names = {"Mastodon", "Taodian"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        try:
            mastodon.start_mastodon_backend()
            set_config(self.CONFIG)
            return True
        except Exception as e:
            logger.error(f"Failed to start Mastodon backend: {e}")
            return False

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """
        check:
        - toot text contains product name
        - toot text contains price
        - toot images are the expected images
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()

        # Check if header image matches expected image
        toots = mastodon.get_latest_toots_by_username(self.EXPECTED_USERNAME, limit=1)
        if not toots:
            return 0.0, f"No toots found for user: {self.EXPECTED_USERNAME}"
        toot = toots[0]

        toot_text = toot.get("text")
        # check product name
        if self.EXPECTED_PRODUCT_NAME.lower() not in toot_text.lower():
            return (
                0.0,
                f"Product name mismatch: {toot_text} does not contain {self.EXPECTED_PRODUCT_NAME}",
            )

        # check price
        if self.EXPECTED_PRICE.lower() not in toot_text.lower():
            return 0.0, f"Price mismatch: {toot_text} does not contain {self.EXPECTED_PRICE}"

        # check images
        toot_id = toot.get("id")
        images = mastodon.get_images_by_status_id(toot_id)
        if not images:
            return 0.0, f"No images found for toot: {toot_id}"

        toot_image_id = images[0].get("media_attachment_id")
        toot_image_name = images[0].get("file_name")
        toot_image_path = mastodon.get_toot_images_path(toot_image_id, toot_image_name)
        if not os.path.exists(toot_image_path):
            return 0.0, f"Image path not found: {toot_image_path}"

        expected_image_path = os.path.join(self.EXPECTED_IMAGES_PATH, self.EXPECTED_IMAGES)
        if not os.path.exists(expected_image_path):
            return 0.0, f"Expected image path not found: {expected_image_path}"

        toot_image_md5 = mastodon.compute_md5(toot_image_path)
        expected_md5 = mastodon.compute_md5(expected_image_path)
        if toot_image_md5 != expected_md5:
            toot_image_phash = mastodon.compute_phash(toot_image_path)
            expected_phash = mastodon.compute_phash(expected_image_path)
            if abs(toot_image_phash - expected_phash) > 5:
                return 0.0, "Perceptual hash does not match, image not matched"

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        clear_config()
        clear_callback_files(controller.device)
        try:
            mastodon.stop_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to stop Mastodon backend: {e}")
            return False
        return True
