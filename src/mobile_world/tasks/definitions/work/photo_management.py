"""Mattermost email task implementation - send contract via email and create calendar event."""

from mobile_world.runtime.app_helpers import system
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class PhotoManagementTask(BaseTask):
    """Photo management task - handle photo management."""

    task_tags = {"lang-en"}
    goal = "Find all my food pics from the past month and help me classify them into different folders named travel locations. You can find where I visited from calendar."
    snapshot_tag = "init_state"

    app_names = {"Gallery", "Calendar"}

    def initialize_task_hook(self, controller: AndroidController) -> None:
        # the snapshot has a bug, we need to activate adb keyboard
        controller.activate_adb_keyboard()

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        folders = system.get_file_list("/sdcard/DCIM")
        folders: list[str] = [f.lower() for f in folders]
        if "paris" not in folders or "tokyo" not in folders:
            return 0.0, "Paris or Tokyo folder is not found"
        paris_photos: list[str] = system.get_file_list("/sdcard/DCIM/Paris")
        tokyo_photos: list[str] = system.get_file_list("/sdcard/DCIM/Tokyo")

        if not (len(paris_photos) == 3 and len(tokyo_photos) == 4):
            return 0.0, "Wrongly classified photos"
        for p in paris_photos:
            if "PAR" not in p:
                return 0.0, f"Wrongly classified photos: {p}"
        for p in tokyo_photos:
            if "TOK" not in p:
                return 0.0, f"Wrongly classified photos: {p}"
        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
