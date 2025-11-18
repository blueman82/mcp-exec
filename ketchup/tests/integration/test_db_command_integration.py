"""
Integration tests for the /archive Slack command and its interactions with the database and
Slack posting logic.

These tests verify the integration between the SlackArchiveCommand, DynamoDBStore,
BlockKitBuilder, and SlackPostingHandler.

What is being tested:
    - The /archive command's ability to read archived channel data from DynamoDB and present
      it to users via Slack Block Kit messages.
    - Handling of normal, empty, and error scenarios for database reads.
    - Correct posting of messages to Slack at each step of the command flow.
    - Edge cases such as missing optional fields, no results, and database exceptions.

Coverage:
    - Success path: DB returns archived channels, BlockKitBuilder formats and posts results.
    - No results: DB returns empty, handler posts 'no channels found' message.
    - Error path: DB read raises exception, handler posts error message.
    - All major side effects (Slack posting, DB calls, block kit formatting) are asserted.

Expected outcomes:
    - All Slack messages and DB calls are made as expected for each scenario.
    - No unhandled exceptions propagate out of the handler.
    - Edge cases (missing fields, empty results, errors) are handled gracefully and user is
      notified.

Dependencies:
    - All external dependencies (DynamoDBStore, BlockKitBuilder, SlackPostingHandler) are
      mocked.
    - No real AWS or Slack calls are made.
    - Tests require pytest, pytest-asyncio, and pytest-mock.

Test structure:
    - Each test is fully isolated and uses fixtures for dependencies.
    - All test functions use Google-style docstrings and detailed inline comments.
    - All test logic is covered by assertions; no logic is skipped.

Example test flow:
    1. User issues /archive command in Slack DM.
    2. Handler posts initial 'retrieving' message.
    3. Handler reads archived channels from DynamoDB.
    4. Handler posts results as Block Kit, or 'no channels found', or error message as
       appropriate.

See the test plan and README for further details on coverage and standards.
"""

import pytest
from pytest_mock import MockerFixture

from packages.db.dynamodb_store import DynamoDBStore
from packages.slack.blockkits.base import BlockKitBuilder
from packages.slack.command_processing.archive_command import SlackArchiveCommand
from packages.slack.command_processing.command_parameters.models import (
    ArchiveCommandParams,
    CommandContext,
    CommandType,
)
from packages.slack.messages.posting import SlackPostingHandler

# F401: Remove unused imports (AsyncMock, patch, MagicMock)
# from unittest.mock import AsyncMock, patch, MagicMock


# Sample data for testing
MOCK_USER_ID = "U123USER"
MOCK_CHANNEL_ID = "C123CHANNEL"
MOCK_RESPONSE_URL = "https://hooks.slack.com/commands/T123/123/XYZ"

MOCK_ARCHIVED_CHANNELS_DATA = {
    "CARCHIVE1": {
        "channel_name": "archived-channel-1",
        "customer_name": "Cust A",
        "jira_ticket": "JIRA-1",
        "archived_at": 1700000000,
    },
    "CARCHIVE2": {
        "channel_name": "archived-channel-2",
        "archived_at": 1700000100,
        # Missing optional fields
    },
}

EXPECTED_CHANNEL_SUMMARIES = [
    {
        "channel_id": "CARCHIVE1",
        "channel_name": "archived-channel-1",
        "customer_name": "Cust A",
        "jira_ticket": "JIRA-1",
        "archived_at": 1700000000,
    },
    {
        "channel_id": "CARCHIVE2",
        "channel_name": "archived-channel-2",
        "customer_name": "NOT YET AVAILABLE",  # Default value
        "jira_ticket": "NOT YET AVAILABLE",  # Default value
        "archived_at": 1700000100,
    },
]


