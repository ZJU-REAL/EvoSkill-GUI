"""Send high dividend stocks list via SMS task implementation."""

from mobile_world.runtime.app_helpers import mcp as mcp_helper
from mobile_world.runtime.app_helpers.system import check_sms_via_adb
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class SendHighDividendStocksSmsTask(BaseTask):
    """Send high dividend stocks list via SMS task."""

    goal = (
        "我想长期拿一点高股息的蓝筹股，帮我筛一下当前股息率大于 4% 的股票名单，"
        "列出最高的前3只股票，每个股票占一行，按照（股票名称 (证券代码) : 股息率）的格式将结果短信发送给177663344"
    )
    task_tags = {"agent-mcp", "lang-cn"}

    RECIPIENT_PHONE = "177663344"

    DIV_FILTER_TYPE = 1
    DIV_FILTER_VALUE = 4.0
    TOP_N = 3

    app_names = {"MCP-stockstar", "Messages"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize task - no special setup needed."""
        return True

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        all_stocks = await mcp_helper.get_high_dividend_stocks(
            div_filter_type=self.DIV_FILTER_TYPE,
            div_filter_value=self.DIV_FILTER_VALUE,
        )

        sorted_stocks = sorted(all_stocks, key=lambda x: x["div_rate"], reverse=True)
        top_3_stocks = sorted_stocks[: self.TOP_N]

        expected_lines = []
        for stock in top_3_stocks:
            security_code = stock.get("security_code", "").strip()
            div_rate = str(stock.get("div_rate", "")).strip()
            expected_lines.append(security_code)
            expected_lines.append(div_rate)

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
