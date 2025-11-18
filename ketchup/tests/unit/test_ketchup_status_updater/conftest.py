"""
Shared test fixtures for status updater tests.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import at module level to comply with CLAUDE.md import rules
from ketchup_status_updater.processor import AutoStatusProcessor


@pytest.fixture
def mock_status_updater_deps():
    """
    Comprehensive mock dependencies for status updater components.

    Returns:
        Dict containing all mocked dependencies for AutoStatusProcessor
        and AutoStatusGenerator with proper async/sync mock types.
    """
    return {
        # Core dependencies
        'openai': AsyncMock(),
        'slack': AsyncMock(),
        'dynamodb': AsyncMock(),

        # Specific service mocks
        'db_store': MagicMock(),
        'mcp_client': AsyncMock(),
        'secrets_manager': AsyncMock(),
        'slack_config': MagicMock(openai_model="gpt-4"),
        'openai_handler': AsyncMock(),
        'channel_info_ops': AsyncMock(),
        'channel_msg_ops': AsyncMock(),
        'posting_handler': AsyncMock(),
        'channel_operations': AsyncMock(),
        'channel_membership_ops': AsyncMock(),
        'feature_service': AsyncMock(),
    }


@pytest.fixture
def mock_processor_deps():
    """Mock dependencies specifically for AutoStatusProcessor."""
    deps = {
        "db_store": MagicMock(),
        "mcp_client": AsyncMock(),
        "secrets_manager": AsyncMock(),
        "slack_config": MagicMock(),
        "openai_handler": AsyncMock(),
        "channel_info_ops": AsyncMock(),
        "channel_msg_ops": AsyncMock(),
        "posting_handler": AsyncMock(),
        "channel_operations": AsyncMock(),
        "channel_membership_ops": AsyncMock(),
        "feature_service": AsyncMock(),
    }

    # Set up common mock behaviors
    deps["db_store"].client = AsyncMock()
    deps["db_store"].client.get_item = AsyncMock(return_value={})  # No pause settings by default
    deps["db_store"].table_name = "test_table"
    deps["channel_operations"].query_ops = AsyncMock()
    deps["channel_operations"].update_channel_fields = AsyncMock()
    deps["channel_membership_ops"].lookup_membership_of_channels = AsyncMock()
    deps["secrets_manager"].get_bot_slack_user_id_async = AsyncMock(return_value="U123456")

    return deps


@pytest.fixture
def mock_generator_deps():
    """Mock dependencies specifically for AutoStatusGenerator."""
    deps = {
        "db_store": MagicMock(),
        "mcp_client": AsyncMock(),
        "secrets_manager": AsyncMock(),
        "slack_config": MagicMock(openai_model="gpt-4"),
        "openai_handler": AsyncMock(),
        "channel_msg_ops": AsyncMock(),
        "posting_handler": AsyncMock(),
        "channel_operations": AsyncMock(),
    }

    # Set up common mock behaviors
    deps["db_store"].channel_operations = AsyncMock()
    deps["mcp_client"].get_issue_comments = AsyncMock(return_value=[])
    deps["secrets_manager"].get_bot_slack_user_id_async = AsyncMock(return_value="U123456")
    deps["posting_handler"]._slack_token = "test-token"
    deps["posting_handler"]._init_slack_token = AsyncMock()
    deps["posting_handler"]._post_channel_message = AsyncMock(return_value={"ok": True})

    return deps


@pytest.fixture
def sample_channel():
    """Sample channel data for testing."""
    return {
        "channel_id": "C123456789",
        "channel_name": "test-channel",
        "auto_status_last_run": 0,
        "auto_status_attempt_count": 0,
        "auto_status_last_message_ts": "0",
        "auto_status_last_thread_ts": "0",
        "auto_status_last_content": "",
    }


@pytest.fixture
def sample_channel_details():
    """Sample channel details for testing."""
    return {
        "jira_ticket": "TEST-123",
        "customer_name": "Test Customer",
        "product": "test-product",
        "priority": "high",
        "team": "test-team",
    }


@pytest.fixture
def sample_jira_comments():
    """Sample JIRA comments for testing."""
    return [
        {
            "author": {"displayName": "John Doe"},
            "created": "2024-01-01T10:00:00",
            "body": "Initial comment about the issue",
        },
        {
            "author": {"displayName": "Jane Smith"},
            "created": "2024-01-02T15:30:00",
            "body": "Follow-up comment with additional details",
        },
    ]


@pytest.fixture
def mock_status_updater_environment_variables():
    """Mock environment variables for status updater testing."""
    with patch.dict(os.environ, {"KETCHUP_STATUS_UPDATER_ENABLED": "true"}):
        yield


@pytest.fixture
def dynamic_channel_processor(mock_processor_deps, mock_status_updater_environment_variables):
    """
    Comprehensive fixture for AutoStatusProcessor with all required mocks for dynamic channel testing.

    This fixture provides:
    - All required dependencies properly mocked
    - Consistent test data across all test methods
    - Proper async/await patterns
    - Environment variable configuration

    Returns:
        AutoStatusProcessor: Fully configured processor instance with comprehensive mocks
    """

    # Enhanced mock setup for dynamic channel testing
    deps = mock_processor_deps.copy()

    # Set up comprehensive channel data
    sample_channels = [
        {"channel_id": "C1234567890", "channel_name": "general", "auto_status_last_run": 0},
        {"channel_id": "C0987654321", "channel_name": "random", "auto_status_last_run": 0},
        {"channel_id": "C1111111111", "channel_name": "testing", "auto_status_last_run": 0},
        {"channel_id": "C094DQY7HLH", "channel_name": "test-channel", "auto_status_last_run": 0},
    ]

    # Configure channel operations mock
    deps["channel_operations"].query_ops.get_all_active_channels = AsyncMock(
        return_value=sample_channels
    )

    # Configure database store mock - return empty dict to indicate no pause settings
    deps["db_store"].client = AsyncMock()
    deps["db_store"].client.get_item = AsyncMock(return_value={})
    deps["db_store"].client.put_item = AsyncMock(return_value={"ResponseMetadata": {"HTTPStatusCode": 200}})
    deps["db_store"].table_name = "test_table"

    # Configure feature service mock with default behavior
    deps["feature_service"].is_status_updater_enabled_for_channel = AsyncMock(return_value=True)

    # Create processor instance
    processor = AutoStatusProcessor(**deps)

    # Add mock methods for internal processor functions
    processor._should_process_channel = AsyncMock(return_value=True)
    processor._process_channel = AsyncMock(return_value=True)

    return processor