"""
Test trust endorsement channel-specific enablement.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ketchup_status_updater.status_generator import AutoStatusGenerator


@pytest.fixture
def mock_dependencies():
    """Create mock dependencies for AutoStatusGenerator."""
    return {
        "db_store": AsyncMock(),
        "mcp_client": AsyncMock(),
        "secrets_manager": AsyncMock(),
        "slack_config": MagicMock(),
        "openai_handler": AsyncMock(),
        "channel_info_ops": AsyncMock(),
        "channel_msg_ops": AsyncMock(),
        "posting_handler": AsyncMock(),
        "channel_operations": AsyncMock(),
    }


@pytest.mark.asyncio
async def test_trust_button_only_on_enabled_channels(mock_dependencies):
    """Test that trust buttons only appear on channels with trust_endorsement enabled."""
    generator = AutoStatusGenerator(**mock_dependencies)

    # Mock the posting handler's internal state
    mock_dependencies["posting_handler"]._slack_token = "test-token"
    mock_dependencies["posting_handler"]._post_channel_message = AsyncMock(
        return_value={"ok": True, "ts": "123.456"}
    )

    # Test data
    test_cases = [
        {
            "channel_id": "C123ENABLED",
            "channel_details": {"features": {"trust_endorsement_enabled": True}},
            "should_have_button": True,
            "description": "Channel with trust_endorsement enabled",
        },
        {
            "channel_id": "C456DISABLED",
            "channel_details": {"features": {"trust_endorsement_enabled": False}},
            "should_have_button": False,
            "description": "Channel with trust_endorsement disabled",
        },
        {
            "channel_id": "C789NOFEATURES",
            "channel_details": {},
            "should_have_button": False,
            "description": "Channel with no features defined",
        },
    ]

    with patch("ketchup_status_updater.status_generator.FeatureFlags") as mock_flags:
        # Trust endorsement feature is enabled but not global
        mock_flags.is_trust_endorsement_enabled.return_value = True
        mock_flags.is_trust_endorsement_global.return_value = False

        for test_case in test_cases:
            # Setup channel details mock
            mock_dependencies["channel_operations"].get_channel_details.return_value = (
                test_case["channel_details"]
            )

            # Call the method that posts to Slack
            await generator._post_to_slack_public(
                channel_id=test_case["channel_id"],
                content="Test status update",
                status_update_id="12345_abcd",
            )

            # Get the blocks that were sent
            call_args = mock_dependencies[
                "posting_handler"
            ]._post_channel_message.call_args
            blocks = call_args.kwargs["blocks"]

            # Check if trust button is present
            has_trust_button = any(
                block.get("type") == "actions"
                and any(
                    elem.get("action_id") == "trust_status_update"
                    for elem in block.get("elements", [])
                )
                for block in blocks
            )

            assert (
                has_trust_button == test_case["should_have_button"]
            ), f"{test_case['description']}: Expected button={test_case['should_have_button']}, got={has_trust_button}"

            # Reset mock for next test
            mock_dependencies["posting_handler"]._post_channel_message.reset_mock()


@pytest.mark.asyncio
async def test_trust_button_with_global_enabled(mock_dependencies):
    """Test that trust buttons appear on all channels when global flag is enabled."""
    generator = AutoStatusGenerator(**mock_dependencies)

    # Mock the posting handler's internal state
    mock_dependencies["posting_handler"]._slack_token = "test-token"
    mock_dependencies["posting_handler"]._post_channel_message = AsyncMock(
        return_value={"ok": True, "ts": "123.456"}
    )

    with patch("ketchup_status_updater.status_generator.FeatureFlags") as mock_flags:
        # Trust endorsement is both enabled and global
        mock_flags.is_trust_endorsement_enabled.return_value = True
        mock_flags.is_trust_endorsement_global.return_value = True

        # Channel has no specific enablement
        mock_dependencies["channel_operations"].get_channel_details.return_value = {}

        # Post to channel
        await generator._post_to_slack_public(
            channel_id="C999ANYCHANNEL",
            content="Test status update",
            status_update_id="12345_abcd",
        )

        # Get the blocks that were sent
        call_args = mock_dependencies["posting_handler"]._post_channel_message.call_args
        blocks = call_args.kwargs["blocks"]

        # Should have trust button because global is enabled
        has_trust_button = any(
            block.get("type") == "actions"
            and any(
                elem.get("action_id") == "trust_status_update"
                for elem in block.get("elements", [])
            )
            for block in blocks
        )

        assert has_trust_button, "Should have trust button when global flag is enabled"


@pytest.mark.asyncio
async def test_trust_metadata_storage_respects_channel_enablement(mock_dependencies):
    """Test that trust metadata is only stored for channels with trust_endorsement enabled."""
    generator = AutoStatusGenerator(**mock_dependencies)

    # Mock trust operations
    mock_dependencies["db_store"].trust_ops = AsyncMock()
    mock_dependencies["db_store"].trust_ops.store_status_update_metadata = AsyncMock()

    with patch("ketchup_status_updater.status_generator.FeatureFlags") as mock_flags:
        # Trust endorsement feature is enabled but not global
        mock_flags.is_trust_endorsement_enabled.return_value = True
        mock_flags.is_trust_endorsement_global.return_value = False

        # Test storing metadata for enabled channel
        await generator._store_status_update_metadata(
            channel_id="C123ENABLED",
            channel_name="test-channel",
            status_update_id="12345_abcd",
            message_ts="123.456",
            content_hash="hash123",
        )

        # Should be called since we're directly calling the method
        assert mock_dependencies[
            "db_store"
        ].trust_ops.store_status_update_metadata.called


@pytest.mark.asyncio
async def test_trust_endorsement_button_visibility(mock_dependencies):
    """Test that trust endorsement button should NOT be shown in an unapproved channel."""
    generator = AutoStatusGenerator(**mock_dependencies)

    # Mock the posting handler's internal state
    mock_dependencies["posting_handler"]._slack_token = "test-token"
    mock_dependencies["posting_handler"]._post_channel_message = AsyncMock(
        return_value={"ok": True, "ts": "123.456"}
    )

    with patch("ketchup_status_updater.status_generator.FeatureFlags") as mock_flags:
        # Trust endorsement feature is enabled but not global
        mock_flags.is_trust_endorsement_enabled.return_value = True
        mock_flags.is_trust_endorsement_global.return_value = False

        # Mock a channel that is NOT in TRUST_ENABLED_CHANNELS and has no features
        unapproved_channel_id = "C999UNAPPROVED"
        mock_dependencies["channel_operations"].get_channel_details.return_value = {}

        # Call the method that posts to Slack
        await generator._post_to_slack_public(
            channel_id=unapproved_channel_id,
            content="Test status update",
            status_update_id="12345_abcd",
        )

        # Get the blocks that were sent
        call_args = mock_dependencies["posting_handler"]._post_channel_message.call_args
        blocks = call_args.kwargs["blocks"]

        # Check that trust button is NOT present in unapproved channel
        has_trust_button = any(
            block.get("type") == "actions"
            and any(
                elem.get("action_id") == "trust_status_update"
                for elem in block.get("elements", [])
            )
            for block in blocks
        )

        assert not has_trust_button, f"Trust endorsement button should NOT be shown in unapproved channel {unapproved_channel_id}"

        # Reset mock and test approved channel (C094DQY7HLH is in TRUST_ENABLED_CHANNELS)
        mock_dependencies["posting_handler"]._post_channel_message.reset_mock()

        approved_channel_id = "C094DQY7HLH"  # This is in TRUST_ENABLED_CHANNELS

        await generator._post_to_slack_public(
            channel_id=approved_channel_id,
            content="Test status update",
            status_update_id="12345_efgh",
        )

        # Get the blocks that were sent for approved channel
        call_args = mock_dependencies["posting_handler"]._post_channel_message.call_args
        blocks = call_args.kwargs["blocks"]

        # Check that trust button IS present in approved channel
        has_trust_button = any(
            block.get("type") == "actions"
            and any(
                elem.get("action_id") == "trust_status_update"
                for elem in block.get("elements", [])
            )
            for block in blocks
        )

        assert has_trust_button, f"Trust endorsement button SHOULD be shown in approved channel {approved_channel_id}"
