"""Handover summary generation logic for on-call shift handovers."""

import asyncio
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from packages.ai.core.operations.message_preparation import MessagePreparer
from packages.ai.cost_calculator import TokenTracker
from packages.ai.prompts.handover_summary import (
    get_handover_channel_prompt,
    get_handover_system_prompt,
)
from packages.core.config.handover_config import (
    HANDOVER_MESSAGE_WINDOW_HOURS,
    HANDOVER_SCHEDULE_TIMES,
    HANDOVER_TARGET_CHANNEL,
)
from packages.core.constants import ACCESS_REQUEST_CHANNEL, FEEDBACK_CHANNEL
from packages.core.logging import setup_logger
from packages.core.typed_di.registry import TypedServiceRegistry
from packages.core.typed_di.service_registrations.protocols import (
    AgentConversationStoreProtocol,
    AgentVectorStoreProtocol,
    ChannelMembershipOpsProtocol,
    ChannelOperationsProtocol,
    MCPAsyncClientProtocol,
    OpenAIHandlerProtocol,
    SlackChannelMessageOpsProtocol,
    SlackPostingHandlerProtocol,
)

logger = setup_logger(__name__)


def _sanitize_mrkdwn(text: str) -> str:
    """Remove Slack broadcast tokens and user mentions from text to prevent unwanted pings."""
    # Strip broadcast tokens
    text = re.sub(r"<!channel>", "", text)
    text = re.sub(r"<!here>", "", text)
    text = re.sub(r"<!everyone>", "", text)
    # Strip user mentions (both simple and display name formats)
    text = re.sub(r"<@U[A-Z0-9]+\|[^>]+>", "", text)
    text = re.sub(r"<@U[A-Z0-9]+>", "", text)
    return text


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


async def _get_last_activity(
    conversation_store: Any,
    vector_store: Any,
    channel_id: str,
    channel_msg_ops: Any = None,
) -> Tuple[str, str]:
    """Get last activity timestamp and recent messages for a channel.

    Returns (timestamp_str, recent_messages_text). Both empty strings if unknown.
    Strategy: ChromaDB (has text) → Slack API (has text) → watermark (timestamp only).
    """
    # Try ChromaDB first — has both timestamp and message text
    if vector_store is not None:
        try:
            thirty_days_ago = str(int(datetime.now(timezone.utc).timestamp()) - (30 * 24 * 3600))
            docs = await vector_store.get_by_time_range(
                channel_id=channel_id, since_ts=thirty_days_ago
            )
            if docs:
                last_ts = max(doc.get("metadata", {}).get("message_ts", 0.0) for doc in docs)
                if last_ts > 0:
                    last_dt = datetime.fromtimestamp(last_ts, tz=timezone.utc)
                    # Return last few messages for AI summarization
                    sorted_docs = sorted(
                        docs, key=lambda d: d.get("metadata", {}).get("message_ts", 0.0)
                    )
                    recent_texts = "\n".join(d.get("text", "") for d in sorted_docs[-5:])
                    return last_dt.strftime("%b %d %H:%M UTC"), recent_texts
            logger.debug("No ChromaDB docs for %s in last 30 days", channel_id)
        except Exception as e:
            logger.debug("ChromaDB fallback failed for %s: %s", channel_id, e)

    # Fallback 1: Slack API — fetch a few recent messages for context
    if channel_msg_ops is not None:
        try:
            url = f"{await channel_msg_ops.get_api_base_url()}/conversations.history"
            resp = await channel_msg_ops._make_api_request(
                url, "GET", channel_msg_ops.headers, {"channel": channel_id, "limit": 10}
            )
            if resp and resp["status"] == 200:
                import json as _json

                data = _json.loads(resp["body"])
                if data.get("ok"):
                    msgs = data.get("messages", [])
                    if msgs:
                        last_ts = float(msgs[0].get("ts", 0))
                        if last_ts > 0:
                            last_dt = datetime.fromtimestamp(last_ts, tz=timezone.utc)
                            # Filter to human messages only (no bots, no system subtypes)
                            human_msgs = [
                                m
                                for m in msgs
                                if not m.get("bot_id") and not m.get("subtype") and m.get("text")
                            ]
                            if human_msgs:
                                recent_texts = "\n".join(
                                    m["text"] for m in reversed(human_msgs[:5])
                                )
                                return last_dt.strftime("%b %d %H:%M UTC"), recent_texts
                            # No human messages — return timestamp only
                            return last_dt.strftime("%b %d %H:%M UTC"), ""
        except Exception:
            pass

    # Fallback 2: DynamoDB watermark — timestamp only, no message text
    if conversation_store is not None:
        try:
            watermark = await conversation_store.get_watermark(channel_id)
            if watermark and watermark.latest_ingested_ts != "0":
                last_dt = datetime.fromtimestamp(
                    float(watermark.latest_ingested_ts), tz=timezone.utc
                )
                return last_dt.strftime("%b %d %H:%M UTC"), ""
            logger.debug("No watermark for %s (watermark=%s)", channel_id, watermark)
        except Exception as e:
            logger.debug("Watermark lookup failed for %s: %s", channel_id, e)

    return "", ""


