#!/usr/bin/env python3
"""
CSOPM Notifier Main Entry Point.

Standalone container for CSOPM (Customer Success Operations Project Management)
notifications. Runs the notification poll cycle at 08:00 and 16:00 UTC.

Services Orchestrated:
- CSOPMJIRAPoller: Polls JIRA for new CSOPM assignments
- CSOPMSlackNotifier: Sends Slack DM notifications
- CSOPMStateTracker: Tracks notification state in DynamoDB
- CSOPMReminderService: Processes RCA and closure reminders

Architectural Decisions:
- Standalone container (not unified scheduler): Enables independent scaling,
  simpler deployment, and isolated error handling for CSOPM-specific workloads.
- TypedDI container initialized once at startup: All services share the same
  container for efficient resource utilization (connection pools, etc.).
- Signal handlers for graceful shutdown: Responds to SIGTERM/SIGINT for
  clean container termination.

Health File:
    /tmp/csopm_notifier_health: {unix_timestamp}:{status}
    Docker healthcheck reads this file to verify container health.

Usage:
    # As module
    python -m ketchup_csopm_notifier.main

    # Via run() function (for Docker CMD)
    from ketchup_csopm_notifier.main import run
    run()
"""

import asyncio
import sys

from packages.core.typed_di_integration import get_unified_container
from ketchup_csopm_notifier.scheduler import CSOPMScheduler
from packages.core.logging import setup_logger

logger = setup_logger(__name__)


async def main() -> None:
    """
    Main entry point for the CSOPM notifier.

    Creates a TypedDI container with CSOPM services and starts the scheduler.
    The scheduler runs until a shutdown signal is received.

    Raises:
        Exception: If container initialization or scheduler fails.
    """
    logger.info("CSOPM Notifier starting...")

    try:
        # Create TypedDI container with CSOPM services
        # Container is created once at startup and shared by the scheduler
        logger.info("Initializing CSOPM DI container...")
        container = await get_csopm_container()
        logger.info("CSOPM DI container initialized successfully")

        # Create scheduler with container
        scheduler = CSOPMScheduler(
            container=container,
            health_file_prefix="csopm_notifier",
            base_path="/tmp",
            run_on_start=True,
        )

        # Start the scheduler (blocks until shutdown signal)
        await scheduler.start()

        logger.info("CSOPM Notifier stopped gracefully")

    except Exception as e:
        logger.error("CSOPM Notifier failed: %s", e, exc_info=True)
        raise


def run() -> None:
    """
    Run the CSOPM notifier.

    Entry point for Docker CMD and direct execution.
    Handles KeyboardInterrupt and other exceptions with appropriate exit codes.
    """
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("CSOPM Notifier interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error("Fatal error in CSOPM Notifier: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    run()
