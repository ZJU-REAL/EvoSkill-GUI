"""Get GitHub issue details and send email."""

from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class GetIssueEmailTask(BaseTask):
    """Get GitHub issue details and send email with title and body."""

    goal = (
        "I came across a complex issue #242 while browsing on the subway. "
        "Please help me get the title and main content of this issue from google-research/android_world, "
        "and abstract the question body into an email to send to myself at mike@gmail.com with the subject 'Read Later: Issue 242'"
    )
    task_tags = {"agent-mcp", "lang-en"}

    OWNER = "google-research"
    REPO = "android_world"

    EMAIL_ADDRESS = "mike@gmail.com"
    EMAIL_SUBJECT = "Read Later: Issue 242"
    EXPECTED_TITLE = (
        "How to submit the pull request?"  # "[Question] How to submit the pull request?\"
    )
    EXPECTED_BODY = [
        "Hi Chris",
        "I have done the changes to support Azure open AI",
        "Can you please let me know how to submit the pull request",
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

        if email.get("subject", "").lower().strip() != self.EMAIL_SUBJECT.lower().strip():
            return (
                0.0,
                f"Email subject does not contain issue title: {email.get('subject')} (expected: {self.EMAIL_SUBJECT})",
            )

        email_body = email.get("body", "").strip()
        for sentence in self.EXPECTED_BODY:
            if sentence.lower().strip() not in email_body.lower().strip():
                print(f"Sentence {sentence} not found in email body")

                return 0.0, f"Sentence {sentence} not found in email body"

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        return True
