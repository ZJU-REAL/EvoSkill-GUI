"""Delete useless files task implementation - clean useless files in download directory."""

import os
import random
import tempfile

from loguru import logger

from mobile_world.runtime.controller import AndroidController
from mobile_world.runtime.utils.helpers import execute_adb
from mobile_world.tasks.base import BaseTask


class DeleteUselessFilesAskUserTask(BaseTask):
    """Delete useless files ask user task - clean useless files in download directory for storage saving."""

    task_tags = {"agent-user-interaction", "lang-en"}
    goal = "Help me to clean the useless files in download directory for stoarage saving."

    # Download directory path
    DOWNLOAD_DIR = "/sdcard/Download"

    # Files that should be deleted (useless files)
    useless_files = []

    # Files that should be kept (useful files)
    useful_files = []

    app_names = {
        "Files",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        """Initialize task - create test files in download directory."""
        try:
            logger.info("[TASK_INIT] Initializing delete useless files task")

            # Clean up download directory first
            logger.info(f"Cleaning up existing files in {self.DOWNLOAD_DIR}...")
            execute_adb(f"shell rm -rf {self.DOWNLOAD_DIR}/*")
            execute_adb(f"shell mkdir -p {self.DOWNLOAD_DIR}")

            # Generate random file names
            # Useless files: use normal-looking file names that don't reveal they are useless
            useless_file_patterns = [
                "file_",
                "data_",
                "note_",
                "memo_",
                "record_",
                "info_",
                "log_",
                "archive_",
                "copy_",
                "download_",
            ]

            # Useful files: documents, important files
            useful_file_patterns = [
                "document_",
                "important_",
                "report_",
                "presentation_",
                "contract_",
                "photo_",
            ]

            # Create temporary directory for local files
            temp_dir = tempfile.mkdtemp()

            try:
                # Create 5-8 useless files
                num_useless = random.randint(5, 8)
                self.useless_files = []
                for i in range(num_useless):
                    pattern = random.choice(useless_file_patterns)
                    filename = f"{pattern}{random.randint(1000, 9999)}.txt"
                    file_path = f"{self.DOWNLOAD_DIR}/{filename}"

                    # Create a temporary file with some content
                    local_file = os.path.join(temp_dir, filename)
                    with open(local_file, "w") as f:
                        f.write(f"File content for {filename}\n" * 10)

                    # Push to device
                    result = execute_adb(f"push {local_file} {file_path}")
                    if result.success:
                        self.useless_files.append({"filename": filename, "path": file_path})
                        logger.info(f"Created useless file: {filename}")

                # Create 3-5 useful files (should not be deleted)
                num_useful = random.randint(3, 5)
                self.useful_files = []
                for i in range(num_useful):
                    pattern = random.choice(useful_file_patterns)
                    filename = f"{pattern}{random.randint(1000, 9999)}.txt"
                    file_path = f"{self.DOWNLOAD_DIR}/{filename}"

                    # Create a temporary file with some content
                    local_file = os.path.join(temp_dir, filename)
                    with open(local_file, "w") as f:
                        f.write(f"This is an important file: {filename}\n" * 10)

                    # Push to device
                    result = execute_adb(f"push {local_file} {file_path}")
                    if result.success:
                        self.useful_files.append({"filename": filename, "path": file_path})
                        logger.info(f"Created useful file: {filename}")
            finally:
                # Clean up temporary directory
                for file in os.listdir(temp_dir):
                    os.remove(os.path.join(temp_dir, file))
                os.rmdir(temp_dir)

            # Set up relevant information for the agent
            useless_filenames = [f["filename"] for f in self.useless_files]
            self.relevant_information = (
                f"The download directory is {self.DOWNLOAD_DIR}. "
                f"When the agent let you determine the useless files, the agent must list existing files first."
                f"Before the agent list all files, you must pretend you don't know the file names to be deleted."
                f"The useless files that should be deleted are: {', '.join(useless_filenames)}. "
                f"Once the agent lists all files, you can answer the question about the useless files."
            )

            return True
        except Exception as e:
            logger.error(f"Initialize task failed: {e}")
            return False

    def is_successful(self, controller: AndroidController) -> tuple[float, str]:
        """Check if the delete useless files task was completed successfully."""
        self._check_is_initialized()

        logger.info("Checking task completion...")
        logger.info(f"Expected useless files to be deleted: {len(self.useless_files)}")
        logger.info(f"Expected useful files to be kept: {len(self.useful_files)}")

        # Check if useless files are deleted
        deleted_files = []
        remaining_useless_files = []

        for file_info in self.useless_files:
            file_path = file_info["path"]
            filename = file_info["filename"]

            # Check if file exists
            check_cmd = f"adb -s {controller.device} shell test -f {file_path} && echo EXISTS || echo NOT_EXISTS"
            result = execute_adb(check_cmd)

            if result.success:
                output_stripped = result.output.strip()
                if output_stripped == "EXISTS":
                    remaining_useless_files.append(filename)
                elif output_stripped == "NOT_EXISTS":
                    deleted_files.append(filename)
                else:
                    logger.warning(f"Unexpected output for {filename}: {output_stripped}")
            else:
                deleted_files.append(filename)

        # Check if useful files still exist (should not be deleted)
        remaining_useful_files = []
        deleted_useful_files = []

        for file_info in self.useful_files:
            file_path = file_info["path"]
            filename = file_info["filename"]

            # Check if file exists
            check_cmd = f"adb -s {controller.device} shell test -f {file_path} && echo EXISTS || echo NOT_EXISTS"
            result = execute_adb(check_cmd)

            if result.success:
                output_stripped = result.output.strip()
                if output_stripped == "EXISTS":
                    remaining_useful_files.append(filename)
                elif output_stripped == "NOT_EXISTS":
                    deleted_useful_files.append(filename)
                else:
                    logger.warning(f"Unexpected output for {filename}: {output_stripped}")
            else:
                # If command failed, assume file doesn't exist (deleted)
                deleted_useful_files.append(filename)
                logger.error(f"- Useful file was incorrectly deleted (check failed): {filename}")

        # Evaluate success
        all_useless_deleted = len(remaining_useless_files) == 0
        all_useful_kept = len(deleted_useful_files) == 0

        if all_useless_deleted and all_useful_kept:
            return 1.0, "success"
        else:
            error_messages = []
            if not all_useless_deleted:
                error_messages.append(f"Useless files not deleted: {remaining_useless_files}")
            if not all_useful_kept:
                error_messages.append(f"Useful files incorrectly deleted: {deleted_useful_files}")

            error_msg = "; ".join(error_messages)
            return 0.0, error_msg
