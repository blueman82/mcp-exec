#!/usr/bin/env python3
"""
Maintenance fetcher service - Fetches daily maintenance data from Raven SOAP API.

Runs as scheduled job on prod1 only.
"""

import asyncio
import os
import sys
from datetime import datetime

# Add packages to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from packages.core.logging import setup_logger
from packages.core.typed_di.service_registrations.protocols import (
    DynamoDBStoreProtocol,
    RavenMaintenanceClientProtocol,
)
from packages.core.typed_di.typed_resolver import resolve_typed
from packages.core.typed_di_integration import get_unified_container, cleanup_unified_container

logger = setup_logger(__name__)


async def fetch_and_store_maintenance_data():
    """
    Fetch maintenance data and store in DynamoDB cache.

    Returns:
        Dict with status, records count, and date if successful
    """
    try:
        logger.info(f"Starting maintenance data fetch at {datetime.now()}")

        # Check feature flag
        if (
            not os.getenv("KETCHUP_MAINTENANCE_FETCHER_ENABLED", "false").lower()
            == "true"
        ):
            logger.info("Maintenance fetcher disabled by feature flag")
            return {"status": "disabled"}

        # Initialize TypedServiceRegistry
        logger.info("Initializing TypedServiceRegistry...")
        container = await get_unified_container()

        # Get SOAP client via TypedDI
        soap_client = await resolve_typed(RavenMaintenanceClientProtocol)

        # Fetch today's maintenance data
        date_today = datetime.now().strftime("%Y-%m-%d")
        maintenance_data = await soap_client.fetch_maintenance_data(date_today)

        if maintenance_data is None:
            logger.warning("Failed to fetch maintenance data")
            return {"status": "error", "message": "Fetch failed"}

        logger.info(f"Fetched {len(maintenance_data)} records for {date_today}")

        # Store in DynamoDB via TypedDI
        db_store = await resolve_typed(DynamoDBStoreProtocol)
        success = await db_store.store_maintenance_cache(
            date=date_today, data=maintenance_data
        )

        if success:
            logger.info("Successfully stored maintenance cache")
            return {
                "status": "success",
                "records": len(maintenance_data),
                "date": date_today,
            }
        else:
            logger.error("Failed to store maintenance cache")
            return {"status": "error", "message": "Store failed"}

    except Exception as e:
        logger.error(f"Maintenance fetch failed: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
    finally:
        logger.info("Cleaning up DI container...")
        try:
            await cleanup_unified_container()
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")


def main():
    """Main entry point."""
    try:
        result = asyncio.run(fetch_and_store_maintenance_data())
        logger.info(f"Maintenance fetch result: {result}")
        sys.exit(0 if result.get("status") == "success" else 1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
