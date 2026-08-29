"""Compare ESG ratings from Miotech and Chindices and send email with result."""

from typing import Any

from loguru import logger

from mobile_world.runtime.app_helpers import mail as mail_helper
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class CompareEsgRatingsEmailTask(BaseTask):
    """Compare ESG ratings from Miotech and Chindices and send email with result."""

    goal = (
        "请查询证券代码 600000 在妙盈科技和华证指数的 ESG 评级是否一致。"
        "请email 给chen@gmail.com，title为股票价格，"
        "内容取决于判别结果，如果两家返回的 esg_rate 完全相同，"
        '则内容为"600000在妙盈科技和华证指数的ESG评级一致"，'
        '否则发送"600000在妙盈科技和华证指数的ESG评级不一致"。'
    )
    task_tags = {"agent-mcp", "lang-cn"}

    SECURITY_CODE = "600000"

    EMAIL_ADDRESS = "chen@gmail.com"

    EMAIL_SUBJECT = "股票价格"

    app_names = {"MCP-stockstar", "Mail"}

    @classmethod
    def generate_random_params(cls) -> dict[str, Any]:
        return {}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize task - no special setup needed."""
        logger.info(f"Task initialized: Compare ESG ratings for {self.SECURITY_CODE}")
        return True

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        """
        Check if the task is successful.

        Validation criteria (all must pass to get score 1.0):
        1. Call compare_esg_ratings to determine if ratings are consistent
        2. Email was sent
        3. Email sent to correct address (chen@gmail.com)
        4. Email subject is correct ("股票价格")
        5. Email body matches the comparison result
        """
        self._check_is_initialized()

        logger.info(f"调用 compare_esg_ratings 比较证券代码 {self.SECURITY_CODE} 的 ESG 评级...")

        expected_body = f"{self.SECURITY_CODE}在妙盈科技和华证指数的ESG评级不一致"

        sent_email_info = mail_helper.get_sent_email_info()

        if sent_email_info is None:
            return 0.0, "No email sent"

        email_to = sent_email_info.get("to", "")
        if email_to.lower() != self.EMAIL_ADDRESS.lower():
            return 0.0, (
                f"Email sent to wrong address: '{email_to}' (expected: '{self.EMAIL_ADDRESS}')"
            )

        subject = sent_email_info.get("subject", "")
        if subject != self.EMAIL_SUBJECT:
            return 0.0, (
                f"Email subject is incorrect: '{subject}' (expected: '{self.EMAIL_SUBJECT}')"
            )

        email_body = sent_email_info.get("body", "").strip()

        if expected_body not in email_body:
            return 0.0, (
                f"Email body does not match comparison result. "
                f"Expected to contain: '{expected_body}', "
                f"but found: '{email_body}'"
            )

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        return True
