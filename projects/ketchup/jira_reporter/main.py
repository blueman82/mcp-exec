"""
main.py

Main entry point and orchestration for the JIRA reporter service.
"""

import asyncio
import json
import os
import sys
import time
from typing import Any, Dict

from jira_reporter.archive_handler import JiraReporterArchiveHandler
from jira_reporter.channel_monitor import ChannelMonitor
from jira_reporter.jira_service import JiraService
from jira_reporter.jira_ticket_discovery import JiraTicketDiscovery
from jira_reporter.report_generator import ReportGenerator
from packages.core.logging import setup_logger
from packages.core.sqs_client import SQSClient
from packages.core.typed_di.service_registrations.protocols.command_protocols import (
    FeatureServiceProtocol,
)

# TypedDI Protocol imports
from packages.core.typed_di.service_registrations.protocols.core_protocols import (
    DynamoDBStoreProtocol,
    SecretsManagerProtocol,
)
from packages.core.typed_di.service_registrations.protocols.handler_protocols import (
    OpenAIHandlerProtocol,
)
from packages.core.typed_di.service_registrations.protocols.infrastructure_protocols import (
    IMSTokenManagerProtocol,
)
from packages.core.typed_di.service_registrations.protocols.mcp_protocols import (
    MCPClientProtocol,
)
from packages.core.typed_di.service_registrations.protocols.slack_protocols import (
    SlackChannelArchiveOpsProtocol,
    SlackChannelBotMembershipOpsProtocol,
    SlackChannelMessageOpsProtocol,
)
from packages.core.typed_di_integration import cleanup_unified_container, get_unified_container

logger = setup_logger(__name__)

# Statistics tracking for local logging
stats = {
    "total_processed": 0,
    "successful": 0,
    "failed": 0,
    "skipped": 0,
    "discovered": 0,
    "last_run": None,
    "sqs_processed": 0,
}


def write_health_status(status: str) -> None:
    """Write health status to file for health check monitoring.

    Args:
        status: Current service status ('running', 'idle', 'error')
    """
    try:
        timestamp = int(time.time())
        health_data = f"{timestamp}:{status}"
        with open("/tmp/jira_reporter_health", "w") as f:
            f.write(health_data)
    except Exception as e:
        logger.warning(f"Failed to write health status: {e}")


def write_last_successful_run() -> None:
    """Write timestamp of last successful run for health monitoring."""
    try:
        timestamp = int(time.time())
        with open("/tmp/jira_reporter_last_run", "w") as f:
            f.write(str(timestamp))
    except Exception as e:
        logger.warning(f"Failed to write last run timestamp: {e}")


