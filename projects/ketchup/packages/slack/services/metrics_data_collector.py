"""
metrics_data_collector.py

Collects metrics data from DynamoDB for dashboard generation.
"""

from typing import Any, Dict, List

from packages.core.config.system_channels import get_excluded_channels
from packages.core.logging import setup_logger
from packages.db.operations.channel_operations import ChannelOperations
from packages.db.operations.join_notification_ops import JoinNotificationOps
from packages.slack.channel_operations.channel_membership_ops import (
    ChannelMembershipOps,
)
from packages.slack.models.cso_metrics import CSOChannelCounts, CSOMetrics

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
    ):
        """
        Initialize MetricsDataCollector.

        Args:
            channel_ops: Channel operations for DynamoDB queries
            join_notification_ops: Join notification tracking operations
            channel_membership_ops: Channel membership lookup operations
        """
        self._channel_ops = channel_ops
        self._join_notification_ops = join_notification_ops
        self._channel_membership_ops = channel_membership_ops

    async def _get_current_member_channels(self) -> List[str]:
        """
        Get list of channel IDs where Ketchup is currently a member.

        Returns:
            List of channel IDs (matches /ketchup list behavior)
        """
        slack_channels = (
            await self._channel_membership_ops.lookup_membership_of_channels()
        )
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
                "war_room_unique_users": total unique users,
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
            "war_room_unique_users": 0,
        }

        for month_key in month_keys:
            month_metrics = monthly_data.get(month_key, {})
            aggregated["auto_status_posts"] += month_metrics.get("auto_status_posts", 0)
            aggregated["war_room_sent"] += month_metrics.get("war_room_sent", 0)
            aggregated["war_room_success"] += month_metrics.get("war_room_success", 0)
            aggregated["war_room_failed"] += month_metrics.get("war_room_failed", 0)
            aggregated["war_room_unique_users"] += month_metrics.get(
                "war_room_unique_users", 0
            )

        logger.info(
            f"Aggregated monthly data for {len(month_keys)} months: {aggregated}"
        )
        return aggregated

    async def collect_cso_metrics(
        self,
        start_ts: int,
        end_ts: int,
        period_type: str,
        month_keys: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Collect executive CSO metrics with active vs archived split.

        Note: CSO metrics show current state (coverage, active channels)
        and are not time-filtered. Parameters included for API consistency.

        Args:
            start_ts: Start timestamp
            end_ts: End timestamp
            period_type: "7_days", "monthly", or "quarterly"
            month_keys: Month keys for monthly/quarterly lookups

        Returns:
            Dictionary containing:
            - products_using_ketchup: List of products ["campaign", "ajo"]
            - product_coverage: Per-product coverage stats
            - overall_cso_coverage: Overall CSO coverage percentage
            - auto_notification_delivery: Auto notification delivery rate
            - cso_metrics: CSOMetrics dataclass with active vs archived split
        """
        logger.info(f"Collecting CSO metrics (period: {period_type})")

        try:
            # Get active channels for "Currently Active" count
            active_channels = await self._channel_ops.get_all_channel_details()
            active_list = self._normalize_channels(active_channels)

            # Get recently archived channels (past 7 days) for "Archived" count
            days = (end_ts - start_ts) // (24 * 60 * 60)
            archived_channels = await self._channel_ops.get_all_channel_details(
                archive_lookup=True, days_threshold=days
            )
            archived_list = self._normalize_channels(archived_channels)

            # Combine for full channel list
            channels_list = active_list + archived_list

            # Filter out system channels
            excluded_channels = get_excluded_channels()
            channels_list = [
                ch
                for ch in channels_list
                if ch.get("channel_id") not in excluded_channels
            ]

            if excluded_channels:
                logger.info(
                    f"Excluded {len(excluded_channels)} system channels from metrics"
                )

            cso_channels = self._filter_cso_channels(channels_list)

            # Split CSO channels by archived status
            cso_metrics = self._split_active_vs_archived(cso_channels)

            product_stats = self._calculate_product_coverage(channels_list)
            auto_notification_delivery = (
                await self._calculate_auto_notification_delivery(cso_channels)
            )

            overall_coverage = self._calculate_overall_coverage(product_stats)

            metrics = {
                "products_using_ketchup": list(product_stats.keys()),
                "product_coverage": product_stats,
                "overall_cso_coverage": overall_coverage,
                "auto_notification_delivery": auto_notification_delivery,
                "cso_metrics": cso_metrics,
            }

            logger.info(
                f"CSO metrics collected: {cso_metrics.currently_active.total} active, "
                f"{cso_metrics.archived.total} archived"
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
    ) -> Dict[str, Any]:
        """
        Collect technical system health metrics.

        Args:
            start_ts: Start timestamp
            end_ts: End timestamp
            period_type: "7_days", "monthly", or "quarterly"
            month_keys: Month keys for monthly/quarterly lookups

        Returns:
            Dictionary containing:
            - public_updates: Status update metrics
            - war_room_messages: War room notification metrics
            - system_health: Overall system health statistics
        """
        logger.info(f"Collecting technical metrics (period: {period_type})")

        try:
            # Get all channels from DynamoDB (includes historical channels with counters)
            channels = await self._channel_ops.get_all_channel_details()
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
                monthly_aggregates,  # Reuse from status metrics
            )

            # Fetch recently archived channels for time period from DynamoDB
            days = (end_ts - start_ts) // (24 * 60 * 60)
            archived_channels = await self._channel_ops.get_all_channel_details(
                archive_lookup=True, days_threshold=days
            )
            archived_list = self._normalize_channels(archived_channels)

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
    ) -> Dict[str, Any]:
        """
        Collect JIRA posting metrics for dashboard.

        Args:
            start_ts: Start timestamp
            end_ts: End timestamp
            period_type: "7_days", "monthly", or "quarterly"

        Returns:
            Dictionary containing:
            - total_coverage: Overall posting success rate percentage
            - channels_with_reports: Number of channels with reports posted
            - total_channels: Total CSO channels analyzed
            - posting_details: Breakdown by ticket type and failure reasons
        """
        logger.info(f"Collecting JIRA posting metrics (period: {period_type})")

        try:
            # Delegate to ChannelOperations with time filter
            metrics = await self._channel_ops.get_jira_posting_metrics(start_ts, end_ts)

            # Calculate channels with reports (unique channels that got posted)
            channels_with_reports = (
                metrics["posted_primary"]
                + metrics["posted_csopm"]
                - metrics["posted_both"]
            )

            return {
                "total_coverage": metrics["success_rate"],
                "channels_with_reports": channels_with_reports,
                "total_channels": metrics["total_channels"],
                "posting_details": {
                    "primary_only": (
                        metrics["posted_primary"] - metrics["posted_both"]
                    ),
                    "csopm_only": (metrics["posted_csopm"] - metrics["posted_both"]),
                    "both_tickets": metrics["posted_both"],
                    "no_valid_ticket": metrics["failed_no_ticket"],
                    "api_failures": metrics["failed_api_error"],
                    "pending": metrics["pending"],
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
                    "no_valid_ticket": 0,
                    "api_failures": 0,
                    "pending": 0,
                },
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
            # Collect each section with time parameters
            cso_metrics = await self.collect_cso_metrics(
                start_ts, end_ts, period_type, month_keys
            )
            technical_metrics = await self.collect_technical_metrics(
                start_ts, end_ts, period_type, month_keys
            )
            jira_metrics = await self.collect_jira_posting_metrics(
                start_ts, end_ts, period_type
            )

            # Add JIRA posting metrics to CSO section
            cso_metrics["jira_posting"] = jira_metrics

            return {
                "cso": cso_metrics,
                "technical": technical_metrics,
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

    def _split_active_vs_archived(
        self, cso_channels: List[Dict[str, Any]]
    ) -> CSOMetrics:
        """
        Split CSO channels into currently active vs archived.

        Args:
            cso_channels: List of CSO channel records

        Returns:
            CSOMetrics with counts for active and archived channels
        """
        # Split by archived status
        active_channels = [ch for ch in cso_channels if not ch.get("archived", False)]
        archived_channels = [ch for ch in cso_channels if ch.get("archived", False)]

        # Count Campaign vs AJO for active channels
        active_campaign = len(
            [ch for ch in active_channels if ch.get("product") == "campaign"]
        )
        active_ajo = len([ch for ch in active_channels if ch.get("product") == "ajo"])

        # Count Campaign vs AJO for archived channels
        archived_campaign = len(
            [ch for ch in archived_channels if ch.get("product") == "campaign"]
        )
        archived_ajo = len(
            [ch for ch in archived_channels if ch.get("product") == "ajo"]
        )

        # Create dataclass instances
        currently_active = CSOChannelCounts(
            total=len(active_channels), campaign=active_campaign, ajo=active_ajo
        )

        archived = CSOChannelCounts(
            total=len(archived_channels), campaign=archived_campaign, ajo=archived_ajo
        )

        return CSOMetrics(currently_active=currently_active, archived=archived)

    def _calculate_product_coverage(
        self, channels: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, int]]:
        """Calculate CSO coverage by product from DynamoDB channel records."""
        product_stats = {}

        for product in ["campaign", "ajo"]:
            product_channels = [ch for ch in channels if ch.get("product") == product]
            # All channels in DynamoDB for this product
            cso_count = len(product_channels)
            total = cso_count

            percentage = 100 if cso_count > 0 else 0

            product_stats[product] = {
                "channels": cso_count,
                "total": total,
                "percentage": percentage,
            }

        return product_stats

    def _calculate_overall_coverage(
        self, product_stats: Dict[str, Dict[str, int]]
    ) -> int:
        """Calculate overall CSO coverage percentage."""
        total_channels = sum(stats["total"] for stats in product_stats.values())
        cso_channels = sum(stats["channels"] for stats in product_stats.values())

        if total_channels == 0:
            return 0

        return round((cso_channels / total_channels) * 100)

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
            round((total_delivered / total_attempted) * 100)
            if total_attempted > 0
            else 0
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
            ch
            for ch in channels
            if start_ts <= ch.get("auto_status_last_run", 0) <= end_ts
        ]

        success_count = len(
            [
                ch
                for ch in channels_with_updates
                if ch.get("auto_status_attempt_count", 0) == 0
            ]
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
        # Branch based on period type
        if period_type == "7_days":
            # Use detail record queries (current implementation)
            return await self._calculate_war_room_metrics_7_day(
                channels, start_ts, end_ts
            )
        elif period_type in ["monthly", "quarterly"] and monthly_aggregates:
            # Use monthly aggregates
            return self._calculate_war_room_metrics_from_aggregates(monthly_aggregates)
        else:
            # Fallback to empty
            return {
                "people_joined": 0,
                "unique_users_per_channel": 0,
                "delivery_rate": 0,
                "total_sent": 0,
            }

    async def _calculate_war_room_metrics_7_day(
        self,
        channels: List[Dict[str, Any]],
        start_ts: int,
        end_ts: int,
    ) -> Dict[str, Any]:
        """
        Calculate war room metrics using detail record queries (7-day mode).

        Note: Falls back to all-time stats if detail records don't exist.
        """
        total_delivered = 0
        total_attempted = 0
        total_unique_per_channel = 0
        channels_count = min(20, len(channels))

        # Track if we got any data from time-filtered queries
        got_time_filtered_data = False

        for channel in channels[:channels_count]:
            channel_id = channel.get("channel_id")
            if not channel_id:
                continue

            # Try time-filtered stats first
            stats = await self._join_notification_ops.get_time_filtered_stats(
                channel_id, start_ts, end_ts
            )

            if stats and stats.get("total_sent", 0) > 0:
                # Got time-filtered data
                total_attempted += stats.get("total_sent", 0)
                total_delivered += stats.get("total_success", 0)
                total_unique_per_channel += stats.get("unique_users", 0)
                got_time_filtered_data = True

        # Fallback: If no time-filtered data exists, use all-time stats
        if not got_time_filtered_data:
            logger.info("No time-filtered war room data found, using all-time stats")
            for channel in channels[:channels_count]:
                channel_id = channel.get("channel_id")
                if not channel_id:
                    continue

                stats = await self._join_notification_ops.get_channel_stats(channel_id)
                if stats:
                    total_attempted += stats.get("total_sent", 0)
                    total_delivered += stats.get("total_success", 0)
                    # Note: get_channel_stats doesn't have unique_users field
                    # Use total_success as approximation
                    total_unique_per_channel += stats.get("total_success", 0)

        delivery_rate = (
            round((total_delivered / total_attempted) * 100)
            if total_attempted > 0
            else 0
        )

        return {
            "people_joined": total_delivered,
            "unique_users_per_channel": total_unique_per_channel,
            "delivery_rate": delivery_rate,
            "total_sent": total_attempted,
        }

    def _calculate_war_room_metrics_from_aggregates(
        self,
        monthly_aggregates: Dict[str, int],
    ) -> Dict[str, Any]:
        """
        Calculate war room metrics from monthly aggregates (monthly/quarterly mode).
        """
        total_sent = monthly_aggregates.get("war_room_sent", 0)
        total_success = monthly_aggregates.get("war_room_success", 0)
        unique_users = monthly_aggregates.get("war_room_unique_users", 0)

        delivery_rate = (
            round((total_success / total_sent) * 100) if total_sent > 0 else 0
        )

        return {
            "people_joined": total_success,
            "unique_users_per_channel": unique_users,
            "delivery_rate": delivery_rate,
            "total_sent": total_sent,
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
            "products_using_ketchup": [],
            "product_coverage": {},
            "overall_cso_coverage": 0,
            "auto_notification_delivery": 0,
            "cso_metrics": CSOMetrics(
                currently_active=CSOChannelCounts(0, 0, 0),
                archived=CSOChannelCounts(0, 0, 0),
            ),
            "jira_posting": {
                "total_coverage": 0.0,
                "channels_with_reports": 0,
                "total_channels": 0,
                "posting_details": {
                    "primary_only": 0,
                    "csopm_only": 0,
                    "both_tickets": 0,
                    "no_valid_ticket": 0,
                    "api_failures": 0,
                    "pending": 0,
                },
            },
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
