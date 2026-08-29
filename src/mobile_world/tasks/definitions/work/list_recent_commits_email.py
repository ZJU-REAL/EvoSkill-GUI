"""List recent GitHub commits and send email with the list."""

from mobile_world.runtime.app_helpers import mcp as mcp_helper
from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.app_helpers.system import enable_auto_time_sync
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class ListRecentCommitsEmailTask(BaseTask):
    """List recent commits from GitHub repository and send email with the list."""

    goal = (
        "Help me check the recent 3 commits summary from the google-research/android_world repository (including author and commit message), "
        "format each line as 'author: commit message' and email to mike@gmail.com, "
        'email subject as "Recent Commits"'
    )
    task_tags = {"agent-mcp", "lang-en"}

    OWNER = "google-research"
    REPO = "android_world"
    COMMIT_LIMIT = 3
    EMAIL_ADDRESS = "mike@gmail.com"
    EMAIL_SUBJECT = "Recent Commits"

    app_names = {"MCP-Github", "Mail", "Chrome"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        if not enable_auto_time_sync(controller):  # chrome needs auto time sync to work
            return False
        return True

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        commits_list = await mcp_helper.list_recent_commits(
            owner=self.OWNER, repo=self.REPO, limit=self.COMMIT_LIMIT
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
        for commit_line in commits_list:
            commit_line_lower = commit_line.lower().strip()

            # First try exact match
            if commit_line_lower in email_body:
                continue

            # If exact match fails, check if message part exists (more flexible)
            if ":" in commit_line:
                author_part, message_part = commit_line.split(":", 1)
                author_part = author_part.strip().lower()
                message_part = message_part.strip().lower()

                # Message is the core content, check if it exists in email body
                if message_part and message_part in email_body:
                    # Message found, but author might be different - this is acceptable
                    continue
                else:
                    return (
                        0.0,
                        f"Commit message not found in email body. Expected message: {message_part}, Full line: {commit_line}",
                    )
            else:
                return 0.0, f"Commit line not found in email body: {commit_line}"
        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        return True