@pytest.fixture
def mock_dependencies(mocker: MockerFixture) -> dict:
    """
    Provides mocked dependencies for SlackArchiveCommand.

    Args:
        mocker (MockerFixture): The pytest-mock fixture for patching/mocking.

    Returns:
        dict: Dictionary of mocked dependencies for SlackArchiveCommand.

    Example:
        Used to inject mocks for DynamoDBStore, BlockKitBuilder, and posting handler.
    """
    mock_store = mocker.AsyncMock(spec=DynamoDBStore)
    mock_block_builder = mocker.AsyncMock(spec=BlockKitBuilder)
    mock_posting_handler = mocker.AsyncMock(spec=SlackPostingHandler)
    # Mock other dependencies if needed by constructor (ChannelInfoOps, SlackChannelArchiveOps, SlackChannelRestoreOps, UserStore)
    mock_info_ops = mocker.AsyncMock()
    mock_archive_ops = mocker.AsyncMock()
    mock_restore_ops = mocker.AsyncMock()
    mock_user_store = mocker.AsyncMock()

    return {
        "dynamodb_store": mock_store,
        "block_kit_builder": mock_block_builder,
        "slack_posting_handler": mock_posting_handler,
        "channel_info_ops": mock_info_ops,
        "archive_ops": mock_archive_ops,
        "channel_restore_ops": mock_restore_ops,
        "user_store": mock_user_store,
    }


@pytest.fixture
def archive_command_handler(mock_dependencies: dict) -> SlackArchiveCommand:
    """
    Provides an instance of SlackArchiveCommand with mocked dependencies.

    Args:
        mock_dependencies (dict): Dictionary of mocked dependencies.

    Returns:
        SlackArchiveCommand: Instance with all dependencies mocked.
    """
    return SlackArchiveCommand(**mock_dependencies)


@pytest.mark.asyncio
async def test_archive_command_reads_db_and_sends_blocks(
    archive_command_handler: SlackArchiveCommand,
    mock_dependencies: dict,
):
    """
    Test that the /archive command reads from DynamoDBStore and sends results via
    BlockKitBuilder.

    Args:
        archive_command_handler (SlackArchiveCommand): The handler under test.
        mock_dependencies (dict): Mocked dependencies for the handler.

    Returns:
        None

    Raises:
        AssertionError: If the expected calls or results are not observed.

    Example:
        This test verifies that a valid /archive command with days=30 posts an initial
        message, reads from the DB, and sends the correct block kit summary.

    Edge Cases:
        - Ensures correct transformation of channel summaries, including default values for
          missing fields.
    """
    # Arrange: Set up mocks and parameters for a successful DB read
    mock_store = mock_dependencies["dynamodb_store"]
    mock_block_builder = mock_dependencies["block_kit_builder"]
    mock_posting_handler = mock_dependencies["slack_posting_handler"]

    params = ArchiveCommandParams(
        days=30,
        command_type=CommandType.ARCHIVE,
        original_command="/archive days=30",
        context=CommandContext.DIRECT_MESSAGE,  # Archive only runs in DMs
    )

    # Configure mock return values
    mock_store.get_all_channel_details.return_value = MOCK_ARCHIVED_CHANNELS_DATA

    # Act: Call the handler to process the archive command
    await archive_command_handler.process_archive_params(
        params=params,
        user_id=MOCK_USER_ID,
        incoming_channel=MOCK_CHANNEL_ID,
        response_url=MOCK_RESPONSE_URL,
    )

    # Assert: Check that all expected calls were made
    # 1. Initial message was posted
    mock_posting_handler.post_message.assert_any_call(
        user_id=MOCK_USER_ID,
        channel_id=MOCK_CHANNEL_ID,
        message="Retrieving archived channels from the last 30 days... :mag:",
        response_url=MOCK_RESPONSE_URL,
    )

    # 2. DynamoDBStore was called correctly
    mock_store.get_all_channel_details.assert_awaited_once_with(
        archive_lookup=True, days_threshold=30, product_preference="all_products"
    )

    # 3. BlockKitBuilder was called with the correctly transformed summaries
    mock_block_builder.send_ketchup_archive_block_kit.assert_awaited_once_with(
        response_url=MOCK_RESPONSE_URL,
        summaries=EXPECTED_CHANNEL_SUMMARIES,
        incoming_channel=MOCK_CHANNEL_ID,
    )


