#!/usr/bin/env python3
"""
Reliable async scheduler for metadata updater.
Replaces cron with a Python-native async solution.

Refactored to use BaseScheduler for reduced boilerplate.
"""

import asyncio

from channel_metadata_updater.async_runner import run_metadata_update
from packages.core.logging import setup_logger
from packages.core.schedulers import BaseScheduler

logger = setup_logger(__name__)


class MetadataUpdaterScheduler(BaseScheduler):
    """Scheduler for running metadata updates reliably in Docker."""

    def __init__(self):
        super().__init__(
            health_file_prefix="metadata_scheduler",
            interval_minutes=15,
            base_path="/tmp",
            run_on_start=True,
            scheduler_name="Metadata Updater Scheduler",
        )

    async def run_task(self) -> None:
        """Execute the metadata update task."""
        result = await run_metadata_update()

        # Log the result
        if result.get("statusCode") == 200:
            self.logger.info(f"Result: {result.get('body', {})}")
        else:
            self.logger.error(
                f"Update failed with status {result.get('statusCode')}: {result.get('body', {})}"
            )


async def async_main():
    """Async main entry point."""
    scheduler = MetadataUpdaterScheduler()
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
