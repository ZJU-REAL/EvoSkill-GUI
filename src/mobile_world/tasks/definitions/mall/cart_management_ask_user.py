from typing import Any

from mobile_world.runtime.app_helpers.mall import clear_callback_files, get_recent_callback_content
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class CartManagementAskUserTask(BaseTask):
    """Checkout an item from a mall."""

    task_tags = {"agent-user-interaction", "lang-en"}

    goal = "Please help me delete all short-sleeve items from the shopping cart in the TaoDian app. Log in using the password."
    items_left_prod_ids = {
        "10",
        "11",
        "12",
        "13",
        "14",
        "15",
        "16",
        "17",
        "18",
        "19",
        "21",
        "4",
        "6",
    }
    password = "password"

    app_names = {
        "Taodian",
    }

    @classmethod
    def generate_random_params(cls) -> dict[str, Any]:
        return {}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        self.relevant_information = f"My password of TaoDian app is: {self.password}."
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        data = get_recent_callback_content(1)
        if len(data) == 0:
            return 0.0, "No callback data found"
        data = data[0]

        if data["task_name"] != "购物车删除选中":
            return 0.0, "Conducted action type on taodian is wrong "

        left_items_prod_ids = set([i["prodId"] for i in data["current_cart_items"]]) - set(
            [i["prodId"] for i in data["items_to_delete"]]
        )
        if left_items_prod_ids != self.items_left_prod_ids:
            return 0.0, "Items left prod ids do not match"

        return 1.0, "Success"

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        clear_callback_files(controller.device)
        return True
