"""
processor.py

This module contains the metadata processing handler for the channel metadata updater.
"""

import asyncio
import gc
import json
from typing import Any, Dict, Optional

import aiohttp

from ketchup_unified_scheduler.services.metadata.updater import ChannelMetadataUpdater
from packages.core.logging import setup_logger
from packages.core.typed_di.registry import TypedServiceRegistry
from packages.core.typed_di.service_registrations.protocols.core_protocols import (
    DynamoDBStoreProtocol,
    SecretsManagerProtocol,
    SlackConfigProtocol,
    SlackPostingHandlerProtocol,
)
from packages.core.typed_di.service_registrations.protocols.handler_protocols import (
    OpenAIHandlerProtocol,
)
from packages.core.typed_di.service_registrations.protocols.infrastructure_protocols import (
    TokenTrackerProtocol,
)
from packages.core.typed_di.service_registrations.protocols.operation_protocols import (
    RestoreStateManagerProtocol,
)
from packages.core.typed_di.service_registrations.protocols.slack_protocols import (
    ChannelInfoOpsProtocol,
    ChannelMembershipOpsProtocol,
    SlackChannelMessageOpsProtocol,
)
from packages.core.typed_di_integration import get_unified_container

logger = setup_logger(__name__)


async def cleanup_sessions():
    """
    Close all unclosed aiohttp client sessions before Lambda exits.
    """
    sessions = [obj for obj in gc.get_objects() if isinstance(obj, aiohttp.ClientSession)]

    logger.info("Found %d aiohttp sessions to clean up", len(sessions))

    for session in sessions:
        try:
            if not session.closed:
                logger.info("Closing unclosed aiohttp ClientSession")
                await session.close()
        except Exception as e:
            logger.error("Error closing session: %s", str(e))

    await asyncio.sleep(0.5)


async def create_channel_metadata_updater(container) -> ChannelMetadataUpdater:
    """Construct a ChannelMetadataUpdater using TypedDI container.

    Args:
        container: TypedDI container for service resolution

    Returns:
        Initialized ChannelMetadataUpdater instance
    """
    logger.info("Creating ChannelMetadataUpdater with dependencies from TypedDI.")

    # Dependency Retrieval using TypedDI
    dependencies = {
        "secrets_manager": await container.aget(SecretsManagerProtocol),
        "slack_config": await container.aget(SlackConfigProtocol),
        "channel_info_ops": await container.aget(ChannelInfoOpsProtocol),
        "channel_membership_ops": await container.aget(ChannelMembershipOpsProtocol),
        "channel_msg_ops": await container.aget(SlackChannelMessageOpsProtocol),
        "dynamodb_store": await container.aget(DynamoDBStoreProtocol),
        "ai_handler": await container.aget(OpenAIHandlerProtocol),
        "token_tracker": await container.aget(TokenTrackerProtocol),
        "slack_posting_handler": await container.aget(SlackPostingHandlerProtocol),
        "restore_state_manager": await container.aget(RestoreStateManagerProtocol),
    }

    for name, dep in dependencies.items():
        if dep is None:
            logger.error(
                "Dependency '%s' could not be retrieved from TypedDI. Ensure service is registered.",
                name,
            )
            raise RuntimeError(f"Missing critical dependency: {name}")

    logger.info("All dependencies for ChannelMetadataUpdater retrieved successfully.")
    return ChannelMetadataUpdater(**dependencies)


async def process_channels(
    container: Optional[TypedServiceRegistry] = None,
) -> Dict[str, Any]:
    """Process channels with missing metadata asynchronously.

    Args:
        container: Optional pre-initialized TypedDI container. If None, creates one.

    Returns:
        Dict with status information
    """
    logger.info("Starting metadata update process")

    try:
        if container is None:
            logger.info("Initializing TypedDI container...")
            container = await get_unified_container()
            logger.info("TypedDI container initialized successfully.")
        else:
            logger.info("Using pre-initialized TypedDI container.")
    except Exception as e:
        logger.error(
            "Fatal error during container initialization: %s",
            str(e),
            exc_info=True,
        )
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Container initialization failed: {str(e)}"}),
        }

    updater = None
    try:
        updater = await create_channel_metadata_updater(container)
        await updater.initialize()
        logger.info("Metadata updater initialized successfully")

        channels = await updater.scan_for_incomplete_metadata()

        if not channels:
            logger.info("No channels found with missing metadata")
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "No channels found with missing metadata"}),
            }

        logger.info("Found %d channel(s) with missing metadata", len(channels))

        # Process channels in batch for better concurrency
        stats = await updater.process_channels_batch(channels)

        logger.info(
            "Processing complete. Successfully updated %d/%d channels",
            stats.get("success", 0),
            stats.get("total", 0),
        )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "processed": stats.get("total", 0),
                    "successful": stats.get("success", 0),
                    "skipped": stats.get("skipped", 0),
                    "failed": stats.get("failure", 0),
                }
            ),
        }

    except RuntimeError as e:
        logger.error("Runtime error in metadata update process: %s", str(e))
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
    except Exception as e:
        logger.error("Unexpected error in metadata update process: %s", str(e))
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
    # NOTE: No finally/cleanup block here for unified scheduler context.
    # All dependencies are shared DI singletons that MUST NOT be cleaned up
    # by individual tasks. Cleanup is managed by the DI container lifecycle.
    # See cleanup_clients() docstring for historical context.


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda function handler.

    Args:
        event: The Lambda event data
        context: The Lambda context object

    Returns:
        Dict with status information
    """
    try:
        result = {}  # Initialize result
        try:
            logger.info("Lambda invoked with event: %s", json.dumps(event))
            result = asyncio.run(process_channels(event, context))
        except Exception as e:
            logger.error(
                "Unhandled exception in Lambda handler's process_channels: %s",
                str(e),
                exc_info=True,
            )
            result = {
                "statusCode": 500,
                "body": json.dumps({"error": f"Unhandled processing error: {str(e)}"}),
            }
        finally:
            logger.info("Initiating session cleanup...")
            try:
                asyncio.run(cleanup_sessions())
                logger.info("Session cleanup completed.")
            except Exception as e:
                logger.error(
                    "Error during session cleanup: %s",
                    str(e),
                    exc_info=True,
                )
        return result
    except Exception as top_level_e:
        logger.error(
            "Top-level unhandled exception in Lambda handler: %s",
            str(top_level_e),
            exc_info=True,
        )
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Top-level handler error: {str(top_level_e)}"}),
        }
