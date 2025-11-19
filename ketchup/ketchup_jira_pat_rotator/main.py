#!/usr/bin/env python3
"""
Main entry point for JIRA PAT rotation service.

Initializes TypedDI container, resolves all service dependencies,
and starts the PAT rotation scheduler.

Follows pattern of other Ketchup services (ketchup_status_updater, jira_reporter).
"""

import asyncio
import sys
import time
from datetime import datetime

from packages.core.logging import setup_logger
from packages.core.typed_di_integration import get_unified_container, cleanup_unified_container
from packages.core.config.feature_flags import FeatureFlags
from packages.core.distributed_lock import DistributedLock
from packages.core.typed_di.exceptions import MissingDependencyError

# TypedDI Protocol imports
from packages.core.typed_di.service_registrations.protocols.core_protocols import (
    DynamoDBStoreProtocol,
    SecretsManagerProtocol,
)
from packages.core.typed_di.service_registrations.protocols.infrastructure_protocols import (
    IMSTokenManagerProtocol,
)
from packages.core.typed_di.service_registrations.protocols.mcp_protocols import (
    MCPClientProtocol,
)

from ketchup_jira_pat_rotator.scheduler import PatRotationScheduler
from ketchup_jira_pat_rotator.rotator import PATRotator
from ketchup_jira_pat_rotator.metrics_collector import MetricsCollectorService
from ketchup_jira_pat_rotator.metrics_schema import MetricsStorage

logger = setup_logger(__name__)


async def async_main():
    """
    Async main entry point.

    Initializes TypedDI container, resolves all required services,
    and starts the scheduler loop.

    Raises:
        Exception: If container initialization or scheduler startup fails
    """
    try:
        logger.info("Starting PAT rotation service")

        # Initialize TypedDI container
        logger.info("Initializing TypedDI container...")
        container = await get_unified_container()

        # Resolve required protocols to verify all dependencies are available
        logger.info("Resolving service dependencies...")
        try:
            db_store = await container.aget(DynamoDBStoreProtocol)
            logger.info("DynamoDBStoreProtocol resolved")
        except MissingDependencyError as e:
            logger.error(f"Failed to resolve DynamoDBStoreProtocol: {e}")
            raise

        try:
            secrets_manager = await container.aget(SecretsManagerProtocol)
            logger.info("SecretsManagerProtocol resolved")
        except MissingDependencyError as e:
            logger.error(f"Failed to resolve SecretsManagerProtocol: {e}")
            raise

        try:
            mcp_client = await container.aget(MCPClientProtocol)
            logger.info("MCPClientProtocol resolved")
        except MissingDependencyError as e:
            logger.error(f"Failed to resolve MCPClientProtocol: {e}")
            raise

        try:
            ims_token_manager = await container.aget(IMSTokenManagerProtocol)
            logger.info("IMSTokenManagerProtocol resolved")
        except MissingDependencyError as e:
            logger.error(f"Failed to resolve IMSTokenManagerProtocol: {e}")
            raise

        logger.info("All required services initialized successfully")

        # Initialize metrics collector
        logger.info("Initializing metrics collector service...")
        try:
            # Get configuration from secrets manager or environment
            config = {
                "pat": "primary-token",  # In production, retrieve from secrets
                "patExpiry": datetime.utcnow(),  # In production, retrieve from secrets
                "backupPat": None,  # In production, retrieve from secrets if available
                "backupPatExpiry": None,  # In production, retrieve from secrets if available
            }

            # Initialize metrics storage
            dynamodb_resource = await container.aget(DynamoDBStoreProtocol)
            metrics_storage = MetricsStorage(dynamodb_resource)

            # Create metrics collector
            metrics_collector = MetricsCollectorService(
                metrics_storage=metrics_storage,
                config=config,
                rotation_service=None,  # Could integrate with rotator if needed
            )
            logger.info("Metrics collector service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize metrics collector: {e}")
            # Don't fail if metrics collector can't start; continue with rotation service
            metrics_collector = None

        # Initialize scheduler
        logger.info("Initializing PAT rotation scheduler...")
        scheduler = PatRotationScheduler()

        # Start metrics collector as background task if available
        metrics_collector_task = None
        if metrics_collector:
            logger.info("Starting metrics collector service...")
            metrics_collector_task = asyncio.create_task(metrics_collector.start())

        # Start the scheduler
        logger.info("Starting scheduler loop...")
        try:
            await scheduler.start()
        finally:
            # Stop metrics collector when scheduler stops
            if metrics_collector_task and not metrics_collector_task.done():
                logger.info("Stopping metrics collector service...")
                await metrics_collector.stop()
                try:
                    await metrics_collector_task
                except asyncio.CancelledError:
                    pass

    except Exception as e:
        logger.error(f"Fatal error in PAT rotation service: {e}", exc_info=True)
        raise

    finally:
        # Clean up container
        try:
            logger.info("Cleaning up TypedDI container...")
            await cleanup_unified_container()
        except Exception as cleanup_error:
            logger.error(f"Error during container cleanup: {cleanup_error}")


def main():
    """
    Main entry point.

    Called when service is started. Runs the async main loop.
    """
    try:
        logger.info(f"PAT rotation service started at {datetime.now()}")
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("PAT rotation service interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Unhandled exception in PAT rotation service: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
