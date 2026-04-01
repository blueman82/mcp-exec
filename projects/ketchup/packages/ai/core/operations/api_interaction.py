"""
api_interaction.py

Handles building the payload, executing API calls to Azure OpenAI,
processing responses, tracking tokens, and managing channel re-archiving.
"""

from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional, cast

# Define necessary imports here as logic is moved
from packages.ai.cost_calculator import TokenTracker
from packages.core.config.feature_flags import FeatureFlags
from packages.core.logging import setup_logger
from packages.slack.channel_operations.channel_archive_ops import SlackChannelArchiveOps

logger = setup_logger(__name__)

# Define a type hint for the async request function
AzureApiRequestFunc = Callable[..., Awaitable[Dict[str, Any]]]


class ApiExecutor:
    """Executes OpenAI API requests and processes responses."""

    def __init__(
        self,
        api_request_func: AzureApiRequestFunc,
        endpoint: str,
        api_key: str,
        token_tracker: TokenTracker,
        channel_archive_ops: SlackChannelArchiveOps,
    ):
        """
        Initializes the ApiExecutor.

        Args:
            api_request_func: The async function to make Azure API requests.
            endpoint: The base Azure OpenAI endpoint URL.
            api_key: The API key for the Load Balancer or specific deployment.
            token_tracker: The TokenTracker instance for usage tracking.
            channel_archive_ops: Operations for archiving/unarchiving Slack channels.
        """
        self._api_request_func = api_request_func
        self._endpoint = endpoint
        self._api_key = api_key
        self._token_tracker = token_tracker
        self._channel_archive_ops = channel_archive_ops

    def build_openai_payload(
        self,
        messages: List[Dict[str, str]],
        combined_command: Optional[str],
        normalized_prefs: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Builds the payload for the OpenAI API request.

        Args:
            messages: The list of message objects for the API.
            combined_command: The command string to determine token limits.
            normalized_prefs: Optional preferences including reasoning_effort and max_tokens.
            tools: Optional list of tool definitions to include in the payload.

        Returns:
            The payload dictionary.
        """
        # Extract preferences with defaults
        prefs = normalized_prefs or {}
        reasoning_effort = prefs.get("reasoning_effort", "low")

        # Determine max_tokens based on command or preferences
        if "max_tokens" in prefs:
            max_tokens = prefs["max_tokens"]
        else:
            max_tokens = 1024  # Default token count
            if combined_command and ("status" in combined_command or "report" in combined_command):
                max_tokens = 2048  # Double token count for more verbose responses

        payload = {
            "messages": messages,
            "max_completion_tokens": max_tokens,
            "reasoning_effort": reasoning_effort,
        }

        if tools:
            payload["tools"] = tools

        # Add JSON mode when feature flag enabled
        if FeatureFlags.is_structured_json_output_enabled():
            payload["response_format"] = {"type": "json_object"}
            logger.info("JSON mode enabled: response_format set to json_object")

        return payload

    async def execute_request(
        self,
        payload: Dict[str, Any],
        channel_info: Optional[Dict[str, Any]],
        user_id: Optional[str],
        incoming_channel: Optional[str],
    ) -> Dict[str, Any]:
        """
        Executes the OpenAI API request, processes response, tracks tokens, and handles re-archiving.

        Args:
            payload: The payload for the API request.
            channel_info: Dictionary containing channel information (for re-archiving).
            user_id: Slack user ID (for re-archiving).
            incoming_channel: Original incoming channel ID (for re-archiving context).

        Returns:
            The response data from OpenAI.

        Raises:
            Exception: Reraises exceptions from the API call after logging.
        """
        try:
            # Use the injected function to make the request
            # Assuming the function passed handles the URL construction or takes it as arg
            # Let's refine this: _api_request_func likely needs endpoint/url info.
            # We'll assume for now it's the _make_azure_api_request from the original class
            # and it implicitly uses self._endpoint passed during init.
            # A cleaner way might be to pass endpoint/url explicitly here.
            response_data = await self._api_request_func(
                url=self._endpoint,
                method="POST",
                headers={"api-key": self._api_key},
                json_data=payload,
            )

            # Process token usage and cost
            usage = response_data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", 0)

            self._token_tracker.add_usage(input_tokens, output_tokens)
            cost_details = self._token_tracker.calculate_cost(input_tokens, output_tokens)
            total_cost = cost_details["Total Cost"]

            token_usage_message = (
                f"OpenAI Token Usage - Input Tokens: {input_tokens}, "
                f"Output Tokens: {output_tokens}, Total Tokens: {total_tokens}, "
                f"Cost: ${total_cost:.2f}"
            )
            logger.info(token_usage_message)

            # Re-archive the channel if necessary
            if (
                channel_info
                and channel_info.get("originally_archived")
                and user_id
                and channel_info.get("target_channel")
            ):
                target_channel = channel_info["target_channel"]
                channel_id_for_metadata = target_channel
                logger.info("Re-archiving previously archived channel %s", target_channel)
                try:
                    # Use injected ops
                    await self._channel_archive_ops.archive_channel(
                        user_id=user_id,
                        channel_id=target_channel,
                        incoming_channel=incoming_channel,
                    )
                except Exception as archive_error:
                    logger.error(
                        "Failed to re-archive channel %s: %s",
                        target_channel,
                        str(archive_error),
                        exc_info=True,  # Add traceback for archive error
                    )
            else:
                # Define channel_id_for_metadata even if not re-archiving
                channel_id_for_metadata = incoming_channel

            # Re-insert the metadata block with the fix
            response_data["metadata"] = {
                "channel_id": cast(Any, channel_id_for_metadata),
                "user_id": cast(Any, (user_id if user_id is not None else "unknown")),
                "input_tokens": cast(Any, input_tokens),
                "output_tokens": cast(Any, output_tokens),
                "total_tokens": cast(Any, total_tokens),
                "cost_details": cast(Any, cost_details),
                "model_used": cast(Any, payload.get("model", "unknown")),
                "timestamp": cast(Any, datetime.now().isoformat()),
            }

            return response_data

        except Exception as e:
            # Log the error with traceback
            logger.error("Error during OpenAI API request execution: %s", str(e), exc_info=True)
            # Reraise the original exception
            raise
