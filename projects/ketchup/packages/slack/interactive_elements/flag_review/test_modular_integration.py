#!/usr/bin/env python3
"""
Quick integration test to catch the exact bugs we found in production.
Tests the REAL modular workflow without mocking internal calls.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch


async def test_modal_method_names():
    """Test that would have caught the first bug - method name mismatch."""
    from packages.slack.interactive_elements.flag_review_handler import FlagReviewHandler

    # Create handler with minimal mocks
    posting_handler = Mock()
    db_store = Mock()
    db_store.client = AsyncMock()
    secrets_manager = Mock()
    secrets_manager.get_slack_api_token_async = AsyncMock(return_value="test-token")

    handler = FlagReviewHandler(posting_handler, db_store, secrets_manager)

    # Check the actual method names exist
    modal = handler.modal_orchestrator

    # These MUST be private methods (with underscore)
    assert hasattr(modal, "_validate_trigger_id"), "Missing _validate_trigger_id method"
    assert hasattr(modal, "_display_modal_via_api"), "Missing _display_modal_via_api method"

    # These should NOT exist (bug was calling without underscore)
    assert not hasattr(modal, "validate_trigger_id"), "Public validate_trigger_id should not exist"
    assert not hasattr(
        modal, "display_modal_via_api"
    ), "Public display_modal_via_api should not exist"

    print("✓ Modal method names correct")
    return True


async def test_api_parameter_names():
    """Test that would have caught the second bug - parameter mismatch."""
    import inspect

    from packages.slack.interactive_elements.flag_review.api_client import FlagReviewApiClient

    # Create a mock container
    container = type(
        "Container",
        (),
        {
            "get_secrets_manager": lambda: Mock(),
            "get_db_store": lambda: Mock(),
            "get_posting_handler": lambda: Mock(),
        },
    )()

    api_client = FlagReviewApiClient(container)

    # Check actual method signature
    sig = inspect.signature(api_client.store_command_flag)
    params = list(sig.parameters.keys())

    # Must have these exact parameter names
    assert "original_text" in params, "Missing 'original_text' parameter (not 'feedback_text')"
    assert "original_channel" in params, "Missing 'original_channel' parameter"
    assert "command_type" in params, "Missing 'command_type' parameter"

    print(f"✓ API parameters correct: {params[1:]}")  # Skip 'self'
    return True


async def test_full_workflow():
    """Test the complete workflow that exposed both bugs."""
    from packages.slack.interactive_elements.flag_review_handler import FlagReviewHandler

    # Minimal mocks - only external boundaries
    posting_handler = Mock()
    posting_handler.post_message = AsyncMock(return_value={"ok": True})

    db_store = Mock()
    db_store.client = AsyncMock()
    db_store.client.put_item = AsyncMock(return_value={})
    db_store.table_name = "test_table"

    secrets_manager = Mock()
    secrets_manager.get_slack_api_token_async = AsyncMock(return_value="test-token")

    handler = FlagReviewHandler(posting_handler, db_store, secrets_manager)

    # Mock ONLY the final Slack API call, not internal methods
    with patch("aiohttp.ClientSession") as mock_session:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"ok": True})
        mock_session.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )
        mock_session.return_value.__aexit__ = AsyncMock()

        # Test 1: Flag button click (would trigger first bug)
        payload1 = {
            "type": "block_actions",
            "trigger_id": "trigger_" + "x" * 30,
            "user": {"id": "U123", "username": "test"},
            "channel": {"id": "D123"},  # DM context
            "actions": [{"action_id": "flag_status_review", "value": "D123|msg_ts|cmd_id"}],
        }

        result1 = await handler.process_flag_action(payload1)
        assert result1 is True, "Flag button click failed"
        print("✓ Flag button click workflow successful")

        # Test 2: Form submission (would trigger second bug)
        payload2 = {
            "type": "view_submission",
            "view": {
                "callback_id": "command_flag_review_modal",
                "private_metadata": "C123|cmd_123|status|D789",
                "state": {
                    "values": {"feedback_block": {"feedback_input": {"value": "Test feedback"}}}
                },
            },
            "user": {"id": "U123", "username": "test"},
        }

        result2 = await handler.process_command_flag_action(payload2)
        assert result2 is True, "Form submission failed"
        print("✓ Form submission workflow successful")

    return True


async def main():
    """Run all integration tests."""
    print("\n=== Running Integration Tests That Would Catch Production Bugs ===\n")

    tests = [
        ("Modal Method Names", test_modal_method_names),
        ("API Parameter Names", test_api_parameter_names),
        ("Full Workflow", test_full_workflow),
    ]

    all_passed = True
    for name, test_func in tests:
        try:
            print(f"Testing {name}...")
            result = await test_func()
            if not result:
                print(f"✗ {name} FAILED")
                all_passed = False
        except Exception as e:
            print(f"✗ {name} FAILED with error: {e}")
            all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("✅ ALL TESTS PASSED - These would have caught the production bugs!")
    else:
        print("❌ SOME TESTS FAILED")

    return all_passed


if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)
