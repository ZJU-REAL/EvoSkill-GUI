"""Search GitHub issues and send SMS with issue links."""

from mobile_world.runtime.app_helpers import mcp as mcp_helper
from mobile_world.runtime.app_helpers.system import check_sms_via_adb
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SearchGithubIssuesSmsTask(BaseTask):
    """Search GitHub issues related to error keyword and send SMS with issue links."""

    goal = (
        "我手机上看到一段报错信息里有关键字 TurnOffWifi，"
        "帮我在 GitHub 上搜索仓库google-research/android_world里相关issue，"
        '如果找到类似问题，就所有 issue 链接（","分隔）发短信给同事1776652334，'
        '如果没有搜索到issue短信内容为"no turnoffwifi issues"'
    )
    task_tags = {"agent-mcp", "lang-cn"}

    OWNER = "google-research"
    REPO = "android_world"
    KEYWORD = "TurnOffWifi"
    RECIPIENT_PHONE = "1776652334"

    app_names = {"MCP-Github", "Messages"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        return True

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        issue_urls = await mcp_helper.search_issues(
            owner=self.OWNER, repo=self.REPO, query=self.KEYWORD
        )

        if not issue_urls:
            # this should not happen but let's handle it anyway
            expected_content = "no turnoffwifi issues"

            if not check_sms_via_adb(
                controller, phone_number=self.RECIPIENT_PHONE, content=expected_content
            ):
                return (
                    0.0,
                    f"SMS not found sent to {self.RECIPIENT_PHONE} with content: {expected_content}",
                )
            else:
                return 1.0
        else:
            if not check_sms_via_adb(
                controller, phone_number=self.RECIPIENT_PHONE, content=issue_urls
            ):
                return 0.0, f"SMS does not contain issue URL: {issue_urls}"

            return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        return True
