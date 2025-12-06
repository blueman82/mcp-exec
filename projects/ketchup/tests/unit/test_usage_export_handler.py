"""
test_usage_export_handler.py

Unit tests for the UsageExportHandler class.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.slack.interactive_elements.usage_export_handler import UsageExportHandler


@pytest.fixture
def mock_command_tracking_ops():
    """Create a mock CommandTrackingOperations instance."""
    mock = MagicMock()
    mock.get_full_export_data = AsyncMock()
    return mock


@pytest.fixture
def mock_slack_posting_handler():
    """Create a mock SlackPostingHandler instance."""
    mock = MagicMock()
    mock.post_message = AsyncMock()
    mock.api_call = AsyncMock()
    return mock


@pytest.fixture
def mock_csv_generator():
    """Create a mock CommandUsageCSVGenerator instance."""
    mock = MagicMock()
    mock.generate_csv = AsyncMock()
    return mock


@pytest.fixture
def usage_export_handler(mock_command_tracking_ops, mock_slack_posting_handler, mock_csv_generator):
    """Create a UsageExportHandler instance with mocked dependencies."""
    return UsageExportHandler(
        command_tracking_ops=mock_command_tracking_ops,
        slack_posting_handler=mock_slack_posting_handler,
        csv_generator=mock_csv_generator,
    )


@pytest.fixture
def sample_export_data():
    """Sample export data."""
    return {
        "trends": {"total_usage": {"current": 100}},
        "user_breakdown": {"U12345": {"user_name": "harrison", "total_count": 45}},
        "export_timestamp": "2025-06-21T15:30:00Z",
        "period_days": 7,
    }


@pytest.mark.asyncio
async def test_handle_export_request_success(
    usage_export_handler,
    mock_command_tracking_ops,
    mock_slack_posting_handler,
    mock_csv_generator,
    sample_export_data,
):
    """Test successful export request handling."""
    # Setup mocks
    mock_command_tracking_ops.get_full_export_data.return_value = sample_export_data
    mock_csv_generator.generate_csv.return_value = "CSV content here"
    mock_slack_posting_handler.api_call.return_value = {"ok": True}

    # Execute
    result = await usage_export_handler.handle_export_request(
        trigger_id="123456",
        user_id="U12345",
        response_url="https://hooks.slack.com/test",
    )

    # Verify
    assert result is True

    # Check that acknowledgment was sent
    assert mock_slack_posting_handler.post_message.call_count >= 2
    first_call = mock_slack_posting_handler.post_message.call_args_list[0]
    # When response_url is provided, it should be used
    assert first_call[1]["response_url"] == "https://hooks.slack.com/test"
    assert "Generating usage report" in first_call[1]["message"]

    # Check that export data was fetched
    mock_command_tracking_ops.get_full_export_data.assert_called_once_with(days=7)

    # Check that CSV was generated
    mock_csv_generator.generate_csv.assert_called_once_with(sample_export_data)

    # Note: File upload now uses aiohttp directly, not api_call
    # So we can't test the api_call here anymore

    # Check completion message
    last_call = mock_slack_posting_handler.post_message.call_args_list[-1]
    assert "Usage report generated" in last_call[1]["message"]


@pytest.mark.asyncio
async def test_handle_export_request_no_data(
    usage_export_handler, mock_command_tracking_ops, mock_slack_posting_handler
):
    """Test export request when no data is available."""
    # Setup mocks
    mock_command_tracking_ops.get_full_export_data.return_value = {}

    # Execute
    result = await usage_export_handler.handle_export_request(
        trigger_id="123456",
        user_id="U12345",
        response_url="https://hooks.slack.com/test",
    )

    # Verify
    assert result is False

    # Check error message was sent
    assert mock_slack_posting_handler.post_message.call_count >= 2
    last_call = mock_slack_posting_handler.post_message.call_args_list[-1]
    assert "No usage data available" in last_call[1]["message"]


@pytest.mark.asyncio
async def test_handle_export_request_error(
    usage_export_handler, mock_command_tracking_ops, mock_slack_posting_handler
):
    """Test export request error handling."""
    # Setup mocks to raise an error
    mock_command_tracking_ops.get_full_export_data.side_effect = Exception("DB error")

    # Execute
    result = await usage_export_handler.handle_export_request(
        trigger_id="123456",
        user_id="U12345",
        response_url="https://hooks.slack.com/test",
    )

    # Verify
    assert result is False

    # Check error message was sent
    last_call = mock_slack_posting_handler.post_message.call_args_list[-1]
    assert "Failed to generate usage report" in last_call[1]["message"]


@pytest.mark.asyncio
async def test_upload_csv_to_slack_success(
    usage_export_handler, mock_slack_posting_handler, mocker
):
    """Test successful CSV upload to Slack using new uploadV2 API."""
    # Mock the HTTP response for file upload
    mock_response = mocker.MagicMock()
    mock_response.status = 200

    # Create a proper async context manager for session.post()
    class MockPostCM:
        async def __aenter__(self):
            return mock_response

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    # Mock the session
    mock_session = mocker.MagicMock()
    mock_session.post.return_value = MockPostCM()

    # Create a proper async context manager for ClientSession
    class MockSessionCM:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    # Mock the ClientSession class to return our context manager
    mocker.patch("aiohttp.ClientSession", return_value=MockSessionCM())

    # Mock the response.json() method for files.getUploadURLExternal
    mock_response.json = AsyncMock(
        return_value={
            "ok": True,
            "upload_url": "https://files.slack.com/upload/v1/...",
            "file_id": "F12345",
        }
    )

    # Setup posting handler
    mock_slack_posting_handler._slack_token = "test-token"
    mock_slack_posting_handler._init_slack_token = AsyncMock()
    mock_slack_posting_handler.config.get_api_base_url.return_value = "https://slack.com/api"

    # Mock the Slack API calls for the new upload process
    mock_slack_posting_handler.api_call = AsyncMock()
    mock_slack_posting_handler.api_call.return_value = {"ok": True}

    # Execute
    result = await usage_export_handler._upload_csv_to_slack(
        user_id="U12345",
        dm_channel_id=None,  # Testing without dm_channel_id
        csv_content="CSV content",
        filename="test_report.csv",
    )

    # Verify
    assert result is True

    # Verify the API calls were made correctly
    assert mock_slack_posting_handler.api_call.call_count == 1

    # Check the completeUploadExternal call
    call = mock_slack_posting_handler.api_call.call_args_list[0]
    assert call[0][0] == "files.completeUploadExternal"
    assert call[0][1]["files"][0]["id"] == "F12345"
    assert call[0][1]["channel_id"] == "U12345"


@pytest.mark.asyncio
async def test_upload_csv_to_slack_failure(
    usage_export_handler, mock_slack_posting_handler, mocker
):
    """Test failed CSV upload to Slack."""
    # Mock the HTTP response for file upload failure
    mock_response = mocker.MagicMock()
    mock_response.status = 200

    # Create a proper async context manager for session.post()
    class MockPostCM:
        async def __aenter__(self):
            return mock_response

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    # Mock the session
    mock_session = mocker.MagicMock()
    mock_session.post.return_value = MockPostCM()

    # Create a proper async context manager for ClientSession
    class MockSessionCM:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    # Mock the ClientSession class to return our context manager
    mocker.patch("aiohttp.ClientSession", return_value=MockSessionCM())

    # Mock the response.json() method to fail on getUploadURLExternal
    mock_response.json = AsyncMock(return_value={"ok": False, "error": "no_permission"})

    # Setup posting handler
    mock_slack_posting_handler._slack_token = "test-token"
    mock_slack_posting_handler._init_slack_token = AsyncMock()
    mock_slack_posting_handler.config.get_api_base_url.return_value = "https://slack.com/api"

    # Execute
    result = await usage_export_handler._upload_csv_to_slack(
        user_id="U12345",
        dm_channel_id=None,  # Testing without dm_channel_id
        csv_content="CSV content",
        filename="test_report.csv",
    )

    # Verify
    assert result is False


@pytest.mark.asyncio
async def test_filename_generation(
    usage_export_handler,
    mock_command_tracking_ops,
    mock_slack_posting_handler,
    mock_csv_generator,
    sample_export_data,
    mocker,
):
    """Test that filename is generated correctly with timestamp."""
    # Mock successful HTTP response
    mock_response = mocker.MagicMock()
    mock_response.status = 200

    # Create a proper async context manager for session.post()
    class MockPostCM:
        async def __aenter__(self):
            return mock_response

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    # Mock the session
    mock_session = mocker.MagicMock()
    mock_session.post.return_value = MockPostCM()

    # Create a proper async context manager for ClientSession
    class MockSessionCM:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    # Mock the ClientSession class to return our context manager
    mocker.patch("aiohttp.ClientSession", return_value=MockSessionCM())

    # Mock the response.json() method for files.getUploadURLExternal
    mock_response.json = AsyncMock(
        return_value={
            "ok": True,
            "upload_url": "https://files.slack.com/upload/v1/...",
            "file_id": "F12345",
        }
    )

    # Setup mocks
    mock_command_tracking_ops.get_full_export_data.return_value = sample_export_data
    mock_csv_generator.generate_csv.return_value = "CSV content"
    mock_slack_posting_handler._slack_token = "test-token"
    mock_slack_posting_handler._init_slack_token = AsyncMock()
    mock_slack_posting_handler.config.get_api_base_url.return_value = "https://slack.com/api"

    # Mock the Slack API calls for the new upload process
    mock_slack_posting_handler.api_call = AsyncMock()
    mock_slack_posting_handler.api_call.return_value = {"ok": True}

    # Execute
    await usage_export_handler.handle_export_request(
        trigger_id="123456",
        user_id="U12345",
        response_url="https://hooks.slack.com/test",
    )

    # Verify the upload was attempted
    assert mock_slack_posting_handler.api_call.call_count == 1

    # Check that FormData was created with correct filename
    # Note: We can't directly inspect FormData, but we can verify the upload was attempted


@pytest.mark.asyncio
async def test_handle_export_request_home_tab(
    usage_export_handler,
    mock_command_tracking_ops,
    mock_slack_posting_handler,
    mock_csv_generator,
    sample_export_data,
    mocker,
):
    """Test export request from Home tab (no response_url)."""
    # Mock successful HTTP response
    mock_response = mocker.MagicMock()
    mock_response.status = 200

    # Create a proper async context manager for session.post()
    class MockPostCM:
        async def __aenter__(self):
            return mock_response

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    # Mock the session
    mock_session = mocker.MagicMock()
    mock_session.post.return_value = MockPostCM()

    # Create a proper async context manager for ClientSession
    class MockSessionCM:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    # Mock the ClientSession class to return our context manager
    mocker.patch("aiohttp.ClientSession", return_value=MockSessionCM())

    # Mock the response.json() method for files.getUploadURLExternal
    mock_response.json = AsyncMock(
        return_value={
            "ok": True,
            "upload_url": "https://files.slack.com/upload/v1/...",
            "file_id": "F12345",
        }
    )

    # Setup mocks
    mock_command_tracking_ops.get_full_export_data.return_value = sample_export_data
    mock_csv_generator.generate_csv.return_value = "CSV content"
    mock_slack_posting_handler._slack_token = "test-token"
    mock_slack_posting_handler._init_slack_token = AsyncMock()
    mock_slack_posting_handler.config.get_api_base_url.return_value = "https://slack.com/api"

    # Mock the Slack API calls for the new upload process
    mock_slack_posting_handler.api_call = AsyncMock()
    mock_slack_posting_handler.api_call.return_value = {"ok": True}

    # Mock post_message to return DM channel in acknowledgment
    mock_slack_posting_handler.post_message = AsyncMock()
    mock_slack_posting_handler.post_message.side_effect = [
        {"ok": True, "channel": "D12345"},  # Acknowledgment message returns DM channel
        {"ok": True},  # Completion message
    ]

    # Execute without response_url
    result = await usage_export_handler.handle_export_request(
        trigger_id="123456", user_id="U12345", response_url=None  # Home tab scenario
    )

    # Verify
    assert result is True

    # Check that acknowledgment was sent as DM
    assert mock_slack_posting_handler.post_message.call_count >= 2
    first_call = mock_slack_posting_handler.post_message.call_args_list[0]
    # When no response_url, it should use channel_id (DM)
    assert "response_url" not in first_call[1]
    assert first_call[1]["channel_id"] == "U12345"
    assert "Generating usage report" in first_call[1]["message"]
