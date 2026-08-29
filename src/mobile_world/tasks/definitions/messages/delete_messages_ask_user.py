"""Delete messages from company task implementation."""

from loguru import logger

from mobile_world.runtime.controller import AndroidController
from mobile_world.runtime.utils.helpers import execute_adb
from mobile_world.tasks.base import BaseTask


class DeleteAllMessagesAskUserTask(BaseTask):
    task_tags = {"agent-user-interaction", "lang-en"}

    goal = "Delete all messages in SMS app sent from my company."

    # Company A - the target company whose messages should be deleted
    company_phone = "234567812"  # Company A hotline
    company_name = "TechCorp"
    message_content = "The messages are related to sprint retrospective and deployment issues."

    app_names = {
        "Messages",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize task - set relevant information for user."""
        self.relevant_information = f"My company is {self.company_name} and the phone number is {self.company_phone}. {self.message_content}"
        logger.info("Task initialized successfully")
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """
        Check if task is successful:
        - All messages from company should be deleted (matching company_phone)

        Returns:
            float: 1.0 if successful, 0.0 if failed
        """
        self._check_is_initialized()

        # Query all remaining SMS messages
        query_cmd = f"adb -s {controller.device} shell content query --uri content://sms/"
        result = execute_adb(query_cmd, output=False)

        if not result.success:
            logger.error(f"Failed to query SMS database: {result.error}")
            return 0.0

        lines = result.output.strip().split("\n") if result.output else []

        # Parse messages and count company messages
        company_messages = []

        for line in lines:
            if not line.strip() or not line.startswith("Row:"):
                continue

            # Extract address (phone number)
            import re

            address_match = re.search(r"address=([^,]+)", line)

            if not address_match:
                continue

            address = address_match.group(1).strip()

            # Check if message is from company
            if self.company_phone in address:
                company_messages.append(line)

        logger.info(f"Found company messages remaining (should be 0): {len(company_messages)}")

        if len(company_messages) == 0:
            return 1.0, "success"
        else:
            return 0.0, "task failed, found company messages remaining"
