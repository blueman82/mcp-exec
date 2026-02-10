"""Slack Socket Mode client.

Establishes WebSocket connection to Slack using Socket Mode.
Receives app_mention events and provides event handlers for bot interactions.
"""

import asyncio
from functools import partial

import structlog
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.errors import SlackApiError

from asksplunk.auth.validator import AccessValidator
from asksplunk.secrets import SecretsManager
from asksplunk.session.manager import SessionManager
from asksplunk.slack.formatter import (
    format_clarifying_question,
    format_final_query,
    format_uncertainty_message,
)
from asksplunk.usage import UsageTracker

logger = structlog.get_logger()

_FATAL_SLACK_ERRORS = frozenset({"invalid_auth", "account_inactive", "token_revoked", "not_authed"})


def _is_fatal_slack_error(error: Exception) -> bool:
    if isinstance(error, SlackApiError):
        return error.response.get("error", "") in _FATAL_SLACK_ERRORS
    return False


class SlackClient:
    """Slack client using Socket Mode for event-driven communication.

    Socket Mode eliminates the need for public HTTP endpoints by using
    WebSocket connections for bidirectional communication with Slack.

    Attributes:
        app: AsyncApp instance from slack-bolt
        app_token: Slack app-level token (xapp-*)
        handler: AsyncSocketModeHandler instance
        is_running: Connection status flag
        session_manager: SessionManager instance for conversation tracking
        access_validator: AccessValidator instance for authorization checks
        bot_user_id: Bot's Slack user ID (for mention stripping)
        agent: Agent instance for query generation (optional)
    """

    UNAUTHORIZED_MESSAGE = (
        "You don't currently have access to AskSplunk. "
        "This bot is in limited beta for the Adobe Campaign Operations team. "
        "If you believe you should have access, please contact ORG-OMEARA-ALL@adobe.com."
    )

    AUTH_TEST_TIMEOUT_SECONDS: float = 10.0
    AUTH_TEST_MAX_RETRIES: int = 3
    AUTH_TEST_BACKOFF_BASE: float = 1.0

    def __init__(
        self, bot_token: str, app_token: str, agent=None, usage_tracker: UsageTracker | None = None
    ) -> None:
        """Initialize Slack client with Socket Mode.

        Args:
            bot_token: Slack bot token (xoxb-*)
            app_token: Slack app-level token (xapp-*)
            agent: Agent instance for query processing (optional)
            usage_tracker: UsageTracker instance for DM event recording (optional)

        Example:
            client = SlackClient(
                bot_token="xoxb-...",
                app_token="xapp-...",
                agent=agent
            )
        """
        self.app = AsyncApp(token=bot_token)
        self.app_token = app_token
        self.handler: AsyncSocketModeHandler | None = None
        self.is_running = False
        self.session_manager: SessionManager | None = None  # Will be initialized in start()
        self._session_manager_context: SessionManager | None = None  # Store context manager itself
        self.access_validator: AccessValidator | None = None  # Will be initialized in start()
        self._secrets_manager_context: SecretsManager | None = None  # Store context manager itself
        self.bot_user_id: str | None = None  # Will be set when needed
        self.agent = agent  # Agent for query generation
        self.usage_tracker: UsageTracker | None = usage_tracker  # Can be passed in
        self._usage_tracker_context: UsageTracker | None = None  # Only set if we create it
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register Slack event handlers.

        Registers app_mention event handler that responds to bot mentions
        in channels where the bot is a member.

        Privacy note: Only logs metadata (user, channel, thread_ts).
        Never logs actual message content.
        """

        @self.app.event("app_mention")
        async def handle_mention(event, say, ack):
            """Handle bot mentions in Slack channels.

            Args:
                event: Slack event data containing user, channel, ts, text
                say: Function to send message response
                ack: Function to acknowledge event receipt

            Privacy: Logs metadata only - user ID, channel ID, thread timestamp.
            Never logs the actual message text.
            """
            await ack()

            # Extract thread context: use thread_ts if present (reply in thread),
            # otherwise use ts (new conversation - ts becomes the thread_ts)
            thread_ts = event.get("thread_ts") or event.get("ts")

            try:
                user_id = event.get("user")
                channel_id = event.get("channel")
                text = event.get("text", "")

                # Strip bot mention from text to get clean question
                if self.bot_user_id:
                    text = text.replace(f"<@{self.bot_user_id}>", "").strip()

                # Log only metadata - NEVER log message content
                logger.info(
                    "app_mention_received", user=user_id, channel=channel_id, thread_ts=thread_ts
                )

                # Check session_manager is initialized (should be after start() is called)
                if not self.session_manager:
                    logger.error("session_manager_not_initialized", thread_ts=thread_ts)
                    await say(
                        text="Bot is not ready yet. Please try again in a moment.",
                        thread_ts=thread_ts,
                    )
                    return

                # Access control check
                if self.access_validator and not await self.access_validator.is_authorized(user_id):
                    logger.info("unauthorized_access_attempt", user=user_id, channel=channel_id)
                    await say(text=self.UNAUTHORIZED_MESSAGE, thread_ts=thread_ts)
                    return

                # Check for existing session to determine if this is a new or continuing conversation
                session = await self.session_manager.get_session(thread_ts)

                # Process with agent if available
                if self.agent:
                    status_callback = partial(self._send_status, say, thread_ts)
                    result = await self.agent.process_question(
                        text, thread_ts, user_id, channel_id, status_callback=status_callback
                    )
                    await self._send_agent_response(say, result, thread_ts)
                elif session:
                    # No agent - just acknowledge continuation
                    logger.info("continuing_conversation", thread_ts=thread_ts)
                    await say(text="Continuing conversation...", thread_ts=thread_ts)
                else:
                    # No agent - create session only
                    logger.info("starting_new_conversation", thread_ts=thread_ts)
                    await self.session_manager.create_session(
                        thread_id=thread_ts, user_id=user_id, channel_id=channel_id, question=text
                    )
                    await say(text="Starting new query...", thread_ts=thread_ts)

            except Exception as e:
                # Log error with structured logging
                logger.error(
                    "mention_handler_error", error=str(e), thread_ts=thread_ts, exc_info=True
                )

                # Send user-friendly error message to Slack thread
                await say(
                    text="Sorry, I encountered an error processing your message. Please try again.",
                    thread_ts=thread_ts,
                )

        @self.app.event("message")
        async def handle_dm(event, say, ack):
            """Handle direct messages to the bot.

            Args:
                event: Slack event data containing user, channel, ts, text
                say: Function to send message response
                ack: Function to acknowledge event receipt

            Privacy: Logs metadata only - user ID, channel ID, thread timestamp.
            Never logs the actual message text.
            """
            # Only handle DMs (channel_type == "im"), ignore other message events
            if event.get("channel_type") != "im":
                return

            # Ignore bot's own messages
            if event.get("bot_id"):
                return

            await ack()

            # Record usage event (timestamp only - no user ID for privacy)
            if self.usage_tracker:
                try:
                    await self.usage_tracker.record_event()
                except Exception:
                    logger.warning("usage_tracking_failed", exc_info=True)

            thread_ts = event.get("thread_ts") or event.get("ts")

            try:
                user_id = event.get("user")
                channel_id = event.get("channel")
                text = event.get("text", "")

                # Strip bot mention from text if present
                if self.bot_user_id:
                    text = text.replace(f"<@{self.bot_user_id}>", "").strip()

                # Log only metadata - NEVER log message content
                logger.info("dm_received", user=user_id, channel=channel_id, thread_ts=thread_ts)

                # Check session_manager is initialized
                if not self.session_manager:
                    logger.error("session_manager_not_initialized", thread_ts=thread_ts)
                    await say(
                        text="Bot is not ready yet. Please try again in a moment.",
                        thread_ts=thread_ts,
                    )
                    return

                # Access control check
                if self.access_validator and not await self.access_validator.is_authorized(user_id):
                    logger.info("unauthorized_access_attempt", user=user_id, channel=channel_id)
                    await say(text=self.UNAUTHORIZED_MESSAGE, thread_ts=thread_ts)
                    return

                # Process with agent if available
                if self.agent:
                    status_callback = partial(self._send_status, say, thread_ts)
                    result = await self.agent.process_question(
                        text, thread_ts, user_id, channel_id, status_callback=status_callback
                    )
                    await self._send_agent_response(say, result, thread_ts)
                else:
                    # No agent - check for existing session
                    session = await self.session_manager.get_session(thread_ts)

                    if session:
                        logger.info("continuing_dm_conversation", thread_ts=thread_ts)
                        await say(text="Continuing conversation...", thread_ts=thread_ts)
                    else:
                        logger.info("starting_new_dm_conversation", thread_ts=thread_ts)
                        await self.session_manager.create_session(
                            thread_id=thread_ts,
                            user_id=user_id,
                            channel_id=channel_id,
                            question=text,
                        )
                        await say(text="Starting new query...", thread_ts=thread_ts)

            except Exception as e:
                logger.error("dm_handler_error", error=str(e), thread_ts=thread_ts, exc_info=True)
                await say(
                    text="Sorry, I encountered an error processing your message. Please try again.",
                    thread_ts=thread_ts,
                )

    async def _send_status(self, say, thread_ts: str, msg: str) -> None:
        """Send status message to a specific Slack thread.

        Used with functools.partial to create thread-specific callbacks.

        Args:
            say: Slack say function
            thread_ts: Thread timestamp for reply
            msg: Status message to send
        """
        logger.info("sending_status", thread_ts=thread_ts, msg=msg[:30])
        await say(text=msg, thread_ts=thread_ts)

    async def _send_agent_response(self, say, result: dict, thread_ts: str) -> None:
        """Send agent response to Slack using Block Kit formatting.

        Args:
            say: Slack say function
            result: Agent result dictionary with action and content
            thread_ts: Thread timestamp for reply
        """
        action = result.get("action")

        if action == "query_generated":
            # Format and send SPL query with explanations
            content = result.get("content", {})
            blocks = format_final_query(
                plain_explanation=content.get("plain_explanation", ""),
                spl_query=content.get("spl_query", ""),
                technical_explanation=content.get("technical_explanation", ""),
            )
            await say(
                text=f"SPL Query: {content.get('spl_query', '')}",
                blocks=blocks,
                thread_ts=thread_ts,
            )

        elif action == "clarify":
            # Format and send clarifying question
            content = result.get("content", {})
            question = content.get("question", "I need more information.")
            blocks = format_clarifying_question(
                question=question,
                options=content.get("options", []),
            )
            await say(text=question, blocks=blocks, thread_ts=thread_ts)

        elif action == "uncertain":
            # Agent cannot generate query
            content = result.get("content", {})
            missing_info = content.get("missing_info", "I don't have enough information.")
            blocks = format_uncertainty_message(missing_info)
            await say(
                text=f"I don't have enough information: {missing_info}",
                blocks=blocks,
                thread_ts=thread_ts,
            )

        elif action == "blocked":
            # Content was filtered (injection attempt or harmful content)
            content = result.get("content", {})
            message = content.get("message", "I cannot process that request.")
            await say(text=message, thread_ts=thread_ts)

        elif action == "usage_report":
            # Admin usage report
            content = result.get("content", {})
            message = content.get("message", "No usage data available.")
            await say(text=f":bar_chart: {message}", thread_ts=thread_ts)

        else:
            # Unknown action or processing state
            logger.warning("unknown_agent_action", action=action, thread_ts=thread_ts)
            await say(
                text="Processing your request...",
                thread_ts=thread_ts,
            )

    async def _auth_test_with_retry(self) -> dict:
        for attempt in range(self.AUTH_TEST_MAX_RETRIES):
            try:
                return await asyncio.wait_for(
                    self.app.client.auth_test(),
                    timeout=self.AUTH_TEST_TIMEOUT_SECONDS,
                )
            except Exception as e:
                if _is_fatal_slack_error(e):
                    logger.error("auth_test_fatal_error", error=str(e), attempt=attempt + 1)
                    raise
                if attempt + 1 >= self.AUTH_TEST_MAX_RETRIES:
                    logger.error(
                        "auth_test_failed_all_retries",
                        error=str(e),
                        attempts=self.AUTH_TEST_MAX_RETRIES,
                    )
                    raise
                backoff = self.AUTH_TEST_BACKOFF_BASE * (2**attempt)
                logger.warning(
                    "auth_test_retry",
                    error=str(e),
                    attempt=attempt + 1,
                    backoff_seconds=backoff,
                )
                await asyncio.sleep(backoff)
        raise RuntimeError("unreachable")  # pragma: no cover

    async def start(self) -> None:
        """Start Socket Mode connection.

        Creates AsyncSocketModeHandler and establishes WebSocket connection
        to Slack. Connection persists and automatically reconnects on failure.

        Initializes SessionManager as async context manager to maintain
        DynamoDB connection for the lifetime of the bot.

        Raises:
            SlackApiError: If connection fails or tokens are invalid

        Example:
            await client.start()  # Blocks until connection established
        """
        logger.info("starting_socket_mode_connection")

        # Initialize SecretsManager and AccessValidator
        self._secrets_manager_context = SecretsManager()
        secrets_manager = await self._secrets_manager_context.__aenter__()
        self.access_validator = AccessValidator(secrets_manager)

        # Store context manager, not just the entered value
        self._session_manager_context = SessionManager()
        self.session_manager = await self._session_manager_context.__aenter__()

        # Initialize UsageTracker if not provided via __init__
        if not self.usage_tracker:
            self._usage_tracker_context = UsageTracker()
            self.usage_tracker = await self._usage_tracker_context.__aenter__()

        # Initialize bot_user_id via auth_test API call (with retry)
        auth_response = await self._auth_test_with_retry()
        self.bot_user_id = auth_response["user_id"]
        logger.info("bot_user_initialized", bot_user_id=self.bot_user_id)

        self.handler = AsyncSocketModeHandler(self.app, self.app_token)
        self.is_running = True
        logger.info("socket_mode_handler_starting")
        try:
            await self.handler.start_async()
        except Exception as e:
            self.is_running = False
            if _is_fatal_slack_error(e):
                logger.error("socket_mode_fatal_error", error=str(e), exc_info=True)
            else:
                logger.warning("socket_mode_transient_error", error=str(e))
            raise
        logger.info("socket_mode_connected")

    async def shutdown(self) -> None:
        """Gracefully close WebSocket connection.

        Stops the Socket Mode handler and closes the WebSocket connection.
        Also closes the SessionManager context to properly clean up DynamoDB connection.
        Safe to call even if connection was never started.

        Example:
            await client.shutdown()  # Clean exit
        """
        logger.info("shutting_down_socket_mode")

        # Close session manager first with proper context
        if hasattr(self, "_session_manager_context") and self._session_manager_context:
            await self._session_manager_context.__aexit__(None, None, None)
            self._session_manager_context = None
            self.session_manager = None

        # Close secrets manager
        if hasattr(self, "_secrets_manager_context") and self._secrets_manager_context:
            await self._secrets_manager_context.__aexit__(None, None, None)
            self._secrets_manager_context = None
            self.access_validator = None

        # Close usage tracker only if we created it (not passed in)
        if hasattr(self, "_usage_tracker_context") and self._usage_tracker_context:
            await self._usage_tracker_context.__aexit__(None, None, None)
            self._usage_tracker_context = None
            self.usage_tracker = None

        # Then close socket handler
        if self.handler:
            self.is_running = False
            await self.handler.close_async()
        logger.info("socket_mode_closed")
