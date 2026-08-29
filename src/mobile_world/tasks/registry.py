import importlib.util
import inspect
import os
from pathlib import Path

from loguru import logger

import mobile_world


class TaskRegistry:
    _scan_logged: set[str] = set()

    def __init__(self, task_set_path: str | None = None):
        """
        Initialize TaskRegistry and automatically scan for tasks.

        Args:
            task_set_path: Path to the directory containing task files.
                          If None, uses the installed mobile_world package path.
        """
        self.tasks: dict[str, object] = {}
        if task_set_path is None:
            package_path = Path(mobile_world.__file__).parent
            self.task_set_path = str(package_path / "tasks" / "definitions")
        else:
            self.task_set_path = task_set_path
        self._scan_and_register_tasks()

    def _scan_and_register_tasks(self):
        """Recursively scan the task_set directory and register all tasks."""
        should_log = self.task_set_path not in TaskRegistry._scan_logged
        if should_log:
            TaskRegistry._scan_logged.add(self.task_set_path)
            logger.info(f"Starting task scanning in directory: {self.task_set_path}")

        if not os.path.exists(self.task_set_path):
            logger.warning(f"Task directory not found: {self.task_set_path}")
            return

        task_files = list(Path(self.task_set_path).rglob("*.py"))

        for file_path in task_files:
            if file_path.name == "__init__.py":
                continue

            self._load_tasks_from_file(file_path)

        if should_log:
            logger.info(f"Task registration complete. Total tasks registered: {len(self.tasks)}")
            logger.info(f"Registered tasks: {list(self.tasks.keys())}")

    def _load_tasks_from_file(self, file_path: Path):
        """
        Load and register tasks from a single Python file.

        Args:
            file_path: Path to the Python file
        """
        try:
            module_name = str(file_path.with_suffix("")).replace(os.sep, ".")

            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                logger.warning(f"Could not load spec for file: {file_path}")
                return

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            self._register_tasks_from_module(module, file_path)

        except Exception as e:
            logger.error(f"Error loading tasks from {file_path}: {e}", exc_info=True)

    def _register_tasks_from_module(self, module, file_path: Path):
        """
        Register all BaseTask subclasses from a module.

        Args:
            module: The loaded Python module
            file_path: Path to the source file (for logging)
        """
        try:
            from mobile_world.tasks.base import BaseTask
        except ImportError:
            logger.error("Could not import BaseTask. Please ensure it exists.")
            return

        for name, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, BaseTask)
                and obj is not BaseTask
                and obj.__module__ == module.__name__
            ):
                try:
                    task_instance = obj()
                    task_name = obj.__name__

                    if task_name in self.tasks:
                        logger.warning(
                            f"Task '{task_name}' already registered. Overwriting with instance from {file_path}"
                        )

                    self.tasks[task_name] = task_instance

                except Exception as e:
                    logger.error(
                        f"Error instantiating task '{name}' from {file_path}: {e}",
                        exc_info=True,
                    )

    def get_task(self, task_name: str):
        """
        Retrieve a task by name.

        Args:
            task_name: Name of the task class

        Returns:
            Task instance

        Raises:
            KeyError: If task is not found
        """
        if task_name not in self.tasks:
            logger.error(
                f"Task '{task_name}' not found. Available tasks: {list(self.tasks.keys())}"
            )
            raise KeyError(f"Task '{task_name}' not found in registry")

        return self.tasks[task_name]

    def list_tasks(self) -> list:
        """Return a list of all registered task names."""
        return list(self.tasks.keys())

    def has_task(self, task_name: str) -> bool:
        """Check if a task is registered."""
        return task_name in self.tasks
