#!/usr/bin/env python3
"""
Integration test specifically for the modular flag review fixes.
Tests the exact bugs we found in production.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import asyncio
from unittest.mock import AsyncMock, Mock, patch


async def test_production_bugs():
    """Test that would have caught both production bugs."""
    print("\n=== Testing Flag Review Production Bugs ===\n")
    
    # Import after path setup
    from packages.slack.interactive_elements.flag_review_handler import FlagReviewHandler
    
    # Create handler with minimal mocks
    posting_handler = Mock()
    posting_handler.post_message = AsyncMock(return_value={"ok": True})
    
    db_store = Mock()
    db_store.client = AsyncMock()
    db_store.client.put_item = AsyncMock(return_value={})
    db_store.table_name = "test_table"
    
    secrets_manager = Mock() 
    secrets_manager.get_slack_api_token_async = AsyncMock(return_value="test-token")
    
    handler = FlagReviewHandler(posting_handler, db_store, secrets_manager)
    
    # Test 1: Modal method names (first bug)
    print("Test 1: Checking modal method names...")
    modal = handler.modal_orchestrator
    
    # Check correct private methods exist
    assert hasattr(modal, '_validate_trigger_id'), "Missing _validate_trigger_id"
    assert hasattr(modal, '_display_modal_via_api'), "Missing _display_modal_via_api"
    
    # Check wrong public methods don't exist
    assert not hasattr(modal, 'validate_trigger_id'), "Public validate_trigger_id shouldn't exist"
    assert not hasattr(modal, 'display_modal_via_api'), "Public display_modal_via_api shouldn't exist"
    
    print("✓ Modal method names correct (would have caught bug #1)")
    
    # Test 2: API parameter names (second bug)
    print("\nTest 2: Checking API parameter names...")
    
    # Check the store_command_flag signature
    import inspect
    api_client = handler.command_flag_processor.api_client
    sig = inspect.signature(api_client.store_command_flag)
    params = list(sig.parameters.keys())
    
    assert 'original_text' in params, "Should have 'original_text' not 'feedback_text'"
    assert 'original_channel' in params, "Missing 'original_channel' parameter"
    assert 'feedback_text' not in params, "'feedback_text' should not be a parameter"
    
    print("✓ API parameters correct (would have caught bug #2)")
    
    # Test 3: Full workflow
    print("\nTest 3: Testing full workflow...")
    
    with patch('aiohttp.ClientSession') as mock_session:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"ok": True})
        mock_session.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        mock_session.return_value.__aexit__ = AsyncMock()
        
        # Test flag button click
        payload = {
            "type": "block_actions",
            "trigger_id": "trigger_" + "x" * 40,
            "user": {"id": "U123", "username": "test"},
            "channel": {"id": "D123"},
            "actions": [{"action_id": "flag_status_review", "value": "D123|ts|id"}]
        }
        
        result = await handler.process_flag_action(payload)
        assert result is True, "Flag action failed"
        print("✓ Flag button workflow successful")
        
        # Test form submission
        payload2 = {
            "type": "view_submission",
            "view": {
                "callback_id": "command_flag_review_modal",
                "private_metadata": "C123|cmd_123|status|D789",
                "state": {
                    "values": {
                        "feedback_block": {
                            "feedback_input": {"value": "Test feedback"}
                        }
                    }
                }
            },
            "user": {"id": "U123", "username": "test"}
        }
        
        result2 = await handler.process_command_flag_action(payload2)
        assert result2 is True, "Form submission failed"
        print("✓ Form submission workflow successful")
    
    print("\n" + "=" * 50)
    print("✅ ALL TESTS PASSED - Both production bugs would have been caught!")
    return True


if __name__ == "__main__":
    try:
        result = asyncio.run(test_production_bugs())
        exit(0 if result else 1)
    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