async def process_channel(
    channel_data: Dict[str, Any],
    report_generator: ReportGenerator,
    jira_service: JiraService,
    jira_discovery: JiraTicketDiscovery,
    dynamodb_store: Any,
    skip_activity_check: bool = False,
) -> bool:
    """
    Process a single channel for JIRA reporting.

    Args:
        channel_data: Channel metadata
        report_generator: Report generator service
        jira_service: JIRA service
        jira_discovery: JIRA ticket discovery service
        dynamodb_store: DynamoDB store
        skip_activity_check: Skip the activity check (for archived channels)

    Returns:
        True if successfully processed, False otherwise
    """
    channel_id = channel_data.get("channel_id")
    jira_ticket = channel_data.get("jira_ticket", "")

    try:
        # Update status to in-progress
        await dynamodb_store.channel_ops.update_jira_report_status(
            channel_id=channel_id, status="PROCESSING"
        )

        # Generate report
        logger.info(f"Generating report for channel {channel_id}")
        report_text = await report_generator.generate_report(
            channel_id=channel_id, channel_metadata=channel_data
        )

        if not report_text:
            logger.error(f"Failed to generate report for channel {channel_id}")
            await dynamodb_store.channel_ops.update_jira_report_status(
                channel_id=channel_id, status="FAILED"
            )
            return False

        # Discover CSOPM ticket using reverse lookup
        channel_name = channel_data.get("channel_name", "")
        csopm_ticket = None
        try:
            csopm_ticket = await jira_discovery.discover_csopm_ticket(channel_name, channel_data)

            if csopm_ticket:
                logger.info(f"Discovered CSOPM ticket: {csopm_ticket}")
                stats["discovered"] += 1
            else:
                logger.info(f"No CSOPM ticket found for channel {channel_name}")
        except Exception as e:
            logger.error(f"Error during CSOPM discovery for channel {channel_name}: {str(e)}")
            csopm_ticket = None

        # Check if primary ticket was already marked as invalid
        primary_invalid = channel_data.get("jira_report_primary_invalid", False)

        if primary_invalid:
            logger.warning(
                f"Skipping primary ticket {jira_ticket} - previously marked as invalid/inaccessible"
            )
            primary_success = False  # Skip trying invalid ticket
        else:
            # Post to primary JIRA ticket (this is the critical posting)
            logger.info(f"Posting report to primary JIRA ticket {jira_ticket}")
            primary_success = await jira_service.post_comment_to_ticket(
                jira_ticket_id=jira_ticket, comment_text=report_text
            )

            # If primary ticket doesn't exist, mark it as invalid to skip future attempts
            if not primary_success:
                # Check if it's a "not found" error by trying validation
                ticket_exists = await jira_service._validate_ticket_exists(jira_ticket)
                if not ticket_exists:
                    logger.error(f"Primary ticket {jira_ticket} doesn't exist - marking as invalid")
                    await dynamodb_store.channel_ops.update_channel_fields(
                        channel_id=channel_id, updates={"jira_report_primary_invalid": True}
                    )

        # Post to CSOPM ticket if discovered - but check if already posted
        csopm_success = True  # Default to success if no CSOPM ticket
        if csopm_ticket and csopm_ticket != jira_ticket:
            # Check if we've already posted to CSOPM successfully
            csopm_posted = channel_data.get("jira_report_csopm_posted", False)

            if csopm_posted:
                logger.info(
                    f"Skipping CSOPM ticket {csopm_ticket} - already posted in previous attempt"
                )
                csopm_success = True  # Consider it successful since already done
            else:
                try:
                    logger.info(f"Posting report to CSOPM ticket {csopm_ticket}")
                    csopm_success = await jira_service.post_comment_to_ticket(
                        jira_ticket_id=csopm_ticket, comment_text=report_text
                    )
                    if csopm_success:
                        # Mark CSOPM as posted to avoid duplicates
                        await dynamodb_store.channel_ops.update_channel_fields(
                            channel_id=channel_id,
                            updates={
                                "jira_report_csopm_posted": True,
                                "jira_report_csopm_ticket": csopm_ticket,
                            },
                        )
                        logger.info(f"Marked CSOPM ticket {csopm_ticket} as posted")
                    else:
                        logger.error(f"Failed to post to CSOPM ticket {csopm_ticket}")
                except Exception as e:
                    logger.error(f"Error posting to CSOPM ticket {csopm_ticket}: {str(e)}")
                    csopm_success = False

        # Consider success if EITHER primary OR CSOPM succeeded
        # This prevents infinite retries when primary ticket is invalid but CSOPM works
        if primary_invalid and csopm_success:
            # Primary is permanently invalid but CSOPM worked - consider it done
            success = True
            logger.info(
                "Primary ticket invalid but CSOPM posting successful - marking as PROCESSED"
            )
        else:
            # Normal case - primary posting is critical
            success = primary_success

        # Update status based on result
        if success:
            await dynamodb_store.channel_ops.update_jira_report_status(
                channel_id=channel_id,
                status="PROCESSED",
                retry_count=0,  # Reset retry count on success
            )
            logger.info(f"Successfully processed channel {channel_id}")
            stats["successful"] += 1
            return True
        else:
            # Get current retry count and increment
            current_retry_count = channel_data.get("jira_report_retry_count", 0)
            new_retry_count = current_retry_count + 1

            await dynamodb_store.channel_ops.update_jira_report_status(
                channel_id=channel_id, status="FAILED", retry_count=new_retry_count
            )
            logger.error(
                f"Failed to post report to JIRA for channel {channel_id} "
                f"(retry count: {new_retry_count})"
            )
            stats["failed"] += 1
            return False

    except Exception as e:
        logger.error(f"Error processing channel {channel_id}: {str(e)}")
        await dynamodb_store.channel_ops.update_jira_report_status(
            channel_id=channel_id, status="FAILED"
        )
        stats["failed"] += 1
        return False


