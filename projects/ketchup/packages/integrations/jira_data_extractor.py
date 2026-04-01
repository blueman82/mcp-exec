"""
jira_data_extractor.py

Extracts JIRA ticket information from channel metadata and messages.
Integrates with MCP client and includes caching for performance.
"""

import re
from typing import Any, Dict, List, Optional

from packages.core.logging import setup_logger
from packages.db.dynamodb_store import DynamoDBStore
from packages.integrations.async_mcp_client import AsyncMCPClient
from packages.integrations.jira_cache import JIRACache

logger = setup_logger(__name__)


class JIRADataExtractor:
    """Extracts JIRA ticket data from multiple sources with caching."""

    def __init__(
        self,
        mcp_client: AsyncMCPClient,
        dynamodb_store: DynamoDBStore,
        cache: Optional[JIRACache] = None,
    ):
        """
        Initialize JIRA data extractor.

        Args:
            mcp_client: MCP client for JIRA API access
            dynamodb_store: DynamoDB store for channel metadata
            cache: Optional JIRA cache instance
        """
        self.mcp_client = mcp_client
        self.dynamodb_store = dynamodb_store
        self.cache = cache or JIRACache()

        # JIRA ticket pattern - matches PROJECT-NUMBER format
        self.ticket_pattern = re.compile(r"\b([A-Z]{2,10}-[0-9]{1,7}(?![0-9]))\b")

    async def get_jira_context(
        self, channel_id: str, message_texts: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Get JIRA context for a channel with caching.

        Args:
            channel_id: Slack channel ID
            message_texts: List of message texts to search for tickets

        Returns:
            JIRA context dict with ticket info or None
        """
        # Try cache first
        cache_key = f"context:{channel_id}"
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            logger.info(f"Cache hit for JIRA context: {channel_id}")
            return cached_result

        # Get from source
        result = await self._get_jira_context_from_source(channel_id, message_texts)

        # Cache the result if found
        if result:
            await self.cache.set(cache_key, result)

        return result

    async def _get_jira_context_from_source(
        self, channel_id: str, message_texts: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Get JIRA context from various sources without cache.

        Args:
            channel_id: Slack channel ID
            message_texts: List of message texts to search

        Returns:
            JIRA context dict or None
        """
        try:
            # First check channel metadata for associated JIRA ticket
            channel_metadata = await self.dynamodb_store.get_channel_details(channel_id)

            if channel_metadata and "jira_ticket" in channel_metadata:
                ticket_id = channel_metadata["jira_ticket"]

                # Skip invalid placeholder values
                if ticket_id and ticket_id != "NOT YET AVAILABLE":
                    logger.info(f"Found JIRA ticket in channel metadata: {ticket_id}")

                    # Get full ticket data from JIRA
                    ticket_data = await self._get_ticket_data(ticket_id)
                    if ticket_data:
                        return {
                            "source": "channel_metadata",
                            "ticket_id": ticket_id,
                            "data": ticket_data,
                        }
                else:
                    logger.debug(f"Skipping invalid JIRA ticket placeholder: {ticket_id}")

            # If not in metadata, search messages for ticket references
            ticket_ids = self.extract_ticket_ids(message_texts)

            if ticket_ids:
                # Get data for the first ticket found (could be enhanced to handle multiple)
                ticket_id = ticket_ids[0]
                logger.info(f"Found JIRA ticket in messages: {ticket_id}")

                ticket_data = await self._get_ticket_data(ticket_id)
                if ticket_data:
                    return {
                        "source": "message_text",
                        "ticket_id": ticket_id,
                        "data": ticket_data,
                        "all_tickets": ticket_ids,  # Include all found tickets
                    }

            logger.info(f"No JIRA tickets found for channel: {channel_id}")
            return None

        except Exception as e:
            logger.error(f"Error getting JIRA context: {e}")
            return None

    def extract_ticket_ids(self, message_texts: List[str]) -> List[str]:
        """
        Extract JIRA ticket IDs from message texts.

        Args:
            message_texts: List of message texts to search

        Returns:
            List of unique ticket IDs found
        """
        ticket_ids = []

        for text in message_texts:
            if text:
                matches = self.ticket_pattern.findall(text)
                ticket_ids.extend(matches)

        # Return unique ticket IDs while preserving order
        seen = set()
        unique_tickets = []
        for ticket in ticket_ids:
            if ticket not in seen:
                seen.add(ticket)
                unique_tickets.append(ticket)

        return unique_tickets

    async def _get_ticket_data(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full ticket data from JIRA via MCP, including comments.

        Args:
            ticket_id: JIRA ticket ID

        Returns:
            Ticket data dict with comments or None
        """
        # Validate ticket ID before processing
        if not ticket_id or ticket_id == "NOT YET AVAILABLE":
            logger.debug(f"Invalid ticket ID: {ticket_id}")
            return None

        # Check cache first
        cache_key = f"ticket:{ticket_id}"
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            logger.info(f"Cache hit for ticket: {ticket_id}")
            return cached_data

        try:
            # Get ticket data from MCP
            ticket_data = await self.mcp_client.get_issue(ticket_id)

            if ticket_data:
                # Get comments for the ticket
                comments = await self.mcp_client.get_issue_comments(ticket_id)

                # Filter out bot comments
                bot_users = [
                    "jiradydx",
                    "jira dynamics dx",
                    "monserv",
                    "jarvis",
                    "jarvis automation",
                    "snowjira",
                    "jira project auto-assigner",
                    "agent nexus jira prod user",
                    "ketchup",
                ]
                filtered_comments = []

                for comment in comments:
                    author = comment.get("author", {})
                    author_name = author.get("displayName", "").lower()
                    author_key = author.get("key", "").lower()

                    # Skip if author is a bot
                    if any(bot in author_name or bot in author_key for bot in bot_users):
                        continue

                    filtered_comments.append(
                        {
                            "id": comment.get("id"),
                            "author": author.get("displayName", "Unknown"),
                            "created": comment.get("created"),
                            "updated": comment.get("updated"),
                            "body": comment.get("body", ""),
                        }
                    )

                # Add filtered comments to ticket data
                ticket_data["comments"] = filtered_comments
                logger.info(
                    f"Added {len(filtered_comments)} non-bot comments to ticket {ticket_id}"
                )

                # Cache the result with comments
                await self.cache.set(cache_key, ticket_data)
                return ticket_data

            return None

        except Exception as e:
            logger.error(f"Error getting ticket data for {ticket_id}: {e}")
            return None

    async def search_related_tickets(self, jql: str) -> Optional[List[Dict[str, Any]]]:
        """
        Search for tickets using JQL with caching.

        Args:
            jql: JIRA Query Language string

        Returns:
            List of ticket data or None
        """
        # Use JQL as cache key
        cache_key = f"search:{jql}"
        cached_results = await self.cache.get(cache_key)
        if cached_results:
            logger.info(f"Cache hit for JQL search: {jql}")
            return cached_results

        try:
            # Search via MCP
            results = await self.mcp_client.search_issues(jql)

            if results and "issues" in results:
                issues = results["issues"]
                # Cache the results
                await self.cache.set(cache_key, issues)
                return issues

            return None

        except Exception as e:
            logger.error(f"Error searching JIRA with JQL '{jql}': {e}")
            return None

    async def get_tickets_batch(
        self, ticket_ids: List[str], include_comments: bool = False
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Get multiple tickets in a batch for better performance.

        Args:
            ticket_ids: List of JIRA ticket IDs
            include_comments: Whether to fetch comments for each ticket

        Returns:
            Dict mapping ticket ID to ticket data (or None if not found)
        """
        if not ticket_ids:
            return {}

        result = {}
        uncached_tickets = []

        # Check cache first
        for ticket_id in ticket_ids:
            cache_key = f"ticket:{ticket_id}"
            cached_data = await self.cache.get(cache_key)
            if cached_data:
                logger.info(f"Cache hit for ticket: {ticket_id}")
                result[ticket_id] = cached_data
            else:
                uncached_tickets.append(ticket_id)

        # Batch fetch uncached tickets
        if uncached_tickets:
            logger.info(f"Batch fetching {len(uncached_tickets)} uncached tickets")
            try:
                batch_results = await self.mcp_client.get_issues_batch(uncached_tickets)

                # Process each fetched ticket
                for ticket_id, ticket_data in batch_results.items():
                    if ticket_data:
                        # Optionally fetch comments (still one by one, but could be parallelized)
                        if include_comments:
                            comments = await self.mcp_client.get_issue_comments(ticket_id)

                            # Filter out bot comments
                            bot_users = [
                                "jiradydx",
                                "jira dynamics dx",
                                "monserv",
                                "jarvis",
                                "jarvis automation",
                                "snowjira",
                                "jira project auto-assigner",
                                "agent nexus jira prod user",
                                "ketchup",
                            ]
                            filtered_comments = []

                            for comment in comments:
                                author = comment.get("author", {})
                                author_name = author.get("displayName", "").lower()
                                author_key = author.get("key", "").lower()

                                # Skip if author is a bot
                                if any(
                                    bot in author_name or bot in author_key for bot in bot_users
                                ):
                                    continue

                                filtered_comments.append(
                                    {
                                        "id": comment.get("id"),
                                        "author": author.get("displayName", "Unknown"),
                                        "created": comment.get("created"),
                                        "updated": comment.get("updated"),
                                        "body": comment.get("body", ""),
                                    }
                                )

                            ticket_data["comments"] = filtered_comments
                            logger.info(
                                f"Added {len(filtered_comments)} non-bot comments to ticket {ticket_id}"
                            )

                        # Cache the result
                        cache_key = f"ticket:{ticket_id}"
                        await self.cache.set(cache_key, ticket_data)
                        result[ticket_id] = ticket_data
                    else:
                        result[ticket_id] = None

            except Exception as e:
                logger.error(f"Error batch fetching tickets: {e}")
                # Return None for all failed tickets
                for ticket_id in uncached_tickets:
                    if ticket_id not in result:
                        result[ticket_id] = None

        return result

    async def warm_cache(self, channel_ids: List[str]):
        """
        Pre-populate cache for frequently accessed channels.

        Args:
            channel_ids: List of channel IDs to warm cache for
        """
        logger.info(f"Warming JIRA cache for {len(channel_ids)} channels")

        for channel_id in channel_ids:
            try:
                # Get channel metadata
                metadata = await self.dynamodb_store.get_channel_metadata(channel_id)

                if metadata and "jira_ticket" in metadata:
                    ticket_id = metadata["jira_ticket"]
                    # This will populate the cache
                    await self._get_ticket_data(ticket_id)

            except Exception as e:
                logger.error(f"Error warming cache for channel {channel_id}: {e}")

        logger.info("JIRA cache warming complete")
