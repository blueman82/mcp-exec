"""Worker entry point for background tasks.

This module provides the background worker that runs the polling loop
and Socket Mode event handling independently of the API server.
"""

import asyncio
import signal

import structlog

from bravo import __version__
from bravo.config import get_settings, load_settings
from bravo.container import create_container
from bravo.db import close_pool, init_pool
from bravo.db import queries
from bravo.services.blocks import build_reeval_result_blocks, format_trigger_reasons

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

        Hydrates settings from AWS (if enabled), initializes the database
        pool, and starts concurrent tasks for polling and Socket Mode.
        """
        self.settings = await load_settings()
        self.container = create_container(self.settings)
        logger.info("worker_starting", version=__version__)

        await init_pool(self.settings.database)
        await self.container.initialize_all()

        self.running = True

        poll_task = asyncio.create_task(self._poll_loop())
        socket_task = asyncio.create_task(self._socket_mode_loop())
        reeval_task = asyncio.create_task(self._reeval_loop())

        await asyncio.gather(poll_task, socket_task, reeval_task)

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
                result = await self.container.get("poller_service").run_poll()  # type: ignore[attr-defined]
                logger.info("poll_complete", **result)
            except Exception as e:
                logger.error("poll_error", error=str(e))

            await asyncio.sleep(self.settings.poll_interval_minutes * 60)

    async def _reeval_loop(self) -> None:
        """Re-evaluation queue consumer loop.

        Polls the re_evaluation_queue every 10 seconds, processes one
        job at a time (sequential to prevent LLM API overload), and
        updates the original Slack DM with the re-eval result.
        """
        while self.running:
            try:
                # Reap stale jobs on each cycle (crash recovery)
                reaped = await queries.reap_stale_jobs(timeout_minutes=10)
                if reaped:
                    logger.info("reeval_stale_jobs_reaped", count=reaped)

                job = await queries.dequeue_re_evaluation()
                if job:
                    await self._process_reeval_job(job)
            except Exception:
                logger.exception("reeval_loop_error")

            await asyncio.sleep(10)

    async def _process_reeval_job(self, job: dict) -> None:
        """Process a single re-evaluation queue entry.

        Args:
            job: The dequeued re_evaluation_queue record.
        """
        queue_id = job["id"]
        ticket_key = job["ticket_key"]
        channel_id = job["channel_id"]
        message_ts = job["message_ts"]

        logger.info("reeval_processing", ticket_key=ticket_key, queue_id=str(queue_id))

        try:
            nudge_service = self.container.get("nudge_service")
            result = await nudge_service.evaluate_ticket(ticket_key, force=True)  # type: ignore[attr-defined]

            should_nudge = result.get("should_nudge", False)
            gate_result = result.get("gate_result")

            # Build human-readable trigger reason (no gate codes)
            if should_nudge and gate_result and gate_result.any_failed:
                failed_codes = [
                    code for code, passed in [
                        ("G1", gate_result.g1_passed),
                        ("G2", gate_result.g2_passed),
                        ("G3", gate_result.g3_passed),
                        ("G4", gate_result.g4_passed),
                    ]
                    if not passed
                ]
                trigger_reason = format_trigger_reasons(failed_codes)
            elif should_nudge:
                nudge_reason = result.get("nudge_reason", "")
                trigger_reason = nudge_reason
            else:
                trigger_reason = ""

            if should_nudge:
                result_text = f"Re-evaluation: still needs attention \u2014 {trigger_reason}"
            else:
                result_text = "Re-evaluation: all checks passed"

            await queries.complete_re_evaluation(queue_id, result_text)

            # Update original Slack DM with prominent result
            if channel_id and message_ts:
                slack_service = self.container.get("slack_service")
                original_blocks = await slack_service._fetch_message_blocks(  # type: ignore[attr-defined]
                    channel_id, message_ts,
                )
                updated_blocks = build_reeval_result_blocks(
                    original_blocks=original_blocks,
                    passed=not should_nudge,
                    trigger_reason=trigger_reason,
                )
                await slack_service.update_message(  # type: ignore[attr-defined]
                    channel=channel_id,
                    ts=message_ts,
                    text=result_text,
                    blocks=updated_blocks,
                )

            logger.info(
                "reeval_completed",
                ticket_key=ticket_key,
                queue_id=str(queue_id),
                should_nudge=should_nudge,
            )

        except Exception as exc:
            error_msg = str(exc)
            logger.exception(
                "reeval_processing_failed",
                ticket_key=ticket_key,
                queue_id=str(queue_id),
            )
            await queries.fail_re_evaluation(queue_id, error_msg)

    async def _socket_mode_loop(self) -> None:
        """Socket Mode event handling loop.

        Starts the Slack Socket Mode client for receiving interactive events.
        """
        await self.container.get("slack_service").start_socket_mode()  # type: ignore[attr-defined]


async def run_worker() -> None:
    """Run the worker with signal handling.

    Sets up SIGTERM and SIGINT handlers for graceful shutdown.
    """
    worker = Worker()

    loop = asyncio.get_running_loop()

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