async def process_sqs_messages(
    report_generator: ReportGenerator,
    jira_service: JiraService,
    jira_discovery: JiraTicketDiscovery,
    dynamodb_store: Any,
    feature_service: Any,
) -> int:
    """
    Process messages from SQS queue.

    Args:
        report_generator: Report generator service
        jira_service: JIRA service
        jira_discovery: JIRA ticket discovery service
        dynamodb_store: DynamoDB store
        feature_service: Feature service for checking flags

    Returns:
        Number of messages processed
    """
    queue_url = os.environ.get("KETCHUP_EVENTS_QUEUE_URL")
    if not queue_url:
        logger.info("KETCHUP_EVENTS_QUEUE_URL not configured, skipping SQS processing")
        return 0

    try:
        sqs_client = SQSClient(queue_url=queue_url)
        messages = await sqs_client.receive_messages(max_messages=10)

        if not messages:
            logger.info("No messages in SQS queue")
            return 0

        logger.info(f"Found {len(messages)} messages in SQS queue")
        processed = 0

        for message in messages:
            try:
                # Parse message body
                body = json.loads(message["Body"])

                # Check if this is a channel_archived event for jira_reporter
                if (
                    body.get("event_type") == "channel_archived"
                    and body.get("service") == "jira_reporter"
                ):

                    channel_id = body.get("channel_id")

                    # Get full channel data from DynamoDB
                    channel_data = await dynamodb_store.get_channel_details_consistent(channel_id)
                    if not channel_data:
                        logger.warning(f"Channel {channel_id} not found in DynamoDB")
                        await sqs_client.delete_message(message["ReceiptHandle"])
                        continue

                    # Double-check feature is enabled for this channel
                    if not await feature_service.is_jira_reporter_enabled_for_channel(channel_id):
                        logger.info(f"JIRA reporter not enabled for channel {channel_id}, skipping")
                        await sqs_client.delete_message(message["ReceiptHandle"])
                        stats["skipped"] += 1
                        continue

                    # Process the channel with skip_activity_check=True
                    logger.info(f"Processing archived channel {channel_id} from SQS")
                    success = await process_channel(
                        channel_data=channel_data,
                        report_generator=report_generator,
                        jira_service=jira_service,
                        jira_discovery=jira_discovery,
                        dynamodb_store=dynamodb_store,
                        skip_activity_check=True,
                    )

                    if success:
                        processed += 1
                        stats["sqs_processed"] += 1

                # Delete message regardless of outcome
                await sqs_client.delete_message(message["ReceiptHandle"])

            except Exception as e:
                logger.error(f"Error processing SQS message: {e}")
                # Don't delete on error - let it retry or go to DLQ

        return processed

    except Exception as e:
        logger.error(f"Error accessing SQS queue: {e}")
        return 0


