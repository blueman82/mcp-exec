"""Agent lifecycle handlers for channel events."""

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


async def handle_channel_archive_agent_cleanup(
    channel_id: str,
    conversation_store,
) -> None:
    """Clean up agent session data when a channel is archived.

    Wipes DynamoDB conversation state (thread registrations, watermarks).
    ChromaDB embeddings are intentionally preserved — the RCA Historian
    needs historical message embeddings from archived incident channels
    to find similar past incidents.

    Args:
        channel_id: The archived channel ID.
        conversation_store: ConversationStore instance.
    """
    try:
        await conversation_store.wipe_channel_data(channel_id)
        logger.info("Wiped agent conversation data for archived channel %s", channel_id)
    except Exception as e:
        logger.error(
            "Failed to wipe conversation data for channel %s: %s",
            channel_id,
            e,
            exc_info=True,
        )
