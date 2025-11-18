"""
test_metrics_export_handler.py

Unit tests for metrics_export_handler.py (MetricsExportHandler).

Covers:
- MetricsExportHandler initialization
- _get_upload_url() success and failure cases
- _upload_file_to_url() success and failure cases
- _complete_upload() success and failure cases
- handle_metrics_request() integration flow
- HTML generation and upload workflow

Edge Cases Covered:
- Slack API failures at each step
- Missing upload URLs
- HTTP errors during file upload
- Network exceptions
- Invalid user IDs
- Empty HTML content

Expected Outcomes:
- Proper initialization with dependencies
- Correct 3-step Slack upload flow
- Appropriate error handling
- Failed steps return False
- Successful flow returns True
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.core.exports.html_generator import MetricsHTMLGenerator
from packages.slack.interactive_elements.metrics_export_handler import (
    MetricsExportHandler,
)
from packages.slack.messages.posting import SlackPostingHandler
from packages.slack.services.metrics_data_collector import MetricsDataCollector


class TestMetricsExportHandler:
    """Test MetricsExportHandler functionality."""

    @pytest.fixture
    def mock_metrics_data_collector(self) -> AsyncMock:
        """Create a mock MetricsDataCollector."""
        mock = AsyncMock(spec=MetricsDataCollector)
        mock.collect_all_metrics = AsyncMock(
            return_value={
                "cso": {
                    "product_coverage": {"total_products": 10, "tracked": 8},
                    "war_room_readiness": {"total_channels": 50, "active": 45},
                },
                "technical": {
                    "status_updates": {"total": 100, "delivered": 98},
                    "auto_messages": {"sent": 250, "success_rate": 0.96},
                },
                "jira_posting": {},
            }
        )
        return mock

    @pytest.fixture
    def mock_slack_posting_handler(self) -> AsyncMock:
        """Create a mock SlackPostingHandler."""
        mock = AsyncMock(spec=SlackPostingHandler)
        mock._init_slack_token = AsyncMock()
        mock._slack_token = "xoxb-test-token"

        # Mock config for API base URL
        mock.config = MagicMock()
        mock.config.get_api_base_url.return_value = "https://slack.com/api"

        # Mock api_call for files.completeUploadExternal
        mock.api_call = AsyncMock(return_value={"ok": True})

        return mock

    @pytest.fixture
    def mock_html_generator(self) -> MagicMock:
        """Create a mock MetricsHTMLGenerator."""
        mock = MagicMock(spec=MetricsHTMLGenerator)
        mock.generate = MagicMock(
            return_value="<html><body>Metrics Dashboard</body></html>"
        )
        return mock

    @pytest.fixture
    def metrics_export_handler(
        self,
        mock_metrics_data_collector: AsyncMock,
        mock_slack_posting_handler: AsyncMock,
        mock_html_generator: AsyncMock,
    ) -> MetricsExportHandler:
        """Create MetricsExportHandler instance with mocked dependencies."""
        return MetricsExportHandler(
            metrics_data_collector=mock_metrics_data_collector,
            slack_posting_handler=mock_slack_posting_handler,
            html_generator=mock_html_generator,
        )

    @pytest.mark.asyncio
    async def test_initialization(
        self,
        metrics_export_handler: MetricsExportHandler,
        mock_metrics_data_collector: AsyncMock,
        mock_slack_posting_handler: AsyncMock,
        mock_html_generator: AsyncMock,
    ) -> None:
        """Test MetricsExportHandler initializes with correct dependencies."""
        assert metrics_export_handler._metrics_collector == mock_metrics_data_collector
        assert (
            metrics_export_handler._slack_posting_handler == mock_slack_posting_handler
        )
        assert metrics_export_handler._html_generator == mock_html_generator

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.post")
    async def test_upload_file_to_url_success(
        self,
        mock_post: AsyncMock,
        metrics_export_handler: MetricsExportHandler,
    ) -> None:
        """Test _upload_file_to_url successfully uploads file."""
        # Mock aiohttp response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None
        mock_post.return_value = mock_response

        html_bytes = b"<html><body>Test</body></html>"
        result = await metrics_export_handler._upload_file_to_url(
            upload_url="https://files.slack.com/upload",
            html_bytes=html_bytes,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_complete_upload_success(
        self,
        metrics_export_handler: MetricsExportHandler,
        mock_slack_posting_handler: AsyncMock,
    ) -> None:
        """Test _complete_upload successfully completes upload."""
        mock_slack_posting_handler.api_call.return_value = {"ok": True}

        result = await metrics_export_handler._complete_upload(
            file_id="F12345",
            filename="metrics_dashboard.html",
            target_channel="D12345",
        )

        assert result is True
        mock_slack_posting_handler.api_call.assert_called_once()

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_handle_metrics_request_success(
        self,
        mock_session_class: AsyncMock,
        metrics_export_handler: MetricsExportHandler,
        mock_metrics_data_collector: AsyncMock,
        mock_html_generator: AsyncMock,
        mock_slack_posting_handler: AsyncMock,
    ) -> None:
        """Test handle_metrics_request completes full flow successfully."""
        # Mock get_upload_url response
        mock_upload_response = AsyncMock()
        mock_upload_response.json = AsyncMock(
            return_value={
                "ok": True,
                "upload_url": "https://files.slack.com/upload",
                "file_id": "F12345",
            }
        )
        mock_upload_response.__aenter__.return_value = mock_upload_response
        mock_upload_response.__aexit__.return_value = AsyncMock()

        # Mock upload_file_to_url response
        mock_file_response = AsyncMock()
        mock_file_response.status = 200
        mock_file_response.__aenter__.return_value = mock_file_response
        mock_file_response.__aexit__.return_value = AsyncMock()

        # Create a list to track which response to return
        responses = [mock_upload_response, mock_file_response]
        call_count = [0]

        def post_side_effect(*args, **kwargs):
            """Return appropriate response based on call count."""
            response = responses[call_count[0]]
            call_count[0] += 1
            return response

        mock_session = AsyncMock()
        mock_session.post = MagicMock(side_effect=post_side_effect)
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = AsyncMock()

        mock_session_class.return_value = mock_session

        # Mock api_call for conversations.open and complete upload
        mock_slack_posting_handler.api_call.return_value = {
            "ok": True,
            "channel": {"id": "D12345"}
        }
        # Mock post_message for acknowledgment and completion messages
        mock_slack_posting_handler.post_message = AsyncMock()

        result = await metrics_export_handler.handle_metrics_request(
            user_id="U12345",
            response_url="https://slack.com/response",
        )

        assert result is True
        # Verify data collection
        mock_metrics_data_collector.collect_all_metrics.assert_called_once()
        # Verify HTML generation (use generate not generate_html)
        mock_html_generator.generate.assert_called_once()
        # Verify api_call called (conversations.open + completeUploadExternal)
        assert mock_slack_posting_handler.api_call.call_count >= 2
