"""
cleanup_utils.py

Utilities for cleaning up resources to prevent connection leaks.
"""

import gc
from typing import Any, List, Optional

import aiohttp
import httpx

from packages.core.async_client import AsyncClient
from packages.core.config.feature_flags import FeatureFlags
from packages.core.logging import setup_logger

logger = setup_logger(__name__)


async def cleanup_resources(components: Optional[List[Any]] = None) -> None:
    """
    Clean up resources used in the Lambda function.

    First tries component-specific cleanup, then fallback to GC-based cleanup.

    Args:
        components: List of components to clean up (optional)
    """
    logger.info("Starting resource cleanup")

    # 1. Component-specific cleanup
    if components:
        for component in components:
            try:
                if hasattr(component, "cleanup") and callable(component.cleanup):
                    logger.info("Cleaning up component: %s", type(component).__name__)
                    await component.cleanup()
            except Exception as e:
                logger.error(
                    "Error cleaning component %s: %s", type(component).__name__, str(e)
                )

    # 2. Find and cleanup AsyncClient instances
    try:
        clients = [obj for obj in gc.get_objects() if isinstance(obj, AsyncClient)]
        client_count = len(clients)
        if client_count > 0:
            logger.info("Found %d AsyncClient instances for cleanup", client_count)
            for client in clients:
                try:
                    if hasattr(client, "cleanup") and callable(client.cleanup):
                        await client.cleanup()
                except Exception as e:
                    logger.error("Error cleaning AsyncClient: %s", str(e))
    except Exception as e:
        logger.error("Error in AsyncClient cleanup: %s", str(e))

    # 3a. Tier 3a: Find and close any remaining httpx AsyncClient instances
    try:
        httpx_clients = [
            obj for obj in gc.get_objects() if isinstance(obj, httpx.AsyncClient)
        ]
        httpx_client_count = len(httpx_clients)
        if httpx_client_count > 0:
            logger.info(
                "Tier 3a: Found %d httpx AsyncClient instances for fallback cleanup",
                httpx_client_count
            )
            for client in httpx_clients:
                try:
                    if not client.is_closed:
                        logger.info("Tier 3a: Closing unclosed httpx client")
                        await client.aclose()
                except Exception as e:
                    logger.error("Tier 3a: Error closing httpx client: %s", str(e))
    except Exception as e:
        logger.error("Tier 3a: Error in httpx client cleanup: %s", str(e))

    # 3b. Tier 3b: Find and close any remaining aiohttp sessions (legacy/fallback)
    try:
        sessions = [
            obj for obj in gc.get_objects() if isinstance(obj, aiohttp.ClientSession)
        ]
        session_count = len(sessions)
        if session_count > 0:
            logger.info(
                "Tier 3b: Found %d aiohttp sessions for fallback cleanup",
                session_count
            )
            for session in sessions:
                try:
                    if not session.closed:
                        logger.info("Tier 3b: Closing unclosed aiohttp session")
                        await session.close()
                except Exception as e:
                    logger.error("Tier 3b: Error closing session: %s", str(e))
    except Exception as e:
        logger.error("Tier 3b: Error in aiohttp session cleanup: %s", str(e))

    # 4. Tier 4: Find and close any remaining connectors (only needed if using aiohttp)
    if not FeatureFlags.is_httpx_enabled():
        try:
            connectors = [
                obj for obj in gc.get_objects() if isinstance(obj, aiohttp.TCPConnector)
            ]
            connector_count = len(connectors)
            if connector_count > 0:
                logger.info(
                    "Tier 4: Found %d TCP connectors for cleanup (aiohttp mode)",
                    connector_count
                )
                for connector in connectors:
                    try:
                        if not connector.closed:
                            logger.info("Tier 4: Closing unclosed connector")
                            await connector.close()
                    except Exception as e:
                        logger.error("Tier 4: Error closing connector: %s", str(e))
        except Exception as e:
            logger.error("Tier 4: Error in connector cleanup: %s", str(e))
    else:
        logger.debug(
            "Tier 4: Skipping connector cleanup (httpx mode - no connectors needed)"
        )

    logger.info("Resource cleanup completed")
