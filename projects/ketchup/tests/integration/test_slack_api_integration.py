"""
Integration tests for interactions with the Slack API via client wrappers.

These tests verify the integration between SlackPostingHandler, SlackConfig, and SecretsManager.

What is being tested:
    - Successful posting of ephemeral and channel messages to Slack.
    - Fallback logic for response_url and chat.postMessage.
    - Error handling for invalid blocks and insufficient information.
    - All major side effects (Slack API calls, error propagation) are asserted.

Expected outcomes:
    - Slack messages are posted as expected for each scenario.
    - Errors are handled gracefully and do not propagate unexpectedly.

Dependencies:
    - All external dependencies (Slack API, SecretsManager) are mocked.
    - No real Slack or AWS calls are made.
    - Tests require pytest, pytest-asyncio, and pytest-mock.

Test structure:
    - Each test is fully isolated and uses fixtures for dependencies.
    - All test functions use Google-style docstrings and detailed inline comments.
    - All test logic is covered by assertions; no logic is skipped.

"""

from unittest.mock import ANY, AsyncMock, patch

import httpx
import pytest
from pytest_mock import MockerFixture

from packages.core.constants import FEEDBACK_CHANNEL
from packages.secrets.manager import SecretsManager
from packages.slack.config.slack_config import SlackConfig
from packages.slack.messages.posting import (
    InvalidBlocksForResponseUrlError,
    SlackPostingHandler,
)

MOCK_USER_ID = "U123USER"
MOCK_CHANNEL_ID = "C123CHANNEL"
MOCK_DM_CHANNEL_ID = "D123DM"
MOCK_RESPONSE_URL = "https://hooks.slack.com/commands/T123/123/XYZ"
MOCK_MESSAGE = "Test message"
MOCK_BLOCKS = [{"type": "section", "text": {"type": "mrkdwn", "text": "Test block"}}]
MOCK_TOKEN = "xoxb-test-token"


@pytest.fixture
def mock_slack_config(mocker: MockerFixture) -> SlackConfig:
    """
    Provides a mocked SlackConfig.

    Args:
        mocker (MockerFixture): The pytest-mock fixture for patching/mocking.

    Returns:
        SlackConfig: Mocked SlackConfig instance.

    Example:
        Used to inject a mocked SlackConfig for integration tests.
    """
    config = mocker.MagicMock(spec=SlackConfig)
    config.get_api_base_url.return_value = "https://slack.com/api"
    config.get_headers.return_value = {"Authorization": f"Bearer {MOCK_TOKEN}"}
    return config


@pytest.fixture
def mock_secrets_manager(mocker: MockerFixture) -> SecretsManager:
    """
    Provides a mocked SecretsManager that returns the token.

    Args:
        mocker (MockerFixture): The pytest-mock fixture for patching/mocking.

    Returns:
        SecretsManager: Mocked SecretsManager instance.

    Example:
        Used to inject a mocked SecretsManager for integration tests.
    """
    secrets = mocker.AsyncMock(spec=SecretsManager)
    secrets.get_slack_api_token_async.return_value = MOCK_TOKEN
    return secrets


@pytest.fixture
def posting_handler(
    mock_slack_config: SlackConfig,
    mock_secrets_manager: SecretsManager,
    mocker: MockerFixture,
) -> SlackPostingHandler:
    """
    Provides a SlackPostingHandler instance with mocked dependencies.

    Args:
        mock_slack_config (SlackConfig): Mocked SlackConfig instance.
        mock_secrets_manager (SecretsManager): Mocked SecretsManager instance.
        mocker (MockerFixture): The pytest-mock fixture for patching/mocking.

    Returns:
        SlackPostingHandler: Instance with all dependencies mocked.

    Example:
        Used to inject a mocked SlackPostingHandler for integration tests.
    """
    handler = SlackPostingHandler(
        slack_config=mock_slack_config, secrets_manager=mock_secrets_manager
    )
    # Mock the underlying _make_api_request method
    handler._make_api_request = mocker.AsyncMock()
    return handler


