"""Agent lifecycle handlers for channel events."""

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


async def handle_channel_archive_agent_cleanup(
    channel_id: str,
    conversation_store,
    vector_store,
) -> None:
    """Clean up all agent data when a channel is archived.

    Called from the channel_archive event handler after the standard
    archive processing.

    Args:
        channel_id: The archived channel ID.
        conversation_store: ConversationStore instance.
        vector_store: ChromaVectorStore instance.
    """
    try:
        # Wipe DynamoDB conversation data
        await conversation_store.wipe_channel_data(channel_id)
        logger.info("Wiped agent conversation data for archived channel %s", channel_id)
    except Exception as e:
        logger.error(
            "Failed to wipe conversation data for channel %s: %s",
            channel_id,
            e,
            exc_info=True,
        )

    try:
        # Delete ChromaDB embeddings
        await vector_store.delete_by_channel(channel_id)
        logger.info("Deleted agent embeddings for archived channel %s", channel_id)
    except Exception as e:
        logger.error(
            "Failed to delete embeddings for channel %s: %s",
            channel_id,
            e,
            exc_info=True,
        )
