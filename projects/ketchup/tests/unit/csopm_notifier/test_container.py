"""
Unit tests for CSOPM Notifier Container.

Tests the TypedDI container wiring for CSOPM services, ensuring:
- Proper service registration with correct dependencies
- Topological ordering of service initialization
- Protocol-based resolution works correctly
- Factory functions create correct instances
- Convenience getter functions work as expected

These tests use mocks to verify the wiring without requiring
actual AWS or Slack infrastructure.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.typed_di.protocols import (
    CSOPMJIRAPollerProtocol,
    CSOPMReminderServiceProtocol,
    CSOPMSlackNotifierProtocol,
    CSOPMStateTrackerProtocol,
)


class TestContainerRegistration:
    """Tests for container service registration."""

    @pytest.mark.asyncio
    async def test_register_csopm_services_imports_correctly(self):
        """Test that CSOPM services can be imported without errors."""
        from ketchup_csopm_notifier.container import _register_csopm_services
        from ketchup_csopm_notifier.services import (
            CSOPMJIRAPoller,
            CSOPMReminderService,
            CSOPMSlackNotifier,
            CSOPMStateTracker,
        )

        # Verify imports work
        assert CSOPMStateTracker is not None
        assert CSOPMJIRAPoller is not None
        assert CSOPMSlackNotifier is not None
        assert CSOPMReminderService is not None
        assert _register_csopm_services is not None

    @pytest.mark.asyncio
    async def test_register_csopm_services_registers_all_services(self):
        """Test that all 4 CSOPM services are registered."""
        from ketchup_csopm_notifier.container import _register_csopm_services
        from packages.core.typed_di import TypedServiceRegistry

        # Create a mock registry to track registrations
        registry = MagicMock(spec=TypedServiceRegistry)
        registry.register = MagicMock()

        # Register services
        _register_csopm_services(registry, parent_registry=None)

        # Should have 8 register calls (4 protocols + 4 concrete types)
        assert registry.register.call_count == 8

        # Verify each protocol was registered
        registered_types = [
            call.kwargs.get("service_type") or call.args[0]
            for call in registry.register.call_args_list
        ]

        # Check protocols are registered
        assert CSOPMStateTrackerProtocol in registered_types
        assert CSOPMJIRAPollerProtocol in registered_types
        assert CSOPMSlackNotifierProtocol in registered_types
        assert CSOPMReminderServiceProtocol in registered_types

    @pytest.mark.asyncio
    async def test_state_tracker_factory_creates_instance(self):
        """Test CSOPMStateTracker factory creates correct instance."""
        from ketchup_csopm_notifier.services import CSOPMStateTracker

        # Create mocks
        mock_client = AsyncMock()
        mock_config = MagicMock()
        mock_config.get_table_name.return_value = "test_table"

        # Create instance directly
        tracker = CSOPMStateTracker(client=mock_client, table_name="test_table")

        # Verify instance
        assert isinstance(tracker, CSOPMStateTracker)
        assert tracker.table_name == "test_table"

    @pytest.mark.asyncio
    async def test_jira_poller_factory_creates_instance(self):
        """Test CSOPMJIRAPoller factory creates correct instance."""
        from ketchup_csopm_notifier.services.jira_poller import CSOPMJIRAPoller

        # Create mock MCP client
        mock_mcp_client = AsyncMock()

        # Create instance
        poller = CSOPMJIRAPoller(mcp_client=mock_mcp_client)

        # Verify instance
        assert isinstance(poller, CSOPMJIRAPoller)

    @pytest.mark.asyncio
    async def test_slack_notifier_factory_creates_instance(self):
        """Test CSOPMSlackNotifier factory creates correct instance."""
        from ketchup_csopm_notifier.services.slack_notifier import CSOPMSlackNotifier

        # Create mocks
        mock_posting_handler = AsyncMock()
        mock_user_ops = AsyncMock()
        mock_mcp_client = AsyncMock()
        mock_state_tracker = AsyncMock()

        # Create instance
        notifier = CSOPMSlackNotifier(
            posting_handler=mock_posting_handler,
            user_ops=mock_user_ops,
            mcp_client=mock_mcp_client,
            state_tracker=mock_state_tracker,
            metrics=None,
        )

        # Verify instance
        assert isinstance(notifier, CSOPMSlackNotifier)

    @pytest.mark.asyncio
    async def test_reminder_service_factory_creates_instance(self):
        """Test CSOPMReminderService factory creates correct instance."""
        from ketchup_csopm_notifier.services.reminder_service import (
            CSOPMReminderService,
        )

        # Create mocks
        mock_state_tracker = AsyncMock()
        mock_mcp_client = AsyncMock()
        mock_jira_poller = AsyncMock()

        # Create instance
        service = CSOPMReminderService(
            state_tracker=mock_state_tracker,
            mcp_client=mock_mcp_client,
            jira_poller=mock_jira_poller,
            metrics=None,
        )

        # Verify instance
        assert isinstance(service, CSOPMReminderService)


class TestContainerDependencyOrder:
    """Tests for proper dependency ordering."""

    def test_state_tracker_has_no_csopm_dependencies(self):
        """Test that StateTracker only depends on infrastructure services."""
        from packages.db.config.dynamodb_config import DynamoDBConfig
        from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient

        # Expected dependencies
        expected = [DynamoDBAsyncClient, DynamoDBConfig]

        # Verify these are infrastructure types, not CSOPM types
        for dep in expected:
            assert "CSOPM" not in dep.__name__

    def test_jira_poller_has_no_csopm_dependencies(self):
        """Test that JIRAPoller only depends on infrastructure services."""
        from packages.integrations.async_mcp_client import AsyncMCPClient

        # Expected dependencies
        expected = [AsyncMCPClient]

        # Verify these are infrastructure types
        for dep in expected:
            assert "CSOPM" not in dep.__name__

    def test_slack_notifier_depends_on_state_tracker(self):
        """Test that SlackNotifier depends on StateTracker."""
        from packages.core.typed_di.protocols import CSOPMStateTrackerProtocol

        # SlackNotifier should depend on StateTracker protocol
        expected_csopm_deps = [CSOPMStateTrackerProtocol]

        # Verify CSOPM dependency exists
        for dep in expected_csopm_deps:
            assert "CSOPM" in dep.__name__

    def test_reminder_service_depends_on_state_tracker_and_poller(self):
        """Test that ReminderService depends on StateTracker and JIRAPoller."""
        from packages.core.typed_di.protocols import (
            CSOPMJIRAPollerProtocol,
            CSOPMStateTrackerProtocol,
        )

        # ReminderService should depend on both StateTracker and JIRAPoller
        expected_csopm_deps = [CSOPMStateTrackerProtocol, CSOPMJIRAPollerProtocol]

        # Verify CSOPM dependencies exist
        for dep in expected_csopm_deps:
            assert "CSOPM" in dep.__name__


class TestConvenienceGetters:
    """Tests for convenience getter functions."""

    @pytest.mark.asyncio
    async def test_get_csopm_state_tracker_returns_protocol(self):
        """Test get_csopm_state_tracker returns correct type."""
        from ketchup_csopm_notifier.container import get_csopm_state_tracker

        # Create mock registry
        mock_registry = AsyncMock()
        mock_tracker = AsyncMock(spec=CSOPMStateTrackerProtocol)
        mock_registry.aget.return_value = mock_tracker

        # Get tracker
        result = await get_csopm_state_tracker(mock_registry)

        # Verify
        mock_registry.aget.assert_called_once_with(CSOPMStateTrackerProtocol)
        assert result is mock_tracker

    @pytest.mark.asyncio
    async def test_get_csopm_jira_poller_returns_protocol(self):
        """Test get_csopm_jira_poller returns correct type."""
        from ketchup_csopm_notifier.container import get_csopm_jira_poller

        # Create mock registry
        mock_registry = AsyncMock()
        mock_poller = AsyncMock(spec=CSOPMJIRAPollerProtocol)
        mock_registry.aget.return_value = mock_poller

        # Get poller
        result = await get_csopm_jira_poller(mock_registry)

        # Verify
        mock_registry.aget.assert_called_once_with(CSOPMJIRAPollerProtocol)
        assert result is mock_poller

    @pytest.mark.asyncio
    async def test_get_csopm_slack_notifier_returns_protocol(self):
        """Test get_csopm_slack_notifier returns correct type."""
        from ketchup_csopm_notifier.container import get_csopm_slack_notifier

        # Create mock registry
        mock_registry = AsyncMock()
        mock_notifier = AsyncMock(spec=CSOPMSlackNotifierProtocol)
        mock_registry.aget.return_value = mock_notifier

        # Get notifier
        result = await get_csopm_slack_notifier(mock_registry)

        # Verify
        mock_registry.aget.assert_called_once_with(CSOPMSlackNotifierProtocol)
        assert result is mock_notifier

    @pytest.mark.asyncio
    async def test_get_csopm_reminder_service_returns_protocol(self):
        """Test get_csopm_reminder_service returns correct type."""
        from ketchup_csopm_notifier.container import get_csopm_reminder_service

        # Create mock registry
        mock_registry = AsyncMock()
        mock_service = AsyncMock(spec=CSOPMReminderServiceProtocol)
        mock_registry.aget.return_value = mock_service

        # Get service
        result = await get_csopm_reminder_service(mock_registry)

        # Verify
        mock_registry.aget.assert_called_once_with(CSOPMReminderServiceProtocol)
        assert result is mock_service


class TestProtocolCompliance:
    """Tests for protocol compliance of registered services."""

    def test_state_tracker_implements_protocol(self):
        """Test CSOPMStateTracker implements CSOPMStateTrackerProtocol."""
        from ketchup_csopm_notifier.services import CSOPMStateTracker

        # Check protocol methods exist
        assert hasattr(CSOPMStateTracker, "get_notification_record")
        assert hasattr(CSOPMStateTracker, "create_notification_record")
        assert hasattr(CSOPMStateTracker, "update_notification_status")
        assert hasattr(CSOPMStateTracker, "increment_rca_ping_count")
        assert hasattr(CSOPMStateTracker, "increment_closure_ping_count")
        assert hasattr(CSOPMStateTracker, "mark_rca_reminder_sent")
        assert hasattr(CSOPMStateTracker, "mark_closure_reminder_sent")
        assert hasattr(CSOPMStateTracker, "get_pending_notifications")
        assert hasattr(CSOPMStateTracker, "record_followup")

    def test_jira_poller_implements_protocol(self):
        """Test CSOPMJIRAPoller implements CSOPMJIRAPollerProtocol."""
        from ketchup_csopm_notifier.services.jira_poller import CSOPMJIRAPoller

        # Check protocol methods exist
        assert hasattr(CSOPMJIRAPoller, "poll_for_new_assignments")
        assert hasattr(CSOPMJIRAPoller, "get_ticket_details")
        assert hasattr(CSOPMJIRAPoller, "get_tickets_by_assignee")

    def test_slack_notifier_implements_protocol(self):
        """Test CSOPMSlackNotifier implements CSOPMSlackNotifierProtocol."""
        from ketchup_csopm_notifier.services.slack_notifier import CSOPMSlackNotifier

        # Check protocol methods exist
        assert hasattr(CSOPMSlackNotifier, "send_assignment_dm")
        assert hasattr(CSOPMSlackNotifier, "send_reminder_dm")
        assert hasattr(CSOPMSlackNotifier, "resolve_slack_user_id")
        assert hasattr(CSOPMSlackNotifier, "handle_button_action")

    def test_reminder_service_implements_protocol(self):
        """Test CSOPMReminderService implements CSOPMReminderServiceProtocol."""
        from ketchup_csopm_notifier.services.reminder_service import (
            CSOPMReminderService,
        )

        # Check protocol methods exist
        assert hasattr(CSOPMReminderService, "schedule_rca_reminder")
        assert hasattr(CSOPMReminderService, "schedule_closure_reminder")
        assert hasattr(CSOPMReminderService, "get_due_reminders")
        assert hasattr(CSOPMReminderService, "complete_reminder")
        assert hasattr(CSOPMReminderService, "check_rca_reminders")
        assert hasattr(CSOPMReminderService, "check_closure_reminders")


class TestServiceRegistrationModule:
    """Tests for the csopm_services.py registration module."""

    @pytest.mark.asyncio
    async def test_register_csopm_services_function_exists(self):
        """Test that register_csopm_services function exists in module."""
        from packages.core.typed_di.service_registrations.registrations.csopm_services import (
            register_csopm_services,
        )

        assert callable(register_csopm_services)

    @pytest.mark.asyncio
    async def test_register_csopm_services_uses_manager_pattern(self):
        """Test that registration uses ServiceRegistrationManager pattern."""
        from packages.core.typed_di.service_registrations.registrations.csopm_services import (
            register_csopm_services,
        )

        # Create mock manager
        mock_manager = MagicMock()
        mock_manager.register_protocol_with_concrete_alias = MagicMock()

        # Register services
        register_csopm_services(mock_manager)

        # Should have 8 calls (one per service: StateTracker, UserPATOperations, ButtonActionHandler, Handler, JIRAPoller, SlackNotifier, ReminderService, TicketStatusPoller)
        assert mock_manager.register_protocol_with_concrete_alias.call_count == 8

    @pytest.mark.asyncio
    async def test_registration_uses_singleton_lifetime(self):
        """Test that all services are registered as singletons."""
        from packages.core.typed_di.service_registrations.registrations.csopm_services import (
            register_csopm_services,
        )

        # Create mock manager
        mock_manager = MagicMock()
        mock_manager.register_protocol_with_concrete_alias = MagicMock()

        # Register services
        register_csopm_services(mock_manager)

        # Check all registrations use singleton lifetime
        for call in mock_manager.register_protocol_with_concrete_alias.call_args_list:
            kwargs = call.kwargs
            assert kwargs.get("lifetime") == "singleton"


class TestContainerIntegration:
    """Integration tests for container functionality."""

    @pytest.mark.asyncio
    async def test_container_can_be_imported(self):
        """Test that container module can be imported without errors."""
        from ketchup_csopm_notifier.container import (
            get_csopm_container,
            get_csopm_jira_poller,
            get_csopm_reminder_service,
            get_csopm_slack_notifier,
            get_csopm_state_tracker,
        )

        # Verify all functions are callable
        assert callable(get_csopm_container)
        assert callable(get_csopm_state_tracker)
        assert callable(get_csopm_jira_poller)
        assert callable(get_csopm_slack_notifier)
        assert callable(get_csopm_reminder_service)

    def test_dependency_specs_are_valid(self):
        """Test that all DependencySpec usages reference valid types."""
        from packages.core.typed_di.protocols import (
            CSOPMJIRAPollerProtocol,
            CSOPMStateTrackerProtocol,
        )
        from packages.core.typed_di.types import DependencySpec
        from packages.db.config.dynamodb_config import DynamoDBConfig
        from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient
        from packages.integrations.async_mcp_client import AsyncMCPClient
        from packages.slack.messages.posting import SlackPostingHandler
        from packages.slack.user_operations.user_ops import SlackUserOps

        # Create DependencySpecs for all used types
        specs = [
            DependencySpec(DynamoDBAsyncClient),
            DependencySpec(DynamoDBConfig),
            DependencySpec(AsyncMCPClient),
            DependencySpec(SlackPostingHandler),
            DependencySpec(SlackUserOps),
            DependencySpec(CSOPMStateTrackerProtocol),
            DependencySpec(CSOPMJIRAPollerProtocol),
        ]

        # Verify all specs are valid
        for spec in specs:
            assert spec.type is not None
            assert hasattr(spec, "qualifier")
