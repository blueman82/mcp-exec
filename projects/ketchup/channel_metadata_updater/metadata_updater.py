"""
metadata_updater.py

This module contains the ChannelMetadataUpdater service that orchestrates
metadata extraction and updating using component-based architecture.
"""

from typing import Any, Dict, List, Optional

from channel_metadata_updater.channel_processor import ChannelProcessor
from channel_metadata_updater.metadata_extractor import MetadataExtractor
from channel_metadata_updater.metadata_storage import MetadataStorage
from packages.ai.core.openai_handler import OpenAIHandler
from packages.ai.cost_calculator import TokenTracker, get_token_tracker
from packages.core.logging import setup_logger
from packages.db.config.dynamodb_config import DynamoDBConfig
from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient
from packages.db.dynamodb_store import DynamoDBStore
from packages.db.operations.channel_operations import ChannelOperations

# from packages.core.async_client import AsyncClient
from packages.secrets.manager import SecretsManager  # Corrected path
from packages.slack.channel_operations.channel_archive_ops import SlackChannelArchiveOps
from packages.slack.channel_operations.channel_info_ops import ChannelInfoOps  # Added
from packages.slack.channel_operations.channel_membership_ops import (  # Added
    ChannelMembershipOps,
)

# from packages.slack.channel_operations import SlackChannelLookupOps # Removed
# from packages.slack.channel_operations import SlackChannelMessageOps # Incorrect path
from packages.slack.channel_operations.channel_msg_ops import (  # Corrected path
    SlackChannelMessageOps,
)
from packages.slack.config.slack_config import SlackConfig
from packages.slack.messages.posting import SlackPostingHandler


