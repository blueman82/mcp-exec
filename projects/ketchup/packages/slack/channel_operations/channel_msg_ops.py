"""
Module for managing Slack channel message operations.

This module contains the SlackChannelMessageOps class for fetching messages from Slack channels.
"""

import asyncio
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

import orjson

from packages.core.constants import MAX_RETRIES
from packages.core.jira_constants import VALID_JIRA_PROJECTS
from packages.core.logging import setup_logger
from packages.core.resilience.backoff import BackoffStrategy, ExponentialBackoffStrategy
from packages.slack.channel_operations.channel_archive_ops import SlackChannelArchiveOps
from packages.slack.config.slack_config import SlackConfig
from packages.slack.core.slack_async_client import SlackAsyncClient
from packages.slack.user_operations.user_ops import SlackUserOps

from .slack_message_formatter import SlackMessageFormatter

logger = setup_logger(__name__)

# System message subtypes to filter out for activity detection
FILTERED_SYSTEM_SUBTYPES = {
    "channel_join",  # User joined the channel
    "channel_leave",  # User left the channel
    "channel_topic",  # Topic was changed
    "channel_purpose",  # Purpose/description was changed
    "channel_name",  # Channel was renamed
    "channel_archive",  # Channel was archived
    "channel_unarchive",  # Channel was unarchived
    "pinned_item",  # Item was pinned
    "unpinned_item",  # Item was unpinned
    "bot_add",  # Bot was added
    "bot_remove",  # Bot was removed
}


