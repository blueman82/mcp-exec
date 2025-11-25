"""
channel_filter_operations.py

This module contains filter operations for channels in DynamoDB.
"""

from packages.core.logging import setup_logger
from packages.db.operations.base_operations import BaseOperations

logger = setup_logger(__name__)


class ChannelFilterOperations(BaseOperations):
    """Filter operations for channels in DynamoDB."""

    async def cleanup(self) -> None:
        """
        Clean up any resources used by this operations instance.

        This includes releasing any connections, caches, or other resources
        held by this instance.
        """
        logger.info("Cleaning up ChannelFilterOperations resources")
        await super().cleanup()
