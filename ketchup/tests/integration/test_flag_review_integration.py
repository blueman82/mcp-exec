#!/usr/bin/env python3
"""
Integration test for flag review functionality.

Tests the complete flow of flagging a status update for review,
posting to the review channel, and admin acknowledgment.
"""
import asyncio
from datetime import datetime, timezone

from base_integration_test import BaseIntegrationTest


class TestFlagReviewIntegration(BaseIntegrationTest):
    """Test flag review feature end-to-end."""

    def __init__(self):
        super().__init__(
            test_name="Flag Review Integration Test",
            env_vars={
                "KETCHUP_TRUST_ENDORSEMENT_FEATURE": "true",
                "KETCHUP_TRUST_ENDORSEMENT_GLOBAL": "true",
                "DYNAMODB_TABLE_NAME": "ketchup_channel_information",
            },
        )

    async def run_test(self) -> bool:
        """Run the flag review integration test."""
        # Get required services
        flag_review_handler = self.get_service("flag_review_handler")
        dynamodb_store = self.get_service("dynamodb_store")
        posting_handler = self.get_service("slack_posting")

        if not all([flag_review_handler, dynamodb_store, posting_handler]):
            self.logger.error("Failed to get required services")
            return False

        # Test data
        test_channel_id = "C094BNAUTDJ"  # Test channel
        test_message_ts = f"{int(datetime.now(timezone.utc).timestamp())}.123456"
        test_status_update_id = f"{int(datetime.now(timezone.utc).timestamp())}_test123"
        test_user_id = "U_TEST_USER"
        test_user_name = "test_user"

        try:
            # Test 1: Check rate limiting via validators module
            self.logger.info("Test 1: Testing rate limiting...")
            # Access the validators module from the refactored architecture
            validators = flag_review_handler.validators
            for i in range(15):  # Try 15 times (should hit limit at 10)
                result = validators.check_rate_limit(f"U_TEST_{i}")
                if i < 10:
                    if not result:
                        self.logger.error(
                            f"Rate limit failed at attempt {i+1}, expected to pass"
                        )
                        return False
                else:
                    if result:
                        self.logger.error(
                            f"Rate limit passed at attempt {i+1}, expected to fail"
                        )
                        return False
            self.logger.info("✓ Rate limiting working correctly")

            # Test 2: Atomic flag creation
            self.logger.info("Test 2: Testing atomic flag creation...")

            # First flag should succeed
            result1 = await flag_review_handler._add_flag_atomically(
                channel_id=test_channel_id,
                message_ts=test_message_ts,
                user_id=test_user_id,
                user_name=test_user_name,
                feedback_text="This summary is incorrect",
                validation_issues=[],
                status_update_id=test_status_update_id,
            )

            if not result1["success"]:
                self.logger.error("First flag attempt failed")
                return False
            self.logger.info("✓ First flag created successfully")

            # Second flag should fail (already flagged)
            result2 = await flag_review_handler._add_flag_atomically(
                channel_id=test_channel_id,
                message_ts=test_message_ts,
                user_id="U_DIFFERENT_USER",
                user_name="different_user",
                feedback_text="Also incorrect",
                validation_issues=[],
                status_update_id=test_status_update_id,
            )

            if result2["success"] or result2.get("error") != "already_flagged":
                self.logger.error(
                    "Second flag attempt should have failed with 'already_flagged'"
                )
                return False
            self.logger.info("✓ Duplicate flag correctly rejected")

            # Test 3: Check flag status retrieval
            self.logger.info("Test 3: Testing flag status retrieval...")
            flag_status = await flag_review_handler._get_flag_status(
                test_channel_id, test_message_ts
            )

            if not flag_status or not flag_status["is_flagged"]:
                self.logger.error("Failed to retrieve flag status")
                return False

            if flag_status["flagged_by"] != test_user_id:
                self.logger.error(
                    f"Wrong user in flag status: {flag_status['flagged_by']}"
                )
                return False
            self.logger.info("✓ Flag status retrieved correctly")

            # Test 4: Check feedback data
            self.logger.info("Test 4: Testing feedback data retrieval...")
            feedback_data = await flag_review_handler._get_feedback_data(
                test_channel_id, test_message_ts
            )

            if not feedback_data:
                self.logger.error("Failed to retrieve feedback data")
                return False

            if feedback_data["user_id"] != test_user_id:
                self.logger.error("Wrong user in feedback data")
                return False

            if feedback_data["feedback_text"] != "This summary is incorrect":
                self.logger.error("Wrong feedback text")
                return False
            self.logger.info("✓ Feedback data retrieved correctly")

            # Test 5: Test feedback validation
            self.logger.info("Test 5: Testing feedback validation...")

            # Test with mentions and long text
            test_text = (
                "This summary is wrong <@U123456> should check <#C123456> " + "x" * 2000
            )
            validation_result = await flag_review_handler._validate_feedback(
                text=test_text, user_id=test_user_id, channel_id=test_channel_id
            )

            if not validation_result["valid"]:
                self.logger.error("Validation should not reject feedback")
                return False

            if "truncated_length" not in validation_result["issues"]:
                self.logger.error("Should have detected length truncation")
                return False

            if "contains_mentions" not in validation_result["issues"]:
                self.logger.error("Should have detected mentions")
                return False

            if validation_result["metadata"]["user_mentions"] != 1:
                self.logger.error("Should have found 1 user mention")
                return False

            if validation_result["metadata"]["channel_mentions"] != 1:
                self.logger.error("Should have found 1 channel mention")
                return False
            self.logger.info("✓ Feedback validation working correctly")

            # Test 6: Test payload processing simulation
            self.logger.info("Test 6: Testing payload processing...")

            # Simulate button click payload

            # Update feedback status
            await flag_review_handler._update_feedback_status(
                channel_id=test_channel_id,
                message_ts=test_message_ts,
                status="acknowledged",
                acknowledged_by="U_ADMIN_USER",
                acknowledged_at=datetime.now(timezone.utc).isoformat(),
            )

            # Verify status update
            updated_feedback = await flag_review_handler._get_feedback_data(
                test_channel_id, test_message_ts
            )
            if not updated_feedback or updated_feedback["status"] != "acknowledged":
                self.logger.error("Failed to update feedback status")
                return False
            self.logger.info("✓ Feedback acknowledgment working correctly")

            # Test 7: Cleanup test - archive cleanup
            self.logger.info("Test 7: Testing archive cleanup...")

            # Run cleanup
            cleanup_success = (
                await dynamodb_store.feedback_ops.cleanup_channel_feedback_data(
                    test_channel_id
                )
            )

            if not cleanup_success:
                self.logger.error("Cleanup failed")
                return False

            # Verify data is gone
            flag_status_after = await flag_review_handler._get_flag_status(
                test_channel_id, test_message_ts
            )
            feedback_after = await flag_review_handler._get_feedback_data(
                test_channel_id, test_message_ts
            )

            if flag_status_after or feedback_after:
                self.logger.error("Data still exists after cleanup")
                return False
            self.logger.info("✓ Archive cleanup working correctly")

            return True

        except Exception as e:
            self.logger.error(f"Test failed with exception: {e}", exc_info=True)
            return False


async def main():
    """Run the integration test."""
    test = TestFlagReviewIntegration()
    result = await test.execute()
    exit(0 if result else 1)


if __name__ == "__main__":
    asyncio.run(main())
