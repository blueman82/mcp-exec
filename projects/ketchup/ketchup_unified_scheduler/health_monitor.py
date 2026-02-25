"""
PerTaskHealthMonitor for individual task health tracking.

Provides per-task health status files for monitoring individual task health
within the unified scheduler. Uses /tmp/unified_{task_name}_health pattern
to avoid conflicts with legacy scheduler health files.
"""

import time
from pathlib import Path
from typing import Dict, Optional

from ketchup_unified_scheduler.task_config import TaskConfig


class PerTaskHealthMonitor:
    """
    Health monitor for tracking individual task status within unified scheduler.

    Creates and maintains health status files for each task:
    - /tmp/unified_{task_name}_health: Contains '{timestamp}:{status}'
    - /tmp/unified_{task_name}_last_run: Contains '{timestamp}' of last successful run

    This allows operators to monitor which specific tasks are healthy or failing
    without conflicting with legacy per-service health files.

    Example:
        monitor = PerTaskHealthMonitor()
        monitor.update_task_status("metadata_updater", "running")
        monitor.update_task_last_run("metadata_updater")

        # Get all task statuses for monitoring
        statuses = monitor.get_all_task_statuses()
        # {'metadata_updater': {'status': 'running', 'timestamp': 1234567890}}
    """

    HEALTH_FILE_PATTERN = "/tmp/unified_{task_name}_health"
    LAST_RUN_FILE_PATTERN = "/tmp/unified_{task_name}_last_run"

    def __init__(self, base_path: str = "/tmp"):
        """
        Initialize the health monitor.

        Args:
            base_path: Base directory for health files. Defaults to /tmp.
        """
        self._base_path = Path(base_path)
        self._tracked_tasks: Dict[str, Path] = {}

    def _get_health_file_path(self, task_name: str) -> Path:
        """
        Get the health file path for a task.

        Args:
            task_name: Name of the task.

        Returns:
            Path to the task's health file.
        """
        return self._base_path / f"unified_{task_name}_health"

    def _get_last_run_file_path(self, task_name: str) -> Path:
        """
        Get the last run file path for a task.

        Args:
            task_name: Name of the task.

        Returns:
            Path to the task's last run file.
        """
        return self._base_path / f"unified_{task_name}_last_run"

    def update_task_status(self, task_name: str, status: str) -> None:
        """
        Update the health status for a specific task.

        Writes format: {unix_timestamp}:{status}
        Creates the file if it doesn't exist.

        Args:
            task_name: Name of the task to update.
            status: Current status (starting/running/idle/error/stopped/success).
        """
        health_file = self._get_health_file_path(task_name)
        try:
            health_file.parent.mkdir(parents=True, exist_ok=True)
            health_file.write_text(f"{int(time.time())}:{status}")
            self._tracked_tasks[task_name] = health_file
        except Exception:
            # Silently fail - health updates should not crash the scheduler
            pass

    def update_task_last_run(self, task_name: str) -> None:
        """
        Update the last successful run timestamp for a task.

        Writes format: {unix_timestamp}

        Args:
            task_name: Name of the task that completed successfully.
        """
        last_run_file = self._get_last_run_file_path(task_name)
        try:
            last_run_file.parent.mkdir(parents=True, exist_ok=True)
            last_run_file.write_text(str(int(time.time())))
        except Exception:
            # Silently fail - health updates should not crash the scheduler
            pass

    def get_task_status(self, task_name: str) -> Optional[Dict[str, any]]:
        """
        Get the current health status for a specific task.

        Args:
            task_name: Name of the task to query.

        Returns:
            Dict with 'timestamp' and 'status' keys, or None if file not found.
        """
        health_file = self._get_health_file_path(task_name)
        try:
            if health_file.exists():
                content = health_file.read_text().strip()
                if ":" in content:
                    timestamp_str, status = content.split(":", 1)
                    return {
                        "timestamp": int(timestamp_str),
                        "status": status,
                    }
        except Exception:
            pass  # Health updates must not crash the scheduler — failure logged by caller
        return None

    def get_last_run(self, task_name: str) -> Optional[int]:
        """
        Get the last successful run timestamp for a task.

        Args:
            task_name: Name of the task to query.

        Returns:
            Unix timestamp of last run, or None if not found.
        """
        last_run_file = self._get_last_run_file_path(task_name)
        try:
            if last_run_file.exists():
                content = last_run_file.read_text().strip()
                return int(content)
        except Exception:
            pass  # Health updates must not crash the scheduler — failure logged by caller
        return None

    def get_all_task_statuses(self) -> Dict[str, Dict[str, any]]:
        """
        Get health status for all tracked tasks.

        Reads all health files matching the unified_{task_name}_health pattern
        and returns a dictionary of task statuses.

        Returns:
            Dict mapping task names to their status info:
            {
                'task_name': {
                    'timestamp': 1234567890,
                    'status': 'running',
                    'last_run': 1234567800  # Optional, if available
                }
            }
        """
        statuses = {}

        # Find all unified health files in the base path
        try:
            for health_file in self._base_path.glob("unified_*_health"):
                # Extract task name from filename
                filename = health_file.name
                if filename.startswith("unified_") and filename.endswith("_health"):
                    task_name = filename[8:-7]  # Remove prefix and suffix

                    status_info = self.get_task_status(task_name)
                    if status_info:
                        # Add last run info if available
                        last_run = self.get_last_run(task_name)
                        if last_run:
                            status_info["last_run"] = last_run
                        statuses[task_name] = status_info
        except Exception:
            pass

        return statuses

    def register_task(self, config: TaskConfig) -> None:
        """
        Register a task for health monitoring.

        Initializes the task's health file with 'registered' status.

        Args:
            config: TaskConfig instance to register.
        """
        self.update_task_status(config.name, "registered")

    def clear_task_status(self, task_name: str) -> None:
        """
        Remove health files for a task.

        Args:
            task_name: Name of the task to clear.
        """
        try:
            health_file = self._get_health_file_path(task_name)
            if health_file.exists():
                health_file.unlink()

            last_run_file = self._get_last_run_file_path(task_name)
            if last_run_file.exists():
                last_run_file.unlink()

            if task_name in self._tracked_tasks:
                del self._tracked_tasks[task_name]
        except Exception:
            pass
