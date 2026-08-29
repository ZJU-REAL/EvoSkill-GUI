"""Calculate cart prices separately for me and roommate based on user-provided rules."""

import re
from typing import Any

from mobile_world.runtime.app_helpers.mall import (
    MallConfig,
    clear_callback_files,
    clear_config,
    set_config,
)
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class CalculateCartPricesByOwnerAskUserTask(BaseTask):
    """Calculate cart prices separately for me and roommate based on user-provided rules."""

    task_tags = {"agent-user-interaction", "lang-en"}
    goal = "Help me calculate the prices of items in the Taodian shopping cart separately for me and my roommate, tell me how much each person needs to pay. Answer in the format 'me/roommate:amount', separated by semicolons, no extra content or whitespace."
    snapshot_tag = "init_state"

    CONFIG = MallConfig(showSplashAd=True, requireLogin=False)

    # Expected classification rule from user
    EXPECTED_RULE = "t-shirt related items belong to my roommate, other items are mine"

    # Expected answer values
    EXPECTED_MY_AMOUNT = 16257.99
    EXPECTED_ROOMMATE_AMOUNT = 778.93

    def __init__(self, params: dict[str, Any] = None):
        super().__init__(params)
        self.classification_rule = self.EXPECTED_RULE

    app_names = {
        "Taodian",
    }

    def initialize_task_hook(self, controller: AndroidController) -> None:
        """Initialize task - set mall config and configure user agent."""

        self.relevant_information = (
            f"You need to calculate the prices of the items in the shopping cart separately for me and my roommate. "
            f"The classification rule is: '{self.classification_rule}'."
        )
        set_config(self.CONFIG)

    def _parse_amount(self, amount_str: str) -> float:
        """Parse amount string, handling comma separators."""
        # Remove commas and whitespace, then parse as float
        cleaned = amount_str.replace(",", "").replace("，", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            raise ValueError(f"Cannot parse amount: {amount_str}")

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        answer = controller.interaction_cache
        if not answer or str(answer).strip() == "":
            return 0.0, "interaction_cache is empty"

        answer = str(answer).strip()

        if ";" not in answer and "；" not in answer:
            return 0.0, "Answer does not contain semicolon separator"

        parts = re.split(r"[;；]", answer)
        parts = [p.strip() for p in parts if p.strip()]

        if len(parts) != 2:
            return 0.0, f"Answer does not contain exactly 2 parts. Found {len(parts)} parts"

        my_amount = None
        roommate_amount = None

        for part in parts:
            if ":" not in part and "：" not in part:
                return 0.0, f"Part does not contain colon separator: '{part}'"

            name_amount = re.split(r"[:：]", part, 1)
            if len(name_amount) != 2:
                return 0.0, f"Part format is incorrect: '{part}'"

            name = name_amount[0].strip()
            amount_str = name_amount[1].strip()

            try:
                amount = self._parse_amount(amount_str)
            except ValueError as e:
                return 0.0, f"Cannot parse amount in '{part}': {e}"

            name_lower = name.lower()
            if "me" in name_lower or "my" in name_lower:
                if my_amount is not None:
                    return 0.0, "Duplicate 'me' entry found"
                my_amount = amount
            elif "roommate" in name_lower:
                if roommate_amount is not None:
                    return 0.0, "Duplicate 'roommate' entry found"
                roommate_amount = amount
            else:
                return 0.0, f"Part name is incorrect. Expected 'me' or 'roommate', found: '{name}'"

        if my_amount is None:
            return 0.0, "Missing 'me' amount"
        if roommate_amount is None:
            return 0.0, "Missing 'roommate' amount"

        tolerance = 0.01
        if abs(my_amount - self.EXPECTED_MY_AMOUNT) > tolerance:
            return (
                0.0,
                f"My amount does not match. Expected {self.EXPECTED_MY_AMOUNT}, found {my_amount}",
            )

        if abs(roommate_amount - self.EXPECTED_ROOMMATE_AMOUNT) > tolerance:
            return (
                0.0,
                f"Roommate amount does not match. Expected {self.EXPECTED_ROOMMATE_AMOUNT}, found {roommate_amount}",
            )

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        clear_config()
        clear_callback_files(controller.device)
        return True
