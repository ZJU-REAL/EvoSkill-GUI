"""Manage multiple lists on Mastodon."""

import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonManageMultiListTask(BaseTask):
    goal = (
        "View my lists on Mastodon, delete all previously created lists, and create two new lists. "
        "One list named 'open' should allow only I followed users to reply and add users, whose username contains 'open'. "
        "Another list named 'cute' should allow only members of the list to reply, enable hide members in following, and add users, whose avatar is a dog or cat."
    )

    task_tags = {"lang-en"}

    EXPECTED_USERNAME = "test"

    EXPECTED_NEW_LIST_1_TITLE = "open"
    EXPECTED_NEW_LIST_1_REPLIES_POLICY = 1  # only following users can reply
    EXPECTED_NEW_LIST_1_MEMBERS = {"openCompany", "openUniversity"}
    EXPECTED_NEW_LIST_1_EXCLUSIVE = False

    EXPECTED_NEW_LIST_2_TITLE = "cute"
    EXPECTED_NEW_LIST_2_REPLIES_POLICY = 0  # only list members can reply
    EXPECTED_NEW_LIST_2_EXCLUSIVE = True  # hide members in following
    EXPECTED_NEW_LIST_2_MEMBERS = {"pupper", "kitty", "olivia"}

    REPLIES_POLICY_MAP = {
        "no one": 2,
        "followed": 1,
        "list": 0,
    }

    app_names = {
        "Mastodon",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        try:
            mastodon.start_mastodon_backend()
            return True
        except Exception as e:
            logger.error(f"Failed to start Mastodon backend: {e}")
            return False

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """
        check:
        - list "open" exists
            - replies_policy is the expected replies policy (1)
            - members are the expected members (openCompany, openUniversity)
            - exclusive is the expected exclusive (False)
        - list "cute" exists
            - replies_policy is the expected replies policy (0)
            - exclusive is the expected exclusive (True)
            - members are the expected members (pupper, kitty, olivia)
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()
        time.sleep(1)

        lists = mastodon.get_lists_by_username(self.EXPECTED_USERNAME)
        if lists is None:
            return 0.0, f"Failed to retrieve lists for user '{self.EXPECTED_USERNAME}'"

        # Check new list 'open'
        open_list = next(
            (lst for lst in lists if lst.get("title") == self.EXPECTED_NEW_LIST_1_TITLE), None
        )
        if not open_list:
            return 0.0, f"List '{self.EXPECTED_NEW_LIST_1_TITLE}' not found"

        # Check replies_policy for 'open' list
        if open_list.get("replies_policy") != self.EXPECTED_NEW_LIST_1_REPLIES_POLICY:
            return 0.0, (
                f"List '{self.EXPECTED_NEW_LIST_1_TITLE}' replies_policy mismatch. "
                f"Expected: {self.EXPECTED_NEW_LIST_1_REPLIES_POLICY}, Got: {open_list.get('replies_policy')}"
            )

        # Check exclusive for 'open' list
        if open_list.get("exclusive") != self.EXPECTED_NEW_LIST_1_EXCLUSIVE:
            return 0.0, (
                f"List '{self.EXPECTED_NEW_LIST_1_TITLE}' exclusive mismatch. "
                f"Expected: {self.EXPECTED_NEW_LIST_1_EXCLUSIVE}, Got: {open_list.get('exclusive')}"
            )

        # Check members of 'open' list
        open_members = open_list.get("members", [])
        if not open_members:
            return 0.0, f"List '{self.EXPECTED_NEW_LIST_1_TITLE}' has no members"

        open_members_set = {member.get("username") for member in open_members}
        if open_members_set != self.EXPECTED_NEW_LIST_1_MEMBERS:
            return 0.0, (
                f"List '{self.EXPECTED_NEW_LIST_1_TITLE}' members mismatch. "
                f"Expected: {self.EXPECTED_NEW_LIST_1_MEMBERS}, Got: {open_members_set}"
            )

        # Check new list 'cute'
        cute_list = next(
            (lst for lst in lists if lst.get("title") == self.EXPECTED_NEW_LIST_2_TITLE), None
        )
        if not cute_list:
            return 0.0, f"List '{self.EXPECTED_NEW_LIST_2_TITLE}' not found"

        # Check replies_policy for 'cute' list
        if cute_list.get("replies_policy") != self.EXPECTED_NEW_LIST_2_REPLIES_POLICY:
            return 0.0, (
                f"List '{self.EXPECTED_NEW_LIST_2_TITLE}' replies_policy mismatch. "
                f"Expected: {self.EXPECTED_NEW_LIST_2_REPLIES_POLICY}, Got: {cute_list.get('replies_policy')}"
            )

        # Check exclusive (hide members) for 'cute' list
        if cute_list.get("exclusive") != self.EXPECTED_NEW_LIST_2_EXCLUSIVE:
            return 0.0, (
                f"List '{self.EXPECTED_NEW_LIST_2_TITLE}' exclusive mismatch. "
                f"Expected: {self.EXPECTED_NEW_LIST_2_EXCLUSIVE}, Got: {cute_list.get('exclusive')}"
            )

        # Check members of 'cute' list
        cute_members = cute_list.get("members", [])
        if not cute_members:
            return 0.0, f"List '{self.EXPECTED_NEW_LIST_2_TITLE}' has no members"

        cute_members_set = {member.get("username") for member in cute_members}
        if cute_members_set != self.EXPECTED_NEW_LIST_2_MEMBERS:
            return 0.0, (
                f"List '{self.EXPECTED_NEW_LIST_2_TITLE}' members mismatch. "
                f"Expected: {self.EXPECTED_NEW_LIST_2_MEMBERS}, Got: {cute_members_set}"
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
