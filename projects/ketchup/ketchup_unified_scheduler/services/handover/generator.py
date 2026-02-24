"""Handover summary generation logic for on-call shift handovers."""

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
    mcp_client: MCPAsyncClientProtocol, jira_ticket: str, logger: logging.Logger
) -> str:
    if not jira_ticket or jira_ticket == "NOT YET AVAILABLE":
        return "None"
    try:
        comments = await mcp_client.get_issue_comments(jira_ticket)
        if not comments:
            return "None"
        sorted_comments = sorted(comments, key=lambda x: x.get("created", ""), reverse=True)[:5]
        comment_texts = [
            f"[{c.get('created', '')[:10]}] {c.get('author', {}).get('displayName', 'Unknown')}: {body}"
            for c in sorted_comments
            if (body := c.get("body", "").replace("\n\n", "\n").strip())
        ]
        return "\n".join(comment_texts) if comment_texts else "None"
    except Exception as e:
        logger.warning(f"Could not fetch JIRA comments for {jira_ticket}: {e}")
        return "None"


async def generate_and_post_handover(container: TypedServiceRegistry) -> Dict[str, Any]:
    """Generate and post on-call shift handover summary to Slack."""
    if os.getenv("KETCHUP_HANDOVER_SUMMARY_ENABLED", "false").lower() != "true":
        logger.info("Handover summary feature is disabled")
        return {"status": "disabled"}

    logger.info("Starting handover summary generation")
    try:
        channel_operations = await container.aget(ChannelOperationsProtocol)
        channel_msg_ops = await container.aget(SlackChannelMessageOpsProtocol)
        channel_membership_ops = await container.aget(ChannelMembershipOpsProtocol)
        mcp_client = await container.aget(MCPAsyncClientProtocol)
        openai_handler = await container.aget(OpenAIHandlerProtocol)
        posting_handler = await container.aget(SlackPostingHandlerProtocol)

        all_channels = await channel_operations.query_ops.get_all_active_channels()
        logger.info(f"Found {len(all_channels)} active channels")

        filtered_channels = [
            ch
            for ch in all_channels
            if ch.get("channel_id")
            not in (FEEDBACK_CHANNEL, ACCESS_REQUEST_CHANNEL, HANDOVER_TARGET_CHANNEL)
        ]
        logger.info(f"Processing {len(filtered_channels)} channels after filtering")

        membership_results = await channel_membership_ops.lookup_membership_of_channels(
            [HANDOVER_TARGET_CHANNEL]
        )
        if not membership_results.get(HANDOVER_TARGET_CHANNEL, False):
            logger.error(
                f"Bot is not a member of handover target channel {HANDOVER_TARGET_CHANNEL}"
            )
            return {"status": "not_member"}

        since_ts = str(
            int(datetime.now(timezone.utc).timestamp()) - (HANDOVER_MESSAGE_WINDOW_HOURS * 3600)
        )
        logger.info(f"Collecting messages since {since_ts} ({HANDOVER_MESSAGE_WINDOW_HOURS}h ago)")

        channel_cards = []
        semaphore = asyncio.Semaphore(4)

        async def process_channel(channel: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            channel_id = channel.get("channel_id")
            channel_name = channel.get("channel_name", "unknown")
            async with semaphore:
                try:
                    channel_details = await channel_operations.query_ops.get_channel_details(
                        channel_id
                    )
                    customer_name = channel_details.get("customer_name", "NOT YET AVAILABLE")
                    jira_ticket = channel_details.get("jira_ticket", "")

                    message_preparer = MessagePreparer(
                        token_tracker=TokenTracker(),
                        channel_msg_ops=channel_msg_ops,
                        channel_info_ops=channel_operations.query_ops,
                    )
                    prepared_messages, channel_metadata = (
                        await message_preparer.prepare_messages_for_auto_status(
                            channel_id=channel_id, since_ts=since_ts, suppress_notification=True
                        )
                    )

                    jira_comments_text = await _fetch_jira_comments(mcp_client, jira_ticket, logger)
                    has_messages = channel_metadata.get("has_channel_messages", False)
                    has_jira = jira_comments_text != "None"

                    if not has_messages and not has_jira:
                        logger.info(f"Skipping {channel_id}: no messages or JIRA comments")
                        return None

                    ai_response = await openai_handler.execute_prompt(
                        messages=[
                            {"role": "system", "content": get_handover_system_prompt()},
                            {
                                "role": "user",
                                "content": get_handover_channel_prompt(
                                    channel_name,
                                    customer_name,
                                    jira_ticket,
                                    prepared_messages,
                                    jira_comments_text,
                                ),
                            },
                        ],
                        temperature=0.1,
                        max_tokens=512,
                    )

                    return {
                        "channel_id": channel_id,
                        "channel_name": channel_name,
                        "customer_name": customer_name,
                        "jira_ticket": jira_ticket,
                        "summary": ai_response.strip(),
                    }
                except Exception as e:
                    logger.error(f"Error processing channel {channel_id}: {e}", exc_info=True)
                    return None

        results = await asyncio.gather(
            *[process_channel(ch) for ch in filtered_channels], return_exceptions=True
        )
        channel_cards = [r for r in results if r is not None and not isinstance(r, Exception)]
        logger.info(f"Generated summaries for {len(channel_cards)} channels")

        blocks = _format_handover_message(channel_cards)
        fallback_text = (
            f"Handover Summary - {len(channel_cards)} active incidents"
            if channel_cards
            else "Handover Summary - No active incidents"
        )

        await posting_handler._post_channel_message(
            channel_id=HANDOVER_TARGET_CHANNEL, message=fallback_text, blocks=blocks
        )
        logger.info(f"Successfully posted handover summary with {len(channel_cards)} channels")

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
    timestamp_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    title_text = f"*🔄 Ketchup On-Call Handover Summary*\n_{timestamp_str}_\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": title_text}}]

    if not channel_cards:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "_No active incidents to report_"},
            }
        )
    else:
        for i, card in enumerate(channel_cards):
            jira_link = (
                f" • <https://jira.corp.adobe.com/browse/{card['jira_ticket']}|{card['jira_ticket']}>"
                if card["jira_ticket"] and card["jira_ticket"] != "NOT YET AVAILABLE"
                else ""
            )
            card_text = (
                f"*<#{card['channel_id']}|{card['channel_name']}>*\n"
                f"*Customer:* {card['customer_name']}{jira_link}\n{card['summary']}"
            )
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": card_text}})
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

    footer_text = f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n_{len(channel_cards)} active incidents • Generated by Ketchup_"
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": footer_text}})
    return blocks