async def run_reporting_cycle() -> None:
    """Run a single reporting cycle."""
    try:
        # Write health status at start of cycle
        write_health_status("running")

        # Import feature flags
        from packages.core.config.feature_flags import FeatureFlags

        # Check if JIRA reporter feature is enabled at all
        if not FeatureFlags.is_jira_reporter_enabled():
            logger.info("JIRA reporter feature is not enabled, skipping cycle")
            write_health_status("idle")
            return

        cycle_start_time = time.time()
        logger.info("Starting JIRA reporting cycle")
        stats["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

        # Initialize DI container and store reference
        container = await get_unified_container()

        # Get required services using TypedDI
        dynamodb_store = await container.aget(DynamoDBStoreProtocol)
        openai_handler = await container.aget(OpenAIHandlerProtocol)
        msg_ops = await container.aget(SlackChannelMessageOpsProtocol)
        secrets_manager = await container.aget(SecretsManagerProtocol)
        mcp_client = await container.aget(MCPClientProtocol)
        ims_token_manager = await container.aget(IMSTokenManagerProtocol)
        feature_service = await container.aget(FeatureServiceProtocol)

        # Create JIRA discovery service with MCP client
        jira_discovery = JiraTicketDiscovery(mcp_client=mcp_client)

        # Create archive handler - core functionality of JIRA reporter
        archive_ops = await container.aget(SlackChannelArchiveOpsProtocol)
        bot_membership_ops = await container.aget(SlackChannelBotMembershipOpsProtocol)
        archive_handler = JiraReporterArchiveHandler(
            archive_ops=archive_ops,
            dynamodb_store=dynamodb_store,
            bot_membership_ops=bot_membership_ops,
            secrets_manager=secrets_manager,
        )

        # Run cleanup of any stale unarchived channels from previous runs
        logger.info("Running archive cleanup check")
        cleaned_count = await archive_handler.cleanup_stale_unarchives()
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} stale unarchived channels")

        # Create our services
        channel_monitor = ChannelMonitor(
            dynamodb_store=dynamodb_store,
            jira_discovery=jira_discovery,
            lookback_hours=int(os.environ.get("LOOKBACK_HOURS", "24")),
            msg_ops=msg_ops,
        )
        report_generator = ReportGenerator(
            openai_handler=openai_handler, channel_msg_ops=msg_ops, archive_handler=archive_handler
        )
        jira_service = JiraService(
            secrets_manager=secrets_manager, ims_token_manager=ims_token_manager
        )

        # Process SQS messages first (archived channels)
        sqs_processed = await process_sqs_messages(
            report_generator=report_generator,
            jira_service=jira_service,
            jira_discovery=jira_discovery,
            dynamodb_store=dynamodb_store,
            feature_service=feature_service,
        )

        if sqs_processed > 0:
            logger.info(f"Processed {sqs_processed} channels from SQS queue")

        # Get channels needing reports
        channels = await channel_monitor.get_channels_needing_reports()

        if not channels:
            logger.info("No channels need JIRA reports at this time")
            write_health_status("idle")
            return

        # Filter channels based on feature flag
        enabled_channels = []
        for channel in channels:
            channel_id = channel.get("channel_id")
            if await feature_service.is_jira_reporter_enabled_for_channel(channel_id):
                enabled_channels.append(channel)
            else:
                logger.info(f"JIRA reporter not enabled for channel {channel_id}, skipping")
                stats["skipped"] += 1

        if not enabled_channels:
            logger.info("No channels have JIRA reporter feature enabled")
            write_health_status("idle")
            return

        channels = enabled_channels

        # Process each channel (with rate limiting)
        logger.info(f"Processing {len(channels)} channels for JIRA reports")
        stats["total_processed"] += len(channels)

        # Allow processing up to 5 channels at once
        batch_size = int(os.environ.get("BATCH_SIZE", "5"))
        for i in range(0, len(channels), batch_size):
            batch = channels[i : i + batch_size]
            tasks = []

            for channel in batch:
                task = process_channel(
                    channel_data=channel,
                    report_generator=report_generator,
                    jira_service=jira_service,
                    jira_discovery=jira_discovery,
                    dynamodb_store=dynamodb_store,
                )
                tasks.append(task)

            # Wait for all tasks in batch to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Check results
            success_count = sum(1 for r in results if r is True)
            fail_count = len(batch) - success_count

            logger.info(f"Batch processed: {success_count} succeeded, {fail_count} failed")

            # Add a small delay between batches
            if i + batch_size < len(channels):
                await asyncio.sleep(2)

        # Log cycle statistics
        cycle_duration = time.time() - cycle_start_time
        logger.info(
            f"Cycle statistics - Duration: {cycle_duration:.1f}s, "
            f"Processed: {len(channels)}, Success: {stats['successful']}, "
            f"Failed: {stats['failed']}, CSOPM Discovered: {stats['discovered']}, "
            f"Total since start: {stats['total_processed']}"
        )

        # Write last successful run and health status
        write_last_successful_run()
        write_health_status("idle")

    except Exception as e:
        logger.error(f"Error in reporting cycle: {str(e)}")
        # Write error status on exceptions
        write_health_status("error")

    finally:
        # Clean up clients
        try:
            await cleanup_unified_container()
        except Exception as cleanup_error:
            logger.error(f"Error during client cleanup: {str(cleanup_error)}")

        logger.info("Completed JIRA reporting cycle")


async def main_loop() -> None:
    """Main execution loop for the service."""
    interval_minutes = int(os.environ.get("CHECK_INTERVAL_MINUTES", "15"))
    interval_seconds = interval_minutes * 60

    logger.info(f"Starting JIRA reporter service (interval: {interval_minutes} minutes)")

    # Track cycles for periodic summary
    cycle_count = 0

    while True:
        start_time = time.time()

        # Run reporting cycle
        try:
            await run_reporting_cycle()
            cycle_count += 1

            # Log summary every 12 cycles (approximately every hour at 5-minute intervals)
            if cycle_count % 12 == 0:
                logger.info(
                    f"Hourly summary - Total processed: {stats['total_processed']}, "
                    f"Successful: {stats['successful']}, Failed: {stats['failed']}, "
                    f"SQS processed: {stats['sqs_processed']}, "
                    f"Last run: {stats['last_run']}"
                )
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}")

        # Calculate sleep time, ensuring at least 10 seconds
        elapsed = time.time() - start_time
        sleep_time = max(10, interval_seconds - elapsed)

        logger.info(f"Sleeping for {sleep_time:.1f} seconds until next cycle")

        # Sleep until next cycle
        await asyncio.sleep(sleep_time)


if __name__ == "__main__":
    try:
        # Run the main loop
        asyncio.run(main_loop())
    except Exception as e:
        logger.critical(f"Unhandled exception in main: {str(e)}")
        sys.exit(1)
