#!/usr/bin/env python3
"""Scheduler for maintenance fetcher - runs daily at 1:30 AM UTC."""
import asyncio
import os
from datetime import datetime, timedelta, timezone

from ketchup_maintenance_fetcher.main import fetch_and_store_maintenance_data
from packages.core.logging import setup_logger
from packages.core.schedulers import BaseScheduler

logger = setup_logger(__name__)


class MaintenanceFetcherScheduler(BaseScheduler):
    """Scheduler for running maintenance fetch daily at 1:30 AM UTC."""

    TARGET_HOUR, TARGET_MINUTE = 1, 30

    def __init__(self):
        run_on_start = (
            os.getenv("KETCHUP_MAINTENANCE_FETCHER_RUN_ON_START", "false").lower() == "true"
        )
        super().__init__(
            health_file_prefix="maintenance_fetcher",
            base_path="/app/health",
            run_on_start=run_on_start,
            scheduler_name="Maintenance Fetcher Scheduler",
        )

    def get_sleep_seconds(self) -> int:
        """Calculate seconds until next 1:30 AM UTC."""
        now = datetime.now(timezone.utc)
        target = now.replace(
            hour=self.TARGET_HOUR, minute=self.TARGET_MINUTE, second=0, microsecond=0
        )
        if now >= target:
            target += timedelta(days=1)
        return int((target - now).total_seconds())

    async def run_task(self) -> None:
        result = await fetch_and_store_maintenance_data()
        self.logger.info(f"Maintenance fetch result: {result}")


async def async_main():
    await MaintenanceFetcherScheduler().start()


def main():
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Scheduler interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
