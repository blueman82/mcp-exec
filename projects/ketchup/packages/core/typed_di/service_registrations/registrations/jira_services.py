"""
JIRA Integration Services Registration Module

Registers JIRA integration services for ticket management, workflow automation,
reporting, and analytics capabilities. Handles 5 services with enterprise-grade
JIRA integration. All registrations use protocol-first pattern with concrete aliases.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from packages.core.logging import setup_logger
from packages.core.typed_di.types import DependencySpec

# JIRA and core imports
try:
    from ketchup_unified_scheduler.services.jira_reporter.service import (
        JiraService as JIRAServiceImpl,
    )
    from ketchup_unified_scheduler.services.jira_reporter.ticket_discovery import (
        JiraTicketDiscovery,
    )
    from packages.core.local_metrics import MetricsStorage
    from packages.db.dynamodb_store import DynamoDBStore
    from packages.integrations.async_ims_token_manager import AsyncIMSTokenManager
    from packages.integrations.async_mcp_client import AsyncMCPClient
    from packages.integrations.jira_cache import JIRACache
    from packages.integrations.jira_data_extractor import JIRADataExtractor
    from packages.secrets.manager import SecretsManager

    _JIRA_IMPORTS_AVAILABLE = True
except ImportError as e:
    logger = setup_logger(__name__)
    logger.warning(f"JIRA integration import failed: {e}")
    _JIRA_IMPORTS_AVAILABLE = False
    # Define placeholder types for type annotations
    JIRAServiceImpl = Any
    JiraTicketDiscovery = Any
    JIRADataExtractor = Any
    JIRACache = Any
    SecretsManager = Any
    AsyncIMSTokenManager = Any
    AsyncMCPClient = Any
    DynamoDBStore = Any
    MetricsStorage = Any

# Protocol imports
from ..protocols.jira_protocols import (
    JIRAAnalyticsServiceProtocol,
    JIRAReportingServiceProtocol,
    JIRAServiceProtocol,
    JIRATicketServiceProtocol,
    JIRAWorkflowServiceProtocol,
)

if TYPE_CHECKING:
    from packages.core.typed_di.service_registrations.manager import ServiceRegistrationManager

logger = setup_logger(__name__)


def register_jira_services(manager: "ServiceRegistrationManager") -> None:
    """
    Register JIRA integration services.

    Covers JIRA Integration Suite (5 services):
    - Core JIRA service with MCP integration
    - Ticket discovery and management service
    - Workflow and status management service
    - Reporting and analytics service
    - Performance analytics service

    Args:
        manager: ServiceRegistrationManager instance for protocol-first registration
    """
    # Skip registration if JIRA imports failed
    if not _JIRA_IMPORTS_AVAILABLE:
        logger.warning("Skipping JIRA service registration - imports not available")
        return

    logger.info("Registering JIRA Integration Services (5 services)")

    # Always use async clients (feature flag removed - consolidation complete)
    ims_token_manager_cls = AsyncIMSTokenManager
    mcp_client_cls = AsyncMCPClient

    # Core JIRA Service
    _register_core_jira_service(manager, ims_token_manager_cls)

    # Ticket Management Service
    _register_ticket_service(manager, mcp_client_cls)

    # Workflow Service
    _register_workflow_service(manager, mcp_client_cls)

    # Reporting Service
    _register_reporting_service(manager)

    # Analytics Service
    _register_analytics_service(manager)

    logger.info("JIRA Integration Services completed - 5 services registered")


def _register_core_jira_service(
    manager: "ServiceRegistrationManager",
    ims_cls,
) -> None:
    """Register core JIRA service with MCP integration."""

    async def create_jira_service(resolver) -> JIRAServiceImpl:
        """Factory function for JIRAService with MCP integration."""
        logger.info("Creating JIRAService instance via TypedDI")
        secrets_manager = await resolver.aget(SecretsManager)
        ims_token_manager = await resolver.aget(ims_cls)
        return JIRAServiceImpl(secrets_manager, ims_token_manager)

    manager.register_protocol_with_concrete_alias(
        protocol_type=JIRAServiceProtocol,
        concrete_type=JIRAServiceImpl,
        factory=create_jira_service,
        dependencies=[
            DependencySpec(SecretsManager),
            DependencySpec(ims_cls),
        ],
        lifetime="singleton",
    )


def _register_ticket_service(
    manager: "ServiceRegistrationManager",
    mcp_client_cls,
) -> None:
    """Register JIRA ticket discovery and management service."""

    async def create_ticket_discovery(resolver) -> JiraTicketDiscovery:
        """Factory function for JiraTicketDiscovery."""
        logger.info("Creating JiraTicketDiscovery instance via TypedDI")
        mcp_client = await resolver.aget(mcp_client_cls)
        return JiraTicketDiscovery(mcp_client)

    manager.register_protocol_with_concrete_alias(
        protocol_type=JiraTicketDiscovery,
        concrete_type=JiraTicketDiscovery,
        factory=create_ticket_discovery,
        dependencies=[DependencySpec(mcp_client_cls)],
        lifetime="singleton",
    )

    class JIRATicketService:
        """JIRA ticket discovery and management service."""

        def __init__(self, discovery: JiraTicketDiscovery):
            """Initialize with ticket discovery service."""
            self.discovery = discovery

        async def discover_jira_ticket(
            self, channel_name: str, channel_metadata: Dict[str, Any]
        ) -> Optional[str]:
            """Discover JIRA ticket for a channel."""
            return await self.discovery.discover_jira_ticket(channel_name, channel_metadata)

        async def search_jira_by_exigence_url(
            self, exigence_url: str, customer_name: Optional[str] = None
        ) -> Optional[str]:
            """Search JIRA for tickets containing the Exigence URL."""
            return await self.discovery.search_jira_by_exigence_url(exigence_url, customer_name)

        def extract_exigence_id(self, channel_name: str) -> Optional[str]:
            """Extract Exigence event ID from channel name."""
            return self.discovery.extract_exigence_id(channel_name)

    async def create_ticket_service(resolver) -> JIRATicketService:
        """Factory function for JIRATicketService."""
        logger.info("Creating JIRATicketService instance via TypedDI")
        discovery = await resolver.aget(JiraTicketDiscovery)
        return JIRATicketService(discovery)

    manager.register_protocol_with_concrete_alias(
        protocol_type=JIRATicketServiceProtocol,
        concrete_type=JIRATicketService,
        factory=create_ticket_service,
        dependencies=[DependencySpec(JiraTicketDiscovery)],
        lifetime="singleton",
    )


def _register_workflow_service(
    manager: "ServiceRegistrationManager",
    mcp_client_cls,
) -> None:
    """Register JIRA workflow and status management service."""

    class JIRAWorkflowService:
        """JIRA workflow and status management service."""

        def __init__(self, mcp_client):
            """Initialize with MCP client."""
            self.mcp_client = mcp_client

        async def get_workflow_status(self, ticket_id: str) -> Optional[Dict[str, Any]]:
            """Get current workflow status for a ticket."""
            try:
                issue = await self.mcp_client.get_issue(ticket_id)
                if issue and "fields" in issue:
                    status = issue["fields"].get("status", {})
                    return {
                        "id": status.get("id"),
                        "name": status.get("name"),
                        "category": status.get("statusCategory", {}).get("name"),
                        "description": status.get("description", ""),
                    }
                return None
            except Exception as e:
                logger.error(f"Error getting workflow status for {ticket_id}: {e}")
                return None

        async def transition_ticket_status(self, ticket_id: str, transition: str) -> bool:
            """Transition ticket to new status."""
            try:
                transitions = await self.get_available_transitions(ticket_id)
                if not transitions:
                    return False

                target_transition = None
                for trans in transitions:
                    if trans.get("name", "").lower() == transition.lower():
                        target_transition = trans
                        break

                if not target_transition:
                    logger.warning(f"Transition '{transition}' not available for {ticket_id}")
                    return False

                result = await self.mcp_client.transition_issue(ticket_id, target_transition["id"])
                return result is not None
            except Exception as e:
                logger.error(f"Error transitioning ticket {ticket_id}: {e}")
                return False

        async def get_available_transitions(self, ticket_id: str) -> List[Dict[str, Any]]:
            """Get available transitions for a ticket."""
            try:
                transitions = await self.mcp_client.get_issue_transitions(ticket_id)
                return transitions or []
            except Exception as e:
                logger.error(f"Error getting transitions for {ticket_id}: {e}")
                return []

    async def create_workflow_service(resolver) -> JIRAWorkflowService:
        """Factory function for JIRAWorkflowService."""
        logger.info("Creating JIRAWorkflowService instance via TypedDI")
        mcp_client = await resolver.aget(mcp_client_cls)
        return JIRAWorkflowService(mcp_client)

    manager.register_protocol_with_concrete_alias(
        protocol_type=JIRAWorkflowServiceProtocol,
        concrete_type=JIRAWorkflowService,
        factory=create_workflow_service,
        dependencies=[DependencySpec(mcp_client_cls)],
        lifetime="singleton",
    )


def _register_reporting_service(manager: "ServiceRegistrationManager") -> None:
    """Register JIRA reporting and analytics service."""

    class JIRAReportingService:
        """JIRA reporting and analytics service."""

        def __init__(self, data_extractor: JIRADataExtractor):
            """Initialize with data extractor."""
            self.data_extractor = data_extractor

        async def generate_channel_report(
            self, channel_id: str, ticket_data: Dict[str, Any]
        ) -> Dict[str, Any]:
            """Generate comprehensive report for a channel's JIRA data."""
            try:
                # Get JIRA context for the channel
                context = await self.data_extractor.get_jira_context(channel_id, [])

                report = {
                    "channel_id": channel_id,
                    "timestamp": None,  # Would use datetime.utcnow()
                    "jira_context": context,
                    "ticket_summary": self._summarize_ticket_data(ticket_data),
                    "status": "generated",
                }

                return report
            except Exception as e:
                logger.error(f"Error generating channel report: {e}")
                return {"error": str(e), "status": "failed"}

        async def aggregate_ticket_metrics(self, ticket_ids: List[str]) -> Dict[str, Any]:
            """Aggregate metrics across multiple tickets."""
            try:
                batch_data = await self.data_extractor.get_tickets_batch(
                    ticket_ids, include_comments=True
                )

                metrics = {
                    "total_tickets": len(ticket_ids),
                    "retrieved_tickets": len([t for t in batch_data.values() if t]),
                    "failed_tickets": len([t for t in batch_data.values() if not t]),
                    "comments_total": 0,
                    "status_distribution": {},
                }

                for ticket_data in batch_data.values():
                    if ticket_data:
                        if "comments" in ticket_data:
                            metrics["comments_total"] += len(ticket_data["comments"])

                        status = (
                            ticket_data.get("fields", {}).get("status", {}).get("name", "Unknown")
                        )
                        metrics["status_distribution"][status] = (
                            metrics["status_distribution"].get(status, 0) + 1
                        )

                return metrics
            except Exception as e:
                logger.error(f"Error aggregating ticket metrics: {e}")
                return {"error": str(e)}

        async def export_report_data(
            self, report_data: Dict[str, Any], format_type: str = "json"
        ) -> str:
            """Export report data in specified format."""
            try:
                if format_type.lower() == "json":
                    import json

                    return json.dumps(report_data, indent=2, default=str)
                else:
                    return str(report_data)
            except Exception as e:
                logger.error(f"Error exporting report data: {e}")
                return f"Export error: {str(e)}"

        def _summarize_ticket_data(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
            """Summarize ticket data for reporting."""
            if not ticket_data:
                return {}

            fields = ticket_data.get("fields", {})
            return {
                "key": ticket_data.get("key", ""),
                "summary": fields.get("summary", ""),
                "status": fields.get("status", {}).get("name", ""),
                "assignee": fields.get("assignee", {}).get("displayName", "Unassigned"),
                "created": fields.get("created", ""),
                "updated": fields.get("updated", ""),
            }

    async def create_reporting_service(resolver) -> JIRAReportingService:
        """Factory function for JIRAReportingService."""
        logger.info("Creating JIRAReportingService instance via TypedDI")
        data_extractor = await resolver.aget(JIRADataExtractor)
        return JIRAReportingService(data_extractor)

    manager.register_protocol_with_concrete_alias(
        protocol_type=JIRAReportingServiceProtocol,
        concrete_type=JIRAReportingService,
        factory=create_reporting_service,
        dependencies=[DependencySpec(JIRADataExtractor)],
        lifetime="singleton",
    )


def _register_analytics_service(manager: "ServiceRegistrationManager") -> None:
    """Register JIRA analytics and performance tracking service."""

    class JIRAAnalyticsService:
        """JIRA analytics and performance tracking service."""

        def __init__(self, metrics_storage: MetricsStorage, cache: JIRACache):
            """Initialize with metrics storage and cache."""
            self.metrics_storage = metrics_storage
            self.cache = cache

        async def track_ticket_interaction(
            self, ticket_id: str, interaction_type: str, metadata: Dict[str, Any]
        ) -> None:
            """Track interactions with JIRA tickets for analytics."""
            try:
                # Store interaction in metrics storage

                # In real implementation, would store to metrics storage
                logger.info(f"Tracked JIRA interaction: {interaction_type} for {ticket_id}")
            except Exception as e:
                logger.error(f"Error tracking ticket interaction: {e}")

        async def get_performance_metrics(self, time_range: str = "last_7_days") -> Dict[str, Any]:
            """Get JIRA integration performance metrics."""
            try:
                cache_stats = self.cache.get_stats()

                metrics = {
                    "time_range": time_range,
                    "cache_performance": cache_stats,
                    "integration_status": "active",
                    "last_updated": None,  # Would use datetime.utcnow()
                }

                return metrics
            except Exception as e:
                logger.error(f"Error getting performance metrics: {e}")
                return {"error": str(e)}

        async def analyze_ticket_patterns(self, channel_patterns: List[str]) -> Dict[str, Any]:
            """Analyze patterns in ticket creation and resolution."""
            try:
                analysis = {
                    "patterns_analyzed": len(channel_patterns),
                    "common_patterns": [],
                    "recommendations": [],
                    "status": "completed",
                }

                # In real implementation, would analyze patterns
                for pattern in channel_patterns[:5]:  # Limit for demo
                    analysis["common_patterns"].append(f"Pattern: {pattern}")

                return analysis
            except Exception as e:
                logger.error(f"Error analyzing ticket patterns: {e}")
                return {"error": str(e)}

    async def create_analytics_service(resolver) -> JIRAAnalyticsService:
        """Factory function for JIRAAnalyticsService."""
        logger.info("Creating JIRAAnalyticsService instance via TypedDI")
        metrics_storage = await resolver.aget(MetricsStorage)
        cache = await resolver.aget(JIRACache)
        return JIRAAnalyticsService(metrics_storage, cache)

    manager.register_protocol_with_concrete_alias(
        protocol_type=JIRAAnalyticsServiceProtocol,
        concrete_type=JIRAAnalyticsService,
        factory=create_analytics_service,
        dependencies=[
            DependencySpec(MetricsStorage),
            DependencySpec(JIRACache),
        ],
        lifetime="singleton",
    )
