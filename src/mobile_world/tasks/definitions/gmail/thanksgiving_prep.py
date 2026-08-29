"""Thanksgiving prep task involving chrome search, email send, calendar configuraiton."""

import datetime

import pytz
from loguru import logger

from mobile_world.runtime.app_helpers.fossify_calendar import get_calendar_events
from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.app_helpers.system import reset_chrome
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class ThanksgivingPrepTask(BaseTask):
    goal = (
        "Email me (user@gmail.com) a list of the flavoring ingredients needed to make Pecan pie with subject 'Pie shopping'."
        "You can browse the following link for reference: https://sallysbakingaddiction.com/my-favorite-pecan-pie-recipe/"
        "Then, set an 8 am calendar event titled 'Thanksgiving Shopping' one week before Thanksgiving 2025."
    )

    task_tags = {"lang-en"}

    app_names = {"Mail", "Chrome", "Calendar"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        reset_chrome(controller)
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        # Check sent email
        email_info = get_sent_email_info()
        if email_info is None:
            return 0.0, "No email found"
        recipients = email_info["to"]
        attachments = email_info["attachments"]
        subject = email_info["subject"]
        body = email_info["body"]
        ingredients = {"sugar", "corn syrup", "vanilla"}

        if len(attachments) == 0 and subject == "Pie shopping" and recipients == "user@gmail.com":
            for ingredient in ingredients:
                if ingredient not in body.lower():
                    logger.info("Incorrect email")
                    return 0.0, "incorrect email"

            logger.info("Correct email sent")
        else:
            logger.info("Incorrect email")
            return 0.0, "incorrect email"

        # Check calendar
        calendar_info = get_calendar_events()
        time_zone = pytz.timezone("UTC")
        meet_time = time_zone.localize(datetime.datetime(2025, 11, 20, 8, 0, 0))
        meet_title = "Thanksgiving Shopping"
        start_ts = int(meet_time.timestamp())

        for event in calendar_info:
            if event["title"] == meet_title:
                if event["start_ts"] == start_ts:
                    return 1.0, "success"

        logger.info("Incorrect calendar event")
        return 0.0, "incorrect calendar event"
