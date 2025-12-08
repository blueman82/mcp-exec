#!/usr/bin/env python3
"""
Metadata updater service that runs as a scheduled job.
This replaces the EventBridge-triggered Lambda function.
"""

import os
import sys
from datetime import datetime

# Add packages to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channel_metadata_updater.metadata_processor import handler
from packages.core.logging import setup_logger

logger = setup_logger(__name__)


def run_metadata_update():
    """Run the metadata update process"""
    try:
        logger.info(f"Starting metadata update at {datetime.now()}")

        # Create Lambda-like event
        event = {
            "source": "aws.events",
            "detail-type": "Scheduled Event",
            "time": datetime.now().isoformat(),
        }

        # Run the update
        context = {}  # Lambda context not needed
        result = handler(event, context)

        logger.info(f"Metadata update completed: {result}")

    except Exception as e:
        logger.error(f"Metadata update failed: {e}", exc_info=True)
        raise


def main():
    """Main entry point"""
    try:
        run_metadata_update()
    except Exception as e:
        logger.error(f"Fatal error in metadata updater: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
