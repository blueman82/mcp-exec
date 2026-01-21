"""
metrics_data_collector.py

Collects metrics data from DynamoDB for dashboard generation.
"""

from typing import Any, Dict, List, Optional

from packages.core.config.csopm_config import (
    CSOPM_CLOSURE_REMINDER_DAYS,
    CSOPM_RCA_REMINDER_DAYS,
)
from packages.core.config.system_channels import get_excluded_channels
from packages.core.logging import setup_logger
from packages.core.typed_di.service_registrations.protocols.csopm_protocols import (
    CSOPMStateTrackerProtocol,
)
from packages.db.operations.channel_operations import ChannelOperations
from packages.db.operations.join_notification_ops import JoinNotificationOps
from packages.slack.channel_operations.channel_membership_ops import (
    ChannelMembershipOps,
)

logger = setup_logger(__name__)


class MetricsDataCollector:
    """
    Collects metrics data from DynamoDB for dashboard generation.

    Gathers:
    - Product coverage (campaign/ajo) from channel_information table
    - CSO presence via jira_ticket != "NOT YET AVAILABLE"
    - War room stats from join notification tracking
    - Status update metrics from auto_status fields

    Queries all channels from DynamoDB to leverage persistent counters,
    regardless of current Slack membership status.
    """

    def __init__(
        self,
        channel_ops: ChannelOperations,
        join_notification_ops: JoinNotificationOps,
        channel_membership_ops: ChannelMembershipOps,
        csopm_state_tracker: Optional[CSOPMStateTrackerProtocol] = None,
    ):
        """
        Initialize MetricsDataCollector.

        Args:
            channel_ops: Channel operations for DynamoDB queries
            join_notification_ops: Join notification tracking operations
            channel_membership_ops: Channel membership lookup operations
            csopm_state_tracker: Optional CSOPM state tracker for CSOPM metrics
        """
        self._channel_ops = channel_ops
        self._join_notification_ops = join_notification_ops
        self._channel_membership_ops = channel_membership_ops
        self._csopm_state_tracker = csopm_state_tracker

    async def _get_current_member_channels(self) -> List[str]:
        """
        Get list of channel IDs where Ketchup is currently a member.

        Returns:
            List of channel IDs (matches /ketchup list behavior)
        """
        slack_channels = await self._channel_membership_ops.lookup_membership_of_channels()
        channel_ids = [ch.get("id") for ch in slack_channels if ch.get("id")]
        logger.info(f"Found {len(channel_ids)} channels where Ketchup is a member")
        return channel_ids

    async def _get_monthly_aggregates(self, month_keys: List[str]) -> Dict[str, int]:
        """
        Fetch monthly aggregates from METRICS_SUMMARY record.

        Args:
            month_keys: List of month keys (e.g., ["2025_09", "2025_10"])

        Returns:
            Dictionary with aggregated counts:
            {
                "auto_status_posts": total posts across months,
                "war_room_sent": total notifications sent,
                "war_room_success": total delivered,
                "war_room_failed": total failed,
            }

        """
        from packages.db.dynamodb_store import DynamoDBStore

        # Create DynamoDBStore instance to access monthly aggregates
        db_store = DynamoDBStore(self._channel_ops.client, self._channel_ops.table_name)

        # Get monthly aggregates from METRICS_SUMMARY record
        monthly_data = await db_store.get_monthly_aggregates(month_keys)

        # Aggregate across all months
        aggregated = {
            "auto_status_posts": 0,
            "war_room_sent": 0,
            "war_room_success": 0,
            "war_room_failed": 0,
        }

        for month_key in month_keys:
            month_metrics = monthly_data.get(month_key, {})
            aggregated["auto_status_posts"] += month_metrics.get("auto_status_posts", 0)
            aggregated["war_room_sent"] += month_metrics.get("war_room_sent", 0)
            aggregated["war_room_success"] += month_metrics.get("war_room_success", 0)
            aggregated["war_room_failed"] += month_metrics.get("war_room_failed", 0)

        logger.info(f"Aggregated monthly data for {len(month_keys)} months: {aggregated}")
        return aggregated

    async def collect_cso_metrics(
        self,
        start_ts: int,
        end_ts: int,
        period_type: str,
        month_keys: List[str] = None,
        channels_data: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Collect executive CSO metrics (historical only, no live state).

        For quarterly reports, shows only historical data - total channels
        that existed during the period, not current active/archived split.

        Args:
            start_ts: Start timestamp
            end_ts: End timestamp
            period_type: "7_days", "monthly", or "quarterly"
            month_keys: Month keys for monthly/quarterly lookups
            channels_data: Pre-loaded channels list (optional, avoids duplicate DB calls)

        Returns:
            Dictionary containing:
            - product_counts: Channel counts by product (campaign, ajo, other)
            - auto_notification_delivery: Auto notification delivery rate
        """
        logger.info(f"Collecting CSO metrics (period: {period_type})")

        try:
            # Use pre-loaded channels if provided, otherwise load from DB
            if channels_data is not None:
                channels_list = channels_data
            else:
                # Fallback: load channels (for standalone calls)
                days = (end_ts - start_ts) // (24 * 60 * 60)
                active_channels = await self._channel_ops.get_all_channel_details()
                active_list = self._normalize_channels(active_channels)
                archived_channels = await self._channel_ops.get_all_channel_details(
                    archive_lookup=True, days_threshold=days
                )
                archived_list = self._normalize_channels(archived_channels)
                channels_list = active_list + archived_list

            # Filter out system channels
            excluded_channels = get_excluded_channels()
            channels_list = [
                ch for ch in channels_list if ch.get("channel_id") not in excluded_channels
            ]

            if excluded_channels:
                logger.info(f"Excluded {len(excluded_channels)} system channels from metrics")

            cso_channels = self._filter_cso_channels(channels_list)

            product_counts = self._calculate_product_coverage(channels_list)
            auto_notification_delivery = await self._calculate_auto_notification_delivery(
                cso_channels
            )

            metrics = {
                "product_counts": product_counts,
                "auto_notification_delivery": auto_notification_delivery,
            }

            logger.info(
                f"CSO metrics collected: {product_counts['total']} total channels "
                f"({product_counts['campaign']} Campaign, {product_counts['ajo']} AJO, "
                f"{product_counts['other']} Other)"
            )
            return metrics

        except Exception as e:
            logger.error(f"Error collecting CSO metrics: {e}", exc_info=True)
            return self._get_empty_cso_metrics()

    async def collect_technical_metrics(
        self,
        start_ts: int,
        end_ts: int,
        period_type: str,
        month_keys: List[str] = None,
        channels_data: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Collect technical system health metrics.

        Args:
            start_ts: Start timestamp
            end_ts: End timestamp
            period_type: "7_days", "monthly", or "quarterly"
            month_keys: Month keys for monthly/quarterly lookups
            channels_data: Pre-loaded channels list (optional, avoids duplicate DB calls)

        Returns:
            Dictionary containing:
            - public_updates: Status update metrics
            - war_room_messages: War room notification metrics
            - system_health: Overall system health statistics
        """
        logger.info(f"Collecting technical metrics (period: {period_type})")

        try:
            # Use pre-loaded channels if provided, otherwise load from DB
            if channels_data is not None:
                channels_list = channels_data
            else:
                # Fallback: load channels (for standalone calls)
                channels = await self._channel_ops.get_all_channel_details(include_all=True)
                channels_list = self._normalize_channels(channels)

            # Fetch monthly aggregates if needed
            monthly_aggregates = None
            if period_type in ["monthly", "quarterly"] and month_keys:
                monthly_aggregates = await self._get_monthly_aggregates(month_keys)

            status_metrics = self._calculate_status_update_metrics(
                channels_list, start_ts, end_ts, period_type, monthly_aggregates
            )
            war_room_metrics = await self._calculate_war_room_metrics(
                channels_list,
                start_ts,
                end_ts,
                period_type,
                monthly_aggregates,
            )

            # Filter archived channels from the shared list for health metrics
            days = (end_ts - start_ts) // (24 * 60 * 60)
            threshold_ts = end_ts - (days * 24 * 60 * 60)
            archived_list = [
                ch
                for ch in channels_list
                if ch.get("archived") and ch.get("archived_at", 0) >= threshold_ts
            ]

            health_metrics = self._calculate_system_health(channels_list, archived_list)

            metrics = {
                "public_updates": status_metrics,
                "war_room_messages": war_room_metrics,
                "system_health": health_metrics,
            }

            logger.info("Technical metrics collected successfully")
            return metrics

        except Exception as e:
            logger.error(f"Error collecting technical metrics: {e}", exc_info=True)
            return self._get_empty_technical_metrics()

    async def collect_jira_posting_metrics(
        self,
        start_ts: int,
        end_ts: int,
        period_type: str,
        channels_data: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Collect JIRA posting metrics for dashboard.

        Returns historical metrics only - no live state (pending/failed status).

        Args:
            start_ts: Start timestamp
            end_ts: End timestamp
            period_type: "7_days", "monthly", or "quarterly"
            channels_data: Pre-loaded channels list (optional, avoids duplicate DB calls)

        Returns:
            Dictionary containing:
            - total_coverage: Overall posting success rate percentage
            - channels_with_reports: Number of channels with reports posted
            - total_channels: Total CSO channels analyzed
            - posting_details: Breakdown by ticket type (historical only)
        """
        logger.info(f"Collecting JIRA posting metrics (period: {period_type})")

        try:
            # Delegate to ChannelOperations with time filter and optional pre-loaded channels
            metrics = await self._channel_ops.get_jira_posting_metrics(
                start_ts, end_ts, channels_data=channels_data
            )

            return {
                "total_coverage": metrics["success_rate"],
                "channels_with_reports": metrics["channels_posted"],
                "total_channels": metrics["total_channels"],
                "posting_details": {
                    "primary_only": (metrics["posted_primary"] - metrics["posted_both"]),
                    "csopm_only": (metrics["posted_csopm"] - metrics["posted_both"]),
                    "both_tickets": metrics["posted_both"],
                },
            }

        except Exception as e:
            logger.error(f"Error collecting JIRA posting metrics: {e}", exc_info=True)
            return {
                "total_coverage": 0.0,
                "channels_with_reports": 0,
                "total_channels": 0,
                "posting_details": {
                    "primary_only": 0,
                    "csopm_only": 0,
                    "both_tickets": 0,
                },
            }

    async def collect_csopm_metrics(
        self,
        start_ts: int,
        end_ts: int,
    ) -> Dict[str, Any]:
        """
        Collect CSOPM notification metrics for dashboard.

        Queries NotificationRecord items to calculate:
        - Total notifications sent
        - Acknowledgment counts and timing
        - Reminder statistics

        Args:
            start_ts: Start timestamp for filtering (notifications created after)
            end_ts: End timestamp for filtering (notifications created before)

        Returns:
            Dictionary containing CSOPM metrics.
        """
        logger.info("Collecting CSOPM metrics")

        # Return empty metrics if state tracker not available
        if not self._csopm_state_tracker:
            logger.warning("CSOPM state tracker not available, returning empty metrics")
            return self._get_empty_csopm_metrics()

        try:
            records = await self._csopm_state_tracker.get_all_notification_records()

            # Filter by time range if created_at is available
            filtered_records = []
            for record in records:
                if record.created_at:
                    if start_ts <= record.created_at <= end_ts:
                        filtered_records.append(record)
                else:
                    # Include records without created_at (legacy records)
                    filtered_records.append(record)

            total = len(filtered_records)

            # Count by status
            acknowledged = sum(1 for r in filtered_records if r.notification_status == "ack")
            reminders_stopped = sum(
                1 for r in filtered_records if r.notification_status == "reminders_stopped"
            )
            pending = sum(1 for r in filtered_records if r.notification_status == "pending")

            # Count reminders sent
            rca_reminders_sent = sum(1 for r in filtered_records if r.rca_reminder_sent)
            closure_reminders_sent = sum(1 for r in filtered_records if r.closure_reminder_sent)

            # Calculate acknowledgment timing (within 3 days = 259200 seconds)
            three_days_seconds = 3 * 24 * 60 * 60
            ack_within_3_days = 0
            ack_after_3_days = 0

            for record in filtered_records:
                if record.notification_status == "ack" and record.created_at and record.updated_at:
                    time_to_ack = record.updated_at - record.created_at
                    if time_to_ack <= three_days_seconds:
                        ack_within_3_days += 1
                    else:
                        ack_after_3_days += 1

            # Calculate average ping counts
            total_rca_pings = sum(r.rca_ping_count for r in filtered_records)
            total_closure_pings = sum(r.closure_ping_count for r in filtered_records)
            avg_rca_pings = total_rca_pings / total if total > 0 else 0
            avg_closure_pings = total_closure_pings / total if total > 0 else 0

            # Calculate ticket completion timing (uses CSOPM_RCA_REMINDER_DAYS threshold)
            # completed_at and closed_at fields come from CSOPMTicketStatusPoller (Task 3)
            completion_threshold_seconds = CSOPM_RCA_REMINDER_DAYS * 24 * 60 * 60
            completed_within_threshold = 0
            completed_after_threshold = 0

            for record in filtered_records:
                if record.completed_at and record.created_at:
                    time_to_complete = record.completed_at - record.created_at
                    if time_to_complete <= completion_threshold_seconds:
                        completed_within_threshold += 1
                    else:
                        completed_after_threshold += 1

            # Calculate ticket closure timing (uses CSOPM_CLOSURE_REMINDER_DAYS threshold)
            closure_threshold_seconds = CSOPM_CLOSURE_REMINDER_DAYS * 24 * 60 * 60
            closed_within_threshold = 0
            closed_after_threshold = 0

            for record in filtered_records:
                if record.closed_at and record.created_at:
                    time_to_close = record.closed_at - record.created_at
                    if time_to_close <= closure_threshold_seconds:
                        closed_within_threshold += 1
                    else:
                        closed_after_threshold += 1

            return {
                "total_notifications": total,
                "acknowledged": acknowledged,
                "reminders_stopped": reminders_stopped,
                "pending": pending,
                "rca_reminders_sent": rca_reminders_sent,
                "closure_reminders_sent": closure_reminders_sent,
                "ack_within_3_days": ack_within_3_days,
                "ack_after_3_days": ack_after_3_days,
                "avg_rca_pings": round(avg_rca_pings, 2),
                "avg_closure_pings": round(avg_closure_pings, 2),
                "completed_within_threshold": completed_within_threshold,
                "completed_after_threshold": completed_after_threshold,
                "closed_within_threshold": closed_within_threshold,
                "closed_after_threshold": closed_after_threshold,
                "completion_threshold_days": CSOPM_RCA_REMINDER_DAYS,
                "closure_threshold_days": CSOPM_CLOSURE_REMINDER_DAYS,
            }

        except Exception as e:
            logger.error(f"Error collecting CSOPM metrics: {e}", exc_info=True)
            return self._get_empty_csopm_metrics()

    def _get_empty_csopm_metrics(self) -> Dict[str, Any]:
        """Return empty CSOPM metrics structure."""
        return {
            "total_notifications": 0,
            "acknowledged": 0,
            "reminders_stopped": 0,
            "pending": 0,
            "rca_reminders_sent": 0,
            "closure_reminders_sent": 0,
            "ack_within_3_days": 0,
            "ack_after_3_days": 0,
            "avg_rca_pings": 0.0,
            "avg_closure_pings": 0.0,
            "completed_within_threshold": 0,
            "completed_after_threshold": 0,
            "closed_within_threshold": 0,
            "closed_after_threshold": 0,
            "completion_threshold_days": CSOPM_RCA_REMINDER_DAYS,
            "closure_threshold_days": CSOPM_CLOSURE_REMINDER_DAYS,
        }

    async def collect_all_metrics(
        self,
        start_ts: int,
        end_ts: int,
        period_type: str,
        month_keys: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Collect all metrics for dashboard generation.

        Args:
            start_ts: Start timestamp (Unix epoch)
            end_ts: End timestamp (Unix epoch)
            period_type: "7_days", "monthly", or "quarterly"
            month_keys: List of month keys (e.g., ["2025_09"]) for monthly/quarterly

        Returns:
            Dictionary with cso_metrics, technical_metrics, jira_metrics
        """
        logger.info(f"Collecting all metrics (period: {period_type})")

        try:
            # Load all channels ONCE and share across all metric collectors
            all_channels = await self._channel_ops.get_all_channel_details(include_all=True)
            all_channels_list = self._normalize_channels(all_channels)

            # Collect each section with shared channel data
            cso_metrics = await self.collect_cso_metrics(
                start_ts, end_ts, period_type, month_keys, channels_data=all_channels_list
            )
            technical_metrics = await self.collect_technical_metrics(
                start_ts, end_ts, period_type, month_keys, channels_data=all_channels_list
            )
            jira_metrics = await self.collect_jira_posting_metrics(
                start_ts, end_ts, period_type, channels_data=all_channels_list
            )
            csopm_metrics = await self.collect_csopm_metrics(start_ts, end_ts)

            # Add JIRA posting metrics to CSO section
            cso_metrics["jira_posting"] = jira_metrics

            return {
                "cso": cso_metrics,
                "technical": technical_metrics,
                "csopm": csopm_metrics,
            }
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}", exc_info=True)
            return {
                "cso": self._get_empty_cso_metrics(),
                "technical": self._get_empty_technical_metrics(),
            }

    def _normalize_channels(self, channels: Dict[str, Any]) -> List[Dict]:
        """Convert channel dict to normalized list."""
        return [{**ch, "channel_id": ch_id} for ch_id, ch in channels.items()]

    def _filter_cso_channels(self, channels: List[Dict[str, Any]]) -> List[Dict]:
        """Filter channels with CSO presence (campaign/ajo products)."""
        # Only count campaign/ajo product channels as CSO channels
        return [ch for ch in channels if ch.get("product") in ["campaign", "ajo"]]

    def _calculate_product_coverage(self, channels: List[Dict[str, Any]]) -> Dict[str, int]:
        """Calculate channel counts by product type.

        Returns counts for campaign, ajo, and other (unknown/missing product type).
        """
        campaign_count = len([ch for ch in channels if ch.get("product") == "campaign"])
        ajo_count = len([ch for ch in channels if ch.get("product") == "ajo"])
        other_count = len([ch for ch in channels if ch.get("product") not in ["campaign", "ajo"]])

        return {
            "campaign": campaign_count,
            "ajo": ajo_count,
            "other": other_count,
            "total": campaign_count + ajo_count + other_count,
        }

    async def _calculate_auto_notification_delivery(
        self, cso_channels: List[Dict[str, Any]]
    ) -> int:
        """
        Calculate auto-notification delivery rate.

        Returns percentage of successfully delivered notifications.
        """
        total_delivered = 0
        total_attempted = 0

        for channel in cso_channels[:10]:
            channel_id = channel.get("channel_id")
            if not channel_id:
                continue

            stats = await self._join_notification_ops.get_channel_stats(channel_id)
            if stats:
                success = stats.get("total_success", 0)
                sent = stats.get("total_sent", 0)
                total_delivered += success
                total_attempted += sent

        delivery_rate = (
            round((total_delivered / total_attempted) * 100) if total_attempted > 0 else 0
        )

        return delivery_rate

    def _calculate_status_update_metrics(
        self,
        channels: List[Dict[str, Any]],
        start_ts: int,
        end_ts: int,
        period_type: str,
        monthly_aggregates: Dict[str, int] = None,
    ) -> Dict[str, Any]:
        """
        Calculate status update metrics for specified time period.

        For 7-day mode: Filters channels by auto_status_last_run timestamp
        For monthly/quarterly: Uses pre-aggregated monthly bucket counts

        Args:
            channels: List of channel records
            start_ts: Start timestamp
            end_ts: End timestamp
            period_type: "7_days", "monthly", or "quarterly"
            monthly_aggregates: Pre-fetched monthly aggregates (for monthly/quarterly)

        Note: auto_status_attempt_count is RESET to 0 on success and
        INCREMENTED on failure. So == 0 means success, > 0 means failures.
        """
        # Filter channels that posted in time period
        channels_with_updates = [
            ch for ch in channels if start_ts <= ch.get("auto_status_last_run", 0) <= end_ts
        ]

        success_count = len(
            [ch for ch in channels_with_updates if ch.get("auto_status_attempt_count", 0) == 0]
        )

        total = len(channels_with_updates)
        success_rate = round((success_count / total) * 100, 1) if total > 0 else 0.0

        # Get total posts count
        if period_type == "7_days":
            # For 7-day mode, count channels with recent activity
            # This approximates post count (each channel with activity had at least 1 post)
            total_posts = total  # Use channel count as proxy
        elif period_type in ["monthly", "quarterly"] and monthly_aggregates:
            # Use monthly buckets
            total_posts = monthly_aggregates.get("auto_status_posts", 0)
        else:
            # Fallback
            total_posts = 0

        return {
            "channels_with_updates": total,
            "total_posts": total_posts,
            "success_rate": success_rate,
        }

    async def _calculate_war_room_metrics(
        self,
        channels: List[Dict[str, Any]],
        start_ts: int,
        end_ts: int,
        period_type: str,
        monthly_aggregates: Dict[str, int] = None,
    ) -> Dict[str, Any]:
        """
        Calculate war room message metrics for specified time period.

        For 7-day mode: Queries detail records with time filters
        For monthly/quarterly: Uses pre-aggregated monthly bucket counts

        Note: unique_users counts unique users PER CHANNEL summed across channels,
        not globally unique users (users can appear in multiple channels).
        """
        # Use query-based approach for all period types to get accurate unique user counts
        # (monthly aggregates don't track unique users correctly - same user rejoining
        # the same channel would be counted multiple times in war_room_success)
        return await self._calculate_war_room_metrics_7_day(channels, start_ts, end_ts)

    async def _calculate_war_room_metrics_7_day(
        self,
        channels: List[Dict[str, Any]],
        start_ts: int,
        end_ts: int,
    ) -> Dict[str, Any]:
        """
        Calculate war room metrics from channel data already loaded.

        Uses user_join_notifications field from CSO_DETAILS which is already
        in the channels list - no need for additional DB queries.
        """
        total_delivered = 0
        total_attempted = 0
        total_unique_per_channel = 0

        # Extract user_join_notifications from already-loaded channel data
        for channel in channels:
            ujn = channel.get("user_join_notifications", {})
            if ujn:
                total_attempted += ujn.get("total_sent", 0)
                total_delivered += ujn.get("total_success", 0)
                # Use total_success as unique users approximation
                total_unique_per_channel += ujn.get("total_success", 0)

        delivery_rate = (
            round((total_delivered / total_attempted) * 100) if total_attempted > 0 else 0
        )

        return {
            "people_joined": total_delivered,
            "unique_users_per_channel": total_unique_per_channel,
            "delivery_rate": delivery_rate,
            "total_sent": total_attempted,
        }

    def _calculate_system_health(
        self, channels: List[Dict[str, Any]], archived_channels: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate system health metrics.

        Args:
            channels: All channels from DynamoDB
            archived_channels: Archived channels from DynamoDB (past 7 days)

        Distinguishes between:
        - CSO channels: campaign/ajo product channels
        - Total channels: All channels in DynamoDB (includes internal/feedback)
        - Recently archived: Channels archived in the past 7 days
        """
        active_channels = [ch for ch in channels if not ch.get("archived", False)]

        # Recently archived channels are already filtered by days_threshold in query
        recently_archived = archived_channels

        cso_channels = len(
            [ch for ch in active_channels if ch.get("product") in ["campaign", "ajo"]]
        )

        return {
            "cso_channels": cso_channels,
            "total_channels": len(active_channels),
            "inactive": 0,  # Not tracking inactive channels in member list
            "recently_archived": len(recently_archived),
        }

    def _get_empty_cso_metrics(self) -> Dict[str, Any]:
        """Return empty CSO metrics structure."""
        return {
            "product_counts": {
                "campaign": 0,
                "ajo": 0,
                "other": 0,
                "total": 0,
            },
            "auto_notification_delivery": 0,
        }

    def _get_empty_technical_metrics(self) -> Dict[str, Any]:
        """Return empty technical metrics structure."""
        return {
            "public_updates": {
                "posted_this_week": 0,
                "success_rate": 0.0,
                "channels_receiving": 0,
            },
            "war_room_messages": {
                "people_joined": 0,
                "delivery_rate": 0,
                "total_sent": 0,
            },
            "system_health": {
                "cso_channels": 0,
                "total_channels": 0,
                "inactive": 0,
                "recently_archived": 0,
            },
        }
