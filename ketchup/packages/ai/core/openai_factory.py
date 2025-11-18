"""
OpenAI Handler Factory

This module provides factory functions for creating instances of the OpenAIHandler
with proper dependency injection.
"""

from packages.ai.core.openai_handler import OpenAIHandler
from packages.ai.cost_calculator import get_token_tracker
from packages.core.logging import setup_logger
from packages.secrets.manager import SecretsManager
from packages.slack.channel_operations.channel_archive_ops import SlackChannelArchiveOps
from packages.slack.channel_operations.channel_info_ops import ChannelInfoOps
from packages.slack.channel_operations.channel_membership_ops import (
    ChannelMembershipOps,
)
from packages.slack.channel_operations.channel_msg_ops import SlackChannelMessageOps

logger = setup_logger(__name__)


async def create_openai_handler(
    channel_info_ops: ChannelInfoOps,
    channel_membership_ops: ChannelMembershipOps,
    channel_msg_ops: SlackChannelMessageOps,
    channel_ops: SlackChannelArchiveOps,
    jira_extractor=None,  # Optional JIRA data extractor
) -> OpenAIHandler:
    """
    Factory function to create and initialize an OpenAIHandler with all required dependencies.

    This simplifies the migration from the legacy handler by handling dependency injection.

    Args:
        channel_info_ops: Instance of ChannelInfoOps
        channel_membership_ops: Instance of ChannelMembershipOps
        channel_msg_ops: Instance of SlackChannelMessageOps
        channel_ops: Instance of SlackChannelArchiveOps

    Returns:
        Initialized OpenAIHandler instance
    """
    logger.info("Creating OpenAIHandler with dependencies")

    # Get other dependencies
    token_tracker = get_token_tracker()
    secrets_manager = SecretsManager()

    # Create handler with dependencies
    handler = OpenAIHandler(
        token_tracker=token_tracker,
        secrets_manager=secrets_manager,
        channel_info_ops=channel_info_ops,
        channel_msg_ops=channel_msg_ops,
        channel_ops=channel_ops,
        jira_extractor=jira_extractor,
    )

    # Initialize the handler
    await handler.initialize()
    logger.info("OpenAIHandler initialized successfully")

    return handler
