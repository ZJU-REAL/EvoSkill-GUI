"""Get latest arXiv papers and send SMS with results."""

from mobile_world.runtime.app_helpers import mcp as mcp_helper
from mobile_world.runtime.app_helpers.system import check_sms_via_adb, enable_auto_time_sync
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SendArxivPapersSmsTask(BaseTask):
    """Get latest arXiv cs.AI papers and send SMS with titles and links."""

    goal = (
        "先帮我看一下最近 arXiv 上 cs.AI 分类的新论文，"
        '帮我调5篇最新的，按照"题目：arXiv 链接"每行的格式发送给mike 18753923900'
    )
    task_tags = {"agent-mcp", "lang-cn"}

    CATEGORY = "cs.AI"
    MAX_RESULTS = 5
    RECIPIENT_PHONE = "18753923900"

    app_names = {"MCP-arXiv", "Messages"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        if not enable_auto_time_sync(controller):  # chrome needs auto time sync to work
            return False
        return True

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        papers = await mcp_helper.get_latest_arxiv_papers(
            category=self.CATEGORY, max_results=self.MAX_RESULTS
        )

        expected_lines = [paper["title"] for paper in papers] + [paper["url"] for paper in papers]
        if not check_sms_via_adb(
            controller, phone_number=self.RECIPIENT_PHONE, content=expected_lines
        ):
            return (
                0.0,
                f"SMS not found sent to {self.RECIPIENT_PHONE} with content: {expected_lines}",
            )

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        return True
