"""
Integration tests for CSOPM State Tracker with real AWS DynamoDB.

Tests the CSOPMStateTracker service against real DynamoDB to verify:
1. Notification record creation and retrieval
2. Status updates and ping count incrementing
3. RCA and closure reminder tracking
4. Followup record management
5. Reassignment handling

Requires: AWS configured via .env.test (see .env.test.example)

Test Isolation:
- Uses test-prefixed PK values (TEST_CSOPM_NOTIFICATION#)
- Cleans up test data after each test
- Uses unique ticket keys with timestamps
"""

import asyncio
import time
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from packages.core.logging import setup_logger
from packages.core.typed_di.protocols import CSOPMTicket
from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient
from packages.slack.csopm.state import (
    PK_NOTIFICATION_PREFIX,
    SK_NOTIFICATION,
    CSOPMStateTracker,
)

logger = setup_logger(__name__)


# Test data prefixes for isolation
TEST_TICKET_PREFIX = "TEST_CSOPM-"
TEST_TABLE_NAME = "ketchup_channel_information"


@pytest.mark.integration
@pytest.mark.asyncio
class TestCSOPMStateTrackerDynamoDB:
    """Integration tests for CSOPM State Tracker with real DynamoDB."""

    @classmethod
    def generate_test_ticket_key(cls, suffix: str = "") -> str:
        """Generate a unique test ticket key with timestamp."""
        return f"{TEST_TICKET_PREFIX}{int(time.time())}_{suffix}"

    @classmethod
    def create_test_ticket(cls, ticket_key: str) -> CSOPMTicket:
        """Create a test CSOPMTicket instance."""
        return CSOPMTicket(
            key=ticket_key,
            summary=f"Test ticket for {ticket_key}",
            assignee_username="testuser",
            created_at=datetime.now(timezone.utc),
            status="New",
            exigence_id="12345",
        )

    @pytest_asyncio.fixture
    async def dynamodb_client(self):
        """Create real DynamoDB client.

        AWS profile is loaded from .env.test by root conftest.py.
        Tests are auto-skipped if AWS is not configured.
        """
        client = DynamoDBAsyncClient()
        yield client

    @pytest_asyncio.fixture
    async def state_tracker(self, dynamodb_client):
        """Create CSOPMStateTracker with real DynamoDB client."""
        return CSOPMStateTracker(
            client=dynamodb_client,
            table_name=TEST_TABLE_NAME,
        )

    async def cleanup_test_record(self, dynamodb_client: DynamoDBAsyncClient, ticket_key: str):
        """Clean up test notification record from DynamoDB."""
        try:
            pk = f"{PK_NOTIFICATION_PREFIX}{ticket_key}"
            await dynamodb_client.delete_item(
                table_name=TEST_TABLE_NAME,
                key={
                    "PK": {"S": pk},
                    "SK": {"S": SK_NOTIFICATION},
                },
            )
            logger.info(f"Cleaned up test record: {ticket_key}")
        except Exception as e:
            logger.warning(f"Failed to cleanup test record {ticket_key}: {e}")

    async def test_create_and_retrieve_notification_record(self, state_tracker, dynamodb_client):
        """Test creating and retrieving a notification record in real DynamoDB."""
        ticket_key = self.generate_test_ticket_key("CREATE_RETRIEVE")
        ticket = self.create_test_ticket(ticket_key)
        slack_id = "U_TEST_SLACK_123"

        logger.info(f"Testing create/retrieve with ticket: {ticket_key}")

        try:
            # Create notification record
            created = await state_tracker.create_notification_record(
                ticket=ticket,
                slack_id=slack_id,
            )

            # Verify created record
            assert created is not None
            assert created.ticket_key == ticket_key
            assert created.notification_status == "pending"
            assert created.ping_count == 0
            assert created.assignee_slack_id == slack_id
            assert created.assignee_jira_username == "testuser"
            assert created.rca_reminder_sent is False
            assert created.closure_reminder_sent is False

            # Wait for eventual consistency
            await asyncio.sleep(0.5)

            # Retrieve and verify
            retrieved = await state_tracker.get_notification_record(ticket_key)
            assert retrieved is not None
            assert retrieved.ticket_key == ticket_key
            assert retrieved.notification_status == "pending"
            assert retrieved.assignee_slack_id == slack_id

            logger.info("Successfully created and retrieved notification record")

        finally:
            await self.cleanup_test_record(dynamodb_client, ticket_key)

    async def test_update_notification_status(self, state_tracker, dynamodb_client):
        """Test updating notification status in DynamoDB."""
        ticket_key = self.generate_test_ticket_key("UPDATE_STATUS")
        ticket = self.create_test_ticket(ticket_key)

        logger.info(f"Testing status update with ticket: {ticket_key}")

        try:
            # Create initial record
            await state_tracker.create_notification_record(
                ticket=ticket,
                slack_id="U_TEST_456",
            )
            await asyncio.sleep(0.5)

            # Update status to 'sent'
            updated = await state_tracker.update_notification_status(
                ticket_key=ticket_key,
                status="sent",
            )

            assert updated is not None
            assert updated.notification_status == "sent"

            # Verify persistence
            retrieved = await state_tracker.get_notification_record(ticket_key)
            assert retrieved.notification_status == "sent"

            # Update to 'escalated'
            escalated = await state_tracker.update_notification_status(
                ticket_key=ticket_key,
                status="escalated",
            )
            assert escalated.notification_status == "escalated"

            logger.info("Successfully updated notification status")

        finally:
            await self.cleanup_test_record(dynamodb_client, ticket_key)

    async def test_increment_ping_count(self, state_tracker, dynamodb_client):
        """Test incrementing ping count in DynamoDB."""
        ticket_key = self.generate_test_ticket_key("PING_COUNT")
        ticket = self.create_test_ticket(ticket_key)

        logger.info(f"Testing ping count increment with ticket: {ticket_key}")

        try:
            # Create initial record with ping_count = 0
            await state_tracker.create_notification_record(
                ticket=ticket,
                slack_id="U_TEST_789",
            )
            await asyncio.sleep(0.5)

            # Increment ping count
            updated = await state_tracker.increment_ping_count(ticket_key)
            assert updated is not None
            assert updated.ping_count == 1

            # Increment again
            updated = await state_tracker.increment_ping_count(ticket_key)
            assert updated.ping_count == 2

            # Increment a third time
            updated = await state_tracker.increment_ping_count(ticket_key)
            assert updated.ping_count == 3

            # Verify persistence
            retrieved = await state_tracker.get_notification_record(ticket_key)
            assert retrieved.ping_count == 3

            logger.info("Successfully incremented ping count")

        finally:
            await self.cleanup_test_record(dynamodb_client, ticket_key)

    async def test_mark_rca_reminder_sent(self, state_tracker, dynamodb_client):
        """Test marking RCA reminder as sent in DynamoDB."""
        ticket_key = self.generate_test_ticket_key("RCA_REMINDER")
        ticket = self.create_test_ticket(ticket_key)

        logger.info(f"Testing RCA reminder flag with ticket: {ticket_key}")

        try:
            # Create initial record
            await state_tracker.create_notification_record(
                ticket=ticket,
                slack_id="U_TEST_RCA",
            )
            await asyncio.sleep(0.5)

            # Verify initially false
            initial = await state_tracker.get_notification_record(ticket_key)
            assert initial.rca_reminder_sent is False

            # Mark RCA reminder sent
            updated = await state_tracker.mark_rca_reminder_sent(ticket_key)
            assert updated is not None
            assert updated.rca_reminder_sent is True

            # Verify persistence
            retrieved = await state_tracker.get_notification_record(ticket_key)
            assert retrieved.rca_reminder_sent is True

            logger.info("Successfully marked RCA reminder as sent")

        finally:
            await self.cleanup_test_record(dynamodb_client, ticket_key)

    async def test_mark_closure_reminder_sent(self, state_tracker, dynamodb_client):
        """Test marking closure reminder as sent in DynamoDB."""
        ticket_key = self.generate_test_ticket_key("CLOSURE_REMINDER")
        ticket = self.create_test_ticket(ticket_key)

        logger.info(f"Testing closure reminder flag with ticket: {ticket_key}")

        try:
            # Create initial record
            await state_tracker.create_notification_record(
                ticket=ticket,
                slack_id="U_TEST_CLOSE",
            )
            await asyncio.sleep(0.5)

            # Verify initially false
            initial = await state_tracker.get_notification_record(ticket_key)
            assert initial.closure_reminder_sent is False

            # Mark closure reminder sent
            updated = await state_tracker.mark_closure_reminder_sent(ticket_key)
            assert updated is not None
            assert updated.closure_reminder_sent is True

            # Verify persistence
            retrieved = await state_tracker.get_notification_record(ticket_key)
            assert retrieved.closure_reminder_sent is True

            logger.info("Successfully marked closure reminder as sent")

        finally:
            await self.cleanup_test_record(dynamodb_client, ticket_key)

    async def test_handle_reassignment(self, state_tracker, dynamodb_client):
        """Test handling ticket reassignment in DynamoDB."""
        ticket_key = self.generate_test_ticket_key("REASSIGN")
        ticket = self.create_test_ticket(ticket_key)

        logger.info(f"Testing reassignment with ticket: {ticket_key}")

        try:
            # Create initial record
            await state_tracker.create_notification_record(
                ticket=ticket,
                slack_id="U_ORIGINAL_ASSIGNEE",
            )
            await asyncio.sleep(0.5)

            # Increment ping count to simulate initial notification sent
            await state_tracker.increment_ping_count(ticket_key)
            await state_tracker.increment_ping_count(ticket_key)

            # Verify initial state
            initial = await state_tracker.get_notification_record(ticket_key)
            assert initial.ping_count == 2
            assert initial.assignee_jira_username == "testuser"

            # Handle reassignment
            updated = await state_tracker.handle_reassignment(
                ticket_key=ticket_key,
                new_jira_username="newassignee",
                new_slack_id="U_NEW_ASSIGNEE",
            )

            assert updated is not None
            assert updated.assignee_jira_username == "newassignee"
            assert updated.assignee_slack_id == "U_NEW_ASSIGNEE"
            assert updated.ping_count == 1  # Reset for new assignee

            # Verify persistence
            retrieved = await state_tracker.get_notification_record(ticket_key)
            assert retrieved.assignee_jira_username == "newassignee"
            assert retrieved.assignee_slack_id == "U_NEW_ASSIGNEE"
            assert retrieved.ping_count == 1

            logger.info("Successfully handled reassignment")

        finally:
            await self.cleanup_test_record(dynamodb_client, ticket_key)

    async def test_record_not_found(self, state_tracker):
        """Test retrieving non-existent record returns None."""
        non_existent_key = "CSOPM-NONEXISTENT-12345"

        result = await state_tracker.get_notification_record(non_existent_key)
        assert result is None

    async def test_update_nonexistent_record(self, state_tracker, dynamodb_client):
        """Test updating non-existent record creates it (upsert behavior)."""
        non_existent_key = "CSOPM-NONEXISTENT-67890"

        try:
            result = await state_tracker.update_notification_status(
                ticket_key=non_existent_key,
                status="sent",
            )
            # DynamoDB update_item with return_values="ALL_NEW" creates the item
            # if it doesn't exist (upsert behavior)
            assert result is not None
            assert result.notification_status == "sent"
        finally:
            # Cleanup the created record
            await dynamodb_client.delete_item(
                key={
                    "PK": {"S": f"CSOPM_NOTIFICATION#{non_existent_key}"},
                    "SK": {"S": "NOTIFICATION"},
                },
                table_name=TEST_TABLE_NAME,
            )


