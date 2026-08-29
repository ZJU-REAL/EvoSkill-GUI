"""Get arXiv paper abstract and send email."""

from difflib import SequenceMatcher

from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class GetArxivPaperEmailTask(BaseTask):
    """Get arXiv paper abstract and send email with title and method summary."""

    goal = "I just came across a paper at https://arxiv.org/pdf/2510.20286 — please parse its content, extract the abstract, and email it to mikeshow@gmail.com with the paper title as the subject and the abstract as the body."
    task_tags = {"agent-mcp", "lang-cn"}

    ARXIV_URL = "https://arxiv.org/pdf/2510.20286"
    EMAIL_ADDRESS = "mikeshow@gmail.com"
    EXPECTED_TITLE = (
        "UI-Ins: Enhancing GUI Grounding with Multi-Perspective Instruction-as-Reasoning"
    )
    EXPECTED_SENTENCE = "GUI grounding, which maps natural-language instructions to actionable UI elements, is a core capability of GUI agents. Prior works largely treats instructions as a static proxy for user intent, overlooking the impact of instruction diversity and quality on grounding performance. Through a careful investigation of existing grounding datasets, we find a 23.3% flaw rate in their instructions and show that inference-time exploitation of instruction diversity yields up to a substantial 76% relative performance improvement. In this paper, we introduce the Instruction-as-Reasoning paradigm, treating instructions as dynamic analytical pathways that offer distinct perspectives and enabling the model to select the most effective pathway during reasoning. To achieve this, we propose a two-stage training framework: supervised fine-tuning (SFT) on synthesized, diverse instructions to instill multi-perspective reasoning, followed by reinforcement learning (RL) to optimize pathway selection and composition. Our resulting models, UI-Ins-7B and UI-Ins-32B, achieve state-of-the-art results on five challenging grounding benchmarks and exhibit emergent reasoning, selectively composing and synthesizing novel instruction pathways at inference. In particular, UI-Ins-32B attains the best grounding accuracy, scoring 87.3% on UI-I2E-Bench, 57.0% on ScreenSpot-Pro, and 84.9% on MMBench-GUI L2. Furthermore, our model demonstrates strong agentic potential, achieving a 74.1% success rate on AndroidWorld using UI-Ins-7B as the executor. Our in-depth analysis reveals additional insights such as how reasoning can be formulated to enhance rather than hinder grounding performance, and how our method mitigates policy collapse in the SFT+RL framework. All code and model checkpoints will be publicly released in"

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

        email_subject = email.get("subject", "")
        if email_subject.lower() != self.EXPECTED_TITLE.lower():
            return (
                0.0,
                f"Email subject does not contain paper title. Subject: {email_subject}, Title: {self.EXPECTED_TITLE}",
            )

        email_body = email.get("body", "").strip()
        similarity_score = SequenceMatcher(a=self.EXPECTED_SENTENCE, b=email_body).ratio()
        if similarity_score < 0.8:
            return 0.0, f"Email body similarity score is too low: {similarity_score}"

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        return True
