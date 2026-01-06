"""
orchestration.py

Main orchestration logic for the JIRA reporter service.
Contains run_reporting_cycle and supporting functions.
"""

import asyncio
import json
import os
import time
from typing import Any, Dict, Optional

from ketchup_unified_scheduler.services.jira_reporter.archive_handler import (
    JiraReporterArchiveHandler,
)
from ketchup_unified_scheduler.services.jira_reporter.channel_monitor import ChannelMonitor
from ketchup_unified_scheduler.services.jira_reporter.report_generator import ReportGenerator
from ketchup_unified_scheduler.services.jira_reporter.service import JiraService
from ketchup_unified_scheduler.services.jira_reporter.ticket_discovery import JiraTicketDiscovery
from packages.core.logging import setup_logger
from packages.core.sqs_client import SQSClient
from packages.core.typed_di.registry import TypedServiceRegistry
from packages.core.typed_di.service_registrations.protocols.command_protocols import (
    FeatureServiceProtocol,
)
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
    MCPAsyncClientProtocol,
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
    """Write health status to file for health check monitoring."""
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
    """Process a single channel for JIRA reporting."""
    channel_id = channel_data.get("channel_id")
    jira_ticket = channel_data.get("jira_ticket", "")

    try:
        await dynamodb_store.channel_ops.update_jira_report_status(
            channel_id=channel_id, status="PROCESSING"
        )

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

        channel_name = channel_data.get("channel_name", "")
        csopm_ticket = None
        try:
            csopm_ticket = await jira_discovery.discover_csopm_ticket(channel_name, channel_data)
            if csopm_ticket:
                logger.info(f"Discovered CSOPM ticket: {csopm_ticket}")
                stats["discovered"] += 1
        except Exception as e:
            logger.error(f"Error during CSOPM discovery for channel {channel_name}: {str(e)}")

        primary_invalid = channel_data.get("jira_report_primary_invalid", False)

        if primary_invalid:
            logger.warning(f"Skipping primary ticket {jira_ticket} - previously marked as invalid")
            primary_success = False
        else:
            logger.info(f"Posting report to primary JIRA ticket {jira_ticket}")
            primary_success = await jira_service.post_comment_to_ticket(
                jira_ticket_id=jira_ticket, comment_text=report_text
            )
            if not primary_success:
                ticket_exists = await jira_service._validate_ticket_exists(jira_ticket)
                if not ticket_exists:
                    logger.error(f"Primary ticket {jira_ticket} doesn't exist - marking as invalid")
                    await dynamodb_store.channel_ops.update_channel_fields(
                        channel_id=channel_id, updates={"jira_report_primary_invalid": True}
                    )

        csopm_success = True
        if csopm_ticket and csopm_ticket != jira_ticket:
            csopm_posted = channel_data.get("jira_report_csopm_posted", False)
            if csopm_posted:
                logger.info(f"Skipping CSOPM ticket {csopm_ticket} - already posted")
            else:
                try:
                    logger.info(f"Posting report to CSOPM ticket {csopm_ticket}")
                    csopm_success = await jira_service.post_comment_to_ticket(
                        jira_ticket_id=csopm_ticket, comment_text=report_text
                    )
                    if csopm_success:
                        await dynamodb_store.channel_ops.update_channel_fields(
                            channel_id=channel_id,
                            updates={
                                "jira_report_csopm_posted": True,
                                "jira_report_csopm_ticket": csopm_ticket,
                            },
                        )
                except Exception as e:
                    logger.error(f"Error posting to CSOPM ticket {csopm_ticket}: {str(e)}")
                    csopm_success = False

        if primary_invalid and csopm_success:
            success = True
        else:
            success = primary_success

        if success:
            await dynamodb_store.channel_ops.update_jira_report_status(
                channel_id=channel_id, status="PROCESSED", retry_count=0
            )
            logger.info(f"Successfully processed channel {channel_id}")
            stats["successful"] += 1
            return True
        else:
            current_retry_count = channel_data.get("jira_report_retry_count", 0)
            new_retry_count = current_retry_count + 1
            await dynamodb_store.channel_ops.update_jira_report_status(
                channel_id=channel_id, status="FAILED", retry_count=new_retry_count
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
    """Process messages from SQS queue."""
    queue_url = os.environ.get("KETCHUP_EVENTS_QUEUE_URL")
    if not queue_url:
        return 0

    try:
        sqs_client = SQSClient(queue_url=queue_url)
        messages = await sqs_client.receive_messages(max_messages=10)
        if not messages:
            return 0

        processed = 0
        for message in messages:
            try:
                body = json.loads(message["Body"])
                if (
                    body.get("event_type") == "channel_archived"
                    and body.get("service") == "jira_reporter"
                ):
                    channel_id = body.get("channel_id")
                    channel_data = await dynamodb_store.get_channel_details_consistent(channel_id)
                    if not channel_data:
                        await sqs_client.delete_message(message["ReceiptHandle"])
                        continue

                    if not await feature_service.is_jira_reporter_enabled_for_channel(channel_id):
                        await sqs_client.delete_message(message["ReceiptHandle"])
                        stats["skipped"] += 1
                        continue

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

                await sqs_client.delete_message(message["ReceiptHandle"])
            except Exception as e:
                logger.error(f"Error processing SQS message: {e}")

        return processed
    except Exception as e:
        logger.error(f"Error accessing SQS queue: {e}")
        return 0


async def run_reporting_cycle(
    container: Optional[TypedServiceRegistry] = None,
) -> None:
    """Run a single reporting cycle."""
    try:
        write_health_status("running")
        from packages.core.config.feature_flags import FeatureFlags

        if not FeatureFlags.is_jira_reporter_enabled():
            logger.info("JIRA reporter feature is not enabled, skipping cycle")
            write_health_status("idle")
            return

        cycle_start_time = time.time()
        logger.info("Starting JIRA reporting cycle")
        stats["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

        if container is None:
            container = await get_unified_container()

        dynamodb_store = await container.aget(DynamoDBStoreProtocol)
        openai_handler = await container.aget(OpenAIHandlerProtocol)
        msg_ops = await container.aget(SlackChannelMessageOpsProtocol)
        secrets_manager = await container.aget(SecretsManagerProtocol)
        mcp_client = await container.aget(MCPAsyncClientProtocol)
        ims_token_manager = await container.aget(IMSTokenManagerProtocol)
        feature_service = await container.aget(FeatureServiceProtocol)

        jira_discovery = JiraTicketDiscovery(mcp_client=mcp_client)

        archive_ops = await container.aget(SlackChannelArchiveOpsProtocol)
        bot_membership_ops = await container.aget(SlackChannelBotMembershipOpsProtocol)
        archive_handler = JiraReporterArchiveHandler(
            archive_ops=archive_ops,
            dynamodb_store=dynamodb_store,
            bot_membership_ops=bot_membership_ops,
            secrets_manager=secrets_manager,
        )

        cleaned_count = await archive_handler.cleanup_stale_unarchives()
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} stale unarchived channels")

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

        sqs_processed = await process_sqs_messages(
            report_generator=report_generator,
            jira_service=jira_service,
            jira_discovery=jira_discovery,
            dynamodb_store=dynamodb_store,
            feature_service=feature_service,
        )
        if sqs_processed > 0:
            logger.info(f"Processed {sqs_processed} channels from SQS queue")

        channels = await channel_monitor.get_channels_needing_reports()
        if not channels:
            logger.info("No channels need JIRA reports at this time")
            write_health_status("idle")
            return

        enabled_channels = []
        for channel in channels:
            channel_id = channel.get("channel_id")
            if await feature_service.is_jira_reporter_enabled_for_channel(channel_id):
                enabled_channels.append(channel)
            else:
                stats["skipped"] += 1

        if not enabled_channels:
            write_health_status("idle")
            return

        channels = enabled_channels
        stats["total_processed"] += len(channels)

        batch_size = int(os.environ.get("BATCH_SIZE", "5"))
        for i in range(0, len(channels), batch_size):
            batch = channels[i : i + batch_size]
            tasks = [
                process_channel(
                    channel_data=channel,
                    report_generator=report_generator,
                    jira_service=jira_service,
                    jira_discovery=jira_discovery,
                    dynamodb_store=dynamodb_store,
                )
                for channel in batch
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success_count = sum(1 for r in results if r is True)
            logger.info(
                f"Batch processed: {success_count} succeeded, {len(batch) - success_count} failed"
            )
            if i + batch_size < len(channels):
                await asyncio.sleep(2)

        cycle_duration = time.time() - cycle_start_time
        logger.info(f"Cycle statistics - Duration: {cycle_duration:.1f}s")
        write_last_successful_run()
        write_health_status("idle")

    except Exception as e:
        logger.error(f"Error in reporting cycle: {str(e)}")
        write_health_status("error")
    finally:
        try:
            await cleanup_unified_container()
        except Exception as cleanup_error:
            logger.error(f"Error during client cleanup: {str(cleanup_error)}")
