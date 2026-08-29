from mobile_world.runtime.app_helpers.mall import clear_callback_files, get_recent_callback_content
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class CartManagementTask(BaseTask):
    """Checkout an item from a mall."""

    goal = "最近天气变冷了，请帮我从淘店app的购物车中删除所有短袖T恤衬衫。如果需要登录，可以通过短信验证码登录。"
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

    task_tags = {"lang-cn"}

    app_names = {
        "Taodian",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
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
