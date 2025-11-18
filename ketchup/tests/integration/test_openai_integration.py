"""
Integration tests for interactions with the OpenAI API Executor.

These tests verify the integration between ApiExecutor, TokenTracker, and SlackChannelArchiveOps.

What is being tested:
    - Successful API execution with and without channel re-archiving.
    - Error handling when the API request function fails.
    - Behavior when API succeeds but re-archiving fails.
    - All major side effects (API calls, token tracking, archive ops) are asserted.

Expected outcomes:
    - API requests are made as expected for each scenario.
    - Token usage and cost are tracked correctly.
    - Archive operations are called or not called as appropriate.
    - Errors are handled gracefully and do not propagate unexpectedly.

Dependencies:
    - All external dependencies (API request function, TokenTracker, SlackChannelArchiveOps) are mocked.
    - No real OpenAI or Slack calls are made.
    - Tests require pytest, pytest-asyncio, and pytest-mock.

Test structure:
    - Each test is fully isolated and uses fixtures for dependencies.
    - All test functions use Google-style docstrings and detailed inline comments.
    - All test logic is covered by assertions; no logic is skipped.

See the test plan and README for further details on coverage and standards.
"""

import pytest
from pytest_mock import MockerFixture

from packages.ai.core.operations.api_interaction import ApiExecutor
from packages.ai.cost_calculator import TokenTracker
from packages.slack.channel_operations.channel_archive_ops import SlackChannelArchiveOps

MOCK_ENDPOINT = "https://test.openai.azure.com/"
MOCK_API_KEY = "test-key"
MOCK_USER_ID = "U123USER"
MOCK_INCOMING_CHANNEL = "C456INCOMING"
MOCK_TARGET_CHANNEL = "C789TARGET"


@pytest.fixture
def mock_dependencies(mocker: MockerFixture) -> dict:
    """
    Provides mocked dependencies for ApiExecutor.

    Args:
        mocker (MockerFixture): The pytest-mock fixture for patching/mocking.

    Returns:
        dict: Dictionary of mocked dependencies for ApiExecutor.

    Example:
        Used to inject mocks for API request function, TokenTracker, and archive ops.
    """
    mock_request_func = mocker.AsyncMock()
    mock_token_tracker = mocker.MagicMock(spec=TokenTracker)
    mock_archive_ops = mocker.AsyncMock(spec=SlackChannelArchiveOps)

    # Configure TokenTracker mock
    mock_token_tracker.calculate_cost.return_value = {"Total Cost": 0.001}

    return {
        "api_request_func": mock_request_func,
        "token_tracker": mock_token_tracker,
        "channel_archive_ops": mock_archive_ops,
    }


@pytest.fixture
def api_executor(mock_dependencies: dict) -> ApiExecutor:
    """
    Provides an instance of ApiExecutor with mocked dependencies.

    Args:
        mock_dependencies (dict): Dictionary of mocked dependencies.

    Returns:
        ApiExecutor: Instance with all dependencies mocked.
    """
    return ApiExecutor(
        api_request_func=mock_dependencies["api_request_func"],
        endpoint=MOCK_ENDPOINT,
        api_key=MOCK_API_KEY,
        token_tracker=mock_dependencies["token_tracker"],
        channel_archive_ops=mock_dependencies["channel_archive_ops"],
    )


MOCK_PAYLOAD = {
    "messages": [{"role": "user", "content": "Test prompt"}],
    "max_tokens": 100,
}