@pytest.mark.asyncio
async def test_post_ephemeral_success(posting_handler: SlackPostingHandler):
    """
    Verify successful ephemeral message posting.

    Args:
        posting_handler (SlackPostingHandler): The handler under test.

    Returns:
        None

    Raises:
        AssertionError: If the expected calls or results are not observed.

    Example:
        This test verifies that a valid ephemeral message is posted successfully.
    """
    # Arrange
    mock_make_request = posting_handler._make_api_request
    # SafeResponse format
    mock_response = {
        "status": 200,
        "headers": {},
        "body": b'{"ok": true, "message_ts": "123.456"}',
    }
    mock_make_request.return_value = mock_response

    # Act
    response = await posting_handler.post_message(
        user_id=MOCK_USER_ID,
        channel_id=MOCK_CHANNEL_ID,
        message=MOCK_MESSAGE,
        blocks=MOCK_BLOCKS,
    )

    # Assert
    mock_make_request.assert_awaited_once_with(
        f"{posting_handler.config.get_api_base_url()}/chat.postEphemeral",
        "POST",
        ANY,  # headers
        None,  # params
        ANY,  # json_data containing user, channel, text, blocks
    )
    assert response == {"ok": True, "message_ts": "123.456"}


@pytest.mark.asyncio
async def test_post_message_uses_response_url_on_ephemeral_fail(
    posting_handler: SlackPostingHandler,
):
    """
    Verify response_url is used if ephemeral fails (e.g., returns ok:False).

    Args:
        posting_handler (SlackPostingHandler): The handler under test.

    Returns:
        None

    Raises:
        AssertionError: If the expected calls or results are not observed.

    Example:
        This test verifies that response_url is used as a fallback when ephemeral fails.
    """
    # Arrange
    mock_make_request = posting_handler._make_api_request
    # Simulate failed ephemeral response, then success for response_url
    mock_ephemeral_response = AsyncMock()
    mock_ephemeral_response.json.return_value = {"ok": False, "error": "some_error"}

    # Mock the response_url call to return success (status 200, text 'ok')
    # We need to mock the underlying httpx post call made by _post_response_url
    mock_httpx_response = AsyncMock(spec=httpx.Response)
    mock_httpx_response.status_code = 200
    mock_httpx_response.text = "ok"
    # Patch httpx.AsyncClient.post used within _post_response_url
    # This assumes _post_response_url uses httpx.AsyncClient().post directly
    with (
        patch("httpx.AsyncClient.post", return_value=mock_httpx_response),
        patch.object(
            posting_handler, "_post_response_url", return_value=mock_httpx_response
        ) as mock_post_url,
    ):
        mock_make_request.side_effect = [mock_ephemeral_response]  # Only fail ephemeral

        # Act
        response = await posting_handler.post_message(
            user_id=MOCK_USER_ID,
            channel_id=MOCK_CHANNEL_ID,
            message=MOCK_MESSAGE,
            blocks=MOCK_BLOCKS,
            response_url=MOCK_RESPONSE_URL,
        )

        # Assert
        # Check ephemeral call was first
        mock_make_request.assert_awaited_once_with(
            f"{posting_handler.config.get_api_base_url()}/chat.postEphemeral",
            "POST",
            ANY,
            None,
            ANY,
        )
        # Check response_url call was second (via patch)
        mock_post_url.assert_awaited_once_with(MOCK_RESPONSE_URL, MOCK_MESSAGE, MOCK_BLOCKS)
        # The return value should be from the successful response_url call
        assert response is mock_httpx_response


@pytest.mark.asyncio
async def test_post_message_uses_response_url_if_no_user(
    posting_handler: SlackPostingHandler,
):
    """
    Verify response_url is used directly if user_id is missing.
    """
    # Arrange
    # Simulate ephemeral failure (ok: False)
    mock_ephemeral_response = AsyncMock()
    mock_ephemeral_response.json.return_value = {"ok": False, "error": "some_error"}
    posting_handler._make_api_request.return_value = mock_ephemeral_response
    mock_httpx_response = AsyncMock(spec=httpx.Response)
    mock_httpx_response.status_code = 200
    mock_httpx_response.text = "ok"
    with patch.object(
        posting_handler, "_post_response_url", return_value=mock_httpx_response
    ) as mock_post_url:
        # Act
        response = await posting_handler.post_message(
            user_id=None,  # No user ID
            channel_id=MOCK_CHANNEL_ID,
            message=MOCK_MESSAGE,
            response_url=MOCK_RESPONSE_URL,
        )
        # Assert _post_response_url is called and response is correct
        mock_post_url.assert_awaited_once_with(MOCK_RESPONSE_URL, MOCK_MESSAGE, None)
        assert response is mock_httpx_response


