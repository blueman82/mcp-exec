"""Worker entry point for background tasks.

This module provides the background worker that runs the polling loop
and Socket Mode event handling independently of the API server.
"""

import asyncio
import signal

import structlog

from bravo import __version__
from bravo.config import get_settings
from bravo.container import create_container
from bravo.db import close_pool, init_pool

logger = structlog.get_logger(__name__)


class Worker:
    """Background worker for polling and processing.

    Runs concurrent tasks for Jira polling and Slack Socket Mode
    event handling.

    Attributes:
        settings: Application configuration.
        running: Whether the worker is currently running.
        container: Service registry managing all service lifecycles.
    """

    def __init__(self) -> None:
        """Initialize the worker with all required services."""
        self.settings = get_settings()
        self.running = False
        self.container = create_container(self.settings)

    async def start(self) -> None:
        """Start the worker.

        Initializes the database pool and starts concurrent tasks for
        polling and Socket Mode event handling.
        """
        logger.info("worker_starting", version=__version__)

        await init_pool(self.settings.database)
        await self.container.initialize_all()

        self.running = True

        poll_task = asyncio.create_task(self._poll_loop())
        socket_task = asyncio.create_task(self._socket_mode_loop())

        await asyncio.gather(poll_task, socket_task)

    async def stop(self) -> None:
        """Stop the worker gracefully.

        Closes all service connections and the database pool.
        """
        logger.info("worker_stopping")
        self.running = False

        await self.container.shutdown_all()
        await close_pool()

        logger.info("worker_stopped")

    async def _poll_loop(self) -> None:
        """Main polling loop.

        Continuously polls Jira at the configured interval until stopped.
        """
        while self.running:
            try:
                result = await self.container.get("poller_service").run_poll()
                logger.info("poll_complete", **result)
            except Exception as e:
                logger.error("poll_error", error=str(e))

            await asyncio.sleep(self.settings.poll_interval_minutes * 60)

    async def _socket_mode_loop(self) -> None:
        """Socket Mode event handling loop.

        Starts the Slack Socket Mode client for receiving interactive events.
        """
        await self.container.get("slack_service").start_socket_mode()


async def run_worker() -> None:
    """Run the worker with signal handling.

    Sets up SIGTERM and SIGINT handlers for graceful shutdown.
    """
    worker = Worker()

    loop = asyncio.get_event_loop()

    def handle_signal() -> None:
        asyncio.create_task(worker.stop())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal)

    await worker.start()


def main() -> None:
    """Worker entry point.

    Runs the async worker using asyncio.run().
    """
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
