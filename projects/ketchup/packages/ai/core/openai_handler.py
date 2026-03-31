"""
openai_handler.py

OpenAI Handler based on AzureAsyncClient

This module provides an improved implementation of the OpenAIHandler using
the AzureAsyncClient base class for better connection management and error handling,
delegating specific tasks to specialized submodules.
"""

from typing import Any, Dict, List, Optional, Tuple

import orjson

from packages.ai.core.azure_async_client import AzureAsyncClient
from packages.ai.core.operations.api_interaction import ApiExecutor
from packages.ai.core.operations.message_preparation import MessagePreparer
from packages.ai.core.operations.token_management import TokenManager
from packages.ai.cost_calculator import TokenTracker
from packages.core.async_client import ExponentialBackoffStrategy
from packages.core.config.feature_flags import FeatureFlags
from packages.core.constants import AZURE_OPENAI_ENDPOINT
from packages.core.exceptions import MessagePreparationError
from packages.core.logging import setup_logger
from packages.secrets.manager import SecretsManager
from packages.slack.channel_operations.channel_archive_ops import SlackChannelArchiveOps
from packages.slack.channel_operations.channel_info_ops import ChannelInfoOps
from packages.slack.channel_operations.channel_msg_ops import SlackChannelMessageOps

logger = setup_logger(__name__)


# Define a custom exception for clarity if not already defined globally
class OpenAIError(Exception):
    """Custom exception for OpenAI related errors."""

    # No custom attributes or methods needed; inherits all from Exception.
    # 'pass' is used as a syntactic placeholder because the class body cannot be empty.
    pass


