#!/usr/bin/env python3
"""
Scheduler for PAT rotation service.

Runs daily PAT rotation check using Python async scheduler.
Follows pattern of ketchup_status_updater and ketchup_maintenance_fetcher.
"""

import asyncio
import signal
import time
from datetime import datetime
from pathlib import Path

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class PatRotationScheduler:
    """Scheduler for running PAT rotation checks every 24 hours."""

    ROTATION_INTERVAL_SECONDS = 24 * 60 * 60  # 24 hours

    def __init__(self):
        """Initialize the scheduler."""
        self.running = True
        self.health_file = Path("/tmp/pat_rotator_health")
        self.last_run_file = Path("/tmp/pat_rotator_last_run")

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """
        Handle shutdown signals gracefully.

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    def _update_health_status(self, status: str):
        """
        Update health check file with current status.

        Args:
            status: Current status (starting/idle/running/error/stopped)
        """
        try:
            self.health_file.write_text(f"{int(time.time())}:{status}")
        except Exception as e:
            logger.error(f"Failed to update health status: {e}")

    def _update_last_run(self):
        """Update last run timestamp for health checks."""
        try:
            self.last_run_file.write_text(str(int(time.time())))
        except Exception as e:
            logger.error(f"Failed to update last run timestamp: {e}")

    async def run_rotation_check(self):
        """
        Run the PAT rotation check asynchronously.

        This is a placeholder that will be implemented with actual rotation logic.
        """
        try:
            start_time = time.time()
            logger.info(
                "Starting scheduled PAT rotation check at %s",
                datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            )

            self._update_health_status("running")

            # TODO: Implement actual PAT rotation logic
            # This will call the rotation service to check and rotate PATs
            await asyncio.sleep(0.1)  # Placeholder async operation

            elapsed = time.time() - start_time
            logger.info(f"PAT rotation check completed successfully in {elapsed:.2f} seconds")

            # Update timestamps for health checks
            self._update_last_run()
            self._update_health_status("idle")

        except Exception as e:
            logger.error(f"PAT rotation check failed: {e}", exc_info=True)
            self._update_health_status("error")

    async def start(self):
        """Start the async scheduler."""
        logger.info("PAT Rotation Scheduler starting...")
        logger.info("Scheduled to run every 24 hours")

        # Mark as healthy
        self._update_health_status("starting")

        # Run immediately on startup
        logger.info("Running initial PAT rotation check...")
        await self.run_rotation_check()

        # Main scheduler loop
        logger.info("Entering main scheduler loop...")
        while self.running:
            try:
                # Wait 24 hours before next run
                # Update health status every minute during the wait
                if not self.running:
                    break

                # Update health status every minute for 24 hours
                # 24 hours = 1440 minutes
                for i in range(1440):  # 1440 minutes (24 hours)
                    if not self.running:
                        break
                    self._update_health_status("idle")
                    await asyncio.sleep(60)  # Wait 1 minute

                if self.running:  # Check if we should still be running
                    await self.run_rotation_check()

            except asyncio.CancelledError:
                logger.info("Scheduler cancelled")
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait a minute before retrying

        logger.info("Scheduler stopped")
        self._update_health_status("stopped")


async def async_main():
    """Async main entry point."""
    scheduler = PatRotationScheduler()
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
