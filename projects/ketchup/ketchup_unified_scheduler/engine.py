"""
UnifiedSchedulerEngine for multi-task orchestration.

Orchestrates multiple scheduled tasks concurrently, each running on its own schedule
with isolated error handling. Uses asyncio.create_task() for concurrent execution.
"""

import asyncio
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from ketchup_unified_scheduler.health_monitor import PerTaskHealthMonitor
from ketchup_unified_scheduler.task_config import TaskConfig
from ketchup_unified_scheduler.task_registry import TaskRegistry
from packages.core.logging import setup_logger
from packages.core.typed_di import TypedServiceRegistry


class UnifiedSchedulerEngine:
    """
    Unified scheduler engine that manages multiple concurrent asyncio tasks.

    Each TaskConfig spawns a coroutine that loops: sleep → execute(container) → repeat.
    Uses asyncio.gather() with return_exceptions=True for fault isolation.

    Attributes:
        registry: TaskRegistry containing task configurations.
        running: Boolean flag indicating if scheduler should continue running.
        health_file: Path to unified health status file.
    """

    def __init__(
        self,
        registry: TaskRegistry,
        container: Optional[TypedServiceRegistry] = None,
        health_file_path: str = "/tmp/unified_scheduler_health",
        task_health_monitor: Optional[PerTaskHealthMonitor] = None,
    ):
        """
        Initialize the unified scheduler engine.

        Args:
            registry: TaskRegistry containing task configurations.
            container: Optional TypedServiceRegistry for dependency injection.
            health_file_path: Path to write health status file.
            task_health_monitor: Optional PerTaskHealthMonitor for per-task health tracking.
                                 If not provided, a default instance is created.
        """
        self._registry = registry
        self._container = container
        self.running = True
        self.health_file = Path(health_file_path)
        self._tasks: Dict[str, asyncio.Task] = {}
        self._logger = setup_logger(__name__)
        self._task_health_monitor = task_health_monitor or PerTaskHealthMonitor()

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """
        Handle shutdown signals gracefully.

        Args:
            signum: Signal number received.
            frame: Current stack frame (unused).
        """
        self._logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    def _update_health_status(self, status: str) -> None:
        """
        Update health check file with current status.

        Writes format: {unix_timestamp}:{status}
        Creates parent directories if they don't exist.

        Args:
            status: Current status (starting/running/idle/error/stopped).
        """
        try:
            self.health_file.parent.mkdir(parents=True, exist_ok=True)
            self.health_file.write_text(f"{int(time.time())}:{status}")
        except Exception as e:
            self._logger.error(f"Failed to update health status: {e}")

    def _calculate_sleep_seconds(self, config: TaskConfig) -> int:
        """
        Calculate seconds to sleep before next task run.

        Handles both interval-based (interval_minutes) and time-based (schedule_time)
        scheduling modes.

        Args:
            config: TaskConfig with scheduling parameters.

        Returns:
            Number of seconds to sleep before next execution.
        """
        if config.is_interval_based:
            return config.interval_minutes * 60

        # Time-based scheduling: calculate seconds until next occurrence
        if config.schedule_time:
            now = datetime.now(timezone.utc)
            parts = config.schedule_time.split(":")
            target_hour = int(parts[0])
            target_minute = int(parts[1])

            # Create target time for today
            target_today = now.replace(
                hour=target_hour, minute=target_minute, second=0, microsecond=0
            )

            # If target time has passed today, schedule for tomorrow
            if now >= target_today:
                target_today = target_today.replace(day=target_today.day + 1)
                # Handle month/year rollover using timedelta
                from datetime import timedelta

                target_today = now.replace(
                    hour=target_hour, minute=target_minute, second=0, microsecond=0
                ) + timedelta(days=1)

            seconds_until = (target_today - now).total_seconds()
            return int(seconds_until)

        # Fallback (should never reach here due to TaskConfig validation)
        return 3600

    async def _run_task_loop(self, config: TaskConfig) -> None:
        """
        Run a single task in a loop on its configured schedule.

        Each task runs in its own loop with isolated error handling.
        Errors are logged but do not stop the task from continuing.

        Args:
            config: TaskConfig defining the task and its schedule.
        """
        self._logger.info(f"Task '{config.name}' loop starting...")

        # Run immediately on start
        await self._execute_task(config)

        # Main task loop
        while self.running:
            try:
                sleep_seconds = self._calculate_sleep_seconds(config)
                self._logger.debug(f"Task '{config.name}' sleeping for {sleep_seconds} seconds")

                # Sleep in smaller intervals to check running flag and update health
                # Use 1-second intervals for responsive shutdown (important for tests)
                sleep_interval = 1
                elapsed = 0
                health_update_counter = 0
                while elapsed < sleep_seconds and self.running:
                    await asyncio.sleep(min(sleep_interval, sleep_seconds - elapsed))
                    elapsed += sleep_interval
                    health_update_counter += 1
                    # Update health status every 60 seconds to keep healthcheck happy
                    if health_update_counter >= 60:
                        self._update_health_status("running")
                        health_update_counter = 0

                if not self.running:
                    break

                await self._execute_task(config)

            except asyncio.CancelledError:
                self._logger.info(f"Task '{config.name}' cancelled")
                break
            except Exception as e:
                self._logger.error(f"Task '{config.name}' loop error: {e}", exc_info=True)
                # Continue running despite errors
                await asyncio.sleep(60)

        self._logger.info(f"Task '{config.name}' loop stopped")

    async def _execute_task(self, config: TaskConfig) -> None:
        """
        Execute a single task with error handling.

        Passes the container to the task handler for dependency injection.
        Updates per-task health status before and after execution.

        Args:
            config: TaskConfig defining the task to execute.
        """
        try:
            start_time = time.time()
            self._logger.info(
                f"Task '{config.name}' starting at "
                f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )

            # Update per-task health: running
            self._task_health_monitor.update_task_status(config.name, "running")

            # Call handler with container for dependency injection
            await config.handler(container=self._container)

            elapsed = time.time() - start_time
            self._logger.info(f"Task '{config.name}' completed successfully in {elapsed:.2f}s")

            # Update per-task health: success + last_run timestamp
            self._task_health_monitor.update_task_status(config.name, "success")
            self._task_health_monitor.update_task_last_run(config.name)

        except Exception as e:
            self._logger.error(f"Task '{config.name}' failed: {e}", exc_info=True)
            # Update per-task health: error
            self._task_health_monitor.update_task_status(config.name, "error")

    async def start(self) -> None:
        """
        Start the unified scheduler engine.

        Creates an asyncio.Task for each enabled task in the registry.
        Tasks run concurrently with independent error handling.
        """
        self._logger.info("UnifiedSchedulerEngine starting...")
        self._update_health_status("starting")

        # Get enabled tasks from registry
        enabled_tasks = self._registry.get_enabled_tasks()

        if not enabled_tasks:
            self._logger.warning("No enabled tasks found in registry")
            self._update_health_status("idle")
            # Keep running to allow signal handling (1s interval for responsive shutdown)
            while self.running:
                await asyncio.sleep(1)
            self._update_health_status("stopped")
            return

        self._logger.info(
            f"Starting {len(enabled_tasks)} tasks: " f"{[t.name for t in enabled_tasks]}"
        )

        # Register tasks with per-task health monitor
        for config in enabled_tasks:
            self._task_health_monitor.register_task(config)

        # Create asyncio.Task for each enabled task
        for config in enabled_tasks:
            task = asyncio.create_task(self._run_task_loop(config), name=f"task_{config.name}")
            self._tasks[config.name] = task

        self._update_health_status("running")

        # Wait for all tasks using gather with return_exceptions for fault isolation
        try:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        except asyncio.CancelledError:
            self._logger.info("Scheduler cancelled, stopping all tasks...")

        # Cleanup
        await self._stop_all_tasks()

        # Close DI container sessions (aioboto3/aiohttp) to prevent resource leak warnings
        try:
            from packages.core.typed_di_integration import cleanup_unified_container

            await cleanup_unified_container()
        except Exception as e:
            self._logger.error("Error during container cleanup: %s", e)

        self._update_health_status("stopped")
        self._logger.info("UnifiedSchedulerEngine stopped")

    async def _stop_all_tasks(self) -> None:
        """
        Stop all running tasks gracefully.

        Cancels each asyncio.Task and waits for completion.
        """
        self._logger.info("Stopping all tasks...")

        for name, task in self._tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=5.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    self._logger.debug(f"Task '{name}' cancelled")

        self._tasks.clear()

    def get_task_status(self) -> Dict[str, str]:
        """
        Get the status of all managed tasks.

        Returns:
            Dict mapping task names to their status (running/done/cancelled).
        """
        status = {}
        for name, task in self._tasks.items():
            if task.done():
                if task.cancelled():
                    status[name] = "cancelled"
                elif task.exception():
                    status[name] = "error"
                else:
                    status[name] = "done"
            else:
                status[name] = "running"
        return status