MOCK_API_RESPONSE = {
    "choices": [{"message": {"role": "assistant", "content": "Test response"}}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
}


@pytest.mark.asyncio
async def test_execute_request_success_no_rearchive(
    api_executor: ApiExecutor, mock_dependencies: dict
):
    """
    Verify successful API execution without channel re-archiving.

    Args:
        api_executor (ApiExecutor): The executor under test.
        mock_dependencies (dict): Mocked dependencies for the executor.

    Returns:
        None

    Raises:
        AssertionError: If the expected calls or results are not observed.

    Example:
        This test verifies that a valid API call with no re-archive posts correct metadata and does not call archive ops.
    """
    # Arrange
    mock_request_func = mock_dependencies["api_request_func"]
    mock_token_tracker = mock_dependencies["token_tracker"]
    mock_archive_ops = mock_dependencies["channel_archive_ops"]

    mock_request_func.return_value = MOCK_API_RESPONSE
    channel_info = {"target_channel": MOCK_TARGET_CHANNEL, "originally_archived": False}

    # Act
    response = await api_executor.execute_request(
        payload=MOCK_PAYLOAD,
        channel_info=channel_info,
        user_id=MOCK_USER_ID,
        incoming_channel=MOCK_INCOMING_CHANNEL,
    )

    # Assert
    # 1. API request function called correctly
    mock_request_func.assert_awaited_once_with(
        url=MOCK_ENDPOINT,
        method="POST",
        headers={"api-key": MOCK_API_KEY},
        json_data=MOCK_PAYLOAD,
    )

    # 2. Token tracker updated
    mock_token_tracker.add_usage.assert_called_once_with(10, 5)
    mock_token_tracker.calculate_cost.assert_called_once_with(10, 5)

    # 3. Archive ops NOT called
    mock_archive_ops.archive_channel.assert_not_awaited()

    # 4. Response contains original data and added metadata
    assert response["choices"] == MOCK_API_RESPONSE["choices"]
    assert "metadata" in response
    assert response["metadata"]["input_tokens"] == 10
    assert response["metadata"]["output_tokens"] == 5
    assert response["metadata"]["total_tokens"] == 15
    assert (
        response["metadata"]["channel_id"] == MOCK_INCOMING_CHANNEL
    )  # Not re-archived


@pytest.mark.asyncio
async def test_execute_request_success_with_rearchive(
    api_executor: ApiExecutor, mock_dependencies: dict
):
    """
    Verify successful API execution WITH channel re-archiving.

    Args:
        api_executor (ApiExecutor): The executor under test.
        mock_dependencies (dict): Mocked dependencies for the executor.

    Returns:
        None

    Raises:
        AssertionError: If the expected calls or results are not observed.

    Example:
        This test verifies that a valid API call with re-archive posts correct metadata and calls archive ops.
    """
    # Arrange
    mock_request_func = mock_dependencies["api_request_func"]
    mock_token_tracker = mock_dependencies["token_tracker"]
    mock_archive_ops = mock_dependencies["channel_archive_ops"]

    mock_request_func.return_value = MOCK_API_RESPONSE
    channel_info = {"target_channel": MOCK_TARGET_CHANNEL, "originally_archived": True}

    # Act
    response = await api_executor.execute_request(
        payload=MOCK_PAYLOAD,
        channel_info=channel_info,
        user_id=MOCK_USER_ID,
        incoming_channel=MOCK_INCOMING_CHANNEL,
    )

    # Assert
    # 1. API request function called correctly (details same as previous test)
    mock_request_func.assert_awaited_once()

    # 2. Token tracker updated (details same as previous test)
    mock_token_tracker.add_usage.assert_called_once_with(10, 5)

    # 3. Archive ops WAS called
    mock_archive_ops.archive_channel.assert_awaited_once_with(
        user_id=MOCK_USER_ID,
        channel_id=MOCK_TARGET_CHANNEL,
        incoming_channel=MOCK_INCOMING_CHANNEL,
    )

    # 4. Response contains metadata with the TARGET channel ID
    assert "metadata" in response
    assert response["metadata"]["channel_id"] == MOCK_TARGET_CHANNEL  # Re-archived


@pytest.mark.asyncio
async def test_execute_request_api_failure(
    api_executor: ApiExecutor, mock_dependencies: dict
):
    """
    Verify error handling when the API request function fails.

    Args:
        api_executor (ApiExecutor): The executor under test.
        mock_dependencies (dict): Mocked dependencies for the executor.

    Returns:
        None

    Raises:
        Exception: If the API call fails as expected.

    Example:
        This test verifies that an exception from the API request function is propagated and no side effects occur.
    """
    # Arrange
    mock_request_func = mock_dependencies["api_request_func"]
    mock_token_tracker = mock_dependencies["token_tracker"]
    mock_archive_ops = mock_dependencies["channel_archive_ops"]

    test_exception = Exception("API Call Failed")
    mock_request_func.side_effect = test_exception
    channel_info = {"target_channel": MOCK_TARGET_CHANNEL, "originally_archived": False}

    # Act & Assert
    with pytest.raises(Exception) as excinfo:
        await api_executor.execute_request(
            payload=MOCK_PAYLOAD,
            channel_info=channel_info,
            user_id=MOCK_USER_ID,
            incoming_channel=MOCK_INCOMING_CHANNEL,
        )

    assert excinfo.value is test_exception  # Ensure original exception is re-raised

    # 1. API request function was called
    mock_request_func.assert_awaited_once()

    # 2. Token tracker NOT updated
    mock_token_tracker.add_usage.assert_not_called()

    # 3. Archive ops NOT called
    mock_archive_ops.archive_channel.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_request_rearchive_failure(
    api_executor: ApiExecutor, mock_dependencies: dict
):
    """
    Verify behavior when API succeeds but re-archiving fails (should still return API response).

    Args:
        api_executor (ApiExecutor): The executor under test.
        mock_dependencies (dict): Mocked dependencies for the executor.

    Returns:
        None

    Raises:
        AssertionError: If the expected calls or results are not observed.

    Example:
        This test verifies that a re-archive failure does not prevent a successful API response.
    """
    # Arrange
    mock_request_func = mock_dependencies["api_request_func"]
    mock_token_tracker = mock_dependencies["token_tracker"]
    mock_archive_ops = mock_dependencies["channel_archive_ops"]

    mock_request_func.return_value = MOCK_API_RESPONSE
    archive_exception = Exception("Re-archive Failed")
    mock_archive_ops.archive_channel.side_effect = archive_exception
    channel_info = {"target_channel": MOCK_TARGET_CHANNEL, "originally_archived": True}

    # Act
    # Should not raise an exception, failure is logged internally
    response = await api_executor.execute_request(
        payload=MOCK_PAYLOAD,
        channel_info=channel_info,
        user_id=MOCK_USER_ID,
        incoming_channel=MOCK_INCOMING_CHANNEL,
    )

    # Assert
    # 1. API request function called correctly
    mock_request_func.assert_awaited_once()

    # 2. Token tracker updated
    mock_token_tracker.add_usage.assert_called_once_with(10, 5)

    # 3. Archive ops WAS called
    mock_archive_ops.archive_channel.assert_awaited_once_with(
        user_id=MOCK_USER_ID,
        channel_id=MOCK_TARGET_CHANNEL,
        incoming_channel=MOCK_INCOMING_CHANNEL,
    )

    # 4. Response is still returned, containing metadata with TARGET channel ID
    assert response["choices"] == MOCK_API_RESPONSE["choices"]
    assert "metadata" in response
    assert (
        response["metadata"]["channel_id"] == MOCK_TARGET_CHANNEL
    )  # Attempted re-archive