@pytest.mark.integration
@pytest.mark.asyncio
class TestCSOPMFollowupRecords:
    """Integration tests for CSOPM followup record management."""

    @classmethod
    def generate_test_ticket_key(cls, suffix: str = "") -> str:
        """Generate a unique test ticket key with timestamp."""
        return f"{TEST_TICKET_PREFIX}{int(time.time())}_{suffix}"

    @pytest_asyncio.fixture
    async def dynamodb_client(self):
        """Create real DynamoDB client."""
        client = DynamoDBAsyncClient()
        yield client

    @pytest_asyncio.fixture
    async def state_tracker(self, dynamodb_client):
        """Create CSOPMStateTracker with real DynamoDB client."""
        return CSOPMStateTracker(
            client=dynamodb_client,
            table_name=TEST_TABLE_NAME,
        )

    async def cleanup_followup_records(
        self,
        dynamodb_client: DynamoDBAsyncClient,
        ticket_key: str,
    ):
        """Clean up followup records for a ticket.

        Note: This is a best-effort cleanup. Followup records have
        dynamic sort keys that include timestamps, so we need to
        scan for them.
        """
        try:
            pk = f"{PK_NOTIFICATION_PREFIX}{ticket_key}"

            # Query for all records with this PK
            response = await dynamodb_client.query(
                table_name=TEST_TABLE_NAME,
                key_condition_expression="PK = :pk",
                expression_attribute_values={":pk": {"S": pk}},
            )

            items = response.get("Items", [])
            for item in items:
                sk = item.get("SK", {}).get("S", "")
                await dynamodb_client.delete_item(
                    table_name=TEST_TABLE_NAME,
                    key={
                        "PK": {"S": pk},
                        "SK": {"S": sk},
                    },
                )

            logger.info(f"Cleaned up {len(items)} records for: {ticket_key}")
        except Exception as e:
            logger.warning(f"Failed to cleanup followup records for {ticket_key}: {e}")

    async def test_record_followup(self, state_tracker, dynamodb_client):
        """Test recording a followup in DynamoDB."""
        ticket_key = self.generate_test_ticket_key("FOLLOWUP")
        scheduled_at = datetime.now(timezone.utc)

        logger.info(f"Testing followup recording for: {ticket_key}")

        try:
            # Record a followup
            followup = await state_tracker.record_followup(
                ticket_key=ticket_key,
                followup_type="rca_reminder",
                scheduled_at=scheduled_at,
            )

            assert followup is not None
            assert followup.ticket_key == ticket_key
            assert followup.followup_type == "rca_reminder"
            assert followup.completed is False
            assert followup.completed_at is None

            logger.info("Successfully recorded followup")

        finally:
            await self.cleanup_followup_records(dynamodb_client, ticket_key)

    async def test_record_multiple_followups(self, state_tracker, dynamodb_client):
        """Test recording multiple followups for the same ticket."""
        ticket_key = self.generate_test_ticket_key("MULTI_FOLLOWUP")

        logger.info(f"Testing multiple followups for: {ticket_key}")

        try:
            # Record multiple followup types
            now = datetime.now(timezone.utc)

            followups = []
            for followup_type in ["rca_reminder", "closure_reminder", "ping"]:
                followup = await state_tracker.record_followup(
                    ticket_key=ticket_key,
                    followup_type=followup_type,
                    scheduled_at=now,
                )
                followups.append(followup)

            assert len(followups) == 3
            assert {f.followup_type for f in followups} == {
                "rca_reminder",
                "closure_reminder",
                "ping",
            }

            logger.info("Successfully recorded multiple followups")

        finally:
            await self.cleanup_followup_records(dynamodb_client, ticket_key)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_csopm_state_tracker_end_to_end():
    """End-to-end test of the CSOPM notification lifecycle.

    Tests the complete flow:
    1. Create notification record for new assignment
    2. Update status to sent
    3. Increment ping count
    4. Mark RCA reminder sent
    5. Handle reassignment
    6. Mark closure reminder sent
    7. Update status to escalated

    AWS profile is loaded from .env.test by root conftest.py.
    Test is auto-skipped if AWS is not configured.
    """
    client = DynamoDBAsyncClient()
    state_tracker = CSOPMStateTracker(
        client=client,
        table_name=TEST_TABLE_NAME,
    )
    ticket_key = f"{TEST_TICKET_PREFIX}{int(time.time())}_E2E"

    ticket = CSOPMTicket(
        key=ticket_key,
        summary="E2E test ticket",
        assignee_username="e2e_testuser",
        created_at=datetime.now(timezone.utc),
        status="New",
        exigence_id="99999",
    )

    try:
        logger.info(f"Running E2E test with ticket: {ticket_key}")

        # Step 1: Create notification record
        created = await state_tracker.create_notification_record(
            ticket=ticket,
            slack_id="U_E2E_SLACK",
        )
        assert created.notification_status == "pending"
        assert created.ping_count == 0
        await asyncio.sleep(0.3)

        # Step 2: Update status to sent
        sent = await state_tracker.update_notification_status(ticket_key, "sent")
        assert sent.notification_status == "sent"

        # Step 3: Increment ping count (simulating follow-up pings)
        for expected_count in [1, 2, 3]:
            pinged = await state_tracker.increment_ping_count(ticket_key)
            assert pinged.ping_count == expected_count

        # Step 4: Mark RCA reminder sent
        rca = await state_tracker.mark_rca_reminder_sent(ticket_key)
        assert rca.rca_reminder_sent is True

        # Step 5: Handle reassignment
        reassigned = await state_tracker.handle_reassignment(
            ticket_key=ticket_key,
            new_jira_username="new_e2e_user",
            new_slack_id="U_E2E_NEW",
        )
        assert reassigned.assignee_jira_username == "new_e2e_user"
        assert reassigned.ping_count == 1  # Reset for new assignee

        # Step 6: Mark closure reminder sent
        closure = await state_tracker.mark_closure_reminder_sent(ticket_key)
        assert closure.closure_reminder_sent is True

        # Step 7: Update status to escalated
        escalated = await state_tracker.update_notification_status(ticket_key, "escalated")
        assert escalated.notification_status == "escalated"

        # Verify final state
        final = await state_tracker.get_notification_record(ticket_key)
        assert final.notification_status == "escalated"
        assert final.rca_reminder_sent is True
        assert final.closure_reminder_sent is True
        assert final.assignee_jira_username == "new_e2e_user"
        assert final.assignee_slack_id == "U_E2E_NEW"
        assert final.ping_count == 1

        logger.info("E2E test completed successfully")

    finally:
        # Cleanup
        try:
            pk = f"{PK_NOTIFICATION_PREFIX}{ticket_key}"
            await client.delete_item(
                table_name=TEST_TABLE_NAME,
                key={
                    "PK": {"S": pk},
                    "SK": {"S": SK_NOTIFICATION},
                },
            )
            logger.info(f"Cleaned up E2E test record: {ticket_key}")
        except Exception as e:
            logger.warning(f"Failed to cleanup E2E test: {e}")
