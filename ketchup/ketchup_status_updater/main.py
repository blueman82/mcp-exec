#!/usr/bin/env python3
"""
Auto-status updater service that runs as a scheduled job.
"""
import asyncio
import os
import sys
from datetime import datetime
import time

from packages.core.logging import setup_logger
from packages.core.typed_di_integration import get_unified_container
from packages.core.config.feature_flags import FeatureFlags
from packages.core.distributed_lock import DistributedLock
from packages.core.typed_di.exceptions import MissingDependencyError
from ketchup_status_updater.processor import AutoStatusProcessor

# TypedDI Protocol imports
from packages.core.typed_di.service_registrations.protocols.core_protocols import (
    DynamoDBStoreProtocol,
    SecretsManagerProtocol,
    SlackConfigProtocol,
    SlackPostingHandlerProtocol,
)
from packages.core.typed_di.service_registrations.protocols.handler_protocols import (
    OpenAIHandlerProtocol,
)
from packages.core.typed_di.service_registrations.protocols.slack_protocols import (
    ChannelInfoOpsProtocol,
    SlackChannelMessageOpsProtocol,
    ChannelOperationsProtocol,
    ChannelMembershipOpsProtocol,
)
from packages.core.typed_di.service_registrations.protocols.mcp_protocols import (
    MCPClientProtocol,
)
from packages.core.typed_di.service_registrations.protocols.command_protocols import (
    FeatureServiceProtocol,
)

logger = setup_logger(__name__)

async def run_auto_status():
    """Run the auto-status update process with distributed locking."""
    try:
        logger.info(f"Starting auto-status update at {datetime.now()}")

        # Initialize DI container first (needed for distributed lock)
        logger.info("Initializing DI container...")
        container = await get_unified_container()

        # Get DynamoDB store using TypedDI
        db_store = await container.aget(DynamoDBStoreProtocol)
        distributed_lock = DistributedLock(db_store.client, db_store.table_name)

        # Use distributed lock instead of local file lock
        async with distributed_lock.acquire_lock("AUTO_STATUS_GLOBAL", timeout_seconds=120) as lock_acquired:
            if not lock_acquired:
                logger.warning("Another server is running auto-status, exiting")
                return

            logger.info("Distributed lock acquired, proceeding with status update")

            # Get required services using TypedDI
            mcp_client = await container.aget(MCPClientProtocol)
            secrets_manager = await container.aget(SecretsManagerProtocol)
            slack_config = await container.aget(SlackConfigProtocol)
            openai_handler = await container.aget(OpenAIHandlerProtocol)
            channel_info_ops = await container.aget(ChannelInfoOpsProtocol)
            channel_msg_ops = await container.aget(SlackChannelMessageOpsProtocol)
            posting_handler = await container.aget(SlackPostingHandlerProtocol)
            channel_operations = await container.aget(ChannelOperationsProtocol)
            channel_membership_ops = await container.aget(ChannelMembershipOpsProtocol)

            # Handle optional feature_service with error handling
            feature_service = None
            if FeatureFlags.is_status_updater_enabled():
                try:
                    feature_service = await container.aget(FeatureServiceProtocol)
                except MissingDependencyError:
                    logger.info("Feature service not available - using default settings")
                except Exception as e:
                    logger.warning(f"Could not get feature_service: {e}")

            processor = AutoStatusProcessor(
                db_store=db_store,
                mcp_client=mcp_client,
                secrets_manager=secrets_manager,
                slack_config=slack_config,
                openai_handler=openai_handler,
                channel_info_ops=channel_info_ops,
                channel_msg_ops=channel_msg_ops,
                posting_handler=posting_handler,
                channel_operations=channel_operations,
                channel_membership_ops=channel_membership_ops,
                feature_service=feature_service
            )

            # Process all eligible channels
            results = await processor.process_all_channels()

            logger.info(f"Auto-status update completed: {results}")

    except Exception as e:
        logger.error(f"Auto-status update failed: {e}", exc_info=True)
        raise

def main():
    """Main entry point"""
    try:
        asyncio.run(run_auto_status())
    except Exception as e:
        logger.error(f"Fatal error in auto-status updater: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