class SlackChannelMessageOps(SlackAsyncClient):
    """Responsible for fetching and processing messages from Slack channels."""

    def __init__(
        self,
        user_ops: SlackUserOps,
        archive_ops: SlackChannelArchiveOps,
        slack_config: SlackConfig,
        max_concurrent_requests: int = 10,
        backoff_strategy: Optional[BackoffStrategy] = None,
    ):
        """
        Initialize with injected dependencies.

        Args:
            user_ops: Operations for user lookups.
            archive_ops: Operations for channel archiving.
            slack_config: Pre-initialized SlackConfig instance (required).
            max_concurrent_requests: Maximum number of concurrent requests
            backoff_strategy: Strategy for handling retries and backoff (optional)
        """
        super().__init__(
            slack_config=slack_config,
            max_concurrent_requests=max_concurrent_requests,
            backoff_strategy=backoff_strategy
            or ExponentialBackoffStrategy(max_retries=MAX_RETRIES),
        )
        self.user_ops = user_ops
        self.archive_ops = archive_ops
        self._formatter = SlackMessageFormatter(user_ops=self.user_ops)
        self._bot_user_id = None  # Will be set during initialization
        self._batch_sizer = BatchSizeManager()
        self._latest_message_ts = None  # Track latest message timestamp seen
        self._agent_thread_filter = None  # Lazily resolved agent thread filter
        self._agent_threads_cache: Dict[str, Set[str]] = {}  # channel_id -> agent thread_ts set
        logger.info("SlackChannelMessageOps initialized with injected dependencies.")

    async def set_bot_user_id(self, bot_user_id: str):
        """Set the bot user ID for filtering Ketchup messages."""
        self._bot_user_id = bot_user_id
        logger.info(f"Bot user ID set to {bot_user_id} for message filtering")

    async def _get_agent_threads(self, channel_id: str) -> Set[str]:
        """Lazily resolve and fetch agent thread timestamps for a channel.

        Args:
            channel_id: The channel to look up.

        Returns:
            Set of thread_ts strings belonging to agent conversations, or empty set if unavailable.
        """
        # Check if agent feature is enabled
        if os.environ.get("KETCHUP_AGENT_ENABLED", "false").lower() != "true":
            return set()

        # Return cached result if available
        if channel_id in self._agent_threads_cache:
            return self._agent_threads_cache[channel_id]

        # Try to lazily resolve the agent thread filter from DI
        try:
            if self._agent_thread_filter is None:
                from packages.core.typed_di.registry import TypedServiceRegistry
                from packages.core.typed_di.service_registrations.protocols.agent_protocols import (
                    AgentThreadFilterProtocol,
                )

                # Get the global DI registry
                registry = TypedServiceRegistry.instance()
                self._agent_thread_filter = await registry.aget(AgentThreadFilterProtocol)

            # Get agent threads for this channel
            agent_threads = await self._agent_thread_filter.get_agent_threads(channel_id)
            self._agent_threads_cache[channel_id] = agent_threads
            return agent_threads

        except Exception as e:
            # Agent feature disabled or resolution failed — skip filter gracefully
            logger.debug(f"Agent thread filter unavailable: {e}")
            return set()

    @property
    def latest_message_ts(self) -> Optional[str]:
        """Get the latest message timestamp from the last fetch operation."""
        return self._latest_message_ts

    async def fetch_snippet_content(self, url_private: str) -> str:
        """Fetch the content of a Slack snippet file given its private URL."""
        import httpx

        headers = self.headers

        # httpx and aiohttp have different .get() APIs
        if isinstance(self._session, httpx.AsyncClient):
            # httpx: get() returns Response directly (not a context manager)
            resp = await self._session.get(url_private, headers=headers)
            if resp.status_code == 200:
                return resp.text
            else:
                return f"[Could not retrieve snippet content, status {resp.status_code}]"
        else:
            # aiohttp: get() returns a context manager
            async with self._session.get(url_private, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.text()
                else:
                    return f"[Could not retrieve snippet content, status {resp.status}]"

    async def fetch_channel_messages(
        self,
        channel_id: str,
        oldest_ts: str = "0",
        limit: int = 999999999,
        additional_thread_timestamps: Optional[List[str]] = None,
        include_bot_messages: bool = False,
        include_system_messages: bool = False,
        use_parallel_pagination: bool = True,  # Default to True for performance
    ) -> List[str]:
        """
        Fetch messages from a Slack channel.

        Args:
            channel_id: The ID of the channel to fetch messages from
            oldest_ts: The timestamp of the oldest message to fetch
            limit: The maximum number of messages to fetch
            additional_thread_timestamps: Optional list of thread timestamps to fetch
                even if their parent messages are outside the time window
            include_bot_messages: Whether to include bot messages (default: False)
            include_system_messages: Whether to include system messages like topic changes (default: False)
            use_parallel_pagination: Whether to use parallel pagination for performance (default: True)

        Returns:
            A list of processed message texts
        """
        logger.info("Starting fetch_channel_messages for channel %s", channel_id)

        # Route to parallel or sequential pagination based on flag
        if use_parallel_pagination:
            try:
                return await self._fetch_channel_messages_parallel(
                    channel_id,
                    oldest_ts,
                    limit,
                    additional_thread_timestamps,
                    include_bot_messages,
                    include_system_messages,
                )
            except Exception as e:
                logger.warning(
                    "Parallel pagination failed for channel %s, falling back to sequential: %s",
                    channel_id,
                    str(e),
                )
                # Fall through to sequential implementation

        # Sequential pagination (existing implementation)
        messages_dict: Dict[str, Dict[str, Any]] = {}
        user_mentions: Set[str] = set()
        thread_timestamps: List[str] = []
        next_cursor = None
        was_unarchived = False

        try:
            was_unarchived = await self._temporarily_unarchive_if_needed(channel_id)
            if was_unarchived:
                logger.info("Successfully unarchived channel %s temporarily", channel_id)

            url = f"{await self.get_api_base_url()}/conversations.history"
            headers = self.headers  # Access as property

            # Adaptive batch size
            batch_size = min(self._batch_sizer.get_size(), 200)

            # Apply buffer to oldest timestamp to prevent precision mismatches
            # When stored timestamps are integers but Slack API uses decimal precision,
            # we need to subtract a small buffer to ensure we don't miss messages
            oldest_ts_buffered = oldest_ts
            if oldest_ts and oldest_ts != "0":
                try:
                    # Convert to float, subtract 5 seconds for safety, then back to string
                    # This ensures messages with slightly larger decimal timestamps aren't missed
                    oldest_ts_buffered = str(float(oldest_ts) - 5)
                    logger.debug(
                        f"Applied 5-second buffer to oldest timestamp: {oldest_ts} -> {oldest_ts_buffered}"
                    )
                except (ValueError, TypeError):
                    # If conversion fails, use original value
                    oldest_ts_buffered = oldest_ts
                    logger.warning(
                        f"Could not apply buffer to timestamp {oldest_ts}, using original"
                    )

            params = {
                "channel": channel_id,
                "limit": batch_size,
                "oldest": oldest_ts_buffered,
                # Only request fields we need
                "include_all_metadata": "false",
            }

            while True:
                if next_cursor:
                    params["cursor"] = next_cursor

                try:
                    response = await self._make_api_request(url, "GET", headers, params)
                    # Response is now a SafeResponse dict, parse the body
                    response_data = orjson.loads(response["body"])

                    if response_data.get("ok"):
                        self._batch_sizer.increase_size()  # Success, increase batch size
                        messages = response_data.get("messages", [])

                        await self._collect_batch_data(
                            messages,
                            messages_dict,
                            user_mentions,
                            thread_timestamps,
                            channel_id,
                            include_bot_messages,
                            include_system_messages,
                        )

                        next_cursor = response_data.get("response_metadata", {}).get("next_cursor")
                        if not next_cursor:
                            break
                    else:
                        error = response_data.get("error")
                        logger.error(
                            "Slack API returned error for channel %s: %s",
                            channel_id,
                            error,
                        )
                        self._batch_sizer.decrease_size()  # Error, decrease batch size
                        if error == "not_in_channel":
                            # This error commonly occurs when:
                            # 1. Channel was just unarchived and bot hasn't joined yet
                            # 2. Bot was removed from the channel
                            # 3. Race condition between unarchive and bot join operations
                            #
                            # The error will be automatically retried by the backoff strategy
                            # in _make_api_request since "not_in_channel" is in retryable_errors.
                            # This gives the bot time to complete joining the channel.
                            logger.info(
                                "Got not_in_channel error for channel %s. This will be retried automatically "
                                "with exponential backoff.",
                                channel_id,
                            )
                        # Raise the exception - it will be caught by the backoff strategy in _make_api_request
                        raise Exception(f"Slack API error: {error}")
                except Exception as e:
                    logger.error("Error in fetch_channel_messages: %s", str(e))
                    self._batch_sizer.decrease_size()  # Error, decrease batch size
                    # Let the retry decorator handle retries
                    raise

            # Add any additional thread timestamps that were explicitly requested
            if additional_thread_timestamps:
                # Remove duplicates and add to thread_timestamps
                existing_thread_ts = set(thread_timestamps)
                for ts in additional_thread_timestamps:
                    if ts not in existing_thread_ts:
                        thread_timestamps.append(ts)
                        logger.info(f"Added additional thread {ts} to fetch list")

            # Fetch thread messages if any
            if thread_timestamps:
                thread_messages, thread_user_mentions = await self._fetch_thread_messages_parallel(
                    channel_id, thread_timestamps
                )
                for _, replies in thread_messages.items():
                    for reply in replies:
                        messages_dict[reply["ts"]] = reply

                # Update user mentions with thread user mentions
                user_mentions.update(thread_user_mentions)

            # Use the formatter to process ALL collected messages
            # Before formatting, fetch snippet contents for all messages with snippet files
            for msg in messages_dict.values():
                files = msg.get("files", [])
                for f in files:
                    if f.get("mode") == "snippet" and f.get("url_private"):
                        snippet = await self.fetch_snippet_content(f["url_private"])
                        # Append snippet content to the message text
                        msg["text"] = (
                            msg.get("text", "") + f"\n\n[Snippet: {f.get('name')}]\n{snippet}"
                        )
            processed_messages, _ = await self._formatter.process_message_batch(
                list(messages_dict.values()), user_mentions
            )

            logger.info(
                "Completed processing messages for channel %s. Returning %s formatted messages",
                channel_id,
                len(processed_messages),
            )

            return processed_messages

        finally:
            # Re-archive the channel if we unarchived it
            if was_unarchived:
                logger.info("Re-archiving channel %s after fetching messages", channel_id)
                await self.archive_ops.archive_channel(
                    user_id=None, channel_id=channel_id, incoming_channel=channel_id
                )

    async def _fetch_channel_messages_parallel(
        self,
        channel_id: str,
        oldest_ts: str = "0",
        limit: int = 999999999,
        additional_thread_timestamps: Optional[List[str]] = None,
        include_bot_messages: bool = False,
        include_system_messages: bool = False,
    ) -> List[str]:
        """
        Fetch messages from a Slack channel using parallel pagination for improved performance.

        This method implements concurrent page fetching while preserving all existing functionality
        including message filtering, thread processing, and snippet content fetching.

        Args:
            channel_id: The ID of the channel to fetch messages from
            oldest_ts: The timestamp of the oldest message to fetch
            limit: The maximum number of messages to fetch (unused in parallel - fetches ALL)
            additional_thread_timestamps: Optional list of thread timestamps to fetch
            include_bot_messages: Whether to include bot messages (default: False)
            include_system_messages: Whether to include system messages (default: False)

        Returns:
            A list of processed message texts
        """
        logger.info("Starting parallel pagination for channel %s", channel_id)

        messages_dict: Dict[str, Dict[str, Any]] = {}
        user_mentions: Set[str] = set()
        thread_timestamps: List[str] = []
        was_unarchived = False

        try:
            # Unarchive if needed (same as sequential)
            was_unarchived = await self._temporarily_unarchive_if_needed(channel_id)
            if was_unarchived:
                logger.info("Successfully unarchived channel %s temporarily", channel_id)

            # Phase 1: Discover all available pages first
            cursors = await self._discover_pagination_cursors(channel_id, oldest_ts)
            logger.info("Discovered %d pages to fetch for channel %s", len(cursors), channel_id)

            # Phase 2: Fetch all pages in parallel with controlled concurrency
            all_pages_data = await self._fetch_pages_parallel(channel_id, cursors, oldest_ts)

            # Phase 3: Process all collected data (same as sequential)
            for page_data in all_pages_data:
                if page_data:  # Skip failed pages
                    await self._collect_batch_data(
                        page_data,
                        messages_dict,
                        user_mentions,
                        thread_timestamps,
                        channel_id,
                        include_bot_messages,
                        include_system_messages,
                    )

            # Add additional thread timestamps if provided (same as sequential)
            if additional_thread_timestamps:
                existing_thread_ts = set(thread_timestamps)
                for ts in additional_thread_timestamps:
                    if ts not in existing_thread_ts:
                        thread_timestamps.append(ts)
                        logger.info(f"Added additional thread {ts} to fetch list")

            # Fetch thread messages if any (reuse existing parallel implementation)
            if thread_timestamps:
                thread_messages, thread_user_mentions = await self._fetch_thread_messages_parallel(
                    channel_id, thread_timestamps
                )
                for _, replies in thread_messages.items():
                    for reply in replies:
                        messages_dict[reply["ts"]] = reply
                user_mentions.update(thread_user_mentions)

            # Fetch snippet contents for all messages (same as sequential)
            for msg in messages_dict.values():
                files = msg.get("files", [])
                for f in files:
                    if f.get("mode") == "snippet" and f.get("url_private"):
                        snippet = await self.fetch_snippet_content(f["url_private"])
                        msg["text"] = (
                            msg.get("text", "") + f"\n\n[Snippet: {f.get('name')}]\n{snippet}"
                        )

            # Process messages using existing formatter (same as sequential)
            processed_messages, _ = await self._formatter.process_message_batch(
                list(messages_dict.values()), user_mentions
            )

            logger.info(
                "Completed parallel processing for channel %s. Returning %s formatted messages",
                channel_id,
                len(processed_messages),
            )

            return processed_messages

        finally:
            # Re-archive if we unarchived it (same as sequential)
            if was_unarchived:
                logger.info("Re-archiving channel %s after parallel fetch", channel_id)
                await self.archive_ops.archive_channel(
                    user_id=None, channel_id=channel_id, incoming_channel=channel_id
                )

    async def _discover_pagination_cursors(
        self, channel_id: str, oldest_ts: str = "0"
    ) -> List[Optional[str]]:
        """
        Discover all pagination cursors for a channel by doing a quick sequential scan.

        This lightweight scan collects only cursors, not the full message data,
        allowing us to then fetch all pages in parallel.

        Args:
            channel_id: The channel to scan
            oldest_ts: The timestamp of the oldest message to fetch

        Returns:
            List of cursors (first item is None for the initial page)

        Raises:
            Exception: If cursor discovery fails (propagated to caller for fallback)
        """
        cursors = [None]  # Start with no cursor for first page

        url = f"{await self.get_api_base_url()}/conversations.history"
        headers = self.headers

        # Apply buffer to oldest timestamp to prevent precision mismatches
        oldest_ts_buffered = oldest_ts
        if oldest_ts and oldest_ts != "0":
            try:
                # Convert to float, subtract 5 seconds for safety, then back to string
                # This ensures messages with slightly larger decimal timestamps aren't missed
                oldest_ts_buffered = str(float(oldest_ts) - 5)
                logger.debug(
                    f"Applied 5-second buffer to oldest timestamp in cursor discovery: {oldest_ts} -> {oldest_ts_buffered}"
                )
            except (ValueError, TypeError):
                # If conversion fails, use original value
                oldest_ts_buffered = oldest_ts
                logger.warning(
                    f"Could not apply buffer to timestamp {oldest_ts} in cursor discovery, using original"
                )

        # Use a small batch size for quick cursor discovery
        params = {
            "channel": channel_id,
            "limit": 10,  # Minimal data per request
            "oldest": oldest_ts_buffered,
            "include_all_metadata": "false",
        }

        next_cursor = None
        cursor_count = 0
        max_cursors = 50  # Safety limit to prevent infinite loops

        while cursor_count < max_cursors:
            if next_cursor:
                params["cursor"] = next_cursor

            response = await self._make_api_request(url, "GET", headers, params)
            response_data = orjson.loads(response["body"])

            if response_data.get("ok"):
                next_cursor = response_data.get("response_metadata", {}).get("next_cursor")
                if next_cursor:
                    cursors.append(next_cursor)
                    cursor_count += 1
                else:
                    break
            else:
                error = response_data.get("error")
                logger.error("Error discovering cursors for channel %s: %s", channel_id, error)
                # Re-raise to trigger sequential fallback
                raise Exception(f"Slack API error during cursor discovery: {error}")

            # Minimal delay to respect rate limits during discovery
            await asyncio.sleep(0.05)  # Reduced from 0.1s for faster discovery

        logger.info("Discovered %d cursors for channel %s", len(cursors), channel_id)
        return cursors

    async def _fetch_pages_parallel(
        self, channel_id: str, cursors: List[Optional[str]], oldest_ts: str
    ) -> List[Optional[List[Dict[str, Any]]]]:
        """
        Fetch all pages in parallel using discovered cursors.

        Uses the existing batched parallel pattern from thread fetching
        to respect rate limits while maximizing concurrency.

        Args:
            channel_id: The channel ID
            cursors: List of cursors to fetch (None for first page)
            oldest_ts: Oldest timestamp filter

        Returns:
            List of message arrays (None for failed fetches)
        """
        results = [None] * len(cursors)
        concurrent_workers = 4  # Moderate increase: 2x parallelism while staying under 50 req/min

        # Apply buffer to oldest timestamp to prevent precision mismatches
        oldest_ts_buffered = oldest_ts
        if oldest_ts and oldest_ts != "0":
            try:
                # Convert to float, subtract 5 seconds for safety, then back to string
                # This ensures messages with slightly larger decimal timestamps aren't missed
                oldest_ts_buffered = str(float(oldest_ts) - 5)
                logger.debug(
                    f"Applied 5-second buffer to oldest timestamp in parallel fetch: {oldest_ts} -> {oldest_ts_buffered}"
                )
            except (ValueError, TypeError):
                # If conversion fails, use original value
                oldest_ts_buffered = oldest_ts
                logger.warning(
                    f"Could not apply buffer to timestamp {oldest_ts} in parallel fetch, using original"
                )

        url = f"{await self.get_api_base_url()}/conversations.history"
        headers = self.headers
        batch_size = min(self._batch_sizer.get_size(), 200)

        # Process cursors in batches to control concurrency
        for i in range(0, len(cursors), concurrent_workers):
            batch_cursors = cursors[i : i + concurrent_workers]
            batch_indices = list(range(i, min(i + concurrent_workers, len(cursors))))

            logger.info(
                "Fetching page batch %d-%d for channel %s",
                i + 1,
                min(i + concurrent_workers, len(cursors)),
                channel_id,
            )

            # Create tasks for this batch
            tasks = []
            for cursor in batch_cursors:
                params = {
                    "channel": channel_id,
                    "limit": batch_size,
                    "oldest": oldest_ts_buffered,
                    "include_all_metadata": "false",
                }
                if cursor:
                    params["cursor"] = cursor

                tasks.append(self._fetch_single_page(url, headers, params))

            # Execute batch in parallel
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Store results
            for idx, (batch_idx, result) in enumerate(
                zip(batch_indices, batch_results, strict=False)
            ):
                if isinstance(result, Exception):
                    logger.error(
                        "Failed to fetch page %d for channel %s: %s",
                        batch_idx + 1,
                        channel_id,
                        result,
                    )
                    results[batch_idx] = None
                else:
                    results[batch_idx] = result
                    self._batch_sizer.increase_size()  # Success

            # Delay between batches to respect rate limits
            if i + concurrent_workers < len(cursors):
                await asyncio.sleep(0.5)  # Optimized: 50% faster while staying under limits

        # Filter out failed pages
        successful_pages = [page for page in results if page is not None]
        logger.info(
            "Successfully fetched %d/%d pages for channel %s",
            len(successful_pages),
            len(cursors),
            channel_id,
        )

        return successful_pages

    async def _fetch_single_page(
        self, url: str, headers: dict, params: dict
    ) -> List[Dict[str, Any]]:
        """
        Fetch a single page of messages.

        Args:
            url: API endpoint URL
            headers: Request headers
            params: Request parameters

        Returns:
            List of messages for this page

        Raises:
            Exception: If the page fetch fails
        """
        try:
            response = await self._make_api_request(url, "GET", headers, params)
            response_data = orjson.loads(response["body"])

            if response_data.get("ok"):
                return response_data.get("messages", [])
            else:
                error = response_data.get("error")
                raise Exception(f"Slack API error: {error}")

        except Exception:
            self._batch_sizer.decrease_size()  # Error, decrease batch size
            raise

    async def fetch_channel_messages_streaming(
        self,
        channel_id: str,
        oldest_ts: str = "0",
        additional_thread_timestamps: Optional[List[str]] = None,
        include_bot_messages: bool = False,
        include_system_messages: bool = False,
    ):
        """
        Fetch messages from a Slack channel with streaming pagination.

        Yields batches of processed messages as they are fetched, allowing for
        memory-efficient processing of large channels without loading all
        messages into memory at once.

        Args:
            channel_id: The ID of the channel to fetch messages from
            oldest_ts: The timestamp of the oldest message to fetch
            additional_thread_timestamps: Optional list of thread timestamps
            include_bot_messages: Whether to include bot messages
            include_system_messages: Whether to include system messages

        Yields:
            Batches of processed message texts as they are fetched

        Raises:
            Exception: If the fetch or processing fails
        """
        logger.info("Starting fetch_channel_messages_streaming for channel %s", channel_id)

        messages_dict: Dict[str, Dict[str, Any]] = {}
        user_mentions: Set[str] = set()
        thread_timestamps: List[str] = []
        next_cursor = None
        was_unarchived = False

        try:
            was_unarchived = await self._temporarily_unarchive_if_needed(channel_id)
            if was_unarchived:
                logger.info("Successfully unarchived channel %s temporarily", channel_id)

            # Apply buffer to oldest timestamp to prevent precision mismatches
            oldest_ts_buffered = oldest_ts
            if oldest_ts and oldest_ts != "0":
                try:
                    # Convert to float, subtract 5 seconds for safety, then back to string
                    # This ensures messages with slightly larger decimal timestamps aren't missed
                    oldest_ts_buffered = str(float(oldest_ts) - 5)
                    logger.debug(
                        f"Applied 5-second buffer to oldest timestamp in streaming: {oldest_ts} -> {oldest_ts_buffered}"
                    )
                except (ValueError, TypeError):
                    # If conversion fails, use original value
                    oldest_ts_buffered = oldest_ts
                    logger.warning(
                        f"Could not apply buffer to timestamp {oldest_ts} in streaming, using original"
                    )

            url = f"{await self.get_api_base_url()}/conversations.history"
            headers = self.headers

            batch_size = min(self._batch_sizer.get_size(), 100)
            params = {
                "channel": channel_id,
                "limit": batch_size,
                "oldest": oldest_ts_buffered,
                "include_all_metadata": "false",
            }

            # Fetch and yield message batches
            while True:
                if next_cursor:
                    params["cursor"] = next_cursor

                try:
                    response = await self._make_api_request(url, "GET", headers, params)
                    response_data = orjson.loads(response["body"])

                    if response_data.get("ok"):
                        self._batch_sizer.increase_size()
                        messages = response_data.get("messages", [])

                        # Collect batch data
                        page_messages_dict: Dict[str, Dict[str, Any]] = {}
                        page_user_mentions: Set[str] = set()
                        page_thread_timestamps: List[str] = []

                        await self._collect_batch_data(
                            messages,
                            page_messages_dict,
                            page_user_mentions,
                            page_thread_timestamps,
                            channel_id,
                            include_bot_messages,
                            include_system_messages,
                        )

                        # Process snippet content for this batch
                        for msg in page_messages_dict.values():
                            files = msg.get("files", [])
                            for f in files:
                                if f.get("mode") == "snippet" and f.get("url_private"):
                                    snippet = await self.fetch_snippet_content(f["url_private"])
                                    msg["text"] = (
                                        msg.get("text", "")
                                        + f"\n\n[Snippet: {f.get('name')}]\n{snippet}"
                                    )

                        # Format and yield this batch
                        if page_messages_dict:
                            processed, _ = await self._formatter.process_message_batch(
                                list(page_messages_dict.values()), page_user_mentions
                            )
                            if processed:
                                yield processed

                        # Accumulate for thread processing
                        messages_dict.update(page_messages_dict)
                        user_mentions.update(page_user_mentions)
                        thread_timestamps.extend(page_thread_timestamps)

                        next_cursor = response_data.get("response_metadata", {}).get("next_cursor")
                        if not next_cursor:
                            break
                    else:
                        error = response_data.get("error")
                        logger.error("Slack API error for channel %s: %s", channel_id, error)
                        self._batch_sizer.decrease_size()
                        raise Exception(f"Slack API error: {error}")

                except Exception as e:
                    logger.error("Error in fetch_channel_messages_streaming: %s", str(e))
                    self._batch_sizer.decrease_size()
                    raise

            # Process threads after all main messages are fetched
            if additional_thread_timestamps:
                existing_thread_ts = set(thread_timestamps)
                for ts in additional_thread_timestamps:
                    if ts not in existing_thread_ts:
                        thread_timestamps.append(ts)

            if thread_timestamps:
                thread_messages, thread_user_mentions = await self._fetch_thread_messages_parallel(
                    channel_id, thread_timestamps
                )

                thread_msgs_dict: Dict[str, Dict[str, Any]] = {}
                for _, replies in thread_messages.items():
                    for reply in replies:
                        thread_msgs_dict[reply["ts"]] = reply

                # Process snippet content for threads
                for msg in thread_msgs_dict.values():
                    files = msg.get("files", [])
                    for f in files:
                        if f.get("mode") == "snippet" and f.get("url_private"):
                            snippet = await self.fetch_snippet_content(f["url_private"])
                            msg["text"] = (
                                msg.get("text", "") + f"\n\n[Snippet: {f.get('name')}]\n{snippet}"
                            )

                # Format and yield thread messages
                if thread_msgs_dict:
                    user_mentions.update(thread_user_mentions)
                    processed, _ = await self._formatter.process_message_batch(
                        list(thread_msgs_dict.values()), user_mentions
                    )
                    if processed:
                        yield processed

            logger.info("Completed streaming fetch for channel %s", channel_id)

        finally:
            if was_unarchived:
                logger.info("Re-archiving channel %s after streaming fetch", channel_id)
                await self.archive_ops.archive_channel(
                    user_id=None, channel_id=channel_id, incoming_channel=channel_id
                )

    async def fetch_channel_messages_pipeline(
        self,
        channel_id: str,
        oldest_ts: str = "0",
        additional_thread_timestamps: Optional[List[str]] = None,
        include_bot_messages: bool = False,
        include_system_messages: bool = False,
        batch_size: int = 100,
    ):
        """
        Fetch messages from a Slack channel using pipeline processing.

        Returns an async generator that yields individual processed messages
        one at a time, enabling downstream pipeline processing with minimal
        memory overhead and maximum throughput.

        Args:
            channel_id: The ID of the channel to fetch messages from
            oldest_ts: The timestamp of the oldest message to fetch
            additional_thread_timestamps: Optional list of thread timestamps
            include_bot_messages: Whether to include bot messages
            include_system_messages: Whether to include system messages
            batch_size: Number of messages to fetch per API call

        Yields:
            Individual processed message texts one at a time

        Raises:
            Exception: If the fetch or processing fails
        """
        logger.info("Starting fetch_channel_messages_pipeline for channel %s", channel_id)

        async for message_batch in self.fetch_channel_messages_streaming(
            channel_id,
            oldest_ts,
            additional_thread_timestamps,
            include_bot_messages,
            include_system_messages,
        ):
            # Yield messages one at a time from each batch
            for message in message_batch:
                yield message

        logger.info("Completed pipeline fetch for channel %s", channel_id)

    async def fetch_channel_messages_collected(
        self,
        channel_id: str,
        oldest_ts: str = "0",
        limit: int = 999999999,
        additional_thread_timestamps: Optional[List[str]] = None,
        include_bot_messages: bool = False,
        include_system_messages: bool = False,
        use_parallel_pagination: bool = True,
    ) -> List[str]:
        """
        Fetch messages using streaming pipeline and collect into a list.

        This wrapper uses the streaming pipeline internally for memory efficiency
        during fetching, but returns all messages as a list for compatibility with
        existing code that expects List[str].

        Args:
            channel_id: The ID of the channel to fetch messages from
            oldest_ts: The timestamp of the oldest message to fetch
            limit: Maximum number of messages (unused, for API compatibility)
            additional_thread_timestamps: Optional list of thread timestamps
            include_bot_messages: Whether to include bot messages
            include_system_messages: Whether to include system messages
            use_parallel_pagination: Unused, for API compatibility

        Returns:
            List of all processed message texts

        Raises:
            Exception: If the fetch or processing fails
        """
        logger.info("Starting collected pipeline fetch for channel %s", channel_id)

        all_messages = []
        async for message_batch in self.fetch_channel_messages_streaming(
            channel_id,
            oldest_ts,
            additional_thread_timestamps,
            include_bot_messages,
            include_system_messages,
        ):
            all_messages.extend(message_batch)

        logger.info(
            "Completed collected pipeline fetch for channel %s: %d messages",
            channel_id,
            len(all_messages),
        )

        return all_messages

    async def _collect_batch_data(
        self,
        messages,
        messages_dict,
        user_mentions,
        thread_timestamps,
        channel_id: str,
        include_bot_messages: bool = False,
        include_system_messages: bool = False,
    ):
        """Collects raw message data, filtering out Ketchup interactions and agent threads."""
        latest_ts = "0"

        # First pass: find the absolute latest timestamp from ALL messages (including bot messages)
        for msg in messages:
            msg_ts = msg.get("ts", "0")
            if msg_ts > latest_ts:
                latest_ts = msg_ts

        # Get agent thread timestamps for this channel (cached, empty set if agent disabled)
        agent_threads = await self._get_agent_threads(channel_id)

        # Second pass: collect non-bot and non-system messages
        for msg in messages:
            # Skip ALL bot messages (not just Ketchup's) - unless include_bot_messages is True
            # Check both user field matching bot_user_id AND presence of bot_id field
            if not include_bot_messages:
                if (self._bot_user_id and msg.get("user") == self._bot_user_id) or msg.get(
                    "bot_id"
                ):
                    # logger.info(f"Filtering out bot message: user={msg.get('user')}, bot_id={msg.get('bot_id')}")
                    continue

            # Skip system messages (joins, leaves, topic changes, etc.) unless explicitly included
            if not include_system_messages and msg.get("subtype") in FILTERED_SYSTEM_SUBTYPES:
                # logger.info(f"Filtering out system message: subtype={msg.get('subtype')}")
                continue

            # ── 4th filter layer: Agent thread isolation ──
            # Skip messages that belong to agent conversation threads
            if (
                agent_threads
                and self._agent_thread_filter
                and self._agent_thread_filter.is_agent_thread_message(msg, agent_threads)
            ):
                continue

            # Get message text for filtering
            text = msg.get("text", "")

            # Skip slash commands (prevent duplicate processing)
            if text.strip().startswith("/ketchup"):
                continue

            # Skip messages that mention @Ketchup EXCEPT thread replies
            # These are user interactions with Ketchup that shouldn't affect status/report
            # Thread replies should be kept as they indicate ongoing conversation
            if self._bot_user_id and f"<@{self._bot_user_id}>" in text and "thread_ts" not in msg:
                continue

            # Skip messages that are ONLY valid JIRA tickets (maintenance detection workflow replies)
            # Check for VALID_JIRA_PROJECTS patterns (CPGNREQ-12345, NEO-456, etc.)
            jira_pattern = r"\b(" + "|".join(VALID_JIRA_PROJECTS) + r")-\d+\b"
            if re.search(jira_pattern, text, re.IGNORECASE):
                # Remove JIRA tickets and mentions to check remaining content
                clean_text = re.sub(jira_pattern, "", text, flags=re.IGNORECASE)
                clean_text = re.sub(r"<@[A-Z0-9]+(?:\|[^>]+)?>", "", clean_text)
                clean_text = re.sub(r"<https?://[^>]+>", "", clean_text)  # Remove URLs
                clean_text = clean_text.strip()

                # If less than 10 chars remain, this is likely just a JIRA ticket reply
                if len(clean_text) < 10:
                    continue

            # Store the raw message
            ts = msg.get("ts")
            if ts:
                messages_dict[ts] = msg

            # Collect user mentions from the raw text
            if "text" in msg:
                if "user" in msg:
                    user_mentions.add(msg["user"])
                # Regex to find user mentions like <@Uxxxxxxx> or <@Uxxxxxxx|username>
                user_mentions.update(re.findall(r"<@([A-Z0-9]+)(?:\|[^>]+)?>", msg["text"]))

            # Track thread parent messages
            if "thread_ts" in msg and msg.get("ts") == msg.get("thread_ts"):
                thread_ts = msg.get("thread_ts")
                if thread_ts:
                    thread_timestamps.append(thread_ts)

        # Store the latest timestamp we've seen
        self._latest_message_ts = latest_ts
        # logger.info(f"[TIMESTAMP DEBUG] Latest message timestamp tracked: {latest_ts} for {len(messages_dict)} non-bot messages")

    async def fetch_thread_messages_batch(
        self, channel_id: str, thread_timestamps: List[str]
    ) -> Tuple[Dict[str, List[Dict]], Set[str]]:
        """
        Fetch messages from multiple threads with controlled concurrency.

        Args:
            channel_id: The channel ID
            thread_timestamps: List of thread timestamps to fetch

        Returns:
            Tuple containing:
            - Dictionary mapping thread_ts to list of messages
            - Set of user mentions found in thread messages
        """
        results = {}
        user_mentions = set()

        # Process threads sequentially with small delays to avoid rate limits
        for thread_ts in thread_timestamps:
            try:
                messages = await self.fetch_thread_messages(channel_id, thread_ts)
                results[thread_ts] = messages

                # Extract user mentions
                for msg in messages:
                    if "user" in msg:
                        user_mentions.add(msg["user"])
                    if "text" in msg:
                        user_mentions.update(re.findall(r"<@([A-Z0-9]+)(?:\|[^>]+)?>", msg["text"]))

                # Small delay between requests to avoid rate limits
                await asyncio.sleep(0.3)  # Balanced with reduced concurrent workers
            except Exception as e:
                logger.error(
                    "Error fetching thread messages for channel %s, thread %s: %s",
                    channel_id,
                    thread_ts,
                    str(e),
                )
                results[thread_ts] = []

        return results, user_mentions

    async def _fetch_thread_messages_parallel(
        self, channel_id: str, thread_timestamps: List[str]
    ) -> Tuple[Dict[str, List[Dict]], Set[str]]:
        """
        Fetch messages from multiple threads in parallel with controlled concurrency.

        Args:
            channel_id: The channel ID
            thread_timestamps: List of thread timestamps to fetch

        Returns:
            Tuple containing:
            - Dictionary mapping thread_ts to list of messages
            - Set of user mentions found in thread messages
        """
        results = {}
        user_mentions = set()
        batch_size = 4  # Moderate increase: 2x thread parallelism

        for i in range(0, len(thread_timestamps), batch_size):
            batch = thread_timestamps[i : i + batch_size]
            logger.info(
                "Fetching thread batch %d for channel %s",
                (i // batch_size) + 1,
                channel_id,
            )

            tasks = [self.fetch_thread_messages(channel_id, ts) for ts in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for thread_ts, result in zip(batch, batch_results, strict=False):
                if isinstance(result, Exception):
                    logger.error("Failed to fetch thread %s in parallel: %s", thread_ts, result)
                    results[thread_ts] = []  # Fallback to empty list
                else:
                    results[thread_ts] = result
                    for msg in result:
                        if "user" in msg:
                            user_mentions.add(msg["user"])
                        if "text" in msg:
                            user_mentions.update(
                                re.findall(r"<@([A-Z0-9]+)(?:\|[^>]+)?>", msg["text"])
                            )

            # Delay between batches to respect rate limits
            if i + batch_size < len(thread_timestamps):
                await asyncio.sleep(0.4)  # Optimized: 43% faster for thread fetching

        logger.info(
            "Completed parallel fetch for %d threads in channel %s",
            len(thread_timestamps),
            channel_id,
        )
        return results, user_mentions

    async def check_recent_thread_activity(
        self, channel_id: str, since_ts: str
    ) -> tuple[bool, str, List[str]]:
        """
        Check if there's been any thread activity since a given timestamp.

        This only detects actual new thread replies, not just the existence of threads.

        Args:
            channel_id: The ID of the Slack channel
            since_ts: Check for thread activity after this timestamp

        Returns:
            Tuple of (has_activity, latest_thread_ts, active_thread_timestamps)
        """
        try:
            url = f"{await self.get_api_base_url()}/conversations.history"
            headers = self.headers

            # Get recent messages to check their thread activity
            # We need to check older messages too, as threads can have new replies
            # even if the parent message is old
            params = {
                "channel": channel_id,
                "limit": 200,  # Check last 200 messages for thread activity
            }

            response = await self._make_api_request(url, "GET", headers, params)
            response_data = orjson.loads(response["body"])

            if not response_data.get("ok"):
                logger.error(
                    f"Error fetching messages for thread check: {response_data.get('error')}"
                )
                return False, since_ts, []

            messages = response_data.get("messages", [])
            has_new_activity = False
            latest_thread_ts = since_ts
            active_thread_timestamps = []

            # Check all messages for thread activity
            for msg in messages:
                # Skip bot messages
                if msg.get("bot_id") or msg.get("subtype") == "bot_message":
                    continue

                if msg.get("thread_ts") and msg.get("reply_count", 0) > 0:
                    # Get the latest reply timestamp
                    latest_reply = msg.get("latest_reply", "0")

                    # Count as thread activity if the thread has NEW replies after since_ts
                    # This works for both new threads and replies to old threads
                    # Convert both to float for proper comparison (handles string/int precision issues)
                    try:
                        if float(latest_reply) > float(since_ts):
                            has_new_activity = True
                            active_thread_timestamps.append(msg.get("thread_ts"))
                            if float(latest_reply) > float(latest_thread_ts):
                                latest_thread_ts = latest_reply
                    except (ValueError, TypeError):
                        # Fallback to string comparison if conversion fails
                        if latest_reply > since_ts:
                            has_new_activity = True
                            active_thread_timestamps.append(msg.get("thread_ts"))
                            if latest_reply > latest_thread_ts:
                                latest_thread_ts = latest_reply

            logger.info(
                f"Thread activity check for {channel_id} since {since_ts}: has_new={has_new_activity}, latest={latest_thread_ts}, active_threads={len(active_thread_timestamps)}"
            )
            return has_new_activity, latest_thread_ts, active_thread_timestamps

        except Exception as e:
            logger.error(f"Error checking thread activity: {e}")
            return False, since_ts, []

    async def fetch_thread_messages(self, channel_id: str, thread_ts: str) -> List[Dict]:
        """
        Fetch all messages from a Slack thread using cursor-based pagination.

        Args:
            channel_id: The ID of the Slack channel containing the thread
            thread_ts: The timestamp of the thread's parent message

        Returns:
            List of thread message dictionaries
        """

        # Define the core function to fetch thread messages
        async def _fetch_thread():
            messages = []
            next_cursor = None

            url = f"{await self.get_api_base_url()}/conversations.replies"
            headers = self.headers  # Access as property
            params = {
                "channel": channel_id,
                "ts": thread_ts,
                "limit": 200,
            }

            while True:
                if next_cursor:
                    params["cursor"] = next_cursor

                response = await self._make_api_request(url, "GET", headers, params)
                # Response is now a SafeResponse dict, parse the body
                response_data = orjson.loads(response["body"])

                if not response_data.get("ok"):
                    error = response_data.get("error")

                    # Special handling for not_in_channel: check if channel was re-archived
                    if error == "not_in_channel":
                        is_archived = await self._check_channel_archived(channel_id)
                        if is_archived:
                            logger.info(
                                "Thread fetch skipped - channel %s is archived (likely re-archived after command)",
                                channel_id,
                            )
                            return []  # Don't retry on re-archived channels

                    logger.error(
                        "Error fetching thread messages for channel %s, thread %s: %s",
                        channel_id,
                        thread_ts,
                        error,
                    )
                    raise Exception(f"Slack API error: {error}")

                messages.extend(response_data.get("messages", []))

                # Check for more messages in thread
                next_cursor = response_data.get("response_metadata", {}).get("next_cursor")
                if not next_cursor:
                    break

            return messages

        # Use the backoff strategy to handle retries
        try:
            return await self.execute_with_backoff(_fetch_thread)
        except Exception as e:
            logger.error(
                "Error fetching thread messages for channel %s, thread %s: %s",
                channel_id,
                thread_ts,
                str(e),
            )
            # Re-raise as a clean exception that will be handled by the batch method
            raise RuntimeError("ratelimited")

    async def _check_channel_archived(self, channel_id: str) -> bool:
        """
        Check if a channel is archived.

        Args:
            channel_id: The ID of the channel to check

        Returns:
            True if the channel is archived, False otherwise
        """
        try:
            url = f"{await self.get_api_base_url()}/conversations.info"
            headers = self.headers  # Access as property
            params = {"channel": channel_id}

            response = await self._make_api_request(url, "GET", headers, params)
            # Response is now a SafeResponse dict, parse the body
            response_data = orjson.loads(response["body"])

            if response_data.get("ok"):
                return response_data["channel"].get("is_archived", False)
            return False
        except Exception as e:
            logger.error("Error checking if channel %s is archived: %s", channel_id, str(e))
            return False

    async def _temporarily_unarchive_if_needed(self, channel_id: str) -> bool:
        """
        Check if a channel is archived and unarchive it temporarily.

        Args:
            channel_id: The ID of the channel to check and unarchive

        Returns:
            True if the channel was unarchived, False otherwise
        """
        is_archived = await self._check_channel_archived(channel_id)
        if is_archived:
            logger.info(
                "Channel %s is archived. Temporarily unarchiving to fetch messages.",
                channel_id,
            )
            return await self.archive_ops.unarchive_channel(channel_id)
        return False


class BatchSizeManager:
    """Manages adaptive batch sizing for API requests."""

    def __init__(self, initial_size: int = 100, min_size: int = 20, max_size: int = 200):
        self.size = initial_size
        self.min_size = min_size
        self.max_size = max_size

    def get_size(self) -> int:
        """Get current batch size."""
        return self.size

    def increase_size(self):
        """Increase batch size on success."""
        self.size = min(self.size + 10, self.max_size)

    def decrease_size(self):
        """Decrease batch size on error."""
        self.size = max(self.size - 10, self.min_size)
