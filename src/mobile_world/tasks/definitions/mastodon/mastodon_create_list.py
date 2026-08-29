"""Create a list on Mastodon and add members to it."""

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonCreateListTask(BaseTask):
    goal = 'Create a list called "Family," only followed users can reply, and add my family members — Alex, Emma, and Jack'

    EXPECTED_USERNAME = "test"
    EXPECTED_LIST_TITLE = "Family"
    EXPECTED_LIST_MEMBERS = {"alex", "emma", "jack"}
    EXPECTED_REPLIES_POLICY = 1
    EXPECTED_EXCLUSIVE = False  # default value
    REPLIES_POLICY_MAP = {
        "no one": 2,
        "followed": 1,
        "list": 0,
    }

    task_tags = {"lang-en"}

    app_names = {
        "Mastodon",
    }

    @property
    def snapshot_tag(self) -> str | None:
        return "init_state"

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
        - list title is the expected title (Family)
        - list replies policy is the expected replies policy (followed)
        - list members are the expected members (Alex, Emma, and Jack)
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()

        lists = mastodon.get_lists_by_username(self.EXPECTED_USERNAME)
        if not lists:
            return 0.0, f"Lists not found for user '{self.EXPECTED_USERNAME}'"

        # check the list title
        list = next((list for list in lists if list.get("title") == self.EXPECTED_LIST_TITLE), None)
        if not list:
            return 0.0, f"List title not found: {list}"

        # check the list replies policy
        replies_policy = list.get("replies_policy")
        if replies_policy != self.EXPECTED_REPLIES_POLICY:
            return (
                0.0,
                f"List replies policy mismatch. Expected: {self.EXPECTED_REPLIES_POLICY}, Got: {replies_policy}",
            )

        # check the list members
        members = list.get("members")
        if not members:
            return 0.0, "No members found in list"

        members_set = {member.get("username") for member in members}
        if members_set != self.EXPECTED_LIST_MEMBERS:
            return (
                0.0,
                f"Members mismatch. Expected: {self.EXPECTED_LIST_MEMBERS}, Got: {members_set}",
            )

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        try:
            mastodon.stop_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to stop Mastodon backend: {e}")
        return True
