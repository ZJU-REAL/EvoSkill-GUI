"""Send stock ESG rating via SMS task implementation."""

from loguru import logger

from mobile_world.runtime.app_helpers import mcp as mcp_helper
from mobile_world.runtime.app_helpers.system import check_sms_via_adb
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SendStockEsgRatingSmsTask(BaseTask):
    """Send stock ESG rating via SMS task."""

    goal = (
        "请先筛选出近三年ROE大于250的全部股票，然后将结果中的证券代码按从小到大排序，"
        "取排序后的第一只股票，查询这只股票在妙盈科技的ESG评级。"
        '最终将这只股票的security_code和esg_rate按照"code:rate"的格式短信发送给177663344'
    )
    task_tags = {"agent-mcp", "lang-cn"}

    recipient_phone = "177663344"

    app_names = {"MCP-stockstar", "Messages"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize task - no special setup needed."""
        logger.info("Task initialized: Send stock ESG rating via SMS")
        return True

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        """
        Check if task is successful.

        Validation criteria (all must pass to get score 1.0):
        1. Get stock ESG rating using get_stocks_esg_ratings(filter_type=1, filter_value=250)
        2. SMS was sent to the correct phone number (177663344)
        3. SMS content matches the expected format (code:rate)
        4. SMS content matches the result from get_stocks_esg_ratings
        """
        self._check_is_initialized()
        logger.info("开始获取股票 ESG 评级...")
        ratings = await mcp_helper.get_stocks_esg_ratings(filter_type=1, filter_value=250.0)

        assert ":" in ratings, f"Invalid ratings format: {ratings}"
        parts = ratings.split(":", 1)

        expected_code = parts[0].strip()
        expected_rate = parts[1].strip()

        result = check_sms_via_adb(
            controller,
            phone_number=self.recipient_phone,
            content=f"{expected_code}:{expected_rate}",
        )

        if not result:
            return 0.0, (
                f"未找到发送到{self.recipient_phone}的短信. 请确认短信已发送到正确的手机号"
            )

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        return True
