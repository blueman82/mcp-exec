"""DynamoDB session manager for Slack bot conversations.

Implements async CRUD operations with automatic TTL management.
Privacy-first design: immediate deletion verification after query generation.
"""

from datetime import datetime, timedelta
from typing import Any

import structlog

logger = structlog.get_logger()


class SessionManager:
    """Manages conversation sessions in DynamoDB.

    Handles session lifecycle: creation, updates, retrieval, and deletion.
    Implements 30-minute TTL with automatic reset on updates.
    Verifies deletion for privacy compliance.

    Must be used as async context manager:
        async with SessionManager() as manager:
            await manager.create_session(...)

    Attributes:
        table_name: DynamoDB table name (default: splunk-bot-sessions)
        region: AWS region (default: eu-west-1)
        _table: Optional pre-configured table for testing
        _resource_context: aioboto3 resource context manager
    """

    def __init__(
        self, table=None, table_name: str = "splunk-bot-sessions", region: str = "eu-west-1"
    ):
        """Initialize session manager with DynamoDB table.

        Args:
            table: Optional aioboto3 table for testing (bypasses AWS connection)
            table_name: DynamoDB table name
            region: AWS region
        """
        self.table_name = table_name
        self.region = region
        self._table: Any | None = table
        self._resource_context: Any | None = None

    async def __aenter__(self):
        """Async context manager entry.

        Initializes DynamoDB connection if not provided in __init__.
        Keeps connection open for the lifetime of the context.

        Returns:
            Self for use in async with statement

        Example:
            async with SessionManager() as manager:
                session = await manager.create_session(...)
        """
        if not self._table:
            import aioboto3

            session = aioboto3.Session()
            self._resource_context = session.resource("dynamodb", region_name=self.region)
            resource = await self._resource_context.__aenter__()
            self._table = await resource.Table(self.table_name)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit.

        Closes DynamoDB connection if it was opened by this instance.

        Args:
            exc_type: Exception type if raised
            exc_val: Exception value if raised
            exc_tb: Exception traceback if raised
        """
        if self._resource_context:
            await self._resource_context.__aexit__(exc_type, exc_val, exc_tb)
            self._table = None
            self._resource_context = None

    async def _get_table(self):
        """Get DynamoDB table resource.

        Returns:
            aioboto3 DynamoDB table resource

        Raises:
            RuntimeError: If called outside async context manager

        Note:
            Must be used within async context manager to ensure connection is open.
        """
        if not self._table:
            raise RuntimeError(
                "SessionManager must be used as async context manager. "
                "Use: async with SessionManager() as manager: ..."
            )
        return self._table

    def _calculate_ttl(self) -> int:
        """Calculate TTL timestamp 30 minutes from now.

        Returns:
            Unix epoch timestamp (seconds since 1970-01-01)

        Note:
            DynamoDB TTL attribute must be Number type in epoch seconds.
            Active conversations reset TTL on every update.
        """
        return int((datetime.now() + timedelta(minutes=30)).timestamp())

    async def create_session(
        self, thread_id: str, user_id: str, channel_id: str, question: str
    ) -> dict[str, Any]:
        """Create new session with initial state.

        Args:
            thread_id: Slack thread timestamp (unique identifier)
            user_id: Slack user ID
            channel_id: Slack channel ID
            question: User's initial question (stored temporarily for query generation)

        Returns:
            Created session dict with keys:
                - thread_id: Session identifier
                - user_id: Slack user ID
                - channel_id: Slack channel ID
                - agent_state: Initial state (INITIALIZE)
                - original_question: User's question for query generation
                - created_at: ISO timestamp
                - ttl: Unix epoch timestamp (30 min from now)

        Note:
            Question stored temporarily in session for agent processing.
            Session is deleted immediately upon COMPLETE state (privacy).
        """
        table = await self._get_table()

        session: dict[str, Any] = {
            "thread_id": thread_id,
            "user_id": user_id,
            "channel_id": channel_id,
            "agent_state": "INITIALIZE",
            "original_question": question,
            "created_at": datetime.now().isoformat(),
            "ttl": self._calculate_ttl(),
        }

        await table.put_item(Item=session)
        logger.info("session_created", thread_id=thread_id)
        return session

    async def update_session(self, thread_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Update session and reset TTL.

        Args:
            thread_id: Session identifier
            updates: Dict of fields to update (e.g., {"agent_state": "EVALUATE"})

        Returns:
            Updated session dict

        Note:
            Always resets TTL to 30 minutes from now.
            Prevents active conversations from expiring.
            Adds updated_at timestamp automatically.
        """
        table = await self._get_table()

        # Always reset TTL on update (keep active conversations alive)
        updates["ttl"] = self._calculate_ttl()
        updates["updated_at"] = datetime.now().isoformat()

        # Build DynamoDB UpdateExpression with attribute name aliases
        # (ttl is a reserved keyword in DynamoDB)
        expr_names = {f"#{k}": k for k in updates}
        update_expr = "SET " + ", ".join([f"#{k} = :{k}" for k in updates])
        expr_values = {f":{k}": v for k, v in updates.items()}

        await table.update_item(
            Key={"thread_id": thread_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
        )

        logger.info("session_updated", thread_id=thread_id)
        return await self.get_session(thread_id)  # type: ignore[return-value]

    async def get_session(self, thread_id: str) -> dict[str, Any] | None:
        """Retrieve session by thread_id.

        Args:
            thread_id: Session identifier

        Returns:
            Session dict if exists, None otherwise

        Note:
            Does not log anything for privacy.
            Caller responsible for logging metadata only.
        """
        table = await self._get_table()
        response = await table.get_item(Key={"thread_id": thread_id})
        # boto3 types response.get("Item") as Any, so we use type: ignore
        return response.get("Item")  # type: ignore[no-any-return]

    async def delete_session(self, thread_id: str):
        """Delete session with verification (privacy requirement).

        Args:
            thread_id: Session identifier

        Raises:
            SessionDeletionError: If deletion fails after retry (privacy violation)

        Note:
            Critical privacy requirement: Immediately delete after COMPLETE state.
            Does NOT rely on DynamoDB TTL (TTL is backup only).
            Verifies deletion succeeded and retries if needed.
        """
        from asksplunk.session import SessionDeletionError

        table = await self._get_table()

        # Delete session
        await table.delete_item(Key={"thread_id": thread_id})

        # Defensive: Verify deletion succeeded
        response = await table.get_item(Key={"thread_id": thread_id})
        if "Item" in response:
            logger.warning(
                "deletion_verification_failed",
                thread_id=thread_id,
                action="retrying",
            )
            # Retry once
            await table.delete_item(Key={"thread_id": thread_id})

            # Verify retry succeeded
            response = await table.get_item(Key={"thread_id": thread_id})
            if "Item" in response:
                # Critical privacy violation - deletion failed after retry
                logger.error(
                    "deletion_failed_after_retry", thread_id=thread_id, severity="critical"
                )
                raise SessionDeletionError(
                    f"Failed to delete session {thread_id} after retry - privacy violation"
                )

        logger.info("session_deleted", thread_id=thread_id)
