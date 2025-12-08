#!/usr/bin/env python3
"""
BaseScheduler abstract base class for scheduler consolidation.

Provides common functionality for all Ketchup schedulers:
- Signal handling (SIGTERM, SIGINT) with graceful shutdown
- Health file management (timestamp:status format)
- Last run file tracking
- Main async loop with running flag
- Support for both interval-based and time-based scheduling
"""

import asyncio
import signal
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from packages.core.logging import setup_logger


class BaseScheduler(ABC):
    """
    Abstract base class for Ketchup schedulers.

    Provides common functionality including signal handling, health file management,
    and the main scheduler loop. Subclasses must implement the run_task() method.

    Supports both interval-based scheduling (every N minutes) and time-based
    scheduling (daily at specific time) through the get_sleep_seconds() method.

    Attributes:
        running: Boolean flag indicating if scheduler should continue running.
        health_file: Path to health status file.
        last_run_file: Path to last run timestamp file.
        interval_minutes: Default interval between runs in minutes.
        run_on_start: Whether to run task immediately on startup.
        scheduler_name: Name used for logging.
    """

    def __init__(
        self,
        health_file_prefix: str,
        base_path: str = "/tmp",
        interval_minutes: int = 60,
        run_on_start: bool = True,
        scheduler_name: Optional[str] = None,
    ):
        """
        Initialize the base scheduler.

        Args:
            health_file_prefix: Prefix for health/last_run files (e.g., 'scheduler', 'metadata_scheduler')
            base_path: Base directory for health files (default: '/tmp', some use '/app/health/')
            interval_minutes: Minutes between runs for interval-based scheduling (default: 60)
            run_on_start: Whether to run task immediately on startup (default: True)
            scheduler_name: Name for logging (defaults to class name)
        """
        self.running = True
        self.interval_minutes = interval_minutes
        self.run_on_start = run_on_start
        self.scheduler_name = scheduler_name or self.__class__.__name__

        # Set up health file paths
        base = Path(base_path)
        self.health_file = base / f"{health_file_prefix}_health"
        self.last_run_file = base / f"{health_file_prefix}_last_run"

        # Set up logger
        self.logger = setup_logger(self.__class__.__module__)

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """
        Handle shutdown signals gracefully.

        Args:
            signum: Signal number received
            frame: Current stack frame (unused)
        """
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    def _update_health_status(self, status: str) -> None:
        """
        Update health check file with current status.

        Writes format: {unix_timestamp}:{status}
        Creates parent directories if they don't exist.

        Args:
            status: Current status (starting/idle/running/error/stopped)
        """
        try:
            self.health_file.parent.mkdir(parents=True, exist_ok=True)
            self.health_file.write_text(f"{int(time.time())}:{status}")
        except Exception as e:
            self.logger.error(f"Failed to update health status: {e}")

    def _update_last_run(self) -> None:
        """
        Update last run timestamp for health checks.

        Writes the current unix timestamp to the last_run file.
        Creates parent directories if they don't exist.
        """
        try:
            self.last_run_file.parent.mkdir(parents=True, exist_ok=True)
            self.last_run_file.write_text(str(int(time.time())))
        except Exception as e:
            self.logger.error(f"Failed to update last run timestamp: {e}")

    def get_sleep_seconds(self) -> int:
        """
        Get seconds to sleep before next run.

        Default implementation returns interval_minutes * 60.
        Override this method for time-based scheduling (e.g., daily at specific time).

        Returns:
            Number of seconds to sleep before next task execution.
        """
        return self.interval_minutes * 60

    @abstractmethod
    async def run_task(self) -> None:
        """
        Execute the scheduled task.

        Subclasses must implement this method with their specific task logic.
        This method should:
        1. Log the start of the task
        2. Update health status to 'running'
        3. Perform the actual work
        4. Update health status to 'idle' on success or 'error' on failure

        Note: The base class handles calling _update_last_run() and health status
        updates around the task execution, but subclasses may add additional
        status updates if needed.
        """
        pass

    async def _execute_task_with_tracking(self) -> None:
        """
        Execute the task with timing and health tracking.

        Wraps run_task() with logging and error handling.
        """
        try:
            start_time = time.time()
            self.logger.info(
                "Starting scheduled task at %s",
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            )

            self._update_health_status("running")

            await self.run_task()

            elapsed = time.time() - start_time
            self.logger.info(f"Task completed successfully in {elapsed:.2f} seconds")

            # Update timestamps for health checks
            self._update_last_run()
            self._update_health_status("idle")

        except Exception as e:
            self.logger.error(f"Task failed: {e}", exc_info=True)
            self._update_health_status("error")

    async def start(self) -> None:
        """
        Start the scheduler main loop.

        Template method that:
        1. Logs startup message
        2. Marks health status as 'starting'
        3. Optionally runs task immediately (if run_on_start=True)
        4. Enters main loop: sleep for get_sleep_seconds(), updating health every minute
        5. Runs task after sleep completes
        6. Handles graceful shutdown on signals or cancellation
        """
        self.logger.info(f"{self.scheduler_name} starting...")

        sleep_seconds = self.get_sleep_seconds()
        if sleep_seconds >= 3600:
            self.logger.info(f"Scheduled to run every {sleep_seconds / 3600:.1f} hours")
        else:
            self.logger.info(f"Scheduled to run every {sleep_seconds // 60} minutes")

        # Mark as healthy
        self._update_health_status("starting")

        # Optionally run immediately on startup
        if self.run_on_start:
            self.logger.info("Running initial task...")
            await self._execute_task_with_tracking()
        else:
            self.logger.info("Skipping initial task (run_on_start=False)")

        # Main scheduler loop
        self.logger.info("Entering main scheduler loop...")
        while self.running:
            try:
                # Recalculate sleep time (important for time-based scheduling)
                sleep_seconds = self.get_sleep_seconds()

                if not self.running:
                    break

                # Sleep while updating health every minute
                minutes_to_wait = sleep_seconds // 60
                for _ in range(minutes_to_wait):
                    if not self.running:
                        break
                    self._update_health_status("idle")
                    await asyncio.sleep(60)  # Wait 1 minute

                # Sleep remaining seconds
                if self.running:
                    remaining_seconds = sleep_seconds % 60
                    if remaining_seconds > 0:
                        await asyncio.sleep(remaining_seconds)

                # Run the task
                if self.running:
                    await self._execute_task_with_tracking()

            except asyncio.CancelledError:
                self.logger.info("Scheduler cancelled")
                break
            except Exception as e:
                self.logger.error(f"Scheduler loop error: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait a minute before retrying

        self.logger.info("Scheduler stopped")
        self._update_health_status("stopped")
