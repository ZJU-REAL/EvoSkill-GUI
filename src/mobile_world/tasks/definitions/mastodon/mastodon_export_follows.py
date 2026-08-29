"""Export followers of a specific user on Mastodon."""

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.runtime.utils.helpers import execute_adb
from mobile_world.tasks.base import BaseTask


class MastodonExportFollowsTask(BaseTask):
    goal = "In Mastodon, export my follows in settings and save it as my_following.csv."

    EXPECTED_USERNAME = "test"
    EXPECTED_FOLLOWERS_FILE = "my_following.csv"
    EXPORT_DIRS = [  # common directories for export file
        "/sdcard/Download",
        "/storage/emulated/0/Download",
    ]

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

        last_error = None
        for export_dir in self.EXPORT_DIRS:
            result = execute_adb(f"adb -s {controller.device} shell ls {export_dir}")
            if result.success:
                if not result.output:
                    last_error = f"Directory {export_dir} is empty"
                    continue

                files = [f.strip() for f in result.output.strip().split("\n") if f.strip()]
                if self.EXPECTED_FOLLOWERS_FILE in files:
                    return 1.0
                else:
                    last_error = (
                        f"Export file '{self.EXPECTED_FOLLOWERS_FILE}' not found in {export_dir}"
                    )
                    continue
            else:
                last_error = f"Failed to list files in directory {export_dir}: {result.error}"
                continue

        return (
            0.0,
            last_error
            or f"Export file '{self.EXPECTED_FOLLOWERS_FILE}' not found in any common directory",
        )

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        try:
            mastodon.stop_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to stop Mastodon backend: {e}")
        return True