@pytest.mark.asyncio
async def test_post_message_uses_channel_post_as_fallback(
    posting_handler: SlackPostingHandler,
):
    """
    Verify chat.postMessage is used if ephemeral/response_url are not viable.
    """
    # Arrange
    # Simulate ephemeral failure (ok: False), then chat.postMessage success (ok: True)
    # SafeResponse format
    mock_channel_response = {
        "status": 200,
        "headers": {},
        "body": b'{"ok": true, "message_ts": "123.456"}',
    }
    posting_handler._make_api_request.return_value = mock_channel_response

    # Act
    response = await posting_handler.post_message(
        user_id=None,  # No user ID
        channel_id=FEEDBACK_CHANNEL,  # Use FEEDBACK_CHANNEL for fallback
        message=MOCK_MESSAGE,
        response_url=None,  # No response URL
    )
    # Assert only one call to chat.postMessage (no ephemeral since no user_id)
    base_url = posting_handler.config.get_api_base_url()
    calls = posting_handler._make_api_request.await_args_list
    assert len(calls) == 1
    assert calls[0][0][0] == f"{base_url}/chat.postMessage"
    assert response == {"ok": True, "message_ts": "123.456"}


@pytest.mark.asyncio
async def test_post_message_raises_value_error_if_no_options(
    posting_handler: SlackPostingHandler,
):
    """
    Verify ValueError is raised if no posting method is possible.

    Args:
        posting_handler (SlackPostingHandler): The handler under test.

    Returns:
        None

    Raises:
        ValueError: If insufficient information is provided to post a message.

    Example:
        This test verifies that ValueError is raised when no posting method is possible.
    """
    # Act & Assert
    with pytest.raises(ValueError) as excinfo:
        await posting_handler.post_message(
            user_id=None, channel_id=None, message=MOCK_MESSAGE, response_url=None
        )
    assert "Insufficient information" in str(excinfo.value)


@pytest.mark.asyncio
async def test_post_message_reraises_invalid_blocks_error(
    posting_handler: SlackPostingHandler,
):
    """
    Verify InvalidBlocksForResponseUrlError is re-raised from response_url post.

    Args:
        posting_handler (SlackPostingHandler): The handler under test.

    Returns:
        None

    Raises:
        InvalidBlocksForResponseUrlError: If blocks are not allowed in response_url post.

    Example:
        This test verifies that InvalidBlocksForResponseUrlError is re-raised when blocks are not allowed.
    """
    # Arrange
    mock_make_request = posting_handler._make_api_request
    # Simulate InvalidBlocks error during response_url attempt
    invalid_blocks_exception = InvalidBlocksForResponseUrlError("Blocks not allowed")
    # Need to simulate ephemeral failure first
    mock_ephemeral_response = AsyncMock()
    mock_ephemeral_response.json.return_value = {"ok": False, "error": "some_error"}

    # Mock _post_response_url directly to raise the specific error
    with patch.object(
        posting_handler, "_post_response_url", side_effect=invalid_blocks_exception
    ) as mock_post_url:
        mock_make_request.side_effect = [mock_ephemeral_response]  # Fail ephemeral

        # Act & Assert
        with pytest.raises(InvalidBlocksForResponseUrlError) as excinfo:
            await posting_handler.post_message(
                user_id=MOCK_USER_ID,
                channel_id=MOCK_CHANNEL_ID,
                message=MOCK_MESSAGE,
                blocks=MOCK_BLOCKS,
                response_url=MOCK_RESPONSE_URL,
            )

        # Assert ephemeral was called
        mock_make_request.assert_awaited_once()
        # Assert _post_response_url was called
        mock_post_url.assert_awaited_once_with(MOCK_RESPONSE_URL, MOCK_MESSAGE, MOCK_BLOCKS)
        assert "Blocks not allowed" in str(excinfo.value)