async def generate_and_post_handover(container: TypedServiceRegistry) -> Dict[str, Any]:
    """Generate and post on-call shift handover summary to Slack."""
    if os.getenv("KETCHUP_HANDOVER_SUMMARY_ENABLED", "false").lower() != "true":
        logger.info("Handover summary feature is disabled")
        return {"status": "disabled"}

    now = datetime.now(timezone.utc)
    current_minute = now.strftime("%H:%M")
    previous_minute = (now - timedelta(seconds=60)).strftime("%H:%M")
    if (
        current_minute not in HANDOVER_SCHEDULE_TIMES
        and previous_minute not in HANDOVER_SCHEDULE_TIMES
    ):
        logger.info(
            f"Skipping handover: time {current_minute} not in schedule {HANDOVER_SCHEDULE_TIMES}"
        )
        return {"status": "skipped_not_scheduled"}

    logger.info("Starting handover summary generation")
    try:
        channel_operations = await container.aget(ChannelOperationsProtocol)
        channel_msg_ops = await container.aget(SlackChannelMessageOpsProtocol)
        channel_membership_ops = await container.aget(ChannelMembershipOpsProtocol)
        mcp_client = await container.aget(MCPAsyncClientProtocol)
        openai_handler = await container.aget(OpenAIHandlerProtocol)
        posting_handler = await container.aget(SlackPostingHandlerProtocol)

        vector_store = None
        conversation_store = None
        try:
            vector_store = await container.aget(AgentVectorStoreProtocol)
            conversation_store = await container.aget(AgentConversationStoreProtocol)
            logger.info("ChromaDB vector store available for handover")
        except Exception:
            logger.info("ChromaDB vector store not available, will use Slack API")

        all_channels = await channel_operations.query_ops.get_all_active_channels()
        logger.info(f"Found {len(all_channels)} active channels")

        filtered_channels = [
            ch
            for ch in all_channels
            if ch.get("channel_id")
            not in (FEEDBACK_CHANNEL, ACCESS_REQUEST_CHANNEL, HANDOVER_TARGET_CHANNEL)
        ]
        logger.info(f"Processing {len(filtered_channels)} channels after filtering")

        member_channels = await channel_membership_ops.lookup_membership_of_channels()
        member_channel_ids = {ch.get("id") for ch in member_channels}
        if HANDOVER_TARGET_CHANNEL not in member_channel_ids:
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
            if not isinstance(channel_id, str):
                logger.warning(f"Invalid channel_id type: {type(channel_id)}, skipping channel")
                return None
            channel_name = channel.get("channel_name", "unknown")
            async with semaphore:
                try:
                    channel_details = await channel_operations.query_ops.get_channel_details(
                        channel_id
                    )
                    customer_name = channel_details.get("customer_name", "NOT YET AVAILABLE")
                    jira_ticket = channel_details.get("jira_ticket", "")

                    prepared_messages = ""
                    channel_metadata = {"has_channel_messages": False}

                    # Try ChromaDB first (pre-indexed messages from real-time ingestor)
                    if vector_store is not None:
                        try:
                            docs = await vector_store.get_by_time_range(
                                channel_id=channel_id, since_ts=since_ts
                            )
                            if docs:
                                prepared_messages = "\n".join(doc["text"] for doc in docs)
                                channel_metadata["has_channel_messages"] = True
                                logger.info(
                                    "ChromaDB returned %d docs for %s",
                                    len(docs),
                                    channel_id,
                                )
                        except Exception as e:
                            logger.warning(
                                "ChromaDB failed for %s, falling back to Slack API: %s",
                                channel_id,
                                e,
                            )

                    # Fallback: Slack API via MessagePreparer
                    if not prepared_messages:
                        message_preparer = MessagePreparer(
                            token_tracker=TokenTracker(),
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

                    jira_comments_text = await _fetch_jira_comments(mcp_client, jira_ticket, logger)
                    has_messages = channel_metadata.get("has_channel_messages", False)
                    has_jira = jira_comments_text != "None"

                    if not has_messages and not has_jira:
                        last_activity_ts, last_messages = await _get_last_activity(
                            conversation_store, vector_store, channel_id, channel_msg_ops
                        )
                        if last_activity_ts and last_messages:
                            # Pass last messages through AI for consistent summary
                            ai_response = await openai_handler.execute_prompt(
                                messages=[
                                    {"role": "system", "content": get_handover_system_prompt()},
                                    {
                                        "role": "user",
                                        "content": get_handover_channel_prompt(
                                            channel_name,
                                            customer_name,
                                            jira_ticket,
                                            last_messages,
                                            jira_comments_text,
                                        ),
                                    },
                                ],
                                reasoning_effort="low",
                                max_tokens=256,
                            )
                            summary = (
                                f"No updates in the last {HANDOVER_MESSAGE_WINDOW_HOURS}h"
                                f" (last activity {last_activity_ts}).\n"
                                f"{_sanitize_mrkdwn(ai_response.strip())}"
                            )
                        elif last_activity_ts:
                            summary = (
                                f"No updates in the last {HANDOVER_MESSAGE_WINDOW_HOURS}h."
                                f" Last activity: {last_activity_ts}."
                            )
                        else:
                            summary = f"No updates in the last {HANDOVER_MESSAGE_WINDOW_HOURS}h."
                        logger.info(f"No activity for {channel_id}, including in summary")
                        return {
                            "channel_id": channel_id,
                            "channel_name": channel_name,
                            "customer_name": customer_name,
                            "jira_ticket": jira_ticket,
                            "summary": summary,
                        }

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
                        "summary": _sanitize_mrkdwn(ai_response.strip()),
                    }
                except Exception as e:
                    logger.error(f"Error processing channel {channel_id}: {e}", exc_info=True)
                    return None

        results = await asyncio.gather(
            *[process_channel(ch) for ch in filtered_channels], return_exceptions=True
        )
        channel_cards: List[Dict[str, Any]] = [r for r in results if r is not None and not isinstance(r, Exception)]  # type: ignore[assignment]
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
    # Slack API limit: max 50 blocks per message
    if len(blocks) > 50:
        blocks = blocks[:49]
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"_...and more ({len(channel_cards)} total incidents) • Truncated to fit Slack limits_",
                },
            }
        )
    return blocks