class OpenAIHandler(AzureAsyncClient):
    """
    Acts as a Facade, orchestrating interactions with Azure OpenAI API.

    Delegates tasks like message preparation, token management, and API execution
    to specialized submodule classes. Inherits from AzureAsyncClient for connection
    management.
    """

    def __init__(
        self,
        token_tracker: TokenTracker,
        secrets_manager: SecretsManager,
        channel_info_ops: ChannelInfoOps,
        channel_msg_ops: SlackChannelMessageOps,
        channel_ops: SlackChannelArchiveOps,
        jira_extractor: Optional[
            Any
        ] = None,  # Optional[JIRADataExtractor] - using Any to avoid circular import
    ):
        """Initialize the OpenAI handler with injected dependencies."""
        # Define a more persistent backoff strategy
        persistent_backoff_strategy = ExponentialBackoffStrategy(
            max_retries=10,
            base_delay=1.0,
            max_delay=60.0,
            jitter=True,
        )
        logger.info(
            f"OpenAIHandler: Initializing with AZURE_OPENAI_ENDPOINT: {AZURE_OPENAI_ENDPOINT}"
        )
        super().__init__(
            api_key=None,  # API key set during initialize
            endpoint=AZURE_OPENAI_ENDPOINT,
            max_concurrent_requests=5,  # Balanced for concurrent users while reducing resource overhead
            request_timeout=180,
            backoff_strategy=persistent_backoff_strategy,  # Pass the custom strategy
        )
        # Store injected dependencies needed by submodules
        self._token_tracker = token_tracker
        self._secrets_manager = secrets_manager
        self._channel_info_ops = channel_info_ops
        self._channel_msg_ops = channel_msg_ops
        self._channel_ops = channel_ops
        self._jira_extractor = jira_extractor

        # Instantiate stateless/dependency-free submodules here
        self._token_manager = TokenManager()
        self._message_preparer = MessagePreparer(
            token_tracker=self._token_tracker,
            channel_msg_ops=self._channel_msg_ops,
            channel_info_ops=self._channel_info_ops,
        )

        # Defer instantiation of ApiExecutor until API key is available
        self._api_executor: Optional[ApiExecutor] = None
        self._lb_api_key: Optional[str] = None  # Store the key locally

    async def initialize(self) -> "OpenAIHandler":
        """
        Initialize the base client session and submodule dependencies requiring API keys.

        Returns:
            Self for method chaining.
        """
        logger.info("Initializing OpenAIHandler and submodules...")
        # Fetch API key using injected secrets_manager
        self._api_key = (
            await self._secrets_manager.get_azure_openai_lb_api_key()
        )  # Used by base client
        self._lb_api_key = self._api_key  # Store LB key explicitly

        if not self._lb_api_key:
            raise ValueError("Failed to retrieve Azure OpenAI LB API key.")

        # Initialize the base AzureAsyncClient session
        await self.setup()

        # Check if endpoint is None after setup (shouldn't be, but safety check)
        if self._endpoint is None:
            raise ValueError(
                "Azure OpenAI endpoint is None after setup. Cannot initialize ApiExecutor."
            )

        # Now instantiate ApiExecutor with the fetched key and base client's request method
        self._api_executor = ApiExecutor(
            api_request_func=self._make_azure_api_request,  # Pass the actual request func
            endpoint=self._endpoint,
            api_key=self._lb_api_key,
            token_tracker=self._token_tracker,
            channel_archive_ops=self._channel_ops,
        )

        logger.info("OpenAIHandler initialized successfully.")
        return self

    async def _get_or_prepare_messages(
        self,
        messages: Optional[List[Dict[str, str]]],
        combined_command: Optional[str],
        user_id: Optional[str],
        incoming_channel: Optional[str],
        passed_channel_id: Optional[str],
        channel_name: Optional[str],
        query_text: Optional[str],
        oldest_ts: str = "0",
        normalized_prefs_for_ai: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Dict[str, str]], Optional[Dict[str, Any]]]:
        """
        Returns the provided messages or prepares them using MessagePreparer.

        Handles parameter validation and catches MessagePreparationError.

        Args:
            messages: Optional list of messages to use directly.
            combined_command: The verified command string.
            user_id: The Slack user ID.
            incoming_channel: The channel where the command was issued.
            passed_channel_id: The target channel ID (if provided).
            channel_name: The name of the channel (may be fetched).
            query_text: The query text for query commands.
            oldest_ts: Slack timestamp for filtering messages. "0" means fetch all messages.
            normalized_prefs_for_ai: Optional dictionary of normalized user preferences for AI.

        Returns:
            Tuple containing the list of messages and optional channel_info.
            Messages list might contain error indicators if preparation failed.

        Raises:
            ValueError: If required parameters are missing when messages need preparation.
        """
        if messages is not None:
            logger.info("Using directly provided messages.")
            # If messages are provided, channel_info is not fetched/needed here.
            return messages, None

        # Messages need preparation
        logger.info("Preparing messages using MessagePreparer.")
        if not combined_command or not user_id or not incoming_channel:
            # Raise ValueError for missing core parameters needed for prep
            raise ValueError(
                "Missing required parameters (command, user_id, incoming_channel) for message preparation."
            )

        try:
            # Attempt to prepare messages using the MessagePreparer
            prepared_messages, channel_info = await self._message_preparer.prepare_messages(
                combined_command=combined_command,
                user_id=user_id,
                incoming_channel=incoming_channel,
                passed_channel_id=passed_channel_id,
                channel_name=channel_name,
                query_text=query_text,
                oldest_ts=oldest_ts,
                normalized_user_preferences=normalized_prefs_for_ai,
            )
            # Enrich with JIRA context if available
            enriched_messages = await self._enrich_with_jira_context(
                prepared_messages, passed_channel_id or incoming_channel
            )

            # Return the successfully prepared messages and any channel info obtained
            return enriched_messages, channel_info

        except MessagePreparationError as e:
            # Catch the specific error raised by MessagePreparer
            logger.error("Message preparation failed: %s", e)
            # Re-raise the exception instead of converting to AI messages
            # This allows the calling command to handle the error appropriately
            # and prevents error details from being sent to the AI
            raise

    def _parse_json_response(self, raw_content: str) -> str:
        """Parse JSON response and extract response_text.

        Raises:
            orjson.JSONDecodeError: If raw_content is not valid JSON.
        """
        from packages.ai.core.json_response import safe_extract_response_text

        result = safe_extract_response_text(raw_content, fallback="")
        if not result:
            # Raise so _extract_response_content can retry
            raise ValueError("Empty response_text from JSON extraction")
        return result

    async def _extract_response_content(
        self,
        raw_content: str,
        messages: List[Dict[str, str]],
        normalized_prefs_for_ai: Dict[str, Any],
    ) -> str:
        """Extract response text, retrying once on JSON parse failure."""
        if not FeatureFlags.is_structured_json_output_enabled():
            return raw_content

        try:
            extracted = self._parse_json_response(raw_content)
            logger.info("Extracted text from JSON response (%d chars)", len(extracted))
            return extracted
        except (orjson.JSONDecodeError, ValueError):
            logger.warning("JSON parse failed, retrying API call once")

        try:
            response = await self.call_openai_endpoint(
                messages=messages,
                normalized_prefs_for_ai=normalized_prefs_for_ai,
            )
            retry_content = response["choices"][0]["message"]["content"]
            extracted = self._parse_json_response(retry_content)
            logger.info("Retry succeeded, extracted text (%d chars)", len(extracted))
            return extracted
        except Exception as e:
            logger.error("Retry also failed, returning raw content: %s", e)

        return raw_content

    async def process_with_context(
        self,
        messages: List[Dict[str, str]],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        max_context_messages: int = 10,
        reasoning_effort: str = "low",
        max_tokens: int = 1000,
    ) -> str:
        """
        Process query with conversation context.

        Args:
            messages: Current messages to process
            conversation_history: Optional conversation history
            max_context_messages: Maximum context messages to include
            reasoning_effort: Model reasoning effort setting
            max_tokens: Maximum tokens in response

        Returns:
            The model's response as a string
        """
        logger.info("Processing query with conversation context")

        # Build full message list with context
        full_messages = []

        # Add conversation history if provided
        if conversation_history:
            # Limit context messages
            context_messages = conversation_history[-max_context_messages:]
            full_messages.extend(context_messages)
            logger.info(f"Added {len(context_messages)} context messages")

        # Add current messages
        full_messages.extend(messages)

        # Execute the request
        try:
            normalized_prefs = {"reasoning_effort": reasoning_effort, "max_tokens": max_tokens}
            response = await self.call_openai_endpoint(
                messages=full_messages,
                normalized_prefs_for_ai=normalized_prefs,
            )
            raw_content = response["choices"][0]["message"]["content"]
            return await self._extract_response_content(
                raw_content, full_messages, normalized_prefs
            )
        except Exception as e:
            logger.error(f"Error processing with context: {e}")
            raise

    async def execute_prompt(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> str:
        """
        Execute a prompt with the given messages.

        This is a simpler interface for direct prompt execution,
        used by components like the CommandClassifier.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Model temperature setting
            max_tokens: Maximum tokens in response

        Returns:
            The model's response as a string
        """
        logger.info("Executing prompt with OpenAI")

        try:
            normalized_prefs = {"temperature": temperature, "max_tokens": max_tokens}
            response = await self.call_openai_endpoint(
                messages=messages,
                normalized_prefs_for_ai=normalized_prefs,
            )
            raw_content = response["choices"][0]["message"]["content"]
            return await self._extract_response_content(raw_content, messages, normalized_prefs)
        except Exception as e:
            logger.error(f"Error executing prompt: {e}")
            raise

    async def call_openai_endpoint(
        self,
        combined_command: Optional[str] = None,
        user_id: Optional[str] = None,
        incoming_channel: Optional[str] = None,
        passed_channel_id: Optional[str] = None,
        channel_name: Optional[str] = None,
        query_text: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        oldest_ts: str = "0",
        normalized_prefs_for_ai: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Invoke the Azure OpenAI endpoint via orchestrated submodules.

        Prepares messages, handles token limits, builds payload, executes request,
        and processes response by delegating to MessagePreparer, TokenManager,
        and ApiExecutor.

        Args:
            combined_command: The verified command string.
            user_id: The Slack user ID.
            incoming_channel: The channel where the command was issued.
            passed_channel_id: The target channel ID (if provided).
            channel_name: The name of the channel (may be fetched).
            query_text: The query text for query commands.
            messages: Optional list of messages to use directly.
            oldest_ts: Slack timestamp for filtering messages. "0" means fetch all messages.
            normalized_prefs_for_ai: Optional dictionary of normalized user preferences for AI.

        Returns:
            The response dictionary from OpenAI.

        Raises:
            OpenAIError: If submodules are not initialized or API call fails.
            ValueError: If required parameters are missing or message prep fails.
        """
        logger.info("Starting call_openai_endpoint orchestration.")
        if not self._message_preparer or not self._token_manager or not self._api_executor:
            raise OpenAIError("OpenAIHandler submodules not initialized. Call initialize() first.")

        try:
            # 1. Prepare messages if not provided directly
            messages, channel_info = await self._get_or_prepare_messages(
                messages=messages,
                combined_command=combined_command,
                user_id=user_id,
                incoming_channel=incoming_channel,
                passed_channel_id=passed_channel_id,
                channel_name=channel_name,
                query_text=query_text,
                oldest_ts=oldest_ts,
                normalized_prefs_for_ai=normalized_prefs_for_ai,
            )

            # 2. Handle token limits (check, notify, truncate) using TokenManager
            logger.info("Enforcing token limits using TokenManager.")
            channel_context_id = (
                incoming_channel or passed_channel_id
            )  # ID for notification context

            processed_messages = await self._token_manager.enforce_token_limit(
                messages=messages,
                user_id=user_id,
                channel_context_id=channel_context_id,
            )  # type: ignore[dict-item]

            # 3. Build the OpenAI payload using ApiExecutor
            logger.info("Building payload using ApiExecutor.")
            payload = self._api_executor.build_openai_payload(
                messages=processed_messages,
                combined_command=combined_command,
                normalized_prefs=normalized_prefs_for_ai,
            )

            # 4. Execute request, process response, track tokens, re-archive using ApiExecutor
            logger.info("Executing request using ApiExecutor.")
            response_data = await self._api_executor.execute_request(
                payload=payload,
                channel_info=channel_info,  # Pass channel info for potential re-archive
                user_id=user_id,
                incoming_channel=incoming_channel,  # Pass for re-archive context
            )

            logger.info("call_openai_endpoint completed successfully.")
            return response_data

        except ValueError as e:  # Catch config/parameter errors
            logger.error(
                "Configuration or parameter error in call_openai_endpoint: %s",
                str(e),
                exc_info=True,
            )
            raise  # Re-raise ValueErrors

        except MessagePreparationError as e:  # Catch message preparation errors
            logger.error(
                "Message preparation error in call_openai_endpoint: %s",
                str(e),
                exc_info=True,
            )
            raise  # Re-raise MessagePreparationError without wrapping

        except Exception as e:  # Catch errors from API calls or unexpected issues
            # Errors from _api_executor.execute_request are already logged there
            # Log context specific to this top-level orchestration failure
            logger.error(
                "Error during call_openai_endpoint orchestration: %s",
                str(e),
                exc_info=True,
            )
            # Wrap in OpenAIError or re-raise depending on desired upstream handling
            raise OpenAIError(f"OpenAI endpoint call failed: {str(e)}") from e

    @property
    def api_key(self) -> str:
        """
        Get the Azure OpenAI API key.

        Returns:
            The API key for Azure OpenAI.

        Raises:
            ValueError: If the handler hasn't been initialized yet.
        """
        if self._lb_api_key is None:
            raise ValueError("OpenAIHandler not initialized. Call initialize() first.")
        return self._lb_api_key

    def get_usage_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current token usage from the tracker.

        Returns:
            Dictionary with usage information.
        """
        return self._token_tracker.get_usage_summary()

    async def _enrich_with_jira_context(
        self, messages: List[Dict[str, str]], channel_id: str
    ) -> List[Dict[str, str]]:
        """
        Enrich messages with JIRA context if available.

        Args:
            messages: List of message dictionaries
            channel_id: Channel ID for context

        Returns:
            Enriched messages list with JIRA context added as system message
        """
        if not self._jira_extractor:
            logger.info("No JIRA extractor available, skipping enrichment")
            return messages

        try:
            # Extract text from user messages for JIRA search
            message_texts = [
                msg.get("content", "") for msg in messages if msg.get("role") == "user"
            ]

            # Get JIRA context from the extractor
            jira_context = await self._jira_extractor.get_jira_context(channel_id, message_texts)

            if jira_context:
                logger.info(f"Enriching messages with JIRA context for channel {channel_id}")

                # Format basic ticket info
                ticket_data = jira_context.get("data", {})
                fields = ticket_data.get("fields", {})

                jira_content = (
                    "JIRA Context Information:\n"
                    f"Ticket ID: {jira_context.get('ticket_id', 'Unknown')}\n"
                    f"Summary: {fields.get('summary', 'N/A')}\n"
                    f"Status: {fields.get('status', {}).get('name', 'N/A')}\n"
                    f"Priority: {fields.get('priority', {}).get('name', 'N/A')}\n"
                    f"Assignee: {fields.get('assignee', {}).get('displayName', 'Unassigned')}\n"
                )

                # Add description if available
                description = fields.get("description", "")
                if description and description.strip():
                    # Limit description length to avoid overwhelming the context
                    max_desc_length = 2000
                    truncated_desc = description.strip()[:max_desc_length]
                    if len(description.strip()) > max_desc_length:
                        truncated_desc += "\n... [description truncated]"
                    jira_content += f"\nDescription:\n{truncated_desc}\n"

                # Add comments if available
                comments = ticket_data.get("comments", [])
                if comments:
                    jira_content += "\nRecent Comments (excluding bots):\n"
                    # Show up to 5 most recent comments
                    for comment in comments[-5:]:
                        # Parse the timestamp
                        created = comment.get("created", "")
                        if created:
                            # Convert ISO format to readable format
                            try:
                                from datetime import datetime

                                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                                formatted_date = dt.strftime("%d-%b-%Y, %H:%M UTC")
                            except Exception:
                                formatted_date = created
                        else:
                            formatted_date = "Unknown date"

                        author = comment.get("author", "Unknown")
                        body = comment.get("body", "")

                        # Pass raw JIRA comment body without complex formatting
                        # The AI will handle formatting according to prompt instructions
                        # No truncation - show full comment content

                        # Format comment with basic indentation
                        jira_content += f"- {formatted_date} - {author}:\n"
                        # Add basic 2-space indentation for readability
                        # The AI will handle proper formatting based on prompt instructions
                        indented_body = "\n".join(["  " + line for line in body.split("\n")])
                        jira_content += f"{indented_body}\n\n"

                jira_content += (
                    "\nUse this JIRA context to provide more accurate and relevant responses."
                )

                # Format JIRA context as a system message
                jira_system_msg = {"role": "system", "content": jira_content}

                # Insert JIRA context at the beginning of messages
                enriched_messages = [jira_system_msg] + messages
                return enriched_messages
            else:
                logger.info("No JIRA context found for enrichment")
                return messages

        except Exception as e:
            logger.error(f"Error enriching messages with JIRA context: {e}")
            # Return original messages on error
            return messages

    async def cleanup(self) -> None:
        """
        Clean up resources used by the handler, primarily the base client session.
        """
        logger.info("Cleaning up OpenAIHandler resources (closing session)")
        # Call the base class cleanup which should handle the session
        await super().cleanup()
        # Reset local state if necessary
        self._api_executor = None
        self._lb_api_key = None
        logger.info("OpenAIHandler cleanup completed.")
