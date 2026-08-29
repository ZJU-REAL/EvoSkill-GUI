"""Mattermost email task implementation - send contract via email and create calendar event."""

from mobile_world.runtime.app_helpers import mail, mattermost
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MattermostEmailTask(BaseTask):
    """Mattermost email task - handle contract processing via Mattermost and email."""

    goal = "Sam has sent me a signed contract on Mattermost. Send it to our Legal (legal@company.com) through email. Include the tracking code. Send sam a quick confirmation when you're done. Thanks."
    snapshot_tag = "init_state"

    CONFIRMATION_CODE = "TT-POC-2025-BLPINE-042"

    FILE_NAME = "contract_signed-faeqaq54ojf6tb7oocpceiaeqw.pdf"
    EMAIL_ADDRESS = "legal@company.com"

    task_tags = {"lang-en"}

    app_names = {"Mattermost", "Mail"}

    def initialize_task_hook(self, controller: AndroidController) -> None:
        mattermost.start_mattermost_backend()

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        # to check if the task is successful, we need the mattermost backend to be running
        assert mattermost.is_mattermost_healthy()

        # check 1: the email is sent to legal@company.com and the attachment is the contract, subject contains the tracking code
        sent_email_info = mail.get_sent_email_info()
        if sent_email_info is None:
            return 0.0, f"No email sent: {sent_email_info}"
        if sent_email_info["to"] != "legal@company.com":
            return 0.0, f"Email sent to the wrong address: {sent_email_info['to']}"
        if (
            self.CONFIRMATION_CODE.lower() not in sent_email_info["subject"].lower()
            and self.CONFIRMATION_CODE.lower() not in sent_email_info["body"].lower()
        ):
            return (
                0.0,
                f"Subject or body does not contain the tracking code: {sent_email_info['subject']} {sent_email_info['body']}",
            )

        if (
            len(sent_email_info["attachments"]) != 1
        ):
            return 0.0, f"Attachment is not the contract: {sent_email_info['attachments']}"

        # check 2: the last message is sent from harry to sam from the postgres database
        latest_post = mattermost.get_latest_messages()[0]
        if (
            latest_post[4] != mattermost.HARRY_ID
            or latest_post[5] != mattermost.SAM_HARRY_CHANNEL_ID
        ):
            # we only check the last message from harry to sam in the sam_harry channel. we don't handle the content.
            return 0.0, "Last message is not from harry to sam in the sam_harry channel"
        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        mattermost.stop_mattermost_backend()
