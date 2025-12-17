"""
Integration tests for the JIRA reporter end-to-end flow.

Tests the complete flow from archived channel detection to JIRA comment posting
using mocked external services but real internal components.
"""

import json
import os

# Import test configuration
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ketchup_unified_scheduler.services.jira_reporter.channel_monitor import ChannelMonitor
from ketchup_unified_scheduler.services.jira_reporter.report_generator import ReportGenerator
from ketchup_unified_scheduler.services.jira_reporter.service import (
    JiraService,
    process_channel,
    run_reporting_cycle,
)
from ketchup_unified_scheduler.services.jira_reporter.ticket_discovery import JiraTicketDiscovery

sys.path.append(os.path.join(os.path.dirname(__file__), "../../unit/test_jira_reporter"))
from test_config import TEST_CHANNELS, TEST_JIRA_TICKETS, TEST_MESSAGES


@pytest.mark.asyncio
class TestEndToEndFlow:
    """Test the complete JIRA reporter flow."""

    @pytest.fixture
    def mock_dynamodb_store(self):
        """Create a mock DynamoDB store with test data."""
        store = MagicMock()
        store.channel_ops = MagicMock()

        # Return test channels for get_channels_needing_jira_reports
        test_channels = [
            TEST_CHANNELS["with_existing_ticket"],
            TEST_CHANNELS["with_exigence_id"],
            TEST_CHANNELS["cso_no_ticket"],
        ]
        store.channel_ops.get_channels_needing_jira_reports = AsyncMock(return_value=test_channels)
        store.channel_ops.update_jira_report_status = AsyncMock()
        store.update_channel_metadata = AsyncMock()

        return store

    @pytest.fixture
    def mock_openai_handler(self):
        """Create a mock OpenAI handler that generates test reports."""
        handler = MagicMock()
        handler.generate_response = AsyncMock(
            return_value="""
h3. Executive Summary
Test incident report generated for integration testing.

h3. People Involved
- Test User 1: Identified issue
- Test User 2: Implemented fix

h3. Incident Timeline
- 2024-01-01 00:00:00 UTC: Issue reported
- 2024-01-01 00:05:00 UTC: Issue resolved

h3. Resolution & Mitigation
Test resolution for integration testing.
"""
        )
        return handler

    @pytest.fixture
    def mock_msg_ops(self):
        """Create mock message operations."""
        ops = MagicMock()
        ops.fetch_channel_messages = AsyncMock(return_value=TEST_MESSAGES)
        return ops

    @pytest.fixture
    def mock_jira_tool(self):
        """Create mock JIRA tool for discovery."""
        tool = MagicMock()
        # Return CSOPM ticket for Exigence URL search
        tool._arun = AsyncMock(
            return_value=json.dumps({"issues": [{"key": TEST_JIRA_TICKETS["CSOPM"]}]})
        )
        return tool

    async def test_process_channel_with_existing_ticket(
        self, mock_dynamodb_store, mock_openai_handler, mock_msg_ops, mock_jira_tool
    ):
        """Test processing a channel that already has a JIRA ticket."""
        # Arrange
        channel_data = TEST_CHANNELS["with_existing_ticket"]

        report_generator = ReportGenerator(
            openai_handler=mock_openai_handler, channel_msg_ops=mock_msg_ops
        )

        # Create JIRA discovery service
        jira_discovery = JiraTicketDiscovery(mcp_client=mock_jira_tool)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = AsyncMock(status_code=200)  # Ticket exists
            mock_client.post.return_value = AsyncMock(status_code=200)  # Comment posted

            jira_service = JiraService(secrets_manager=MagicMock(), ims_token_manager=MagicMock())

            # Act
            result = await process_channel(
                channel_data=channel_data,
                report_generator=report_generator,
                jira_service=jira_service,
                jira_discovery=jira_discovery,
                dynamodb_store=mock_dynamodb_store,
            )

            # Assert
            assert result is True

            # Verify status updates
            status_calls = mock_dynamodb_store.channel_ops.update_jira_report_status.call_args_list
            assert len(status_calls) == 2
            assert status_calls[0].kwargs["status"] == "PROCESSING"
            assert status_calls[1].kwargs["status"] == "PROCESSED"

            # Verify JIRA comment was posted
            post_call = mock_client.post.call_args
            payload = post_call.kwargs["json"]
            assert payload["issueIdOrKey"] == TEST_JIRA_TICKETS["CPGNREQ"]
            assert "Executive Summary" in payload["comment"]["body"]

    async def test_process_channel_with_discovery(
        self, mock_dynamodb_store, mock_openai_handler, mock_msg_ops, mock_jira_tool
    ):
        """Test processing a channel that needs JIRA ticket discovery."""
        # Arrange
        channel_data = TEST_CHANNELS["with_exigence_id"].copy()

        # Create services
        jira_discovery = JiraTicketDiscovery(jira_search_tool=mock_jira_tool)
        ChannelMonitor(dynamodb_store=mock_dynamodb_store, jira_discovery=jira_discovery)

        # Test discovery first
        discovered_ticket = await jira_discovery.discover_jira_ticket(
            channel_name=channel_data["channel_name"], channel_metadata=channel_data
        )

        assert discovered_ticket == TEST_JIRA_TICKETS["CSOPM"]

        # Update channel data with discovered ticket
        channel_data["jira_ticket"] = discovered_ticket

        # Now test the full processing
        report_generator = ReportGenerator(
            openai_handler=mock_openai_handler, channel_msg_ops=mock_msg_ops
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = AsyncMock(status_code=200)
            mock_client.post.return_value = AsyncMock(status_code=200)

            jira_service = JiraService(secrets_manager=MagicMock(), ims_token_manager=MagicMock())

            # Act
            result = await process_channel(
                channel_data=channel_data,
                report_generator=report_generator,
                jira_service=jira_service,
                jira_discovery=jira_discovery,
                dynamodb_store=mock_dynamodb_store,
            )

            # Assert
            assert result is True

            # Verify JIRA comment includes discovered ticket
            post_call = mock_client.post.call_args
            payload = post_call.kwargs["json"]
            assert payload["issueIdOrKey"] == TEST_JIRA_TICKETS["CSOPM"]

    async def test_full_reporting_cycle(
        self, mock_dynamodb_store, mock_openai_handler, mock_msg_ops, mock_jira_tool
    ):
        """Test a complete reporting cycle with multiple channels."""
        # Arrange
        with (
            patch(
                "ketchup_unified_scheduler.services.jira_reporter.service.get_container"
            ) as mock_get_container,
            patch(
                "ketchup_unified_scheduler.services.jira_reporter.service.initialize_all_clients"
            ) as mock_init_clients,
            patch(
                "ketchup_unified_scheduler.services.jira_reporter.service.cleanup_all_clients"
            ) as mock_cleanup_clients,
            patch("httpx.AsyncClient") as mock_client_class,
        ):

            # Setup mocks
            mock_container = MagicMock()
            mock_get_container.return_value = mock_container
            mock_init_clients.return_value = None
            mock_cleanup_clients.return_value = None

            # Configure container to return our mocked services
            mock_container.resolve.side_effect = lambda key: {
                "dynamodb_store": mock_dynamodb_store,
                "openai_handler": mock_openai_handler,
                "msg_ops": mock_msg_ops,
                "secrets_manager": MagicMock(),
                "jira_mcp_tool": mock_jira_tool,
            }.get(key)

            # Setup HTTP client mock
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = AsyncMock(status_code=200)
            mock_client.post.return_value = AsyncMock(status_code=200)

            # Act
            await run_reporting_cycle()

            # Assert
            # Verify channels were fetched
            mock_dynamodb_store.channel_ops.get_channels_needing_jira_reports.assert_called_once()

            # Verify status updates were made
            status_updates = (
                mock_dynamodb_store.channel_ops.update_jira_report_status.call_args_list
            )
            assert len(status_updates) > 0

            # Verify cleanup was called
            mock_cleanup_clients.assert_called_once()

    async def test_error_handling_in_process_channel(
        self, mock_dynamodb_store, mock_openai_handler, mock_msg_ops, mock_jira_tool
    ):
        """Test error handling when report generation fails."""
        # Arrange
        channel_data = TEST_CHANNELS["with_existing_ticket"]

        # Make report generation fail
        mock_openai_handler.generate_response.return_value = None

        report_generator = ReportGenerator(
            openai_handler=mock_openai_handler, channel_msg_ops=mock_msg_ops
        )

        # Create JIRA discovery service
        jira_discovery = JiraTicketDiscovery(mcp_client=mock_jira_tool)

        jira_service = JiraService(secrets_manager=MagicMock(), ims_token_manager=MagicMock())

        # Act
        result = await process_channel(
            channel_data=channel_data,
            report_generator=report_generator,
            jira_service=jira_service,
            jira_discovery=jira_discovery,
            dynamodb_store=mock_dynamodb_store,
        )

        # Assert
        assert result is False

        # Verify status was set to FAILED
        last_status_call = mock_dynamodb_store.channel_ops.update_jira_report_status.call_args_list[
            -1
        ]
        assert last_status_call.kwargs["status"] == "FAILED"

    async def test_batch_processing(self, mock_dynamodb_store):
        """Test batch processing of multiple channels."""
        # Arrange
        # Create 10 test channels
        many_channels = []
        for i in range(10):
            channel = TEST_CHANNELS["with_existing_ticket"].copy()
            channel["channel_id"] = f"C_TEST_{i:03d}"
            channel["channel_name"] = f"cso_20240101{i:04d}_test_{i}"
            many_channels.append(channel)

        mock_dynamodb_store.channel_ops.get_channels_needing_jira_reports.return_value = (
            many_channels
        )

        # Track processed channels
        processed_channels = []

        async def mock_process(channel_data, **kwargs):
            processed_channels.append(channel_data["channel_id"])
            return True

        with (
            patch(
                "ketchup_unified_scheduler.services.jira_reporter.service.process_channel",
                side_effect=mock_process,
            ),
            patch("ketchup_unified_scheduler.services.jira_reporter.service.get_container"),
            patch(
                "ketchup_unified_scheduler.services.jira_reporter.service.initialize_all_clients"
            ),
            patch("ketchup_unified_scheduler.services.jira_reporter.service.cleanup_all_clients"),
            patch.dict(os.environ, {"BATCH_SIZE": "3"}),
        ):  # Process 3 at a time

            # Setup container mock
            mock_container = MagicMock()
            mock_container.resolve.side_effect = lambda key: {
                "dynamodb_store": mock_dynamodb_store,
                "openai_handler": MagicMock(),
                "msg_ops": MagicMock(),
                "secrets_manager": MagicMock(),
                "jira_mcp_tool": MagicMock(),
            }.get(key)

            from ketchup_unified_scheduler.services.jira_reporter.service import get_container

            get_container.return_value = mock_container

            # Act
            await run_reporting_cycle()

            # Assert
            assert len(processed_channels) == 10  # All channels processed
            # Verify batching occurred (hard to test exact batching without timing)

    async def test_real_slack_channel_integration(
        self, mock_dynamodb_store, mock_openai_handler, mock_msg_ops, mock_jira_tool
    ):
        """Test with real Slack channel C094DQY7HLH and test JIRA tickets."""
        # Arrange - Use the real Slack channel provided
        real_channel_data = {
            "channel_id": "C094DQY7HLH",
            "channel_name": "cso_202501010001_test_integration_78155",
            "customer_name": "Test Integration Customer",
            "jira_ticket": TEST_JIRA_TICKETS["CPGNREQ"],  # Use the test ticket
            "archived_at": int(time.time()) - 3600,  # Archived 1 hour ago
            "exigence_id": "78155",
            "exigence_url": "https://adobe.app.exigence.io/secure/index.html#/events/78155/situationroom",
        }

        report_generator = ReportGenerator(
            openai_handler=mock_openai_handler, channel_msg_ops=mock_msg_ops
        )

        # Create JIRA discovery service
        jira_discovery = JiraTicketDiscovery(mcp_client=mock_jira_tool)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock JIRA API responses
            mock_client.get.return_value = AsyncMock(
                status_code=200,
                json=AsyncMock(return_value={"key": TEST_JIRA_TICKETS["CPGNREQ"]}),
            )
            mock_client.post.return_value = AsyncMock(
                status_code=200, json=AsyncMock(return_value={"id": "comment-12345"})
            )

            jira_service = JiraService(secrets_manager=MagicMock(), ims_token_manager=MagicMock())

            # Act
            result = await process_channel(
                channel_data=real_channel_data,
                report_generator=report_generator,
                jira_service=jira_service,
                jira_discovery=jira_discovery,
                dynamodb_store=mock_dynamodb_store,
            )

            # Assert
            assert result is True

            # Verify correct channel was processed
            status_calls = mock_dynamodb_store.channel_ops.update_jira_report_status.call_args_list
            assert any(
                call.kwargs["channel_id"] == "C094DQY7HLH" and call.kwargs["status"] == "PROCESSED"
                for call in status_calls
            )

            # Verify JIRA comment was posted to the correct ticket
            post_call = mock_client.post.call_args
            assert TEST_JIRA_TICKETS["CPGNREQ"] in str(post_call)

            # Test with the second JIRA ticket (CSOPM)
            real_channel_data["jira_ticket"] = TEST_JIRA_TICKETS["CSOPM"]
            result2 = await process_channel(
                channel_data=real_channel_data,
                report_generator=report_generator,
                jira_service=jira_service,
                jira_discovery=jira_discovery,
                dynamodb_store=mock_dynamodb_store,
            )

            assert result2 is True
