#!/usr/bin/env python3
"""
Production-like integration test for flag review modular architecture.

This test would have caught the exact bugs we found in production:
1. Method name mismatches (_validate_trigger_id, _display_modal_via_api)
2. Parameter name mismatches (original_text vs feedback_text)

Tests the COMPLETE workflow with real AWS services where possible.
"""
import os
import sys
import asyncio
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from base_integration_test import BaseIntegrationTest


class TestFlagReviewModularIntegration(BaseIntegrationTest):
    """Production-like test for the refactored flag review system."""

    def __init__(self):
        super().__init__(
            test_name="Flag Review Modular Integration Test",
            env_vars={
                "DYNAMODB_TABLE_NAME": "ketchup_channel_information",
                "AWS_REGION": "eu-west-1",
                "AWS_SECRET_NAME": "Ketchup_Token_Secrets",
            },
        )

    async def run_test(self) -> bool:
        """Run the complete flag review workflow test."""
        try:
            # Get required services from DI container
            flag_review_handler = self.get_service("flag_review_handler")
            dynamodb_store = self.get_service("dynamodb_store")
            
            if not all([flag_review_handler, dynamodb_store]):
                self.logger.error("Failed to get required services")
                return False

            # Test 1: Verify modular architecture is properly initialized
            self.logger.info("Test 1: Verifying modular architecture...")
            if not self._verify_modular_architecture(flag_review_handler):
                return False
            self.logger.info("✓ Modular architecture verified")

            # Test 2: Test modal display workflow (would catch first bug)
            self.logger.info("Test 2: Testing modal display workflow...")
            if not await self._test_modal_display_workflow(flag_review_handler):
                return False
            self.logger.info("✓ Modal display workflow successful")

            # Test 3: Test form submission workflow (would catch second bug)
            self.logger.info("Test 3: Testing form submission workflow...")
            if not await self._test_form_submission_workflow(flag_review_handler):
                return False
            self.logger.info("✓ Form submission workflow successful")

            # Test 4: Test DM context handling
            self.logger.info("Test 4: Testing DM context handling...")
            if not await self._test_dm_context_handling(flag_review_handler):
                return False
            self.logger.info("✓ DM context handling successful")

            # Test 5: End-to-end workflow with real DynamoDB
            self.logger.info("Test 5: Testing end-to-end with real DynamoDB...")
            if not await self._test_end_to_end_with_dynamodb(flag_review_handler, dynamodb_store):
                return False
            self.logger.info("✓ End-to-end workflow successful")

            self.logger.info("\n" + "=" * 50)
            self.logger.info("✅ ALL TESTS PASSED - Production bugs would have been caught!")
            return True

        except Exception as e:
            self.logger.error(f"Test failed with exception: {e}", exc_info=True)
            return False

    def _verify_modular_architecture(self, handler) -> bool:
        """Verify the modular architecture is properly set up."""
        # Check all required modules exist
        required_modules = [
            'status_flag_processor',
            'command_flag_processor', 
            'admin_action_processor',
            'modal_orchestrator',
            'validators'
        ]
        
        for module in required_modules:
            if not hasattr(handler, module):
                self.logger.error(f"Missing module: {module}")
                return False

        # Verify modal orchestrator has correct method names (would catch bug #1)
        modal = handler.modal_orchestrator
        
        # These MUST be private methods
        if not hasattr(modal, '_validate_trigger_id'):
            self.logger.error("Missing _validate_trigger_id method")
            return False
        if not hasattr(modal, '_display_modal_via_api'):
            self.logger.error("Missing _display_modal_via_api method")
            return False
            
        # These should NOT exist (the bug was calling these)
        if hasattr(modal, 'validate_trigger_id'):
            self.logger.error("Public validate_trigger_id should not exist")
            return False
        if hasattr(modal, 'display_modal_via_api'):
            self.logger.error("Public display_modal_via_api should not exist")
            return False

        return True

    async def _test_modal_display_workflow(self, handler) -> bool:
        """Test the modal display workflow that exposed the first bug."""
        # Create a realistic payload from a flag button click
        payload = {
            "type": "block_actions",
            "trigger_id": "trigger_" + "x" * 40,  # Valid length
            "user": {"id": "U_TEST_USER", "username": "test_user"},
            "channel": {"id": "C_TEST_CHANNEL"},
            "actions": [{
                "action_id": "flag_status_review",
                "value": "C_TEST|1234567890.123456|status_123"
            }],
            "response_url": "https://hooks.slack.com/test"
        }

        # Mock ONLY the final Slack API call, let everything else run
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"ok": True})
            
            mock_post = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__.return_value.post = mock_post
            mock_session.return_value.__aexit__ = AsyncMock()

            # This will exercise the full chain:
            # handler → status_flag_processor → modal_orchestrator → _display_modal_via_api
            result = await handler.process_flag_action(payload)
            
            if not result:
                self.logger.error("Modal display workflow failed")
                return False
                
            # Verify the API was called (modal was displayed)
            if not mock_post.called:
                self.logger.error("Slack API was not called")
                return False

        return True

    async def _test_form_submission_workflow(self, handler) -> bool:
        """Test the form submission workflow that exposed the second bug."""
        # Create a realistic modal submission payload
        payload = {
            "type": "view_submission",
            "view": {
                "callback_id": "command_flag_review_modal",
                "private_metadata": "C_TEST|cmd_123|status|D_ORIGINAL",
                "state": {
                    "values": {
                        "feedback_block": {
                            "feedback_input": {"value": "This output is incorrect"}
                        }
                    }
                }
            },
            "user": {"id": "U_TEST_USER", "username": "test_user"}
        }

        # Mock database operations but let the parameter passing work
        original_put_item = handler.db_store.client.put_item
        captured_item = None
        
        async def capture_put_item(**kwargs):
            nonlocal captured_item
            captured_item = kwargs.get('item', {})
            return {"ResponseMetadata": {}}
        
        handler.db_store.client.put_item = AsyncMock(side_effect=capture_put_item)

        try:
            # This will exercise: handler → command_flag_processor → api_client.store_command_flag
            result = await handler.process_command_flag_action(payload)
            
            if not result:
                self.logger.error("Form submission workflow failed")
                return False
            
            # Verify correct parameters were stored (would catch bug #2)
            if captured_item:
                # Check for 'original_text' not 'feedback_text'
                if 'original_text' not in captured_item:
                    self.logger.error("Missing 'original_text' in stored item")
                    return False
                if captured_item['original_text'].get('S') != "This output is incorrect":
                    self.logger.error("Wrong text stored")
                    return False
                    
                # Check for 'original_channel'
                if 'original_channel' not in captured_item:
                    self.logger.error("Missing 'original_channel' in stored item")
                    return False
                if captured_item['original_channel'].get('S') != "D_ORIGINAL":
                    self.logger.error("Wrong channel stored")
                    return False
            else:
                self.logger.error("No item was captured")
                return False
                
        finally:
            # Restore original
            handler.db_store.client.put_item = original_put_item

        return True

    async def _test_dm_context_handling(self, handler) -> bool:
        """Test that DM context is properly preserved."""
        dm_channel = "D_USER_DM"
        
        # Test from DM command
        dm_payload = {
            "type": "block_actions",
            "trigger_id": "trigger_" + "x" * 40,
            "user": {"id": "U_DM_USER", "username": "dm_user"},
            "channel": {"id": dm_channel},  # DM channel
            "actions": [{
                "action_id": "flag_status_review",
                "value": f"{dm_channel}|1234567890.123456|cmd_dm_123|status"
            }]
        }

        # Mock the modal display to capture the metadata
        captured_metadata = None
        
        async def capture_modal_display(trigger_id, modal_view, modal_type):
            nonlocal captured_metadata
            captured_metadata = modal_view.get('private_metadata', '')
            return True
        
        original_method = handler.modal_orchestrator._display_modal_via_api
        handler.modal_orchestrator._display_modal_via_api = AsyncMock(side_effect=capture_modal_display)

        try:
            result = await handler.process_flag_action(dm_payload)
            
            if not result:
                self.logger.error("DM context handling failed")
                return False
                
            # Verify DM context was preserved in metadata
            if not captured_metadata or dm_channel not in captured_metadata:
                self.logger.error(f"DM context not preserved: {captured_metadata}")
                return False
                
        finally:
            handler.modal_orchestrator._display_modal_via_api = original_method

        return True

    async def _test_end_to_end_with_dynamodb(self, handler, dynamodb_store) -> bool:
        """Test end-to-end with real DynamoDB operations."""
        test_channel = "C_E2E_TEST"
        f"{int(datetime.now(timezone.utc).timestamp())}.123456"
        test_cmd_id = f"{int(datetime.now(timezone.utc).timestamp())}_e2e"
        
        try:
            # Store command flag using the actual API client method
            api_client = handler.command_flag_processor.api_client
            
            # This tests the exact parameter names we fixed
            success = await api_client.store_command_flag(
                channel_id=test_channel,
                command_execution_id=test_cmd_id,
                user_id="U_E2E_USER",
                user_name="e2e_user",
                original_text="E2E test feedback",  # NOT feedback_text
                command_type="status",
                original_channel="D_E2E_DM"  # Required parameter
            )
            
            if not success:
                self.logger.error("Failed to store command flag")
                return False

            # Verify data was stored correctly
            result = await dynamodb_store.client.get_item(
                table_name=dynamodb_store.table_name,
                key={
                    "PK": {"S": f"FEEDBACK#{test_channel}#{test_cmd_id}"},
                    "SK": {"S": "FLAG#U_E2E_USER"}
                }
            )
            
            if 'Item' not in result:
                self.logger.error("Item not found in DynamoDB")
                return False
                
            item = result['Item']
            if item.get('original_text', {}).get('S') != "E2E test feedback":
                self.logger.error("Wrong text in DynamoDB")
                return False
            if item.get('original_channel', {}).get('S') != "D_E2E_DM":
                self.logger.error("Wrong channel in DynamoDB")
                return False

            # Clean up test data
            await dynamodb_store.client.delete_item(
                table_name=dynamodb_store.table_name,
                key={
                    "PK": {"S": f"FEEDBACK#{test_channel}#{test_cmd_id}"},
                    "SK": {"S": "FLAG#U_E2E_USER"}
                }
            )

        except Exception as e:
            self.logger.error(f"E2E test failed: {e}")
            return False

        return True


async def main():
    """Run the production-like integration test."""
    test = TestFlagReviewModularIntegration()
    result = await test.execute()
    exit(0 if result else 1)


if __name__ == "__main__":
    asyncio.run(main())
