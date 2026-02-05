"""Application entry point for AskSplunk Slack bot.

Handles application startup, signal handling, and graceful shutdown.
Fetches secrets from AWS Secrets Manager and starts the Slack Socket Mode client.
"""

import asyncio
import os
import signal
import sys

import chromadb
import structlog
from openai import AsyncAzureOpenAI

from asksplunk.agent.orchestrator import Agent
from asksplunk.retriever.retriever import DocumentRetriever
from asksplunk.secrets import SecretsManager
from asksplunk.session.manager import SessionManager
from asksplunk.slack.client import SlackClient
from asksplunk.usage import UsageTracker

logger = structlog.get_logger()


async def shutdown(client: SlackClient, loop: asyncio.AbstractEventLoop) -> None:
    """Gracefully shutdown the application.

    Stops the Slack client, closes all async tasks, and stops the event loop.
    Ensures all resources are properly cleaned up before exit.

    Args:
        client: SlackClient instance to shutdown
        loop: Event loop to stop

    Example:
        await shutdown(client, asyncio.get_event_loop())
    """
    logger.info("shutdown_initiated")

    try:
        # Shutdown Slack client (also closes SessionManager)
        await client.shutdown()
        logger.info("slack_client_shutdown_complete")
    except Exception as e:
        logger.error("shutdown_error", error=str(e), exc_info=True)

    # Stop the event loop
    loop.stop()
    logger.info("event_loop_stopped")


def create_signal_handler(client: SlackClient, loop: asyncio.AbstractEventLoop):
    """Create signal handler for graceful shutdown.

    Args:
        client: SlackClient instance to shutdown
        loop: Event loop to stop

    Returns:
        Signal handler function that creates shutdown task

    Example:
        handler = create_signal_handler(client, loop)
        signal.signal(signal.SIGTERM, handler)
    """

    def handle_signal(signum: int, _frame) -> None:
        """Handle termination signals.

        Args:
            signum: Signal number received
            _frame: Current stack frame (unused)
        """
        sig_name = signal.Signals(signum).name
        logger.info("signal_received", signal=sig_name)
        asyncio.create_task(shutdown(client, loop))

    return handle_signal


async def main() -> None:
    """Main application entry point.

    Performs the following steps:
    1. Fetches Slack tokens and OpenAI config from AWS Secrets Manager
    2. Creates ChromaDB client and DocumentRetriever
    3. Creates Agent with retriever and OpenAI client
    4. Creates SlackClient with agent
    5. Registers signal handlers for SIGTERM and SIGINT
    6. Starts the Socket Mode connection (blocks until shutdown)

    Raises:
        Exception: If startup fails or secrets cannot be retrieved

    Example:
        asyncio.run(main())
    """
    logger.info("application_starting")

    client: SlackClient | None = None
    secrets_manager_ctx: SecretsManager | None = None
    session_manager_ctx: SessionManager | None = None
    usage_tracker_ctx: UsageTracker | None = None

    try:
        # Create SecretsManager (kept open for dynamic admin lookups)
        logger.info("fetching_secrets")
        secrets_manager_ctx = SecretsManager()
        secrets_manager = await secrets_manager_ctx.__aenter__()

        tokens = await secrets_manager.get_slack_tokens()
        bot_token = tokens["bot_token"]
        app_token = tokens["app_token"]
        openai_config = await secrets_manager.get_azure_openai_config()

        logger.info("secrets_retrieved")

        # Create Azure OpenAI client
        openai_client = AsyncAzureOpenAI(
            azure_endpoint=openai_config["endpoint"],
            api_key=openai_config["api_key"],
            api_version=openai_config.get("api_version", "2024-02-15-preview"),
        )
        logger.info("openai_client_created")

        # Create ChromaDB client
        chromadb_host = os.environ.get("CHROMADB_HOST", "localhost")
        chromadb_port = int(os.environ.get("CHROMADB_PORT", "8000"))
        chroma_client = chromadb.HttpClient(host=chromadb_host, port=chromadb_port)
        logger.info("chromadb_client_created", host=chromadb_host, port=chromadb_port)

        # Create DocumentRetriever
        retriever = DocumentRetriever(openai_client=openai_client, chroma_client=chroma_client)
        logger.info("retriever_created")

        # Create SessionManager
        session_manager_ctx = SessionManager()
        session_manager = await session_manager_ctx.__aenter__()
        logger.info("session_manager_created")

        # Create UsageTracker
        usage_tracker_ctx = UsageTracker()
        usage_tracker = await usage_tracker_ctx.__aenter__()
        logger.info("usage_tracker_created")

        # Create Agent
        chat_model = openai_config.get("chat_deployment", "gpt-5")
        agent = Agent(
            retriever=retriever,
            session_manager=session_manager,
            openai_client=openai_client,
            chat_model=chat_model,
            usage_tracker=usage_tracker,
        )
        logger.info("agent_created")

        # Create Slack client with agent and usage tracker
        client = SlackClient(
            bot_token=bot_token,
            app_token=app_token,
            agent=agent,
            usage_tracker=usage_tracker,
        )
        logger.info("slack_client_created")

        # Register signal handlers for graceful shutdown
        loop = asyncio.get_event_loop()
        signal_handler = create_signal_handler(client, loop)

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        logger.info("signal_handlers_registered", signals=["SIGTERM", "SIGINT"])

        # Start the bot (blocks until shutdown signal received)
        logger.info("starting_slack_bot")
        await client.start()

    except KeyboardInterrupt:
        logger.info("keyboard_interrupt_received")
        if client:
            await shutdown(client, asyncio.get_event_loop())

    except Exception as e:
        logger.error("application_startup_error", error=str(e), exc_info=True)
        # Ensure cleanup runs even on startup failure
        if client:
            try:
                await client.shutdown()
            except Exception as shutdown_error:
                logger.error("cleanup_error", error=str(shutdown_error), exc_info=True)
        # Clean up usage tracker if created (client.shutdown won't close it since we passed it in)
        if usage_tracker_ctx:
            try:
                await usage_tracker_ctx.__aexit__(None, None, None)
            except Exception as tracker_error:
                logger.error("usage_tracker_cleanup_error", error=str(tracker_error), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    """Entry point when running as script.

    Example:
        python -m asksplunk.main
    """
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("application_terminated_by_user")
        sys.exit(0)
