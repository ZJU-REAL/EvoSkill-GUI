"""Generate stock candidate list based on dividend rate and ESG rating."""

from loguru import logger

from mobile_world.runtime.app_helpers import mcp as mcp_helper
from mobile_world.runtime.controller import AndroidController
from mobile_world.runtime.utils.helpers import execute_adb
from mobile_world.tasks.base import BaseTask


class StockCandidateListTask(BaseTask):
    """Generate stock candidate list based on dividend rate and ESG rating."""

    goal = (
        "帮我在当前股息率大于 4% 的股票里，挑5只 ESG 评级在 BBB 及以上的，给我列个候选名单。"
        "每个股票占一行，按照(股票名称 (证券代码):ESG评级)的格式显示，"
        "记录到price.txt文件，存储在系统中的Documents文件夹下。"
    )
    task_tags = {"agent-mcp", "lang-cn"}

    FILE_NAME = "price.txt"
    DOCUMENTS_PATH = "/sdcard/Documents"
    FILE_PATH = f"{DOCUMENTS_PATH}/{FILE_NAME}"

    DIV_FILTER_TYPE = 1
    DIV_FILTER_VALUE = 4.0  # 4%
    MIN_ESG_RATING = "BBB"
    MAX_STOCKS = 5

    app_names = {"MCP-stockstar", "Files"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize task - ensure Documents folder exists."""
        logger.info("Initializing stock candidate list task...")

        # Ensure Documents folder exists
        result = execute_adb(f"shell mkdir -p {self.DOCUMENTS_PATH}")
        if not result.success:
            logger.error(f"Failed to create Documents folder: {result.error}")
            return False

        logger.info(f"Documents folder ready: {self.DOCUMENTS_PATH}")
        return True

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        """Check if the task is successful."""
        self._check_is_initialized()
        expected_stocks = await mcp_helper.get_stocks_by_div_rate_and_esg(
            div_filter_type=self.DIV_FILTER_TYPE,
            div_filter_value=self.DIV_FILTER_VALUE,
            min_esg_rating=self.MIN_ESG_RATING,
            max_stocks=self.MAX_STOCKS,
        )

        read_result = execute_adb(f"adb -s {controller.device} shell cat {self.FILE_PATH}")

        if not read_result.success:
            return 0.0, f"File {self.FILE_NAME} not found or failed to read"

        file_content = read_result.output.strip()
        if not file_content:
            return 0.0, "File is empty"

        assert expected_stocks, "Failed to get stocks by div rate and ESG rating"

        # Validate each expected stock is in file
        for stock in expected_stocks:
            security_code = stock.get("security_code", "").strip()
            esg_rate = stock.get("esg_rate", "").strip()

            if security_code not in file_content:
                return 0.0, f"Stock {security_code} not found in file"

            if esg_rate not in file_content:
                return 0.0, f"ESG rating {esg_rate} not found in file"

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        return True
