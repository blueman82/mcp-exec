"""JIRA backfill ingestor — fetches and indexes JIRA ticket data for a channel.

On bot join, fetches the JIRA ticket associated with the channel (from DynamoDB
metadata or message text), then embeds the ticket summary, description, and
comments as ChromaDB documents with source="jira" metadata.

This is a one-shot operation per channel (no pagination needed — JIRA tickets
are small). Deterministic doc IDs make re-runs idempotent.
"""

import time
from typing import Any, Dict, List, Optional

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class JiraBackfillIngestor:
    """Backfills JIRA ticket context into the vector store for a channel.

    Fetches ticket data via JIRADataExtractor, formats it into embeddable
    documents, and stores them in ChromaDB. Idempotent — deterministic doc IDs
    mean duplicate runs just overwrite with the same data.
    """

    def __init__(
        self,
        embeddings_client,
        vector_store,
        jira_data_extractor,
    ):
        """
        Args:
            embeddings_client: AzureEmbeddingsClient for computing embeddings.
            vector_store: ChromaVectorStore for storing documents.
            jira_data_extractor: JIRADataExtractor for fetching ticket data.
        """
        self._embeddings_client = embeddings_client
        self._vector_store = vector_store
        self._jira_extractor = jira_data_extractor

    async def backfill_jira(self, channel_id: str) -> int:
        """Fetch and index JIRA ticket data for a channel.

        Args:
            channel_id: The Slack channel to backfill JIRA data for.

        Returns:
            Number of documents stored.
        """
        try:
            # get_jira_context checks channel metadata first, then message text
            # We pass empty message_texts since we want metadata-based lookup;
            # message-based extraction will happen if metadata has no ticket
            context = await self._jira_extractor.get_jira_context(channel_id, [])

            if not context:
                logger.info("No JIRA ticket found for channel %s", channel_id)
                return 0

            ticket_id = context["ticket_id"]
            ticket_data = context["data"]

            logger.info(
                "JIRA backfill for %s: ticket %s (source: %s)",
                channel_id,
                ticket_id,
                context.get("source", "unknown"),
            )

            documents = self._format_ticket_documents(ticket_id, ticket_data, channel_id)
            if not documents:
                logger.info("No embeddable content from JIRA ticket %s", ticket_id)
                return 0

            # Embed and store
            texts = [d["text"] for d in documents]
            embeddings = await self._embeddings_client.embed_texts(texts)

            store_docs = []
            for doc, embedding in zip(documents, embeddings):
                store_docs.append(
                    {
                        "id": doc["id"],
                        "text": doc["text"],
                        "metadata": doc["metadata"],
                    }
                )

            await self._vector_store.add_documents(store_docs, embeddings)

            logger.info(
                "JIRA backfill complete for %s: %d documents from ticket %s",
                channel_id,
                len(store_docs),
                ticket_id,
            )
            return len(store_docs)

        except Exception as e:
            logger.error(
                "JIRA backfill failed for channel %s: %s",
                channel_id,
                e,
                exc_info=True,
            )
            return 0

    def _format_ticket_documents(
        self,
        ticket_id: str,
        ticket_data: Dict[str, Any],
        channel_id: str,
    ) -> List[Dict[str, Any]]:
        """Format JIRA ticket data into embeddable documents.

        Creates one document for the ticket itself (summary + description +
        status fields) and one document per human comment.

        Args:
            ticket_id: JIRA ticket key (e.g. "CAMP-12345").
            ticket_data: Full ticket dict from JIRADataExtractor.
            channel_id: The Slack channel ID.

        Returns:
            List of document dicts with id, text, and metadata.
        """
        documents = []
        now = int(time.time())
        fields = ticket_data.get("fields", ticket_data)

        # -- Ticket summary document --
        summary = fields.get("summary", "")
        description = fields.get("description", "")
        status = _nested_get(fields, "status", "name") or "Unknown"
        priority = _nested_get(fields, "priority", "name") or "Unknown"
        assignee = _nested_get(fields, "assignee", "displayName") or "Unassigned"

        ticket_text = (
            f"[JIRA:{ticket_id}] Status: {status} | "
            f"Priority: {priority} | Assignee: {assignee}\n"
            f"Summary: {summary}"
        )
        if description:
            # Truncate very long descriptions to avoid embedding noise
            desc = description[:2000] if len(description) > 2000 else description
            ticket_text += f"\nDescription: {desc}"

        if ticket_text.strip():
            documents.append(
                {
                    "id": f"{channel_id}:jira:{ticket_id}",
                    "text": ticket_text,
                    "metadata": {
                        "channel_id": channel_id,
                        "message_ts": 0.0,
                        "user_id": "jira",
                        "has_thread_replies": False,
                        "ingested_at": now,
                        "source": "jira",
                        "jira_ticket_id": ticket_id,
                        "jira_doc_type": "ticket",
                    },
                }
            )

        # -- Comment documents --
        comments = ticket_data.get("comments", [])
        for comment in comments:
            comment_id = comment.get("id", "unknown")
            author = comment.get("author", "Unknown")
            body = comment.get("body", "").strip()
            created = comment.get("created", "")

            if not body:
                continue

            # Truncate very long comments
            if len(body) > 2000:
                body = body[:2000]

            comment_text = f"[JIRA:{ticket_id}:comment] {author} ({created}): {body}"

            documents.append(
                {
                    "id": f"{channel_id}:jira:{ticket_id}:c:{comment_id}",
                    "text": comment_text,
                    "metadata": {
                        "channel_id": channel_id,
                        "message_ts": 0.0,
                        "user_id": "jira",
                        "has_thread_replies": False,
                        "ingested_at": now,
                        "source": "jira",
                        "jira_ticket_id": ticket_id,
                        "jira_doc_type": "comment",
                    },
                }
            )

        return documents


def _nested_get(data: dict, key1: str, key2: str) -> Optional[str]:
    """Safely get a nested dict value like data[key1][key2]."""
    inner = data.get(key1)
    if isinstance(inner, dict):
        return inner.get(key2)
    return None
