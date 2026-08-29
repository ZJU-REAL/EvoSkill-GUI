"""List GitHub issues and send email with the list."""

from mobile_world.runtime.app_helpers import mcp as mcp_helper
from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.app_helpers.system import enable_auto_time_sync
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class ListGithubIssuesEmailTask(BaseTask):
    """List open issues from GitHub repository and send email with the list."""

    goal = (
        "Help me list the open issues from the google-research/android_world repository (only title and number), "
        "organize them into a simple todo list, with each line formatted as title: number, email to mike@gmail.com, "
        "subject as `Issues To Fix`, content as the obtained issues, if there are none then set the email content to `No open issues.`"
    )
    task_tags = {"agent-mcp", "lang-en"}

    OWNER = "google-research"
    REPO = "android_world"
    STATE = "open"
    EMAIL_ADDRESS = "mike@gmail.com"
    EMAIL_SUBJECT = "Issues To Fix"

    app_names = {"MCP-Github", "Mail", "Chrome"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        if not enable_auto_time_sync(controller):  # chrome needs auto time sync to work
            return False
        return True

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        open_issues = await mcp_helper.list_open_issues(
            owner=self.OWNER, repo=self.REPO, state=self.STATE
        )

        email = get_sent_email_info()
        if email is None:
            return 0.0, "No email sent"

        if email.get("to", "").lower() != self.EMAIL_ADDRESS.lower():
            return (
                0.0,
                f"Email sent to wrong address: {email.get('to')} (expected: {self.EMAIL_ADDRESS})",
            )

        if email.get("subject", "") != self.EMAIL_SUBJECT:
            return (
                0.0,
                f"Email subject incorrect: {email.get('subject')} (expected: {self.EMAIL_SUBJECT})",
            )

        email_body = email.get("body", "").strip().lower()
        for issue in open_issues:
            title = issue.get("title", "").lower()
            number = str(issue.get("number", "")).lower()
            if title not in email_body or number not in email_body:
                return 0.0, f'Issue "{title}" "{number}" not found in email body'

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        return True
