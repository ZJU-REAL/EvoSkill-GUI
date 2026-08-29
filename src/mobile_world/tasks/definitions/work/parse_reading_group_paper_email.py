"""Parse arXiv paper content and send email."""

from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class ParseReadingGroupPaperEmailTask(BaseTask):
    """Parse arXiv paper content and send email."""

    goal = (
        "我刚听完一场线上 reading group，报告是一篇 arXiv 论文，ID 是 2401.01234，"
        '帮我把这篇论文摘要email给mikeshow@gmail.com，标题为"reading group paper"'
    )
    task_tags = {"agent-mcp", "lang-cn"}

    ARXIV_ID = "2401.01234"
    EMAIL_ADDRESS = "mikeshow@gmail.com"
    EMAIL_SUBJECT = "reading group paper"
    EXPECTED_ABSTRACT_WORDS = "Survival analysis can sometimes involve individuals who will not experience the event of interest, forming what is known as the cured group. Identifying such individuals is not always possible beforehand, as they provide only right-censored data. Ignoring the presence of the cured group can introduce bias in the final model. This paper presents a method for estimating a semiparametric additive hazards model that accounts for the cured fraction. Unlike regression coefficients in a hazard ratio model, those in an additive hazard model measure hazard differences. The proposed method uses a primal-dual interior point algorithm to obtain constrained maximum penalized likelihood estimates of the model parameters, including the regression coefficients and the baseline hazard, subject to certain non-negativity constraints.".split()

    app_names = {"MCP-arXiv", "Mail"}

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

        email_body = email.get("body", "").strip().lower()

        if (
            sum(word.lower() in email_body for word in self.EXPECTED_ABSTRACT_WORDS)
            / len(self.EXPECTED_ABSTRACT_WORDS)
            < 0.97
        ):
            return 0.0, "Paper abstract not found in email body"

        return 1.0, "Success"

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        return True