@pytest.mark.asyncio
async def test_archive_command_no_channels_found(
    archive_command_handler: SlackArchiveCommand,
    mock_dependencies: dict,
):
    """
    Test that the /archive command handles the case where no archived channels are found.

    Args:
        archive_command_handler (SlackArchiveCommand): The handler under test.
        mock_dependencies (dict): Mocked dependencies for the handler.

    Returns:
        None

    Raises:
        AssertionError: If the expected calls or results are not observed.

    Example:
        This test verifies that a valid /archive command with days=7 and no DB results
        posts an initial message, a 'no channels found' message, and does not call
        BlockKitBuilder.

    Edge Cases:
        - Ensures the handler does not attempt to send a block kit when there are no
          results.
    """
    # Arrange: Set up mocks and parameters for an empty DB result
    mock_store = mock_dependencies["dynamodb_store"]
    mock_block_builder = mock_dependencies["block_kit_builder"]
    mock_posting_handler = mock_dependencies["slack_posting_handler"]

    params = ArchiveCommandParams(
        days=7,
        command_type=CommandType.ARCHIVE,
        original_command="/archive days=7",
        context=CommandContext.DIRECT_MESSAGE,
    )

    # Configure mock return value (empty dict)
    mock_store.get_all_channel_details.return_value = {}

    # Act: Call the handler to process the archive command
    await archive_command_handler.process_archive_params(
        params=params,
        user_id=MOCK_USER_ID,
        incoming_channel=MOCK_CHANNEL_ID,
        response_url=MOCK_RESPONSE_URL,
    )

    # Assert: Check that all expected calls were made
    # 1. Initial message was posted
    mock_posting_handler.post_message.assert_any_call(
        user_id=MOCK_USER_ID,
        channel_id=MOCK_CHANNEL_ID,
        message="Retrieving archived channels from the last 7 days... :mag:",
        response_url=MOCK_RESPONSE_URL,
    )

    # 2. DynamoDBStore was called correctly
    mock_store.get_all_channel_details.assert_awaited_once_with(
        archive_lookup=True, days_threshold=7, product_preference="all_products"
    )

    # 3. "No channels found" message was posted
    mock_posting_handler.post_message.assert_any_call(
        user_id=MOCK_USER_ID,
        channel_id=MOCK_CHANNEL_ID,
        message="No archived channels found.",
        response_url=MOCK_RESPONSE_URL,
    )

    # 4. BlockKitBuilder was NOT called
    mock_block_builder.send_ketchup_archive_block_kit.assert_not_awaited()


@pytest.mark.asyncio
async def test_archive_command_db_read_exception(
    archive_command_handler: SlackArchiveCommand,
    mock_dependencies: dict,
):
    """
    Test error handling when DynamoDBStore raises an exception during read.

    Args:
        archive_command_handler (SlackArchiveCommand): The handler under test.
        mock_dependencies (dict): Mocked dependencies for the handler.

    Returns:
        None

    Raises:
        AssertionError: If the expected calls or results are not observed.

    Example:
        This test verifies that a DB read exception results in an error message being
        posted.

    Edge Cases:
        - Ensures the handler does not crash and posts an error message to the user.
    """
    # Arrange: Set up mocks and parameters for a DB exception
    mock_store = mock_dependencies["dynamodb_store"]
    mock_block_builder = mock_dependencies["block_kit_builder"]
    mock_posting_handler = mock_dependencies["slack_posting_handler"]

    params = ArchiveCommandParams(
        days=90,
        command_type=CommandType.ARCHIVE,
        original_command="/archive days=90",
        context=CommandContext.DIRECT_MESSAGE,
    )
    test_exception = Exception("DynamoDB Read Error")

    # Configure mock to raise exception
    mock_store.get_all_channel_details.side_effect = test_exception

    # Act: Call the handler to process the archive command
    await archive_command_handler.process_archive_params(
        params=params,
        user_id=MOCK_USER_ID,
        incoming_channel=MOCK_CHANNEL_ID,
        response_url=MOCK_RESPONSE_URL,
    )

    # Assert: Check that all expected calls were made
    # 1. Initial message was posted
    mock_posting_handler.post_message.assert_any_call(
        user_id=MOCK_USER_ID,
        channel_id=MOCK_CHANNEL_ID,
        message="Retrieving archived channels from the last 90 days... :mag:",
        response_url=MOCK_RESPONSE_URL,
    )

    # 2. DynamoDBStore was called correctly
    mock_store.get_all_channel_details.assert_awaited_once_with(
        archive_lookup=True, days_threshold=90, product_preference="all_products"
    )

    # 3. Error message was posted
    mock_posting_handler.post_message.assert_any_call(
        user_id=MOCK_USER_ID,
        channel_id=MOCK_CHANNEL_ID,
        message=f"Error processing archive request: {test_exception}",
        response_url=MOCK_RESPONSE_URL,
    )

    # 4. BlockKitBuilder was NOT called
    mock_block_builder.send_ketchup_archive_block_kit.assert_not_awaited()
