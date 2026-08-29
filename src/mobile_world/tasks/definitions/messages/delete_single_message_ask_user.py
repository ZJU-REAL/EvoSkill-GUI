"""Delete messages from company task implementation."""

from loguru import logger

from mobile_world.runtime.controller import AndroidController
from mobile_world.runtime.utils.helpers import execute_adb
from mobile_world.tasks.base import BaseTask


class DeleteMessagesAskUserTask(BaseTask):
    task_tags = {"agent-user-interaction", "lang-en"}

    goal = "Delete the message about deployment issues in SMS app sent from my company."

    # Company A - the target company whose messages should be deleted
    company_phone = "234567812"  # Company A hotline
    company_name = "TechCorp"

    # Two messages from company
    message_to_keep = "The sprint retrospective notes are in the shared doc. Please add your feedback by tomorrow."
    message_to_delete = "Thanks! Added my thoughts on the deployment issues we had."
    message_content = "There are two messages from my company. One is about sprint retrospective notes, and another is about deployment issues."

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
        - The message about deployment issues should be deleted
        - The message about sprint retrospective should still exist

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

        # Parse messages and check for both messages
        import re

        found_message_to_keep = False
        found_message_to_delete = False

        for line in lines:
            if not line.strip() or not line.startswith("Row:"):
                continue

            # Extract address (phone number)
            address_match = re.search(r"address=([^,]+)", line)
            if not address_match:
                continue

            address = address_match.group(1).strip()

            # Only check messages from company
            if self.company_phone in address:
                # Extract message body
                body_match = re.search(r"body=([^,]+?)(?:,\s*\w+=|$)", line)
                if body_match:
                    body = body_match.group(1).strip()

                    # Check if it's the message to keep or delete
                    if "sprint retrospective" in body.lower():
                        found_message_to_keep = True
                        logger.info(f"Found message to keep: {body[:50]}...")
                    elif "deployment issues" in body.lower():
                        found_message_to_delete = True
                        logger.info(f"Found message to delete (should not exist): {body[:50]}...")

        logger.info(f"Message to keep exists: {found_message_to_keep}")
        logger.info(f"Message to delete exists: {found_message_to_delete}")

        # Success criteria: message to keep exists AND message to delete does not exist
        if found_message_to_keep and not found_message_to_delete:
            logger.info(
                "- Task completed successfully! Deployment message deleted, retrospective message kept. Score: 1.0"
            )
            return 1.0, "success"
        elif not found_message_to_keep and not found_message_to_delete:
            logger.warning(
                "- Task failed - Both messages were deleted (should only delete deployment message). Score: 0.0"
            )
            return 0.0, "task failed, both messages deleted"
        elif not found_message_to_keep and found_message_to_delete:
            logger.warning(
                "- Task failed - Wrong message deleted (kept deployment, deleted retrospective). Score: 0.0"
            )
            return 0.0, "task failed, wrong message deleted"
        else:  # found_message_to_keep and found_message_to_delete
            logger.warning(
                "- Task failed - Deployment message still exists (should be deleted). Score: 0.0"
            )
            return 0.0, "task failed, deployment message not deleted"
