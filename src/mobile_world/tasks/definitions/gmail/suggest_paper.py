"""Suggest paper email task implementation."""

from pathlib import Path

from loguru import logger

from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.app_helpers.system import (
    reset_chrome,
)
from mobile_world.runtime.controller import AndroidController
from mobile_world.runtime.utils.helpers import execute_adb
from mobile_world.tasks.base import BaseTask


class SuggestPaperTask(BaseTask):
    goal = (
        "Reply to Tony's email asking for paper suggestions with a pdf of the ddpm paper (save the pdf to Download with the name `ddpm.pdf`)."
        "Mention the full name and the abstract of the paper in the email body."
    )

    correct_recipient = "tony101@email.com"
    attachment = "ddpm.pdf"
    correct_body = "denoising diffusion probabilistic models"
    abstract_keywords = ["langevin", "9.46", "3.17", "lsun", "256"]

    task_tags = {"lang-en"}

    app_names = {"Mail", "Chrome", "Files"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Inject test email and reset Mail app."""
        root_path = Path(__file__).resolve().parent
        local_json_path = root_path / "assets" / "suggestPaper.json"

        remote_json_path = "/sdcard/Android/data/com.gmailclone/files/state.json"

        if not local_json_path.exists():
            logger.error(f"Email state file not found: {local_json_path}")
            return False

        result = execute_adb(f"push {local_json_path} {remote_json_path}")
        if not result.success:
            logger.error(f"Failed to push email JSON to emulator: {result.error}")
            return False

        result1 = execute_adb("shell am force-stop com.gmailclone")
        result2 = execute_adb("shell am start -n com.gmailclone/.MainActivity")
        if not result1.success or not result2.success:
            logger.warning(
                f"Failed to restart Mail app: {result1.error if not result1.success else result2.error}"
            )

        reset_chrome(controller)

        logger.info("Successfully injected emails and restarted Mail app.")
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """Check if the task succeeded by verifying the paper suggestion email was sent as a reply with."""
        self._check_is_initialized()

        result = execute_adb("shell ls /sdcard/Download/ddpm.pdf")
        if not result.success:
            return 0.0, "No pdf found"
        email = get_sent_email_info()
        if email is None:
            return 0.0, "No email found"
        attachments = email["attachments"]
        if not email["subject"] == "RE: Literature Review Suggestions":
            return 0.0, "Wrong subject"
        if email["to"].lower() == self.correct_recipient.lower():
            contents = email["body"].lower()
            if self.correct_body not in contents:
                return 0.0, "Wrong body"
            for keyword in self.abstract_keywords:
                if keyword not in contents:
                    return 0.0, "Wrong abstract"
            if len(attachments) != 1 or attachments[0]["name"] != self.attachment:
                return 0.0, "Wrong attachments"

        return 1.0, "Correct email sent"
