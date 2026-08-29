"""admin get server info (database size)"""

import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonGetServerInfoTask(BaseTask):
    goal = "On mastodon, switch to owner account, then go to settings backend to query the database size, and post a toot to tell the result, use MB as the unit"

    EXPECTED_USERNAME = "owner"

    task_tags = {"lang-en"}

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
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()
        time.sleep(1)

        owner_toot = mastodon.get_latest_toots_by_username(self.EXPECTED_USERNAME, limit=1)
        if not owner_toot:
            return 0.0, f"Failed to get {self.EXPECTED_USERNAME} toots"
        toot_text = owner_toot[0]["text"]

        # get database size info
        database_content = mastodon.get_database_size()
        if not database_content:
            return 0.0, "Failed to get database size info"
        database_size = database_content["size_pretty"]

        # check database size in the owner toot
        if database_size not in toot_text:
            # remove the space, e.g. xx.xx MB -> xx.xxMB
            database_size_no_space = database_size.replace(" ", "")
            if database_size_no_space not in toot_text:
                return (
                    0.0,
                    f"The database size info not correct, expected: {database_size}, actual: {toot_text}",
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
