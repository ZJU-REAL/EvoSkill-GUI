"""Search arXiv MLLM papers and send email with links."""

from mobile_world.runtime.app_helpers import mcp as mcp_helper
from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.app_helpers.system import enable_auto_time_sync
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SearchMllmPapersEmailTask(BaseTask):
    """Search arXiv for MLLM papers and send email with paper links."""

    goal = (
        "我准备写博士 thesis 相关工作，方向是「multimodal large language models」，"
        "帮我在 arXiv 搜索 multimodal large language model 相关论文，找最近发表的5篇，"
        "把论文的链接email给mikeshow@gmail.com, 标题为mllm，内容为5篇论文的链接，链接之间有换行符"
    )
    task_tags = {"agent-mcp", "lang-cn"}

    SEARCH_QUERY = "multimodal large language model"
    MAX_RESULTS = 5
    EMAIL_ADDRESS = "mikeshow@gmail.com"
    EMAIL_SUBJECT = "mllm"

    app_names = {"MCP-arXiv", "Mail"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        if not enable_auto_time_sync(controller):  # chrome needs auto time sync to work
            return False
        return True

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        papers = await mcp_helper.search_arxiv_papers(
            query=self.SEARCH_QUERY, max_results=self.MAX_RESULTS
        )

        expected_urls = [paper["url"] for paper in papers]

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

        for url in expected_urls:
            if url.lower().strip() not in email_body.lower().strip():
                return 0.0, f"Paper URL not found in email body: {url}"

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        return True
