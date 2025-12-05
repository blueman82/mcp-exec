"""
test_metrics_command.py

Unit tests for metrics_command.py (MetricsCommand).

Covers:
- MetricsCommand initialization
- Metrics dashboard generation success
- Metrics dashboard generation failure
- Integration with MetricsExportHandler
- Response format validation

Edge Cases Covered:
- Export handler failure
- Missing response_url
- Exception handling during generation

Expected Outcomes:
- Proper initialization with dependencies
- Correct metrics generation flow
- Appropriate status codes and messages
- Error handling
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from packages.secrets.manager import SecretsManager
from packages.slack.command_processing.command_parameters.models import (
    CommandContext,
    CommandType,
    MetricsCommandParams,
)
from packages.slack.command_processing.metrics_command import MetricsCommand
from packages.slack.interactive_elements.metrics_export_handler import MetricsExportHandler
from packages.slack.messages.posting import SlackPostingHandler
from packages.slack.user_operations.user_ops import SlackUserOps


class TestMetricsCommand:
    """Test MetricsCommand functionality."""

    @pytest.fixture
    def mock_slack_posting(self) -> AsyncMock:
        """Create a mock SlackPostingHandler."""
        return AsyncMock(spec=SlackPostingHandler)

    @pytest.fixture
    def mock_metrics_export_handler(self) -> AsyncMock:
        """Create a mock MetricsExportHandler."""
        mock = AsyncMock(spec=MetricsExportHandler)
        mock.handle_metrics_request = AsyncMock(return_value=True)
        return mock

    @pytest.fixture
    def mock_secrets_manager(self) -> AsyncMock:
        """Create a mock SecretsManager."""
        mock = AsyncMock(spec=SecretsManager)
        # Mock admin users list
        mock.get_secret_async = AsyncMock(
            return_value={
                "usage_stats_admin_users": '["Gary Harrison", "Alan O\'Meara", "Nicolas Vallet"]'
            }
        )
        return mock

    @pytest.fixture
    def mock_slack_user_ops(self) -> AsyncMock:
        """Create a mock SlackUserOps."""
        mock = AsyncMock(spec=SlackUserOps)
        # Mock user info with admin user
        mock._fetch_user_info_internal = AsyncMock(
            return_value={"profile": {"real_name": "Gary Harrison", "email": "harrison@adobe.com"}}
        )
        return mock

    @pytest.fixture
    def metrics_command(
        self,
        mock_slack_posting: AsyncMock,
        mock_metrics_export_handler: AsyncMock,
        mock_secrets_manager: AsyncMock,
        mock_slack_user_ops: AsyncMock,
    ) -> MetricsCommand:
        """Create a MetricsCommand instance with mocked dependencies."""
        return MetricsCommand(
            slack_posting_handler=mock_slack_posting,
            metrics_export_handler=mock_metrics_export_handler,
            secrets_manager=mock_secrets_manager,
            slack_user_ops=mock_slack_user_ops,
        )

    @pytest.mark.asyncio
    async def test_initialization(
        self,
        metrics_command: MetricsCommand,
        mock_slack_posting: AsyncMock,
        mock_metrics_export_handler: AsyncMock,
    ) -> None:
        """Test MetricsCommand initializes with correct dependencies."""
        assert metrics_command.posting_handler == mock_slack_posting
        assert metrics_command.metrics_export_handler == mock_metrics_export_handler

    @pytest.mark.asyncio
    async def test_process_metrics_params_success(
        self,
        metrics_command: MetricsCommand,
        mock_metrics_export_handler: AsyncMock,
    ) -> None:
        """Test successful metrics dashboard generation."""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=7)

        params = MetricsCommandParams(
            user_id="U12345",
            user_name="test.user",
            channel_id="D12345",
            command_text="/ketchup metrics",
            response_url="https://slack.com/response",
            original_command="/ketchup metrics",
            command_type=CommandType.METRICS,
            context=CommandContext.DIRECT_MESSAGE,
            time_period_type="7_days",
            start_date=start_date,
            end_date=end_date,
            month=None,
            quarter=None,
            year=end_date.year,
            is_partial=False,
        )

        result = await metrics_command.process_metrics_params(
            params=params,
            user_id="U12345",
            incoming_channel="D12345",
            response_url="https://slack.com/response",
        )

        assert result == {"statusCode": 200, "body": "Metrics dashboard generated"}
        mock_metrics_export_handler.handle_metrics_request.assert_called_once_with(
            user_id="U12345",
            response_url="https://slack.com/response",
            time_params={
                "period_type": "7_days",
                "start_ts": int(start_date.timestamp()),
                "end_ts": int(end_date.timestamp()),
                "month": None,
                "quarter": None,
                "year": end_date.year,
                "is_partial": False,
                "start_date": start_date,
                "end_date": end_date,
            },
        )

    @pytest.mark.asyncio
    async def test_process_metrics_params_failure(
        self,
        metrics_command: MetricsCommand,
        mock_metrics_export_handler: AsyncMock,
    ) -> None:
        """Test metrics dashboard generation failure."""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=7)

        params = MetricsCommandParams(
            user_id="U12345",
            user_name="test.user",
            channel_id="D12345",
            command_text="/ketchup metrics",
            response_url="https://slack.com/response",
            original_command="/ketchup metrics",
            command_type=CommandType.METRICS,
            context=CommandContext.DIRECT_MESSAGE,
            time_period_type="7_days",
            start_date=start_date,
            end_date=end_date,
            month=None,
            quarter=None,
            year=end_date.year,
            is_partial=False,
        )

        # Mock export handler to return failure
        mock_metrics_export_handler.handle_metrics_request.return_value = False

        result = await metrics_command.process_metrics_params(
            params=params,
            user_id="U12345",
            incoming_channel="D12345",
            response_url="https://slack.com/response",
        )

        assert result == {"statusCode": 500, "body": "Failed to generate metrics"}
        mock_metrics_export_handler.handle_metrics_request.assert_called_once_with(
            user_id="U12345",
            response_url="https://slack.com/response",
            time_params={
                "period_type": "7_days",
                "start_ts": int(start_date.timestamp()),
                "end_ts": int(end_date.timestamp()),
                "month": None,
                "quarter": None,
                "year": end_date.year,
                "is_partial": False,
                "start_date": start_date,
                "end_date": end_date,
            },
        )

    @pytest.mark.asyncio
    async def test_process_metrics_params_without_response_url(
        self,
        metrics_command: MetricsCommand,
        mock_metrics_export_handler: AsyncMock,
    ) -> None:
        """Test metrics generation without response URL."""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=7)

        params = MetricsCommandParams(
            user_id="U12345",
            user_name="test.user",
            channel_id="D12345",
            command_text="/ketchup metrics",
            response_url=None,
            original_command="/ketchup metrics",
            command_type=CommandType.METRICS,
            context=CommandContext.DIRECT_MESSAGE,
            time_period_type="7_days",
            start_date=start_date,
            end_date=end_date,
            month=None,
            quarter=None,
            year=end_date.year,
            is_partial=False,
        )

        result = await metrics_command.process_metrics_params(
            params=params,
            user_id="U12345",
            incoming_channel="D12345",
            response_url=None,
        )

        assert result == {"statusCode": 200, "body": "Metrics dashboard generated"}
        mock_metrics_export_handler.handle_metrics_request.assert_called_once_with(
            user_id="U12345",
            response_url=None,
            time_params={
                "period_type": "7_days",
                "start_ts": int(start_date.timestamp()),
                "end_ts": int(end_date.timestamp()),
                "month": None,
                "quarter": None,
                "year": end_date.year,
                "is_partial": False,
                "start_date": start_date,
                "end_date": end_date,
            },
        )

    @pytest.mark.asyncio
    async def test_process_metrics_params_exception_handling(
        self,
        metrics_command: MetricsCommand,
        mock_metrics_export_handler: AsyncMock,
    ) -> None:
        """Test exception handling during metrics generation."""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=7)

        params = MetricsCommandParams(
            user_id="U12345",
            user_name="test.user",
            channel_id="D12345",
            command_text="/ketchup metrics",
            response_url="https://slack.com/response",
            original_command="/ketchup metrics",
            command_type=CommandType.METRICS,
            context=CommandContext.DIRECT_MESSAGE,
            time_period_type="7_days",
            start_date=start_date,
            end_date=end_date,
            month=None,
            quarter=None,
            year=end_date.year,
            is_partial=False,
        )

        # Mock export handler to raise exception
        mock_metrics_export_handler.handle_metrics_request.side_effect = Exception("Test exception")

        # Should propagate exception (no try-except in process_metrics_params)
        with pytest.raises(Exception, match="Test exception"):
            await metrics_command.process_metrics_params(
                params=params,
                user_id="U12345",
                incoming_channel="D12345",
                response_url="https://slack.com/response",
            )

    @pytest.mark.asyncio
    async def test_process_metrics_params_different_users(
        self,
        metrics_command: MetricsCommand,
        mock_metrics_export_handler: AsyncMock,
    ) -> None:
        """Test metrics generation for different users."""
        users = ["U11111", "U22222", "U33333"]
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=7)

        for user_id in users:
            params = MetricsCommandParams(
                user_id=user_id,
                user_name=f"user.{user_id}",
                channel_id=f"D{user_id}",
                command_text="/ketchup metrics",
                response_url=f"https://slack.com/response/{user_id}",
                original_command="/ketchup metrics",
                command_type=CommandType.METRICS,
                context=CommandContext.DIRECT_MESSAGE,
                time_period_type="7_days",
                start_date=start_date,
                end_date=end_date,
                month=None,
                quarter=None,
                year=end_date.year,
                is_partial=False,
            )

            result = await metrics_command.process_metrics_params(
                params=params,
                user_id=user_id,
                incoming_channel=f"D{user_id}",
                response_url=f"https://slack.com/response/{user_id}",
            )

            assert result == {"statusCode": 200, "body": "Metrics dashboard generated"}

        # Verify called for each user
        assert mock_metrics_export_handler.handle_metrics_request.call_count == 3