class ChannelMetadataUpdater:
    """Service to orchestrate channel metadata extraction and updates."""

    def __init__(
        self,
        secrets_manager: SecretsManager,
        slack_config: SlackConfig,
        channel_info_ops: Optional[ChannelInfoOps] = None,
        channel_membership_ops: Optional[ChannelMembershipOps] = None,
        channel_msg_ops: Optional[SlackChannelMessageOps] = None,
        dynamodb_store: Optional[DynamoDBStore] = None,
        channel_operations: Optional[ChannelOperations] = None,
        ai_handler: Optional[OpenAIHandler] = None,
        token_tracker: Optional[TokenTracker] = None,
        max_concurrency: int = 10,
        slack_posting_handler: Optional["SlackPostingHandler"] = None,
        restore_state_manager: Optional[Any] = None,
    ):
        """Initialize with dependencies and concurrency controls.

        Args:
            secrets_manager: Pre-initialized SecretsManager instance (required)
            slack_config: Pre-initialized SlackConfig instance (required)
            channel_info_ops: Slack channel info operations client
            channel_membership_ops: Slack channel membership operations client
            channel_msg_ops: Slack message operations client
            dynamodb_store: DynamoDB operations client
            channel_operations: Channel operations client for timestamp tracking
            ai_handler: AI model client
            token_tracker: Token tracking for AI cost calculation
            max_concurrency: Maximum concurrent channel processing
            slack_posting_handler: Pre-initialized SlackPostingHandler instance (required for DI)
            restore_state_manager: Pre-initialized RestoreStateManager instance (required for DI)
        """
        self.secrets_manager = secrets_manager
        self.slack_config = slack_config

        # Store injected Ops instances - cannot create defaults easily here
        self.channel_info_ops = channel_info_ops
        self.channel_membership_ops = channel_membership_ops

        # Initialize ChannelMessageOps, passing required dependencies
        if channel_msg_ops is not None:
            self.channel_msg_ops = channel_msg_ops
        else:
            raise NotImplementedError("A pre-initialized SlackChannelMessageOps must be provided.")

        if dynamodb_store is not None:
            self.dynamodb_store = dynamodb_store
        else:
            config = DynamoDBConfig()
            client = DynamoDBAsyncClient(config=config)
            self.dynamodb_store = DynamoDBStore(client=client, table_name=config.get_table_name())

        # Initialize ChannelOperations for timestamp tracking
        if channel_operations is not None:
            self.channel_operations = channel_operations
        else:
            # Use existing ChannelOperations from DynamoDBStore
            self.channel_operations = self.dynamodb_store.channel_ops

        self.token_tracker = token_tracker or get_token_tracker()

        # Store ai_handler if provided, otherwise mark for initialization
        self._ai_handler_instance = ai_handler
        self._needs_ai_handler_init = ai_handler is None

        # Store posting handler and restore state manager for DI
        self.slack_posting_handler = slack_posting_handler
        self.restore_state_manager = restore_state_manager

        # Placeholder for MetadataExtractor, initialized in async initialize method
        self.metadata_extractor: Optional[MetadataExtractor] = None

        # Initialize other components (these don't need the AI handler directly)
        self.channel_processor = ChannelProcessor(
            channel_msg_ops=self.channel_msg_ops,
            dynamodb_store=self.dynamodb_store,
            max_concurrency=max_concurrency,
        )
        self.metadata_storage = MetadataStorage(dynamodb_store=self.dynamodb_store)
        self.logger = setup_logger(__name__)

    async def initialize(self) -> "ChannelMetadataUpdater":
        """Asynchronously initializes components that require async setup, like AI Handler."""
        if self._needs_ai_handler_init:
            self.logger.info("Initializing internally created OpenAIHandler.")
            # Ensure required Ops were injected if we need to create AI Handler internally
            if not self.channel_info_ops:
                raise ValueError("ChannelInfoOps must be provided if AI Handler is not injected.")
            if not self.channel_membership_ops:
                raise ValueError(
                    "ChannelMembershipOps must be provided if AI Handler is not injected."
                )
            if not self.channel_msg_ops:
                # This should have been created in __init__, but check anyway
                raise ValueError(
                    "ChannelMessageOps must be available if AI Handler is not injected."
                )
            if not self.slack_posting_handler:
                raise ValueError("SlackPostingHandler must be provided for DI.")
            if not self.restore_state_manager:
                raise ValueError("RestoreStateManager must be provided for DI.")

            # Initialize ArchiveOps dependency needed by OpenAIHandler
            archive_ops_dep = SlackChannelArchiveOps(
                posting_handler=self.slack_posting_handler,
                secrets_manager=self.secrets_manager,
                dynamodb_store=self.dynamodb_store,
                state_manager=self.restore_state_manager,
                slack_config=self.slack_config,
            )

            # Create the new handler with injected dependencies
            self._ai_handler_instance = OpenAIHandler(
                token_tracker=self.token_tracker,
                secrets_manager=self.secrets_manager,
                channel_info_ops=self.channel_info_ops,  # Pass stored instance
                channel_msg_ops=self.channel_msg_ops,
                channel_ops=archive_ops_dep,  # Pass initialized instance
            )
            await self._ai_handler_instance.initialize()
        elif self._ai_handler_instance:  # Handler was injected
            self.logger.info("Using pre-injected OpenAIHandler.")
            # Optional: Add a check here to ensure the injected handler is initialized if desired
            # if not self._ai_handler_instance.is_initialized(): # Assuming an is_initialized method exists
            #    raise ValueError("Injected OpenAIHandler must be initialized.")
            pass
        else:
            # This case should ideally not happen if __init__ logic is correct
            raise RuntimeError("AI Handler state is inconsistent after init.")

        # Now initialize MetadataExtractor with the ready AI handler
        self.metadata_extractor = MetadataExtractor(ai_handler=self._ai_handler_instance)
        self.logger.info("ChannelMetadataUpdater initialized successfully.")
        return self

    async def scan_for_incomplete_metadata(self) -> List[str]:
        """
        Scan for channels with missing or incomplete metadata.

        Returns:
            List of channel IDs with incomplete metadata
        """
        return await self.metadata_storage.scan_for_incomplete_metadata()

    async def process_channels_batch(self, channel_ids: List[str]) -> Dict[str, int]:
        """
        Process multiple channels concurrently.

        Args:
            channel_ids: List of channel IDs to process

        Returns:
            Statistics of processing results
        """
        # NOTE: No finally/cleanup block here. In the unified scheduler context,
        # all dependencies are shared DI singletons that should NOT be cleaned up
        # by individual tasks. Cleanup is managed by the DI container lifecycle.
        return await self.channel_processor.process_channels_batch(
            channel_ids, self.extract_and_store_metadata
        )

    async def extract_and_store_metadata(self, channel_id: str) -> bool:
        """
        Extract metadata for a channel and store it in DynamoDB.

        Args:
            channel_id: The Slack channel ID to process

        Returns:
            bool: True if metadata was successfully extracted and stored
        """
        self.logger.info("Starting metadata extraction for channel %s", channel_id)
        try:
            # Check if channel needs metadata update
            if not await self.metadata_storage.needs_metadata_update(channel_id):
                self.logger.info("Channel %s already has complete metadata", channel_id)
                return True

            # Fetch channel messages
            messages = await self.channel_processor.fetch_channel_messages(channel_id)

            if not messages:
                self.logger.warning("No messages found for channel %s", channel_id)
                return False

            # Extract metadata using AI
            if self.metadata_extractor is None:
                raise RuntimeError(
                    "MetadataExtractor is not initialized. Call initialize() before extracting metadata."
                )
            metadata = await self.metadata_extractor.extract_metadata_with_ai(channel_id, messages)

            # Store extracted metadata
            return await self.metadata_storage.store_extracted_metadata(channel_id, metadata)
        except Exception as e:
            # Robust check for channel_not_found error
            error_str = str(e).lower()
            error_data = getattr(e, "response_data", {})
            if "channel_not_found" in error_str or (
                isinstance(error_data, dict) and error_data.get("error") == "channel_not_found"
            ):
                self.logger.warning("Channel %s not found. Deleting from DB.", channel_id)
                # Use DI'd DynamoDBStore for deletion
                if self.dynamodb_store:
                    await self.dynamodb_store.delete_channel_if_exists(channel_id)
                else:
                    await self.metadata_storage.dynamodb_store.delete_channel_if_exists(channel_id)
                return True
            self.logger.error(
                "Error extracting metadata for channel %s: %s",
                channel_id,
                str(e),
                exc_info=True,
            )
            return False

    async def cleanup_clients(self) -> None:
        """Clean up client connections.

        NOTE: In the unified scheduler context, ALL dependencies are shared
        DI singletons that MUST NOT be cleaned up by individual tasks.
        Cleaning up shared singletons causes "Session is closed" errors
        for other tasks running concurrently.

        This method is intentionally a no-op. Cleanup is managed by the
        DI container lifecycle, not by individual service consumers.

        Historical context: This method previously closed aiohttp sessions
        using gc.get_objects(), which broke the shared DynamoDB session
        and caused status_updater to fail with "Session is closed" errors.
        """
        # Do NOT clean up any injected dependencies - they are shared singletons.
        # Do NOT use gc.get_objects() to close sessions - that closes shared sessions.
        pass
