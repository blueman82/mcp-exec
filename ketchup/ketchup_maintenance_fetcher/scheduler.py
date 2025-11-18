#!/usr/bin/env python3
"""
Scheduler for maintenance fetcher.

Runs daily at 1:30 AM UTC using Python async scheduler.
"""

import asyncio
import os
import signal
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ketchup_maintenance_fetcher.main import fetch_and_store_maintenance_data
from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class MaintenanceFetcherScheduler:
    """Scheduler for running maintenance fetch daily at 1:30 AM UTC."""

    TARGET_HOUR = 1
    TARGET_MINUTE = 30

    def __init__(self):
        """Initialize the scheduler."""
        self.running = True
        self.health_file = Path("/app/health/maintenance_fetcher_health")
        self.last_run_file = Path("/app/health/maintenance_fetcher_last_run")
        self.run_on_start = (
            os.getenv("KETCHUP_MAINTENANCE_FETCHER_RUN_ON_START", "false").lower()
            == "true"
        )

        # Set up signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """
        Handle shutdown signals gracefully.

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def _update_health_status(self, status: str):
        """
        Update health check file.

        Args:
            status: Current status (starting/idle/running/error/stopped)
        """
        try:
            self.health_file.parent.mkdir(parents=True, exist_ok=True)
            self.health_file.write_text(f"{int(time.time())}:{status}")
        except Exception as e:
            logger.error(f"Failed to update health status: {e}")

    def _update_last_run(self):
        """Update last run timestamp."""
        try:
            self.last_run_file.parent.mkdir(parents=True, exist_ok=True)
            self.last_run_file.write_text(str(int(time.time())))
        except Exception as e:
            logger.error(f"Failed to update last run: {e}")

    def _seconds_until_target_time(self) -> int:
        """
        Calculate seconds until next 1:30 AM UTC.

        Uses timedelta to avoid month boundary issues (Jan 31 → Feb 1).

        Returns:
            Seconds until next scheduled run
        """
        now = datetime.now(timezone.utc)
        target = now.replace(
            hour=self.TARGET_HOUR, minute=self.TARGET_MINUTE, second=0, microsecond=0
        )

        # If target time has passed today, schedule for tomorrow
        if now >= target:
            target = target + timedelta(days=1)

        delta = target - now
        return int(delta.total_seconds())

    async def run_maintenance_fetch(self):
        """Run the maintenance fetch."""
        try:
            start_time = time.time()
            logger.info(
                f"Starting scheduled maintenance fetch at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
            )

            self._update_health_status("running")

            # Run fetch
            result = await fetch_and_store_maintenance_data()

            elapsed = time.time() - start_time
            logger.info(f"Maintenance fetch completed in {elapsed:.2f}s: {result}")

            # Update timestamps
            self._update_last_run()
            self._update_health_status("idle")

        except Exception as e:
            logger.error(f"Maintenance fetch failed: {e}", exc_info=True)
            self._update_health_status("error")

    async def _run_initial_fetch_if_enabled(self):
        """Run initial fetch if RUN_ON_START environment variable is true."""
        if self.run_on_start:
            logger.info("Running initial maintenance fetch (RUN_ON_START=true)")
            await self.run_maintenance_fetch()
        else:
            logger.info("Skipping initial fetch (RUN_ON_START=false)")

    async def start(self):
        """Start the scheduler."""
        logger.info("Maintenance Fetcher Scheduler starting...")
        logger.info(
            f"Scheduled to run daily at {self.TARGET_HOUR:02d}:{self.TARGET_MINUTE:02d} UTC"
        )

        self._update_health_status("starting")
        await self._run_initial_fetch_if_enabled()

        # Main scheduler loop
        logger.info("Entering main scheduler loop...")
        while self.running:
            try:
                # Calculate time until next 1:30 AM UTC
                seconds_until_run = self._seconds_until_target_time()
                logger.info(
                    f"Next run in {seconds_until_run} seconds ({seconds_until_run/3600:.1f} hours)"
                )

                # Wait until target time (checking health every minute)
                for _ in range(seconds_until_run // 60):
                    if not self.running:
                        break
                    self._update_health_status("idle")
                    await asyncio.sleep(60)

                # Sleep remaining seconds
                if self.running:
                    remaining = seconds_until_run % 60
                    await asyncio.sleep(remaining)

                # Run fetch at 1:30 AM UTC
                if self.running:
                    await self.run_maintenance_fetch()

            except asyncio.CancelledError:
                logger.info("Scheduler cancelled")
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}", exc_info=True)
                await asyncio.sleep(60)

        logger.info("Scheduler stopped")
        self._update_health_status("stopped")


async def async_main():
    """Async main entry point."""
    scheduler = MaintenanceFetcherScheduler()
    await scheduler.start()


def main():
    """Main entry point."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Scheduler interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
