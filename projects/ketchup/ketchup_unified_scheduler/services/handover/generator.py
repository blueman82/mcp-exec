"""
generator.py

This module contains the handover summary generation logic for on-call shift handovers.

The generator:
1. Collects messages and JIRA comments from active incident channels
2. Uses AI to generate ultra-compact summaries (1-2 bullets per channel)
3. Posts formatted handover summary to a designated Slack channel

Feature flag controlled via KETCHUP_HANDOVER_SUMMARY_ENABLED environment variable.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from packages.ai.core.operations.message_preparation import MessagePreparer
from packages.ai.cost_calculator import TokenTracker
from packages.ai.prompts.handover_summary import (
    get_handover_channel_prompt,
    get_handover_system_prompt,
)
from packages.core.config.handover_config import (
    HANDOVER_MESSAGE_WINDOW_HOURS,
    HANDOVER_TARGET_CHANNEL,
)
from packages.core.constants import ACCESS_REQUEST_CHANNEL, FEEDBACK_CHANNEL
from packages.core.logging import setup_logger
from packages.core.typed_di.service_registrations.protocols import (
    ChannelMembershipOpsProtocol,
    ChannelOperationsProtocol,
    MCPAsyncClientProtocol,
    OpenAIHandlerProtocol,
    SlackChannelMessageOpsProtocol,
    SlackPostingHandlerProtocol,
)
from packages.core.typed_di.typed_service_registry import TypedServiceRegistry

logger = setup_logger(__name__)


async def _fetch_jira_comments(
    mcp_client: MCPAsyncClientProtocol, jira_ticket: str, logger
) -> str:
    """
    Fetch and format JIRA comments for a ticket.

    Args:
        mcp_client: MCP client for JIRA API calls
        jira_ticket: JIRA ticket ID
        logger: Logger instance

    Returns:
        Formatted JIRA comments text, or "None" if no comments or error
    """
    if not jira_ticket or jira_ticket == "NOT YET AVAILABLE":
        return "None"

    try:
        comments = await mcp_client.get_issue_comments(jira_ticket)
        if not comments:
            return "None"

        # Sort by created date (most recent first) and take top 5
        sorted_comments = sorted(
            comments, key=lambda x: x.get("created", ""), reverse=True
        )[:5]

        comment_texts = []
        for comment in sorted_comments:
            author = comment.get("author", {}).get("displayName", "Unknown")
            created = comment.get("created", "")[:10]  # Just date part
            body = comment.get("body", "")
            clean_body = body.replace("\n\n", "\n").strip()
            if clean_body:
                comment_texts.append(f"[{created}] {author}: {clean_body}")

        return "\n".join(comment_texts) if comment_texts else "None"

    except Exception as e:
        logger.warning(f"Could not fetch JIRA comments for {jira_ticket}: {e}")
        return "None"


async def generate_and_post_handover(container: TypedServiceRegistry) -> Dict[str, Any]:
    """
    Generate and post on-call shift handover summary to Slack.

    This function:
    1. Checks if handover summary feature is enabled
    2. Collects messages and JIRA comments from active incident channels
    3. Uses AI to generate ultra-compact summaries (1-2 bullets per channel)
    4. Posts formatted Block Kit message to the handover target channel

    Args:
        container: TypedDI service container with all required dependencies

    Returns:
        Dict with status, channel_count, and timestamp. Possible status values:
        - "disabled": Feature flag is not enabled
        - "not_member": Bot is not a member of the target channel
        - "success": Handover summary posted successfully
        - "error": An error occurred during generation

    Environment Variables:
        KETCHUP_HANDOVER_SUMMARY_ENABLED: Must be "true" to enable this feature
        KETCHUP_HANDOVER_TARGET_CHANNEL: Channel ID where summary is posted
        KETCHUP_HANDOVER_MESSAGE_WINDOW_HOURS: Hours to look back for messages
    """
    # Step 1: Check feature flag (fail fast at boundary)
    if os.getenv("KETCHUP_HANDOVER_SUMMARY_ENABLED", "false").lower() != "true":
        logger.info("Handover summary feature is disabled")
        return {"status": "disabled"}

    logger.info("Starting handover summary generation")

    try:

        # Step 2: Resolve services from container
        channel_operations = await container.aget(ChannelOperationsProtocol)
        channel_msg_ops = await container.aget(SlackChannelMessageOpsProtocol)
        channel_membership_ops = await container.aget(ChannelMembershipOpsProtocol)
        mcp_client = await container.aget(MCPAsyncClientProtocol)
        openai_handler = await container.aget(OpenAIHandlerProtocol)
        posting_handler = await container.aget(SlackPostingHandlerProtocol)

        # Step 3: Get all active channels
        all_channels = await channel_operations.query_ops.get_all_active_channels()
        logger.info(f"Found {len(all_channels)} active channels")

        # Step 4: Filter out special channels and the handover target channel itself
        filtered_channels = [
            ch
            for ch in all_channels
            if ch.get("channel_id")
            not in (FEEDBACK_CHANNEL, ACCESS_REQUEST_CHANNEL, HANDOVER_TARGET_CHANNEL)
        ]
        logger.info(
            f"Processing {len(filtered_channels)} channels after filtering special channels"
        )

        # Step 5: Check bot membership in target channel
        membership_results = await channel_membership_ops.lookup_membership_of_channels(
            [HANDOVER_TARGET_CHANNEL]
        )
        if not membership_results.get(HANDOVER_TARGET_CHANNEL, False):
            logger.error(
                f"Bot is not a member of handover target channel {HANDOVER_TARGET_CHANNEL}"
            )
            return {"status": "not_member"}

        # Step 6: Calculate time window for message collection
        since_ts = str(
            int(datetime.now(timezone.utc).timestamp()) - (HANDOVER_MESSAGE_WINDOW_HOURS * 3600)
        )
        logger.info(f"Collecting messages since {since_ts} ({HANDOVER_MESSAGE_WINDOW_HOURS}h ago)")

        # Step 7: Process channels with concurrency control
        channel_cards = []
        semaphore = asyncio.Semaphore(4)  # Process 4 channels in parallel

        async def process_channel(channel: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            """Process a single channel and return its summary card."""
            channel_id = channel.get("channel_id")
            channel_name = channel.get("channel_name", "unknown")

            async with semaphore:
                try:
                    # Step 7a: Get channel details
                    channel_details = await channel_operations.query_ops.get_channel_details(
                        channel_id
                    )
                    customer_name = channel_details.get("customer_name", "NOT YET AVAILABLE")
                    jira_ticket = channel_details.get("jira_ticket", "")

                    # Step 7b: Prepare messages using MessagePreparer
                    token_tracker = TokenTracker()
                    message_preparer = MessagePreparer(
                        token_tracker=token_tracker,
                        channel_msg_ops=channel_msg_ops,
                        channel_info_ops=channel_operations.query_ops,
                    )

                    prepared_messages, channel_metadata = (
                        await message_preparer.prepare_messages_for_auto_status(
                            channel_id=channel_id,
                            since_ts=since_ts,
                            suppress_notification=True,
                        )
                    )

                    # Step 7c: Fetch JIRA comments if ticket exists
                    jira_comments_text = await _fetch_jira_comments(
                        mcp_client, jira_ticket, logger
                    )

                    # Step 7d: Skip channel if no messages AND no JIRA comments
                    has_messages = channel_metadata.get("has_channel_messages", False)
                    has_jira = jira_comments_text != "None"

                    if not has_messages and not has_jira:
                        logger.info(f"Skipping {channel_id}: no messages or JIRA comments")
                        return None

                    # Step 7e: Call OpenAI with handover prompt
                    system_prompt = get_handover_system_prompt()
                    channel_prompt = get_handover_channel_prompt(
                        channel_name=channel_name,
                        customer_name=customer_name,
                        jira_ticket=jira_ticket,
                        messages=prepared_messages,
                        jira_comments=jira_comments_text,
                    )

                    ai_response = await openai_handler.execute_prompt(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": channel_prompt},
                        ],
                        temperature=0.1,
                        max_tokens=512,
                    )

                    summary = ai_response.strip()

                    # Step 7f: Build channel card
                    return {
                        "channel_id": channel_id,
                        "channel_name": channel_name,
                        "customer_name": customer_name,
                        "jira_ticket": jira_ticket,
                        "summary": summary,
                    }

                except Exception as e:
                    logger.error(f"Error processing channel {channel_id}: {e}", exc_info=True)
                    return None

        # Process all channels in parallel
        tasks = [process_channel(ch) for ch in filtered_channels]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out None values and exceptions
        for result in results:
            if result is not None and not isinstance(result, Exception):
                channel_cards.append(result)

        logger.info(f"Generated summaries for {len(channel_cards)} channels")

        # Step 8: Format Block Kit message
        blocks = _format_handover_message(channel_cards)

        # Step 9: Post to HANDOVER_TARGET_CHANNEL
        fallback_text = (
            f"Handover Summary - {len(channel_cards)} active incidents"
            if channel_cards
            else "Handover Summary - No active incidents"
        )

        await posting_handler._post_channel_message(
            channel_id=HANDOVER_TARGET_CHANNEL,
            message=fallback_text,
            blocks=blocks,
        )

        logger.info(f"Successfully posted handover summary with {len(channel_cards)} channels")

        # Step 10: Return success status
        return {
            "status": "success",
            "channel_count": len(channel_cards),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error generating handover summary: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def _format_handover_message(channel_cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Format handover summary as Block Kit message.

    Uses Option B card format:
    - Title with emoji
    - Timestamp subtitle
    - Heavy dividers (━━━) at top and bottom
    - Per channel: bold channel link, Customer line with JIRA link, bullet summary
    - Light dividers (───) between channels
    - Footer with metrics

    Args:
        channel_cards: List of channel summary dicts with keys:
                      channel_id, channel_name, customer_name, jira_ticket, summary

    Returns:
        List of Block Kit blocks for Slack message
    """
    blocks = []

    # Title section
    timestamp_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    title_text = f"*🔄 Ketchup On-Call Handover Summary*\n_{timestamp_str}_\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": title_text}})

    if not channel_cards:
        # No active incidents
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "_No active incidents to report_"},
            }
        )
    else:
        # Add each channel card
        for i, card in enumerate(channel_cards):
            channel_id = card["channel_id"]
            channel_name = card["channel_name"]
            customer_name = card["customer_name"]
            jira_ticket = card["jira_ticket"]
            summary = card["summary"]

            # Build card text
            card_text = f"*<#{channel_id}|{channel_name}>*\n"
            card_text += f"*Customer:* {customer_name}"

            # Add JIRA link if available
            if jira_ticket and jira_ticket != "NOT YET AVAILABLE":
                jira_url = f"https://jira.corp.adobe.com/browse/{jira_ticket}"
                card_text += f" • <{jira_url}|{jira_ticket}>"

            card_text += f"\n{summary}"

            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": card_text}})

            # Add light divider between cards (but not after the last one)
            if i < len(channel_cards) - 1:
                blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "─────────────────────────────────────────",
                        },
                    }
                )

    # Bottom heavy divider and footer
    footer_text = (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"_{len(channel_cards)} active incidents • Generated by Ketchup_"
    )
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": footer_text}})

    return blocks
