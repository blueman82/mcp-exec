#!/usr/bin/env python3
"""
Async runner for metadata updater that can be called directly without Lambda event wrapper.
"""

import json
from typing import Any, Dict

from channel_metadata_updater.metadata_processor import (
    cleanup_sessions,
    create_channel_metadata_updater,
)
from packages.core.logging import setup_logger
from packages.core.typed_di_integration import get_unified_container

logger = setup_logger(__name__)


async def run_metadata_update() -> Dict[str, Any]:
    """Run the metadata update process asynchronously.

    Returns:
        Dict with status information
    """
    logger.info("Starting metadata update process")

    try:
        logger.info("Initializing TypedDI container...")
        container = await get_unified_container()
        logger.info("TypedDI container initialized successfully.")
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

        logger.info("Found %d channels with missing metadata", len(channels))

        # Process channels in batch for better concurrency
        stats = await updater.process_channels_batch(channels)

        logger.info(
            "Processing completed. Successfully updated %d/%d channels",
            stats.get("success", 0),
            stats.get("total", 0),
        )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": f"Processed {len(channels)} channels with missing metadata",
                    "processed": stats.get("total", 0),
                    "successful": stats.get("success", 0),
                    "skipped": stats.get("skipped", 0),
                    "failed": stats.get("failure", 0),
                }
            ),
        }

    except Exception as e:
        logger.error("Error in process_channels: %s", str(e), exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }
    finally:
        if updater:
            await updater.cleanup_clients()

        # Final session cleanup
        await cleanup_sessions()

        logger.info("All cleanup completed")
