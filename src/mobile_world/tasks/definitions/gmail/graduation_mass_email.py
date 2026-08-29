"""Check email and send mass email task implementation."""

import datetime
from pathlib import Path

import pytz
from loguru import logger

from mobile_world.runtime.app_helpers.fossify_calendar import get_calendar_events
from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.app_helpers.system import enable_auto_time_sync
from mobile_world.runtime.controller import AndroidController
from mobile_world.runtime.utils.helpers import execute_adb
from mobile_world.tasks.base import BaseTask


class GraduationMassEmailTask(BaseTask):
    goal = (
        "Search up the UF academic calendar and find out the week that grades are due in the Spring 2026 semester."
        "Then, set a calendar event at 6pm on the Saturday of that week titled 'Graduation Party'"
        "Search my email for the list of students graduating from the math department this year."
        "Send an email to all the graduates with the subject 'Graduation Party' and body 'Don't forget about this year's graduation party! More details coming soon.' "
    )

    task_tags = {"lang-en"}

    app_names = {"Mail", "Chrome", "Calendar"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Inject test email and reset Mail app."""
        root_path = Path(__file__).resolve().parent
        local_json_path = root_path / "assets" / "graduationMassEmail.json"
        local_attachment_path = root_path / "assets" / "receipt.jpg"

        remote_json_path = "/sdcard/Android/data/com.gmailclone/files/state.json"
        remote_attachment_path = "/sdcard/Android/data/com.gmailclone/files/attachments/receipt.jpg"

        if not local_json_path.exists():
            logger.error(f"Email state file not found: {local_json_path}")
            return False

        result = execute_adb(f"push {local_json_path} {remote_json_path}")
        if not result.success:
            logger.error(f"Failed to push email JSON to emulator: {result.error}")
            return False

        result1 = execute_adb(
            f"push {local_attachment_path} {remote_attachment_path}", root_required=True
        )
        if not result1.success:
            logger.error(f"Failed to push attachment to emulator: {result1.error}")
            return False

        result2 = execute_adb("shell am start -n com.gmailclone/.MainActivity", root_required=True)
        if not result2.success:
            logger.warning(f"Failed to restart Mail app: {result2.error}")

        logger.info("Successfully injected emails and restarted Mail app.")
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        # # Check sent email
        email_info = get_sent_email_info()
        if email_info is None:
            return 0.0, "No email found"
        recipients = email_info["to"]
        attachments = email_info["attachments"]
        subject = email_info["subject"]
        body = email_info["body"]
        correct_recipients = [
            "bob@gmail.com",
            "alice@gmail.com",
            "dave@gmail.com",
            "carl@gmail.com",
        ]

        if len(attachments) == 0 and subject == "Graduation Party":
            if body == "Don't forget about this year's graduation party! More details coming soon.":
                for person in correct_recipients:
                    if person not in recipients:
                        logger.info("Incorrect email")
                        return 0.0
                logger.info("Correct email sent")
        else:
            logger.info("Incorrect email sent")

        # Check calendar
        calendar_info = get_calendar_events()
        time_zone = pytz.timezone("UTC")
        meet_time = time_zone.localize(datetime.datetime(2026, 5, 9, 18, 0, 0))
        meet_title = "Graduation Party"
        start_ts = int(meet_time.timestamp())

        for event in calendar_info:
            if event["title"] == meet_title:
                if event["start_ts"] == start_ts:
                    return 1.0

        logger.info("Incorrect calendar event")
        return 0.0
