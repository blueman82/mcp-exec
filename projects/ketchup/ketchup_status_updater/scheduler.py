#!/usr/bin/env python3
"""
Reliable async scheduler for status updater.
Replaces flaky cron with a Python-native async solution.

Migrated to use BaseScheduler for consolidated scheduler functionality.
"""

import asyncio
from pathlib import Path

from ketchup_status_updater.main import run_auto_status
from packages.core.logging import setup_logger
from packages.core.schedulers import BaseScheduler

logger = setup_logger(__name__)


class StatusUpdaterScheduler(BaseScheduler):
    """Scheduler for running status updates reliably in Docker."""

    def __init__(self):
        super().__init__(
            health_file_prefix="scheduler",
            base_path="/tmp",
            interval_minutes=55,
            run_on_start=True,
            scheduler_name="Status Updater Scheduler",
        )
        # Override for backward compatibility (original was /tmp/last_run)
        self.last_run_file = Path("/tmp/last_run")

    async def run_task(self) -> None:
        """Execute the status update task."""
        await run_auto_status()


async def async_main():
    """Async main entry point."""
    scheduler = StatusUpdaterScheduler()
    await scheduler.start()


def main():
    """Main entry point."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Scheduler interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error in scheduler: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
