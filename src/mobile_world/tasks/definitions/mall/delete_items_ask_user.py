"""Delete items ask user task implementation - selectively remove electronic products from shopping cart."""

from typing import Any

from loguru import logger

from mobile_world.runtime.app_helpers.mall import clear_callback_files, get_recent_callback_content
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class DeleteItemsAskUserTask(BaseTask):
    """Delete items ask user task - selectively remove electronic products from shopping cart."""

    task_tags = {"agent-user-interaction", "lang-en"}
    goal = "I want to remove some electronic products in the shopping cart of the TaoDian app."

    items_left_prod_ids = {
        "19",
        "12",
        "21",
        "10",
        "18",
        "22",
        "1",
        "15",
        "17",
        "7",
        "11",
        "16",
        "6",
        "14",
        "4",
        "9",
        "5",
        "3",
        "2",
        "13",
    }
    password = "password"

    electronic_products = ["iPhone 15 Pro", "Smart watch"]

    app_names = {
        "Taodian",
    }

    @classmethod
    def generate_random_params(cls) -> dict[str, Any]:
        return {}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize task - set up relevant information for the agent."""
        try:
            clear_callback_files(controller.device)

            self.relevant_information = (
                f"You want let the GUI agent delete {', '.join(self.electronic_products)} from the shopping cart of the TaoDian app."
                f"When the GUI agent asks about which electronic products should be deleted in the shopping cart, "
                f"you must require the agent to first list all products in the cart. "
                f"Before the agent lists all electronic products, you must pretend you don't know which electronic products should be deleted. "
                f"If the agent provide the list of electronic products, you must answer to agent with the correct answer: {', '.join(self.electronic_products)} should be deleted."
                f"If the agent ask you wether agree the login protocol, you must answer to agent with the correct answer: agree."
                f"If the agent ask you the password of TaoDian app, you should let the agent login with message verification code."
            )

            logger.info(f"Relevant information set: {self.relevant_information}")
            return True
        except Exception as e:
            logger.error(f"Initialize task failed: {e}")
            return False

    def is_successful(self, controller: AndroidController) -> tuple[float, str]:
        self._check_is_initialized()

        data = get_recent_callback_content(1)
        if len(data) == 0:
            return 0.0, "No callback data found"
        data = data[0]

        if data["task_name"] != "购物车删除选中":
            return 0.0, "Conducted action type on taodian is wrong "

        left_items_prod_ids = set([i["prodId"] for i in data["current_cart_items"]])
        if left_items_prod_ids != self.items_left_prod_ids:
            return 0.0, "Items left prod ids do not match"

        return 1.0, "Success"

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        clear_callback_files(controller.device)
        return True
