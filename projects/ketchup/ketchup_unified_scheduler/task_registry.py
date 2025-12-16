"""
TaskRegistry for managing scheduled task configurations.

Provides registration, lookup, and filtering of tasks based on their
configuration and runtime feature flag states.
"""

import os
from typing import Dict, List

from ketchup_unified_scheduler.task_config import TaskConfig


class TaskRegistry:
    """
    Registry for managing scheduled task configurations.

    Provides methods to register tasks, look up tasks by name, and filter
    tasks based on their enabled state and feature flags.

    The registry evaluates feature flags at runtime using os.getenv(),
    allowing dynamic enable/disable of tasks without code changes.

    Example:
        registry = TaskRegistry()
        registry.register(TaskConfig(
            name="metadata_updater",
            handler=update_metadata,
            interval_minutes=15,
            feature_flag="KETCHUP_METADATA_UPDATER_FEATURE"
        ))

        # Get all tasks that are currently enabled
        enabled_tasks = registry.get_enabled_tasks()

        # Get a specific task
        task = registry.get_task("metadata_updater")
    """

    def __init__(self):
        """Initialize an empty task registry."""
        self._tasks: Dict[str, TaskConfig] = {}

    def register(self, config: TaskConfig) -> None:
        """
        Register a task configuration.

        Args:
            config: TaskConfig instance to register.

        Raises:
            ValueError: If a task with the same name is already registered.
        """
        if config.name in self._tasks:
            raise ValueError(f"Task '{config.name}' is already registered")
        self._tasks[config.name] = config

    def get_task(self, name: str) -> TaskConfig:
        """
        Get a task configuration by name.

        Args:
            name: The unique task name.

        Returns:
            TaskConfig for the specified task.

        Raises:
            KeyError: If no task with the given name is registered.
        """
        if name not in self._tasks:
            raise KeyError(f"Task '{name}' is not registered")
        return self._tasks[name]

    def list_tasks(self) -> List[TaskConfig]:
        """
        List all registered tasks.

        Returns:
            List of all TaskConfig instances in registration order.
        """
        return list(self._tasks.values())

    def get_enabled_tasks(self) -> List[TaskConfig]:
        """
        Get all tasks that are currently enabled.

        A task is considered enabled if:
        1. Its 'enabled' field is True, AND
        2. Its feature flag (if set) evaluates to true via os.getenv()

        Feature flag evaluation:
        - If feature_flag is None, the task is enabled (no flag to check)
        - If feature_flag is set, checks os.getenv(feature_flag, 'true')
        - Default is 'true' for backward compatibility

        Returns:
            List of TaskConfig instances that are currently enabled.
        """
        enabled_tasks = []
        for config in self._tasks.values():
            if self._is_task_enabled(config):
                enabled_tasks.append(config)
        return enabled_tasks

    def _is_task_enabled(self, config: TaskConfig) -> bool:
        """
        Check if a task is enabled based on its config and feature flag.

        Args:
            config: TaskConfig to check.

        Returns:
            True if the task should run, False otherwise.
        """
        # Check static enabled flag first
        if not config.enabled:
            return False

        # Check feature flag if set
        if config.feature_flag is not None:
            # Default to 'true' for backward compatibility
            flag_value = os.getenv(config.feature_flag, "true")
            return flag_value.lower() == "true"

        return True

    def unregister(self, name: str) -> bool:
        """
        Unregister a task by name.

        Args:
            name: The unique task name to remove.

        Returns:
            True if task was removed, False if not found.
        """
        if name in self._tasks:
            del self._tasks[name]
            return True
        return False

    def clear(self) -> None:
        """Remove all registered tasks."""
        self._tasks.clear()

    def __len__(self) -> int:
        """Return the number of registered tasks."""
        return len(self._tasks)

    def __contains__(self, name: str) -> bool:
        """Check if a task is registered by name."""
        return name in self._tasks
