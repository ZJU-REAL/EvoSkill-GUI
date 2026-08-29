"""Search Python repositories and send email with results."""

from mobile_world.runtime.app_helpers import mcp as mcp_helper
from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SearchPythonReposEmailTask(BaseTask):
    """Search Python repositories and send email with top 5 newest repos."""

    goal = (
        "I'm on the subway and want to find some Python open source projects to learn from. "
        "Help me search on GitHub for repositories with language:Python stars:>1000, "
        "select the most starred 5 repositories, format it as 'repo name -- repo link', "
        "organize them into the email content with line breaks between different repository information, "
        'set the email title to "Python Learning", and send it to mike@gmail.com'
    )
    task_tags = {"agent-mcp", "lang-en"}

    SEARCH_QUERY = "language:Python stars:>200000 sort:stars"  # as of 2025-11-28, the top 5 repositories have more than 200000 stars
    REPO_LIMIT = 5
    EMAIL_ADDRESS = "mike@gmail.com"
    EMAIL_SUBJECT = "Python Learning"

    app_names = {"MCP-Github", "Mail"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        return True

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        repos = await mcp_helper.search_repositories(
            query=self.SEARCH_QUERY, per_page=self.REPO_LIMIT
        )
        expected_lines = []
        for repo in repos:
            name = repo.get("full_name", repo.get("name", ""))
            html_url = repo.get("html_url", "")
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
        for line in expected_lines:
            if line.lower().strip() not in email_body.lower().strip():
                return 0.0, f"Repository not found in email body: {line[:50]}"

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        return True
