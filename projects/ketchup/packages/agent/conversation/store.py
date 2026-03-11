"""DynamoDB conversation store for Ketchup Agent."""

import time
from typing import List, Optional, Set

from packages.core.constants import DYNAMODB_TABLE_NAME
from packages.core.logging import setup_logger
from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient
from packages.db.operations.base_operations import BaseOperations

from .models import ConversationTurn, MessageWatermark

logger = setup_logger(__name__)

# DynamoDB key prefixes
PK_CONVERSATION = "AGENT_CONVERSATION#"
PK_THREAD = "AGENT_THREAD#"
PK_WATERMARK = "AGENT_WATERMARK#"
SK_TURN_PREFIX = "TURN#"
SK_THREAD_PREFIX = "THREAD#"
SK_WATERMARK = "WATERMARK"


class ConversationStore(BaseOperations):
    """DynamoDB operations for agent conversations, threads, and watermarks."""

    def __init__(self, dynamodb_client: DynamoDBAsyncClient):
        super().__init__(client=dynamodb_client, table_name=DYNAMODB_TABLE_NAME)

    # ── Conversation Turns ──────────────────────────────────────────

    async def store_turn(self, turn: ConversationTurn) -> None:
        """Store a conversation turn.

        Args:
            turn: The conversation turn to store.
        """
        item = {
            "PK": {"S": f"{PK_CONVERSATION}{turn.channel_id}"},
            "SK": {"S": f"{SK_TURN_PREFIX}{turn.timestamp}"},
            "channel_id": {"S": turn.channel_id},
            "thread_ts": {"S": turn.thread_ts},
            "timestamp": {"S": turn.timestamp},
            "role": {"S": turn.role},
            "content": {"S": turn.content},
        }
        if turn.user_id:
            item["user_id"] = {"S": turn.user_id}

        await self.client.put_item(table_name=self.table_name, item=item)
        logger.info(
            "Stored %s turn for channel %s thread %s",
            turn.role,
            turn.channel_id,
            turn.thread_ts,
        )

    async def get_history(
        self,
        channel_id: str,
        thread_ts: str,
        limit: int = 10,
    ) -> List[ConversationTurn]:
        """Get conversation history for a specific thread.

        Args:
            channel_id: The channel ID.
            thread_ts: The thread timestamp to filter by.
            limit: Maximum number of turns to return.

        Returns:
            List of ConversationTurn objects, ordered by timestamp ascending.
        """
        # Paginate to collect `limit` items after DynamoDB filter_expression.
        # DynamoDB's Limit applies BEFORE filter, so a single page may yield
        # fewer than `limit` matching items when multiple threads share the PK.
        turns = []
        exclusive_start_key = None
        page_size = limit * 5  # Read headroom to account for filtered-out items

        while len(turns) < limit:
            query_kwargs = {
                "table_name": self.table_name,
                "key_condition_expression": "PK = :pk AND begins_with(SK, :sk_prefix)",
                "expression_attribute_values": {
                    ":pk": {"S": f"{PK_CONVERSATION}{channel_id}"},
                    ":sk_prefix": {"S": SK_TURN_PREFIX},
                    ":thread_ts": {"S": thread_ts},
                },
                "filter_expression": "thread_ts = :thread_ts",
                "scan_index_forward": False,  # newest first
                "limit": page_size,
            }
            if exclusive_start_key:
                query_kwargs["exclusive_start_key"] = exclusive_start_key

            response = await self.client.query(**query_kwargs)

            for item in response.get("Items", []):
                normalized = self._normalize_item(item)
                turns.append(
                    ConversationTurn(
                        channel_id=normalized["channel_id"],
                        thread_ts=normalized["thread_ts"],
                        timestamp=str(normalized["timestamp"]),
                        role=normalized["role"],
                        content=normalized["content"],
                        user_id=normalized.get("user_id"),
                    )
                )
                if len(turns) >= limit:
                    break

            exclusive_start_key = response.get("LastEvaluatedKey")
            if not exclusive_start_key:
                break

        # We fetched newest-first; reverse for chronological order
        turns.reverse()
        return turns

    # ── Agent Thread Registry ───────────────────────────────────────

    async def register_thread(self, channel_id: str, thread_ts: str) -> None:
        """Register a new agent conversation thread.

        Args:
            channel_id: The channel ID.
            thread_ts: The Slack thread timestamp.
        """
        now = int(time.time())
        item = {
            "PK": {"S": f"{PK_THREAD}{channel_id}"},
            "SK": {"S": f"{SK_THREAD_PREFIX}{thread_ts}"},
            "channel_id": {"S": channel_id},
            "thread_ts": {"S": thread_ts},
            "created_at": {"N": str(now)},
            "last_active_at": {"N": str(now)},
            "status": {"S": "active"},
        }
        await self.client.put_item(table_name=self.table_name, item=item)
        logger.info("Registered agent thread %s in channel %s", thread_ts, channel_id)

    async def update_thread_activity(self, channel_id: str, thread_ts: str) -> None:
        """Update the last_active_at timestamp for a thread.

        Args:
            channel_id: The channel ID.
            thread_ts: The thread timestamp.
        """
        now = int(time.time())
        await self.client.update_item(
            table_name=self.table_name,
            key={
                "PK": {"S": f"{PK_THREAD}{channel_id}"},
                "SK": {"S": f"{SK_THREAD_PREFIX}{thread_ts}"},
            },
            update_expression="SET last_active_at = :now",
            expression_attribute_values={":now": {"N": str(now)}},
        )

    async def is_agent_thread(self, channel_id: str, thread_ts: str) -> bool:
        """Check if a thread_ts belongs to an agent conversation.

        Args:
            channel_id: The channel ID.
            thread_ts: The thread timestamp to check.

        Returns:
            True if this is an agent thread.
        """
        response = await self.client.get_item(
            table_name=self.table_name,
            key={
                "PK": {"S": f"{PK_THREAD}{channel_id}"},
                "SK": {"S": f"{SK_THREAD_PREFIX}{thread_ts}"},
            },
        )
        return "Item" in response

    async def get_agent_thread_ts_set(self, channel_id: str) -> Set[str]:
        """Get all agent thread timestamps for a channel.

        Used for cross-feature isolation: status-updater, /status, /report,
        /query, and JIRA reporter filter out messages in these threads.

        Args:
            channel_id: The channel ID.

        Returns:
            Set of thread_ts strings belonging to agent conversations.
        """
        thread_ts_set = set()
        exclusive_start_key = None

        while True:
            query_kwargs = {
                "table_name": self.table_name,
                "key_condition_expression": "PK = :pk AND begins_with(SK, :sk_prefix)",
                "expression_attribute_values": {
                    ":pk": {"S": f"{PK_THREAD}{channel_id}"},
                    ":sk_prefix": {"S": SK_THREAD_PREFIX},
                },
                "projection_expression": "thread_ts",
            }
            if exclusive_start_key:
                query_kwargs["exclusive_start_key"] = exclusive_start_key

            response = await self.client.query(**query_kwargs)

            for item in response.get("Items", []):
                normalized = self._normalize_item(item)
                thread_ts_set.add(str(normalized["thread_ts"]))

            exclusive_start_key = response.get("LastEvaluatedKey")
            if not exclusive_start_key:
                break

        logger.info(
            "Loaded %d agent thread timestamps for channel %s",
            len(thread_ts_set),
            channel_id,
        )
        return thread_ts_set

    # ── Message Watermark ───────────────────────────────────────────

    async def get_watermark(self, channel_id: str) -> Optional[MessageWatermark]:
        """Get the message ingestion watermark for a channel.

        Args:
            channel_id: The channel ID.

        Returns:
            MessageWatermark if exists, None otherwise.
        """
        response = await self.client.get_item(
            table_name=self.table_name,
            key={
                "PK": {"S": f"{PK_WATERMARK}{channel_id}"},
                "SK": {"S": SK_WATERMARK},
            },
        )

        if "Item" not in response:
            return None

        normalized = self._normalize_item(response["Item"])
        return MessageWatermark(
            channel_id=channel_id,
            latest_ingested_ts=str(normalized.get("latest_ingested_ts", "0")),
            backfill_complete=normalized.get("backfill_complete", False),
            backfill_started_at=normalized.get("backfill_started_at"),
            total_ingested=normalized.get("total_ingested", 0),
        )

    async def update_watermark(
        self,
        channel_id: str,
        latest_ts: str,
        total_ingested: int,
        backfill_complete: bool = False,
    ) -> None:
        """Update the message ingestion watermark.

        Args:
            channel_id: The channel ID.
            latest_ts: The latest ingested message timestamp.
            total_ingested: Total number of messages ingested.
            backfill_complete: Whether backfill has completed.
        """
        now = int(time.time())
        # Use update_item instead of put_item to preserve backfill_started_at
        await self.client.update_item(
            table_name=self.table_name,
            key={
                "PK": {"S": f"{PK_WATERMARK}{channel_id}"},
                "SK": {"S": SK_WATERMARK},
            },
            update_expression=(
                "SET latest_ingested_ts = :ts, backfill_complete = :bc, "
                "total_ingested = :ti, updated_at = :now, channel_id = :cid"
            ),
            expression_attribute_values={
                ":ts": {"S": latest_ts},
                ":bc": {"BOOL": backfill_complete},
                ":ti": {"N": str(total_ingested)},
                ":now": {"N": str(now)},
                ":cid": {"S": channel_id},
            },
        )
        logger.info(
            "Updated watermark for channel %s: ts=%s, total=%d, complete=%s",
            channel_id,
            latest_ts,
            total_ingested,
            backfill_complete,
        )

    async def increment_watermark(self, channel_id: str, latest_ts: str) -> None:
        """Atomically increment watermark counter and update latest_ts.

        Uses DynamoDB update_item (ADD + SET) instead of read-modify-write
        to avoid racing with concurrent backfill completion. The ADD operation
        is atomic server-side, and SET only touches latest_ts — never
        overwrites backfill_complete.

        Args:
            channel_id: The channel ID.
            latest_ts: The latest ingested message timestamp.
        """
        now = int(time.time())
        await self.client.update_item(
            table_name=self.table_name,
            key={
                "PK": {"S": f"{PK_WATERMARK}{channel_id}"},
                "SK": {"S": SK_WATERMARK},
            },
            update_expression=(
                "SET latest_ingested_ts = :ts, updated_at = :now, channel_id = :cid "
                "ADD total_ingested :inc"
            ),
            expression_attribute_values={
                ":ts": {"S": latest_ts},
                ":now": {"N": str(now)},
                ":cid": {"S": channel_id},
                ":inc": {"N": "1"},
            },
        )
        logger.info(
            "Incremented watermark for channel %s: latest_ts=%s",
            channel_id,
            latest_ts,
        )

    async def mark_backfill_started(self, channel_id: str) -> None:
        """Mark that backfill has started for a channel.

        Args:
            channel_id: The channel ID.
        """
        now = int(time.time())
        item = {
            "PK": {"S": f"{PK_WATERMARK}{channel_id}"},
            "SK": {"S": SK_WATERMARK},
            "channel_id": {"S": channel_id},
            "latest_ingested_ts": {"S": "0"},
            "backfill_complete": {"BOOL": False},
            "backfill_started_at": {"N": str(now)},
            "total_ingested": {"N": "0"},
        }
        # Use put_item with condition to avoid overwriting existing watermark
        try:
            await self.client.put_item(
                table_name=self.table_name,
                item=item,
                condition_expression="attribute_not_exists(PK)",
            )
            logger.info("Marked backfill started for channel %s", channel_id)
        except Exception as e:
            # Watermark already exists — backfill already in progress or complete
            if "ConditionalCheckFailedException" in str(e):
                logger.info("Watermark already exists for channel %s, skipping", channel_id)
            else:
                raise

    # ── Lifecycle ───────────────────────────────────────────────────

    async def wipe_channel_data(self, channel_id: str) -> None:
        """Delete all agent data for a channel (on channel_archive).

        Removes: conversation turns, thread registry, and watermark.

        Args:
            channel_id: The channel ID to wipe.
        """
        prefixes = [
            (f"{PK_CONVERSATION}{channel_id}", SK_TURN_PREFIX),
            (f"{PK_THREAD}{channel_id}", SK_THREAD_PREFIX),
            (f"{PK_WATERMARK}{channel_id}", None),
        ]

        total_deleted = 0
        for pk, sk_prefix in prefixes:
            if sk_prefix:
                # Query all items with this PK and SK prefix, paginating
                items = []
                exclusive_start_key = None
                while True:
                    query_kwargs = {
                        "table_name": self.table_name,
                        "key_condition_expression": "PK = :pk AND begins_with(SK, :sk)",
                        "expression_attribute_values": {
                            ":pk": {"S": pk},
                            ":sk": {"S": sk_prefix},
                        },
                    }
                    if exclusive_start_key:
                        query_kwargs["exclusive_start_key"] = exclusive_start_key
                    response = await self.client.query(**query_kwargs)
                    items.extend(response.get("Items", []))
                    exclusive_start_key = response.get("LastEvaluatedKey")
                    if not exclusive_start_key:
                        break
            else:
                # Single item (watermark)
                items = [{"PK": {"S": pk}, "SK": {"S": SK_WATERMARK}}]

            for item in items:
                await self.client.delete_item(
                    table_name=self.table_name,
                    key={"PK": item["PK"], "SK": item["SK"]},
                )
                total_deleted += 1

        logger.info(
            "Wiped %d agent records for channel %s",
            total_deleted,
            channel_id,
        )
