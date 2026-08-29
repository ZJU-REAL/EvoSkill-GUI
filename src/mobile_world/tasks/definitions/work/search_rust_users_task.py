"""Search GitHub Rust users and send email."""

from mobile_world.runtime.app_helpers import mcp as mcp_helper
from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SearchRustUsersTask(BaseTask):
    """Search top 5 GitHub Rust users by followers and send email."""

    goal = (
        "I've been learning Rust recently, help me search on GitHub for active users related to rust, "
        'find the top 5 with the most followers, format their usernames and profile pages as "username: profile link" per line, '
        "email to mikeshow@gmail.com with the title 'top-5 rust users'"
    )

    task_tags = {"agent-mcp", "lang-en"}

    USER_LIMIT = 5
    EMAIL_ADDRESS = "mikeshow@gmail.com"
    EMAIL_SUBJECT = "top-5 rust users"

    app_names = {"MCP-Github", "Mail"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        return True

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        users = await mcp_helper.search_users(
            query="language:Rust", sort="followers", order="desc", per_page=self.USER_LIMIT
        )

        expected_lines = []
        for user in users:
            name = user.get("login", "")
            html_url = user.get("html_url", "")
            expected_lines.append(name)
            expected_lines.append(html_url)

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

        email_body = email.get("body", "").strip()

        for expected_line in expected_lines:
            if expected_line.lower().strip() not in email_body.lower().strip():
                return 0.0, f"Rust user {expected_line} not found in email body"

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        return True
