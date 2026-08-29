"""Download GitHub repository README and send via email."""

from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class DownloadReadmeTask(BaseTask):
    """Download README from GitHub repository and send via email."""

    goal = "Download the README content from the repository google-research/android_world and send an email to mike@gmail.com with the subject `aw_readme notes for macos` about the notes for macos from the README when setting up the environment."
    task_tags = {"agent-mcp", "lang-en"}

    OWNER = "google-research"
    REPO = "android_world"
    EMAIL_ADDRESS = "mike@gmail.com"
    EMAIL_SUBJECT = "aw_readme notes for macos"
    MACOS_KEYWORDS = [
        "https://github.com/amrsa1/Android-Emulator-image/issues/10",
        "ARM",
        "Apple Silicon",
        "buildx",
        "linux/amd64",
        "slowly",
    ]

    app_names = {"MCP-Github", "Mail"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        return True

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

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
        for keyword in self.MACOS_KEYWORDS:
            if keyword.lower() not in email_body.lower():
                return 0.0, f"Keyword {keyword} not found in email body"

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        return True
