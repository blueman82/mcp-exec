# Implementation Plan: CSOPM Link Service

**Created**: 2025-10-29
**Updated**: 2025-10-30 (Added Agent Assignments)
**Updated**: 2025-11-03 (Critical Corrections - DynamoDB API & Query Pattern)
**Updated**: 2025-11-03 (Architectural Correction - Native Email Resolution)
**Target**: Automated CSOPM ticket notification and follow-up creation via Slack
**Estimated Tasks**: 29 tasks (added Task 2.5 for email resolution)
**Estimated Time**: 3-4 days (with parallelization)
**Parallelization Strategy**: Maximum 6-way parallel execution in Phase 2

---

## ⚠️ CRITICAL CORRECTIONS (2025-11-03)

This plan has been updated based on empirical codebase analysis to fix critical discrepancies:

### 1. **DynamoDB API Pattern** ✅ CORRECTED
**Issue**: Original plan used simplified `db_store.put_item(PK=..., SK=...)` which doesn't exist.

**Actual Pattern**: Must use `db_store.client.put_item()` with DynamoDB type descriptors:
```python
await self.db_store.client.put_item(
    item={
        "PK": {"S": "value"},        # String
        "SK": {"S": "value"},        # String
        "count": {"N": "123"},       # Number (as string)
        "flag": {"BOOL": True},      # Boolean
        "ttl": {"N": str(timestamp)} # TTL as number-string
    },
    table_name=self.db_store.table_name
)
```

**Applied to**: Tasks 3, 4, 5 (all DynamoDB operations)

### 2. **Email-to-User-ID Resolution** ✅ ADDED
**Issue**: Original plan assumed `user_ops.get_slack_id_by_email()` exists - it doesn't.

**Solution**: Implement native email resolution in SlackUserOps using Slack's `users.lookupByEmail` API.

**Implementation**: Added **Task 2.5** that adds native method to SlackUserOps:
- Uses Slack API `users.lookupByEmail` endpoint
- Leverages existing retry/backoff decorators from `packages/core/resilience/`
- Integrates with existing UserStore for DB caching
- Reuses SlackAsyncClient base class patterns

**Applied to**: New Task 2.5 added between Tasks 2 and 3

### 3. **Query Pattern** ✅ CORRECTED
**Issue**: Original plan used `db_store.query_items()` which doesn't exist.

**Actual Pattern**: Must use `db_store.client.query()` with key conditions:
```python
response = await self.db_store.client.query(
    table_name=self.db_store.table_name,
    key_condition_expression="PK = :pk AND begins_with(SK, :sk_prefix)",
    expression_attribute_values={
        ":pk": {"S": f"CSOPM_TICKET#{ticket_id}"},
        ":sk_prefix": {"S": "FOLLOWUP#"}
    },
    select="COUNT"
)
count = response.get("Count", 0)
```

**Applied to**: Task 5 (`_is_first_followup()` helper method)

### 4. **Protocol Location** ℹ️ CLARIFIED
**Note**: Protocols should be in `packages/core/typed_di/service_registrations/protocols/`, NOT `packages/services/protocols/`. This aligns with existing codebase structure.

---

## Execution Strategy

This implementation plan uses **10 phases** with **strategic parallelization**:
- **Maximum Concurrency**: 6 agents (Phase 2)
- **QA Strategy**: Phase-based verification (7 checkpoints vs 28 task-by-task)
- **Timeline Compression**: 60-70% reduction (10-12 days → 3.5-4 days)
- **Total Agent Assignments**: 26 across 28 tasks

### Phase Overview
1. **Phase 1** (Sequential): Foundation - Protocol + Slack Client + Email Resolution (Tasks 1, 2, 2.5)
2. **Phase 2** (6-way Parallel): Core service methods + infrastructure prep ⭐ PEAK
3. **Phase 3** (Sequential): TypedDI integration
4. **Phase 4** (Sequential): FastAPI foundation
5. **Phase 5** (4-way Parallel): FastAPI features + health check
6. **Phase 6** (Sequential): Workflow orchestration
7. **Phase 7** (3-way Parallel): Docker + Testing
8. **Phase 8** (Sequential): Metrics integration
9. **Phase 9** (Sequential): Documentation finalization
10. **Phase 10** (Sequential): Validation + Deployment

## Context for the Engineer

You are implementing this feature in the Ketchup codebase that:
- Uses **Python 3.12** with **FastAPI** for microservices
- Follows **TypedDI** pattern for dependency injection (protocol-first architecture)
- Uses **DynamoDB single-table design** with PK/SK composite keys
- Integrates with **MCP-JIRA** (Model Context Protocol on port 8081) for JIRA operations
- Uses **Slack Bot API** for interactive messaging
- Tests with **pytest** and **pytest-asyncio**
- Deploys as **Docker containers** on prod1/prod2 behind load balancer
- Uses **Python logging** (not CloudWatch) - logs viewable via ketchup-log-viewer

**You are expected to**:
- Write tests BEFORE implementation (TDD - Test-Driven Development)
- Commit frequently (after each completed task or logical grouping)
- Follow existing code patterns extensively
- Keep changes minimal (YAGNI - You Aren't Gonna Need It)
- Avoid duplication (DRY - Don't Repeat Yourself)
- Reference existing services: jira-reporter, status-updater, maintenance-fetcher

## Prerequisites Checklist

Before starting, verify:

- [ ] Python 3.12 installed
- [ ] Docker and Docker Compose installed
- [ ] AWS CLI configured with `campaign_prod_v7` profile, region `eu-west-1`
- [ ] SSH access to ketchup-prod1.campaign.adobe.com
- [ ] MCP-JIRA server running locally (port 8081)
- [ ] DynamoDB accessible (AWS DynamoDB) - `ketchup_channel_information` table
- [ ] Branch created: `git checkout -b feature/csopm-link-service`
- [ ] Familiarize with existing services:
  - `jira_reporter/` - Similar polling pattern
  - `packages/integrations/async_mcp_client.py` - JIRA integration (MCPAsyncClient)
  - `packages/slack/user_operations/user_ops.py` - Slack user resolution
  - `packages/db/dynamodb_store.py` - DynamoDB operations
  - `packages/slack/interactive_elements/payload_processor.py` - Slack interactive element processing
  - `packages/core/event_parsing_utils.py` - Event parsing utilities
  - `packages/core/jira_constants.py` - Valid JIRA project constants

---

# PHASE 1: Foundation (Sequential - Day 1 Morning)

**Duration**: 5-6 hours
**Parallelization**: ❌ Sequential (critical path - no parallelization possible)
**Why Sequential**: Protocol defines all interfaces - everything depends on this foundation

---

## Task 1: Create Service Protocol Definition

**File(s)**: `packages/services/protocols/csopm_link_protocol.py`
**Depends on**: None
**Estimated time**: 3-4 hours

### 🤖 Agent Assignment

- **Agent**: `1x python-backend-tdd-agent`
- **Parallel**: ❌ **MUST be first** - Defines interfaces for all subsequent work
- **Phase**: Phase 1
- **Launch Command**: `/task python-backend-tdd-agent "Create Service Protocol Definition per Task 1 in docs/plans/csopm-link-service.md"`

### What you're building

Creating the protocol (interface) for the CSOPM link service following Ketchup's TypedDI pattern. This defines the contract that the concrete implementation must fulfill.

### Test First (TDD)

**Test file**: `tests/unit/services/protocols/test_csopm_link_protocol.py`

**Test structure**:
```python
test protocol can be imported
test protocol has required methods
test protocol methods have correct signatures
```

**Test specifics**:
- No mocking needed (just structural validation)
- Assert method signatures match expected async patterns
- Verify return type hints are correct

**Example test skeleton**:
```python
# tests/unit/services/protocols/test_csopm_link_protocol.py
import pytest
from typing import get_type_hints
from packages.services.protocols.csopm_link_protocol import CSOPMLinkServiceProtocol


def test_protocol_has_poll_method():
    """Test that protocol defines poll_for_new_csopm_tickets method."""
    assert hasattr(CSOPMLinkServiceProtocol, 'poll_for_new_csopm_tickets')

    # Verify it's an async method
    hints = get_type_hints(CSOPMLinkServiceProtocol.poll_for_new_csopm_tickets)
    assert 'return' in hints


def test_protocol_has_send_notification_method():
    """Test that protocol defines send_notification_to_assignee method."""
    assert hasattr(CSOPMLinkServiceProtocol, 'send_notification_to_assignee')


def test_protocol_has_create_followup_method():
    """Test that protocol defines create_followup_ticket method."""
    assert hasattr(CSOPMLinkServiceProtocol, 'create_followup_ticket')


def test_protocol_has_get_metrics_method():
    """Test that protocol defines get_metrics method."""
    assert hasattr(CSOPMLinkServiceProtocol, 'get_metrics')
```

### Implementation

**Approach**:
Create a Protocol class (from typing module) that defines the interface. Follow the pattern from existing Slack services.

**Code structure**:
```python
# packages/services/protocols/csopm_link_protocol.py
from typing import Protocol, Dict, Any, List, Optional


class CSOPMLinkServiceProtocol(Protocol):
    """Protocol defining CSOPM link service interface."""

    async def poll_for_new_csopm_tickets(self) -> List[Dict[str, Any]]:
        """
        Poll JIRA for new CSOPM tickets created in last 15 minutes.

        Returns:
            List of CSOPM ticket dictionaries
        """
        ...

    async def send_notification_to_assignee(
        self, csopm_ticket: Dict[str, Any]
    ) -> bool:
        """
        Send DM notification to CSOPM assignee with ticket details.

        Args:
            csopm_ticket: CSOPM ticket data from JIRA

        Returns:
            True if notification sent successfully, False otherwise
        """
        ...

    async def create_followup_ticket(
        self, ticket_data: Dict[str, Any], user_id: str
    ) -> Dict[str, Any]:
        """
        Create follow-up ticket and link to CSOPM.

        Args:
            ticket_data: Follow-up ticket details from modal
            user_id: Slack user ID of engineer creating ticket

        Returns:
            Dict with creation result including ticket_id and status
        """
        ...

    async def get_metrics(
        self, period_type: str, month_keys: List[str]
    ) -> Dict[str, Any]:
        """
        Get CSOPM link metrics for specified period.

        Args:
            period_type: 'Q1', 'Q2', 'Q3', 'Q4', 'YTD', 'custom'
            month_keys: List of month keys like ['2025_10', '2025_11']

        Returns:
            Dict with aggregated metrics
        """
        ...
```

**Key points**:
- Follow pattern from: `packages/slack/services/protocols/` (if exists, otherwise create new pattern)
- Use `Protocol` from typing module (Python 3.8+)
- All methods should be async (use `async def`)
- Use type hints extensively
- Methods have `...` body (not `pass`)

**Integration points**:
- Imports needed: `from typing import Protocol, Dict, Any, List, Optional`

### Verification

**Manual testing**:
1. Import the protocol: `python -c "from packages.services.protocols.csopm_link_protocol import CSOPMLinkServiceProtocol; print('OK')"`
2. Verify no syntax errors

**Automated tests**:
```bash
pytest tests/unit/services/protocols/test_csopm_link_protocol.py -v
```

**Expected output**:
```
test_csopm_link_protocol.py::test_protocol_has_poll_method PASSED
test_csopm_link_protocol.py::test_protocol_has_send_notification_method PASSED
test_csopm_link_protocol.py::test_protocol_has_create_followup_method PASSED
test_csopm_link_protocol.py::test_protocol_has_get_metrics_method PASSED
```

### Commit

**Commit message**:
```
feat: Add CSOPMLinkServiceProtocol interface

Create protocol defining CSOPM link service contract:
- poll_for_new_csopm_tickets() for JIRA polling
- send_notification_to_assignee() for Slack notifications
- create_followup_ticket() for ticket creation
- get_metrics() for metrics collection

Follows TypedDI protocol-first pattern.
```

**Files to commit**:
- `packages/services/protocols/__init__.py` (create if missing, empty file)
- `packages/services/protocols/csopm_link_protocol.py`
- `tests/unit/services/protocols/__init__.py` (create if missing, empty file)
- `tests/unit/services/protocols/test_csopm_link_protocol.py`

---

## Task 2: Create Custom Slack Client for CSOPM Operations

**File(s)**: `packages/slack/csopm_slack_client.py`
**Depends on**: Task 1 (needs protocol contracts)
**Estimated time**: 2-3 hours

---

## Task 2.5: Add Email-to-UserID Resolution Method

**File(s)**: `packages/slack/user_operations/user_ops.py`
**Depends on**: Task 2 (SlackConfig setup)
**Estimated time**: 1-1.5 hours (native implementation with tests)

### 🤖 Agent Assignment

- **Agent**: `1x python-backend-tdd-agent`
- **Parallel**: ❌ Sequential (depends on Task 2)
- **Phase**: Phase 1
- **Launch Command**: `/task python-backend-tdd-agent "Add Email Resolution Method per Task 2.5 in docs/plans/csopm-link-service.md"`

### What you're building

Adding native email-to-Slack-user-ID resolution to SlackUserOps using Slack's `users.lookupByEmail` API.

### Test First (TDD)

**Test file**: `tests/unit/slack/test_user_ops_email_resolution.py`

**Test structure**:
```python
test get_slack_id_by_email success
test get_slack_id_by_email not_found
test get_slack_id_by_email api_error
test get_slack_id_by_email caches_result
```

**Test specifics**:
- Mock `_make_api_request` method from base class
- Use `AsyncMock` for async operations
- Verify DB caching with `user_store.batch_store_users`
- Test both success and failure paths

**Example test skeleton**:
```python
import pytest
from unittest.mock import AsyncMock
from packages.slack.user_operations.user_ops import SlackUserOps

@pytest.fixture
def user_ops(slack_config, user_store):
    """Create SlackUserOps with mocked dependencies."""
    ops = SlackUserOps(user_store, slack_config)
    # Mock the base class API request method
    ops._make_api_request = AsyncMock()
    return ops

@pytest.mark.asyncio
async def test_get_slack_id_by_email_success(user_ops):
    """Test successful email to user ID resolution."""
    # Mock API response
    user_ops._make_api_request.return_value = {
        "body": '{"ok": true, "user": {"id": "U12345", "name": "harrison", "profile": {"real_name": "Harrison Smith"}}}'
    }

    result = await user_ops.get_slack_id_by_email("harrison@adobe.com")

    assert result == "U12345"
    user_ops._make_api_request.assert_called_once()

@pytest.mark.asyncio
async def test_get_slack_id_by_email_not_found(user_ops):
    """Test handling when email not found."""
    user_ops._make_api_request.return_value = {
        "body": '{"ok": false, "error": "users_not_found"}'
    }

    result = await user_ops.get_slack_id_by_email("nonexistent@adobe.com")

    assert result is None
```

### Implementation

**Approach**:
Implement native method using Slack's `users.lookupByEmail` API. Follow existing patterns from `_fetch_user_info_internal` method. Use base class `_make_api_request` for API calls. Integrate with existing UserStore for DB caching.

**Code additions to user_ops.py**:
```python
# packages/slack/user_operations/user_ops.py
# Add this method to the SlackUserOps class

from packages.core.resilience.backoff import with_exponential_backoff

class SlackUserOps(SlackAsyncClient):
    # ... existing methods ...

    @with_exponential_backoff()
    async def get_slack_id_by_email(self, email: str) -> Optional[str]:
        """
        Resolve email address to Slack user ID using Slack's users.lookupByEmail API.

        Args:
            email: Email address (e.g., "harrison@adobe.com")

        Returns:
            Slack user ID (e.g., "U12345") or None if not found
        """
        url = f"{self.config.get_api_base_url()}/users.lookupByEmail"
        headers = self.config.get_headers()
        params = {"email": email}

        try:
            response = await self._make_api_request(url, "GET", headers, params)
            # Response is a SafeResponse dict, parse the body
            data = orjson.loads(response["body"])

            if data.get("ok") and "user" in data:
                user = data["user"]
                user_id = user["id"]

                # Cache in memory for this session
                self._user_cache[user_id] = user

                # Extract name for DB storage
                user_name = (
                    user.get("profile", {}).get("real_name")
                    or user.get("name")
                    or email.split("@")[0]
                )

                # Store in DB for future lookups
                await self.user_store.batch_store_users([{
                    "user_id": user_id,
                    "real_name": user_name
                }])

                logger.info(f"Resolved {email} to Slack user ID {user_id}")
                return user_id
            else:
                error = data.get("error", "Unknown error")
                logger.warning(f"Failed to lookup {email}: {error}")
                return None

        except Exception as e:
            logger.error(f"Error looking up {email}: {e}", exc_info=True)
            return None
```

**Key points**:
- Follows existing pattern from `_fetch_user_info_internal` method (user_ops.py:226-256)
- Uses `@with_exponential_backoff()` decorator for retry logic
- Integrates with existing `_user_cache` and `user_store` patterns
- Uses base class `_make_api_request` method from `SlackAsyncClient`
- Parses SafeResponse dict format (matches existing code patterns)

**Integration points**:
- Import: `from packages.core.resilience.backoff import with_exponential_backoff`
- Base class method: `_make_api_request(url, method, headers, params)`
- Uses: Slack API `users.lookupByEmail` endpoint
- Caches results in both memory (`_user_cache`) and DynamoDB (`user_store`)

### Verification

**Automated tests**:
```bash
pytest tests/unit/slack/test_user_ops_email_resolution.py -v
```

**Expected output**:
```
test_user_ops_email_resolution.py::test_get_slack_id_by_email_success PASSED
test_user_ops_email_resolution.py::test_get_slack_id_by_email_not_found PASSED
```

### Commit

**Commit message**:
```
feat: Add email-to-user-ID resolution to SlackUserOps

Add get_slack_id_by_email() method to SlackUserOps:
- Implements Slack's users.lookupByEmail API
- Uses @with_exponential_backoff decorator for retry logic
- Follows existing _fetch_user_info_internal pattern
- Caches results in memory and DynamoDB

Required for CSOPM assignee notification feature.
```

**Files to commit**:
- `packages/slack/user_operations/user_ops.py`
- `tests/unit/slack/test_user_ops_email_resolution.py`

---

### 🤖 Agent Assignment (Task 2 - Original)

- **Agent**: `1x python-backend-tdd-agent` (same or different from Task 1)
- **Parallel**: ❌ Sequential (depends on Task 1 protocol definition)
- **Phase**: Phase 1
- **Launch Command**: `/task python-backend-tdd-agent "Create Custom Slack Client per Task 2 in docs/plans/csopm-link-service.md"`

### What you're building

A specialized Slack client that extends SlackAsyncClient with CSOPM-specific operations like opening DMs and sending notifications with buttons.

### Test First (TDD)

**Test file**: `tests/unit/slack/test_csopm_slack_client.py`

**Test structure**:
```python
test open_dm_and_send_notification success
test open_dm_and_send_notification user_not_found
test open_dm_and_send_notification slack_error
test notification_blocks_formatted_correctly
```

**Test specifics**:
- Mock `self.api_call` method
- Use `AsyncMock` from unittest.mock
- Assert correct Slack API endpoints called
- Verify block structure for notifications

**Example test skeleton**:
```python
# tests/unit/slack/test_csopm_slack_client.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from packages.slack.csopm_slack_client import CSOPMSlackClient
from packages.slack.core.slack_config import SlackConfig


@pytest.fixture
def slack_config():
    """Create test Slack config."""
    return SlackConfig(
        api_token="xoxb-test-token",
        signing_secret="test-secret"
    )


@pytest.fixture
def slack_client(slack_config):
    """Create CSOPM Slack client with mocked api_call."""
    client = CSOPMSlackClient(slack_config)
    client.api_call = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_open_dm_and_send_notification_success(slack_client):
    """Test successfully opening DM and sending notification."""
    # Mock conversations.open response
    slack_client.api_call.side_effect = [
        {"ok": True, "channel": {"id": "D12345"}},  # conversations.open
        {"ok": True, "ts": "1234567890.123"}        # chat.postMessage
    ]

    test_blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Test"}}]

    channel_id, message_ts = await slack_client.open_dm_and_send_notification(
        user_id="U12345",
        blocks=test_blocks
    )

    assert channel_id == "D12345"
    assert message_ts == "1234567890.123"
    assert slack_client.api_call.call_count == 2

    # Verify conversations.open called correctly
    first_call = slack_client.api_call.call_args_list[0]
    assert first_call[0][0] == "conversations.open"
    assert first_call[0][1]["users"] == ["U12345"]

    # Verify chat.postMessage called correctly
    second_call = slack_client.api_call.call_args_list[1]
    assert second_call[0][0] == "chat.postMessage"
    assert second_call[0][1]["channel"] == "D12345"
    assert second_call[0][1]["blocks"] == test_blocks


@pytest.mark.asyncio
async def test_open_dm_fails_gracefully(slack_client):
    """Test graceful failure when DM cannot be opened."""
    slack_client.api_call.side_effect = Exception("Slack API error")

    with pytest.raises(Exception) as exc_info:
        await slack_client.open_dm_and_send_notification(
            user_id="U12345",
            blocks=[]
        )

    assert "Slack API error" in str(exc_info.value)
```

### Implementation

**Approach**:
Extend `SlackAsyncClient` base class and add CSOPM-specific methods. The base class handles connection pooling, retries, and rate limiting.

**Code structure**:
```python
# packages/slack/csopm_slack_client.py
from typing import List, Dict, Tuple
from packages.slack.core.slack_async_client import SlackAsyncClient
from packages.slack.core.slack_config import SlackConfig
from packages.core.logging import setup_logger


class CSOPMSlackClient(SlackAsyncClient):
    """Custom Slack client for CSOPM link operations."""

    def __init__(
        self,
        slack_config: SlackConfig,
        max_concurrent_requests: int = 10,
        request_timeout: int = 30
    ):
        super().__init__(
            slack_config=slack_config,
            max_concurrent_requests=max_concurrent_requests,
            request_timeout=request_timeout
        )
        self.logger = setup_logger(__name__)

    async def open_dm_and_send_notification(
        self, user_id: str, blocks: List[Dict]
    ) -> Tuple[str, str]:
        """
        Open DM channel and send notification in one operation.

        Args:
            user_id: Slack user ID
            blocks: Slack Block Kit blocks for message

        Returns:
            Tuple of (channel_id, message_ts)

        Raises:
            Exception: If DM cannot be opened or message fails
        """
        self.logger.info(f"Opening DM with user {user_id}")

        # Open DM channel
        dm_response = await self.api_call(
            "conversations.open",
            {"users": [user_id]}
        )

        if not dm_response.get("ok"):
            raise Exception(f"Failed to open DM: {dm_response.get('error')}")

        channel_id = dm_response["channel"]["id"]
        self.logger.debug(f"DM channel opened: {channel_id}")

        # Send notification
        msg_response = await self.api_call(
            "chat.postMessage",
            {"channel": channel_id, "blocks": blocks}
        )

        if not msg_response.get("ok"):
            raise Exception(f"Failed to send message: {msg_response.get('error')}")

        message_ts = msg_response["ts"]
        self.logger.info(f"Notification sent to {user_id} in channel {channel_id}")

        return channel_id, message_ts
```

**Key points**:
- Follow pattern from: `packages/slack/core/slack_async_client.py`
- Extend `SlackAsyncClient` (provides api_call method, connection pooling, retries)
- Use setup_logger from `packages/core/logging`
- Return tuple for both channel_id and message_ts (needed for DynamoDB tracking)

**Integration points**:
- Imports needed: `SlackAsyncClient`, `SlackConfig`, `setup_logger`
- Base class provides: `self.api_call(endpoint, payload)`
- Use existing retry and rate limiting from base class

### Verification

**Manual testing**:
```python
# test_slack_client_manual.py
import asyncio
from packages.slack.csopm_slack_client import CSOPMSlackClient
from packages.slack.core.slack_config import SlackConfig

async def test():
    config = SlackConfig(api_token="xoxb-your-token", signing_secret="secret")
    client = CSOPMSlackClient(config)

    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Test notification"}}]
    channel_id, ts = await client.open_dm_and_send_notification("U12345TEST", blocks)
    print(f"Sent to {channel_id} at {ts}")

asyncio.run(test())
```

**Automated tests**:
```bash
pytest tests/unit/slack/test_csopm_slack_client.py -v
```

**Expected output**:
```
test_csopm_slack_client.py::test_open_dm_and_send_notification_success PASSED
test_csopm_slack_client.py::test_open_dm_fails_gracefully PASSED
```

### Commit

**Commit message**:
```
feat: Add CSOPMSlackClient for DM notifications

Create specialized Slack client extending SlackAsyncClient:
- open_dm_and_send_notification() for atomic DM operations
- Handles conversations.open + chat.postMessage
- Returns channel_id and message_ts for tracking

Reuses base class retry logic and connection pooling.
```

**Files to commit**:
- `packages/slack/csopm_slack_client.py`
- `tests/unit/slack/test_csopm_slack_client.py`

---

## ✅ QA CHECKPOINT: Phase 1 Complete

**QA Agent**: `1x architect-review`
**Duration**: 30-45 minutes
**Critical**: ✅ **YES** - Foundation for all work

### Verification Criteria
- [ ] Protocol tests pass (Task 1)
- [ ] Protocol methods have correct signatures
- [ ] Type hints are comprehensive
- [ ] Slack client tests pass (Task 2)
- [ ] Slack client extends base class correctly
- [ ] All tests pass with >80% coverage

### Launch Command
```bash
/task architect-review "Review Phase 1: Protocol design, contracts, Slack client architecture"
```

### Action if RED
🚨 **BLOCK Phase 2** - Fix issues immediately before proceeding

---

# PHASE 2: Core Service Development (6-way Parallel - Day 1 PM → Day 2)

**Duration**: 6-8 hours wall time
**Parallelization**: ✅ **6 agents simultaneously** ⭐ PEAK PARALLELIZATION
**Why Parallel**: Tasks 3-6 are independent service method implementations sharing only the protocol interface

### Launch All 6 Agents in Parallel:
```bash
# Service Methods (4 agents)
/task python-backend-tdd-agent "Implement Polling Logic per Task 3" &
/task python-backend-tdd-agent "Implement Notification Sending per Task 4" &
/task python-backend-tdd-agent "Implement Follow-up Creation per Task 5" &
/task python-backend-tdd-agent "Implement Metrics Collection per Task 6" &
# Infrastructure (1 agent)
/task backend-developer "Create requirements.txt per Task 17" &
# Documentation (1 agent)
/task technical-documentation-specialist "Draft UAT checklist (Task 22) and Deployment docs (Task 25)"
```

---

## Task 3: Implement Core Service with Polling Logic

**File(s)**: `packages/services/csopm_link_service.py`
**Depends on**: Task 1 (Protocol)
**Estimated time**: 2-3 hours

### 🤖 Agent Assignment

- **Agent**: `1x python-backend-tdd-agent`
- **Parallel**: ✅ **YES** - Can run with Tasks 4, 5, 6, 17, 22, 25
- **Phase**: Phase 2
- **Launch Command**: `/task python-backend-tdd-agent "Implement Core Service with Polling Logic per Task 3"`

### What you're building

The main service implementation that polls JIRA for CSOPM tickets, handles deduplication, and manages the workflow. This is the heart of the feature.

### Test First (TDD)

**Test file**: `tests/unit/services/test_csopm_link_service.py`

**Test structure**:
```python
test poll_returns_empty_when_disabled
test poll_for_new_csopm_tickets_success
test poll_deduplicates_already_notified_tickets
test poll_handles_mcp_connection_error
test poll_filters_tickets_without_assignee
test poll_extracts_original_ticket_from_links
```

**Test specifics**:
- Mock all dependencies: `MCPAsyncClient`, `SlackUserOps`, `DynamoDBStore`, `CSOPMSlackClient`
- Use `AsyncMock` for all async methods
- Test deduplication logic thoroughly
- Verify logging calls with `caplog` fixture

**Example test skeleton**:
```python
# tests/unit/services/test_csopm_link_service.py
import pytest
from unittest.mock import AsyncMock, patch
import time

from packages.services.csopm_link_service import CSOPMLinkServiceImpl
from packages.integrations.async_mcp_client import MCPAsyncClient
from packages.slack.user_operations.user_ops import SlackUserOps
from packages.db.dynamodb_store import DynamoDBStore
from packages.slack.csopm_slack_client import CSOPMSlackClient


@pytest.fixture
def mock_dependencies():
    """Create mocked dependencies following TypedDI pattern."""
    return {
        "mcp_client": AsyncMock(spec=MCPAsyncClient),
        "user_ops": AsyncMock(spec=SlackUserOps),
        "db_store": AsyncMock(spec=DynamoDBStore),
        "slack_client": AsyncMock(spec=CSOPMSlackClient),
    }


@pytest.fixture
def service(mock_dependencies):
    """Create service instance with mocked dependencies."""
    return CSOPMLinkServiceImpl(**mock_dependencies)


@pytest.mark.asyncio
async def test_poll_returns_empty_when_disabled(service, mock_dependencies):
    """Test that polling returns empty list when feature is disabled."""
    with patch.dict("os.environ", {"KETCHUP_CSOPM_LINK_ENABLED": "false"}):
        service.enabled = False

        result = await service.poll_for_new_csopm_tickets()

        assert result == []
        mock_dependencies["mcp_client"].search_issues.assert_not_called()


@pytest.mark.asyncio
async def test_poll_for_new_csopm_tickets_success(service, mock_dependencies):
    """Test successful polling for new CSOPM tickets."""
    with patch.dict("os.environ", {"KETCHUP_CSOPM_LINK_ENABLED": "true"}):
        service.enabled = True

        # Setup mock response
        mock_dependencies["mcp_client"].search_issues.return_value = {
            "issues": [
                {
                    "key": "CPGNREQ-123456",
                    "fields": {
                        "summary": "CSOPM - Test Ticket",
                        "assignee": {"name": "harrison"},
                        "issuelinks": [
                            {
                                "type": {"name": "relates to"},
                                "outwardIssue": {"key": "CPGNTT-99999"}
                            }
                        ],
                        "comment": {"comments": []},
                    }
                }
            ]
        }

        # Setup deduplication check (not already notified)
        mock_dependencies["db_store"].get_item.return_value = None

        result = await service.poll_for_new_csopm_tickets()

        assert len(result) == 1
        assert result[0]["key"] == "CPGNREQ-123456"

        # Verify correct JQL used
        mock_dependencies["mcp_client"].search_issues.assert_called_once()
        call_args = mock_dependencies["mcp_client"].search_issues.call_args
        assert "CSOPM" in call_args.kwargs["jql"]
        assert "created >= -15m" in call_args.kwargs["jql"]


@pytest.mark.asyncio
async def test_poll_deduplicates_already_notified(service, mock_dependencies):
    """Test that already-notified tickets are filtered out."""
    with patch.dict("os.environ", {"KETCHUP_CSOPM_LINK_ENABLED": "true"}):
        service.enabled = True

        # Setup mock response with ticket
        mock_dependencies["mcp_client"].search_issues.return_value = {
            "issues": [
                {"key": "CPGNREQ-123456", "fields": {"assignee": {"name": "harrison"}}}
            ]
        }

        # Setup deduplication check (already notified)
        mock_dependencies["db_store"].get_item.return_value = {
            "PK": "CSOPM_TICKET#CPGNREQ-123456",
            "SK": "METADATA",
            "notification_sent_at": int(time.time())
        }

        result = await service.poll_for_new_csopm_tickets()

        # Ticket found but filtered out due to deduplication
        assert len(result) == 0
```

### Implementation

**Approach**:
Implement the CSOPMLinkServiceImpl class with TypedDI constructor injection. Use feature flag to control enable/disable. Implement polling with deduplication check against DynamoDB.

**Code structure**:
```python
# packages/services/csopm_link_service.py
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

from packages.services.protocols.csopm_link_protocol import CSOPMLinkServiceProtocol
from packages.integrations.async_mcp_client import MCPAsyncClient
from packages.slack.user_operations.user_ops import SlackUserOps
from packages.db.dynamodb_store import DynamoDBStore
from packages.slack.csopm_slack_client import CSOPMSlackClient
from packages.core.logging import setup_logger


class CSOPMLinkServiceImpl:
    """Concrete implementation of CSOPM link service."""

    def __init__(
        self,
        mcp_client: MCPAsyncClient,
        user_ops: SlackUserOps,
        db_store: DynamoDBStore,
        slack_client: CSOPMSlackClient,
    ):
        self.mcp_client = mcp_client
        self.user_ops = user_ops
        self.db_store = db_store
        self.slack_client = slack_client
        self.logger = setup_logger(__name__)

        # Feature flag control
        self.enabled = os.getenv("KETCHUP_CSOPM_LINK_ENABLED", "false").lower() == "true"

        if self.enabled:
            self.logger.info("CSOPM Link service enabled")
        else:
            self.logger.info("CSOPM Link service disabled")

    async def poll_for_new_csopm_tickets(self) -> List[Dict[str, Any]]:
        """
        Poll JIRA for new CSOPM tickets in last 15 minutes.

        Returns:
            List of new CSOPM tickets that need notification
        """
        if not self.enabled:
            self.logger.debug("Service disabled, skipping poll")
            return []

        self.logger.info("Polling for new CSOPM tickets")

        try:
            # Search JIRA for recent CSOPM tickets
            result = await self.mcp_client.search_issues(
                jql=(
                    'project = CPGNREQ AND '
                    'summary ~ "CSOPM" AND '
                    'created >= -15m'
                ),
                fields=[
                    'summary', 'description', 'assignee', 'issuelinks',
                    'comment', 'created', 'status'
                ],
                max_results=50
            )

            issues = result.get("issues", [])
            self.logger.info(f"Found {len(issues)} CSOPM tickets in last 15 minutes")

            # Filter out already-notified tickets (deduplication)
            new_tickets = []
            for issue in issues:
                ticket_id = issue["key"]

                # Check if already notified
                # NOTE: DynamoDB client requires key dict with type descriptors
                response = await self.db_store.client.get_item(
                    key={
                        "PK": {"S": f"CSOPM_TICKET#{ticket_id}"},
                        "SK": {"S": "METADATA"}
                    },
                    table_name=self.db_store.table_name
                )

                existing = response.get("Item")
                if existing:
                    self.logger.debug(f"Skipping {ticket_id} - already notified")
                    continue

                # Check if has assignee
                assignee = issue.get("fields", {}).get("assignee")
                if not assignee:
                    self.logger.warning(f"Skipping {ticket_id} - no assignee")
                    continue

                new_tickets.append(issue)

            self.logger.info(f"Filtered to {len(new_tickets)} new tickets needing notification")
            return new_tickets

        except Exception as e:
            self.logger.error(f"Error polling for CSOPM tickets: {e}", exc_info=True)
            return []

    async def send_notification_to_assignee(
        self, csopm_ticket: Dict[str, Any]
    ) -> bool:
        """Implementation stub - will be completed in Task 4."""
        pass

    async def create_followup_ticket(
        self, ticket_data: Dict[str, Any], user_id: str
    ) -> Dict[str, Any]:
        """Implementation stub - will be completed in Task 5."""
        pass

    async def get_metrics(
        self, period_type: str, month_keys: List[str]
    ) -> Dict[str, Any]:
        """Implementation stub - will be completed in Task 6."""
        pass
```

**Key points**:
- Follow pattern from: `jira_reporter/services/jira_posting_service.py` (polling pattern)
- Use environment variable for feature flag: `KETCHUP_CSOPM_LINK_ENABLED`
- Deduplication via DynamoDB `get_item` check
- Filter out tickets without assignee
- Use JQL: `project = CPGNREQ AND summary ~ "CSOPM" AND created >= -15m`

**Integration points**:
- Imports needed: `MCPAsyncClient`, `SlackUserOps`, `DynamoDBStore`, `CSOPMSlackClient`
- Use `mcp_client.search_issues()` for JIRA queries
- Use `db_store.get_item(pk, sk)` for deduplication

### Verification

**Manual testing**:
```python
# Quick test with mocks
import asyncio
from unittest.mock import AsyncMock
from packages.services.csopm_link_service import CSOPMLinkServiceImpl

async def test():
    mcp = AsyncMock()
    mcp.search_issues.return_value = {"issues": []}

    service = CSOPMLinkServiceImpl(mcp, AsyncMock(), AsyncMock(), AsyncMock())
    result = await service.poll_for_new_csopm_tickets()
    print(f"Poll result: {result}")

asyncio.run(test())
```

**Automated tests**:
```bash
pytest tests/unit/services/test_csopm_link_service.py::test_poll_for_new_csopm_tickets_success -v
pytest tests/unit/services/test_csopm_link_service.py::test_poll_deduplicates_already_notified -v
```

**Expected output**:
```
test_csopm_link_service.py::test_poll_returns_empty_when_disabled PASSED
test_csopm_link_service.py::test_poll_for_new_csopm_tickets_success PASSED
test_csopm_link_service.py::test_poll_deduplicates_already_notified PASSED
```

### Commit

**Commit message**:
```
feat: Implement CSOPM ticket polling with deduplication

Add core polling logic to CSOPMLinkServiceImpl:
- Poll JIRA every 15 minutes for new CSOPM tickets
- Deduplicate against DynamoDB (check CSOPM_TICKET# records)
- Filter tickets without assignee
- Feature flag controlled via KETCHUP_CSOPM_LINK_ENABLED

JQL: project = CPGNREQ AND summary ~ "CSOPM" AND created >= -15m
```

**Files to commit**:
- `packages/services/__init__.py` (create if missing)
- `packages/services/csopm_link_service.py`
- `tests/unit/services/__init__.py` (create if missing)
- `tests/unit/services/test_csopm_link_service.py`

---

## Task 4: Implement Notification Sending Logic

**File(s)**: `packages/services/csopm_link_service.py` (add method)
**Depends on**: Task 1 (Protocol)
**Estimated time**: 1.5-2 hours

### 🤖 Agent Assignment

- **Agent**: `1x python-backend-tdd-agent` (different from Task 3)
- **Parallel**: ✅ **YES** - Can run with Tasks 3, 5, 6, 17, 22, 25
- **Phase**: Phase 2
- **Launch Command**: `/task python-backend-tdd-agent "Implement Notification Sending Logic per Task 4"`

### What you're building

Implementing the `send_notification_to_assignee()` method that resolves the JIRA assignee to a Slack user, sends a DM notification with formatted blocks, stores tracking data in DynamoDB, and adds a JIRA comment.

### Test First (TDD)

**Test file**: `tests/unit/services/test_csopm_link_service.py` (add tests)

**Test structure**:
```python
test send_notification_success
test send_notification_user_not_found
test send_notification_slack_error
test send_notification_db_storage_failure
test send_notification_metrics_incremented
```

**Test specifics**:
- Mock `user_ops.get_slack_id_by_email()`
- Mock `slack_client.open_dm_and_send_notification()`
- Mock `db_store.put_item()` and `increment_monthly_counter()`
- Mock `mcp_client.add_jira_comment()`
- Verify all operations called in correct order

**Example test additions**:
```python
@pytest.mark.asyncio
async def test_send_notification_success(service, mock_dependencies):
    """Test successful notification sending."""
    with patch.dict("os.environ", {"KETCHUP_CSOPM_LINK_ENABLED": "true"}):
        service.enabled = True

        csopm_ticket = {
            "key": "CPGNREQ-123456",
            "fields": {
                "assignee": {"name": "harrison"},
                "summary": "CSOPM - Test Issue",
                "description": "Test description",
                "issuelinks": [
                    {"type": {"name": "relates to"}, "outwardIssue": {"key": "CPGNTT-99999"}}
                ],
                "comment": {"comments": []}
            }
        }

        # Setup mocks
        mock_dependencies["user_ops"].get_slack_id_by_email.return_value = "U12345"
        mock_dependencies["slack_client"].open_dm_and_send_notification.return_value = (
            "D12345", "1234567890.123"
        )
        mock_dependencies["db_store"].put_item.return_value = True
        mock_dependencies["mcp_client"].add_jira_comment.return_value = True

        result = await service.send_notification_to_assignee(csopm_ticket)

        assert result is True

        # Verify user lookup
        mock_dependencies["user_ops"].get_slack_id_by_email.assert_called_once_with(
            "harrison@adobe.com"
        )

        # Verify Slack notification sent
        mock_dependencies["slack_client"].open_dm_and_send_notification.assert_called_once()
        call_args = mock_dependencies["slack_client"].open_dm_and_send_notification.call_args
        assert call_args.kwargs["user_id"] == "U12345"
        assert "blocks" in call_args.kwargs

        # Verify DynamoDB record created
        mock_dependencies["db_store"].put_item.assert_called_once()
        db_call = mock_dependencies["db_store"].put_item.call_args
        assert db_call.kwargs["PK"] == "CSOPM_TICKET#CPGNREQ-123456"

        # Verify JIRA comment added
        mock_dependencies["mcp_client"].add_jira_comment.assert_called_once()
        comment_call = mock_dependencies["mcp_client"].add_jira_comment.call_args
        assert "harrison" in comment_call.kwargs["comment"]["body"]


@pytest.mark.asyncio
async def test_send_notification_user_not_found(service, mock_dependencies):
    """Test notification fails gracefully when user not found in Slack."""
    with patch.dict("os.environ", {"KETCHUP_CSOPM_LINK_ENABLED": "true"}):
        service.enabled = True

        csopm_ticket = {
            "key": "CPGNREQ-123456",
            "fields": {"assignee": {"name": "unknown.user"}}
        }

        # User not found in Slack
        mock_dependencies["user_ops"].get_slack_id_by_email.return_value = None

        result = await service.send_notification_to_assignee(csopm_ticket)

        assert result is False
        mock_dependencies["slack_client"].open_dm_and_send_notification.assert_not_called()
```

### Implementation

**Approach**:
Complete the `send_notification_to_assignee()` method stub. Use DB-first user resolution pattern from SlackUserOps. Build Slack blocks with ticket summary, action items, and button. Store notification record in DynamoDB with TTL. Add JIRA comment for audit trail. Increment metrics counter.

**Code additions to csopm_link_service.py**:
```python
    async def send_notification_to_assignee(
        self, csopm_ticket: Dict[str, Any]
    ) -> bool:
        """
        Send DM notification to CSOPM assignee.

        Args:
            csopm_ticket: CSOPM ticket data from JIRA

        Returns:
            True if notification sent successfully, False otherwise
        """
        ticket_id = csopm_ticket["key"]
        fields = csopm_ticket.get("fields", {})
        assignee = fields.get("assignee", {})
        assignee_name = assignee.get("name")

        if not assignee_name:
            self.logger.warning(f"No assignee for {ticket_id}, skipping notification")
            return False

        self.logger.info(f"Sending notification for {ticket_id} to {assignee_name}")

        # Get current month for metrics
        month_key = datetime.now().strftime("%Y_%m")

        try:
            # Resolve JIRA username to Slack user ID (DB-first pattern)
            assignee_email = f"{assignee_name}@adobe.com"
            slack_user_id = await self.user_ops.get_slack_id_by_email(assignee_email)

            if not slack_user_id:
                self.logger.error(f"Could not resolve {assignee_name} to Slack user ID")
                await self.db_store.increment_monthly_counter(
                    'csopm_notifications_failed', month_key, 1
                )
                return False

            # Build notification blocks
            blocks = self._build_notification_blocks(csopm_ticket)

            # Send DM notification
            dm_channel_id, message_ts = await self.slack_client.open_dm_and_send_notification(
                user_id=slack_user_id,
                blocks=blocks
            )

            # Store notification record in DynamoDB
            # NOTE: DynamoDB client requires type descriptors {"S": "value"}, {"N": "123"}
            timestamp = int(time.time())
            await self.db_store.client.put_item(
                item={
                    "PK": {"S": f"CSOPM_TICKET#{ticket_id}"},
                    "SK": {"S": "METADATA"},
                    "csopm_ticket_id": {"S": ticket_id},
                    "original_ticket_id": {"S": self._extract_original_ticket_id(csopm_ticket) or ""},
                    "assignee_email": {"S": assignee_email},
                    "assignee_slack_id": {"S": slack_user_id},
                    "notification_sent_at": {"N": str(timestamp)},
                    "dm_channel_id": {"S": dm_channel_id},
                    "dm_message_ts": {"S": message_ts},
                    "status": {"S": "NOTIFIED"},
                    "ttl": {"N": str(timestamp + (90 * 86400))}
                },
                table_name=self.db_store.table_name
            )

            # Add JIRA comment for audit trail
            await self.mcp_client.add_jira_comment(
                issueIdOrKey=ticket_id,
                comment={
                    "body": f"Message sent to [~{assignee_name}] to review this CSOPM ticket"
                }
            )

            # Increment success metric
            await self.db_store.increment_monthly_counter(
                'csopm_notifications_sent', month_key, 1
            )

            self.logger.info(f"Notification sent successfully for {ticket_id}")
            return True

        except Exception as e:
            self.logger.error(
                f"Failed to send notification for {ticket_id}: {e}",
                exc_info=True
            )

            # Increment failure metric
            await self.db_store.increment_monthly_counter(
                'csopm_notifications_failed', month_key, 1
            )

            return False

    def _build_notification_blocks(self, csopm_ticket: Dict[str, Any]) -> List[Dict]:
        """Build Slack Block Kit blocks for notification message."""
        ticket_id = csopm_ticket["key"]
        fields = csopm_ticket.get("fields", {})
        summary = fields.get("summary", "")
        description = fields.get("description", "")

        # Extract original ticket ID from links
        original_ticket_id = self._extract_original_ticket_id(csopm_ticket)

        # Extract action items from description (lines starting with "- " or "* ")
        action_items = self._extract_action_items(description)

        # Format recent comments
        comments = fields.get("comment", {}).get("comments", [])
        formatted_comments = self._format_recent_comments(comments, limit=3)

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🎫 New CSOPM Ticket: {ticket_id}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Summary:* {summary}\n\n"
                        f"*Original Ticket:* <https://jira.corp.adobe.com/browse/{original_ticket_id}|{original_ticket_id}>\n"
                        f"*CSOPM Ticket:* <https://jira.corp.adobe.com/browse/{ticket_id}|{ticket_id}>"
                    )
                }
            }
        ]

        # Add action items if present
        if action_items:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Action Items:*\n{action_items}"
                }
            })

        # Add recent comments if present
        if formatted_comments:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Recent Comments:*\n{formatted_comments}"
                }
            })

        # Add button to create follow-up
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Create Follow-up Ticket"},
                    "style": "primary",
                    "action_id": "open_followup_modal",
                    "value": json.dumps({
                        "csopm_ticket_id": ticket_id,
                        "original_ticket_id": original_ticket_id
                    })
                }
            ]
        })

        return blocks

    def _extract_original_ticket_id(self, csopm_ticket: Dict[str, Any]) -> Optional[str]:
        """Extract original ticket ID from issue links."""
        links = csopm_ticket.get("fields", {}).get("issuelinks", [])

        for link in links:
            # Check outward link
            outward = link.get("outwardIssue", {}).get("key")
            if outward and not outward.startswith("CPGNREQ"):
                return outward

            # Check inward link
            inward = link.get("inwardIssue", {}).get("key")
            if inward and not inward.startswith("CPGNREQ"):
                return inward

        return None

    def _extract_action_items(self, description: str) -> str:
        """Extract action items from description (lines starting with - or *)."""
        if not description:
            return ""

        action_lines = []
        for line in description.split("\n"):
            stripped = line.strip()
            if stripped.startswith(("- ", "* ")):
                action_lines.append(f"• {stripped[2:]}")

        return "\n".join(action_lines[:5])  # Limit to 5 items

    def _format_recent_comments(self, comments: List[Dict], limit: int = 3) -> str:
        """Format recent comments for display."""
        if not comments:
            return ""

        recent = comments[-limit:]  # Get last N comments
        formatted = []

        for comment in recent:
            author = comment.get("author", {}).get("displayName", "Unknown")
            body = comment.get("body", "")[:200]  # Truncate to 200 chars
            formatted.append(f"_{author}_: {body}...")

        return "\n\n".join(formatted)
```

**Key points**:
- Follow pattern from: `packages/slack/user_operations/user_ops.py` (DB-first user resolution)
- Use `user_ops.get_slack_id_by_email()` for user resolution
- Store with 90-day TTL: `ttl=int(time.time()) + (90 * 86400)`
- JIRA username format: `[~username]` (not `[~username@adobe.com]`)
- Import `json` and `time` modules

**Integration points**:
- Imports needed: `import json`, `import time`
- Use `datetime.now().strftime("%Y_%m")` for month_key
- Use `db_store.increment_monthly_counter()` for metrics

### Verification

**Manual testing**:
Create a test script that sends a real notification to your Slack account using a real CSOPM ticket.

**Automated tests**:
```bash
pytest tests/unit/services/test_csopm_link_service.py::test_send_notification_success -v
pytest tests/unit/services/test_csopm_link_service.py::test_send_notification_user_not_found -v
```

**Expected output**:
```
test_csopm_link_service.py::test_send_notification_success PASSED
test_csopm_link_service.py::test_send_notification_user_not_found PASSED
```

### Commit

**Commit message**:
```
feat: Implement notification sending with Slack DM

Complete send_notification_to_assignee() method:
- DB-first user resolution (email → Slack ID)
- Build Block Kit notification with summary, actions, comments
- Store tracking record in DynamoDB with 90-day TTL
- Add JIRA comment audit trail
- Increment metrics counters (sent/failed)

Uses JIRA username format [~username] without @adobe.com.
```

**Files to commit**:
- `packages/services/csopm_link_service.py`
- `tests/unit/services/test_csopm_link_service.py`

---

## Task 5: Implement Follow-up Ticket Creation

**File(s)**: `packages/services/csopm_link_service.py` (add method)
**Depends on**: Task 1 (Protocol)
**Estimated time**: 1.5-2 hours

### 🤖 Agent Assignment

- **Agent**: `1x python-backend-tdd-agent` (different from Tasks 3-4)
- **Parallel**: ✅ **YES** - Can run with Tasks 3, 4, 6, 17, 22, 25
- **Phase**: Phase 2
- **Launch Command**: `/task python-backend-tdd-agent "Implement Follow-up Ticket Creation per Task 5"`

### What you're building

Implementing the `create_followup_ticket()` method that creates a follow-up ticket in JIRA, links it to the CSOPM ticket, adds a comment, updates status (first follow-up only), and handles partial success scenarios.

### Test First (TDD)

**Test file**: `tests/unit/services/test_csopm_link_service.py` (add tests)

**Test structure**:
```python
test create_followup_ticket_success
test create_followup_partial_success_link_fails
test create_followup_partial_success_comment_fails
test create_followup_ticket_creation_fails
test create_followup_first_updates_status
test create_followup_second_skips_status_update
```

**Example test additions**:
```python
@pytest.mark.asyncio
async def test_create_followup_ticket_success(service, mock_dependencies):
    """Test successful follow-up ticket creation."""
    with patch.dict("os.environ", {"KETCHUP_CSOPM_LINK_ENABLED": "true"}):
        service.enabled = True

        ticket_data = {
            "csopm_ticket_id": "CPGNREQ-123456",
            "project": "CPGNREQ",
            "issue_type": "Task",
            "summary": "Follow-up investigation",
            "description": "Need to investigate further",
            "priority": "P2",
            "severity": "Severity 2"
        }

        # Setup mocks
        mock_dependencies["mcp_client"].create_jira_issue.return_value = {
            "key": "CPGNREQ-99999",
            "self": "https://jira.corp.adobe.com/rest/api/2/issue/12345"
        }
        mock_dependencies["mcp_client"].link_issues.return_value = True
        mock_dependencies["mcp_client"].add_jira_comment.return_value = True
        mock_dependencies["mcp_client"].transition_jira_status_by_name.return_value = True

        # Mock this is first follow-up
        mock_dependencies["db_store"].query_items.return_value = []

        result = await service.create_followup_ticket(ticket_data, "U12345")

        assert result["ticket_created"] is True
        assert result["ticket_id"] == "CPGNREQ-99999"
        assert result["linked"] is True
        assert result["comment_added"] is True
        assert result["status_updated"] is True
        assert len(result["errors"]) == 0

        # Verify ticket created with correct fields
        create_call = mock_dependencies["mcp_client"].create_jira_issue.call_args
        assert create_call.kwargs["fields"]["project"]["key"] == "CPGNREQ"
        assert create_call.kwargs["fields"]["customfield_15900"]["value"] == "P2"
        assert create_call.kwargs["fields"]["customfield_15901"]["value"] == "Severity 2"


@pytest.mark.asyncio
async def test_create_followup_partial_success_link_fails(service, mock_dependencies):
    """Test partial success when ticket created but linking fails."""
    with patch.dict("os.environ", {"KETCHUP_CSOPM_LINK_ENABLED": "true"}):
        service.enabled = True

        ticket_data = {
            "csopm_ticket_id": "CPGNREQ-123456",
            "project": "CPGNREQ",
            "issue_type": "Task",
            "summary": "Test",
            "description": "Test",
            "priority": "P2",
            "severity": "Severity 2"
        }

        # Ticket creation succeeds
        mock_dependencies["mcp_client"].create_jira_issue.return_value = {
            "key": "CPGNREQ-99999"
        }

        # Linking fails
        mock_dependencies["mcp_client"].link_issues.side_effect = Exception("Link failed")

        # Comment succeeds (continues despite link failure)
        mock_dependencies["mcp_client"].add_jira_comment.return_value = True

        result = await service.create_followup_ticket(ticket_data, "U12345")

        assert result["ticket_created"] is True
        assert result["ticket_id"] == "CPGNREQ-99999"
        assert result["linked"] is False
        assert result["comment_added"] is True
        assert "Link failed" in str(result["errors"])
```

### Implementation

**Approach**:
Implement create_followup_ticket() with partial success handling. Create ticket first (most critical), then attempt link/comment/status operations independently. Track each operation's success/failure. Store follow-up record in DynamoDB. Check if first follow-up to decide on status update.

**Code additions to csopm_link_service.py**:
```python
    async def create_followup_ticket(
        self, ticket_data: Dict[str, Any], user_id: str
    ) -> Dict[str, Any]:
        """
        Create follow-up ticket and link to CSOPM.

        Args:
            ticket_data: Follow-up ticket details from modal
            user_id: Slack user ID of engineer creating ticket

        Returns:
            Dict with creation result including ticket_id and status
        """
        csopm_ticket_id = ticket_data["csopm_ticket_id"]
        month_key = datetime.now().strftime("%Y_%m")

        result = {
            "ticket_created": False,
            "ticket_id": None,
            "linked": False,
            "comment_added": False,
            "status_updated": False,
            "errors": []
        }

        self.logger.info(f"Creating follow-up ticket for CSOPM {csopm_ticket_id}")

        try:
            # Step 1: Create ticket (most critical operation)
            response = await self.mcp_client.create_jira_issue(
                fields={
                    "project": {"key": ticket_data["project"]},
                    "summary": ticket_data["summary"],
                    "description": ticket_data["description"],
                    "issuetype": {"name": ticket_data["issue_type"]},
                    "customfield_15900": {"value": ticket_data["priority"]},
                    "customfield_15901": {"value": ticket_data["severity"]}
                }
            )

            result["ticket_created"] = True
            result["ticket_id"] = response["key"]

            self.logger.info(f"Follow-up ticket created: {result['ticket_id']}")

            # Increment success metric
            await self.db_store.increment_monthly_counter(
                'csopm_followups_created', month_key, 1
            )

        except Exception as e:
            # Ticket creation failed - abort
            self.logger.error(f"Failed to create follow-up ticket: {e}", exc_info=True)
            result["errors"].append(f"Ticket creation failed: {e}")

            await self.db_store.increment_monthly_counter(
                'csopm_followups_failed', month_key, 1
            )

            return result

        # Step 2: Link to CSOPM (best effort)
        try:
            await self.mcp_client.link_issues(
                inwardIssue=csopm_ticket_id,
                outwardIssue=result["ticket_id"],
                linkType="relates to",
                comment=f"Follow-up ticket created by Slack user"
            )

            result["linked"] = True

            await self.db_store.increment_monthly_counter(
                'csopm_link_operations_success', month_key, 1
            )

        except Exception as e:
            self.logger.warning(f"Failed to link tickets: {e}")
            result["errors"].append(f"Linking failed: {e}")

            await self.db_store.increment_monthly_counter(
                'csopm_link_operations_failed', month_key, 1
            )

        # Step 3: Add comment to CSOPM (best effort)
        try:
            await self.mcp_client.add_jira_comment(
                issueIdOrKey=csopm_ticket_id,
                comment={
                    "body": (
                        f"Follow-up ticket created: "
                        f"[{result['ticket_id']}|https://jira.corp.adobe.com/browse/{result['ticket_id']}]"
                    )
                }
            )

            result["comment_added"] = True

        except Exception as e:
            self.logger.warning(f"Failed to add comment: {e}")
            result["errors"].append(f"Comment failed: {e}")

        # Step 4: Update CSOPM status to Complete (first follow-up only)
        is_first_followup = await self._is_first_followup(csopm_ticket_id)

        if is_first_followup:
            try:
                await self.mcp_client.transition_jira_status_by_name(
                    issueIdOrKey=csopm_ticket_id,
                    statusName="Complete",
                    comment="First follow-up ticket created, marking CSOPM as complete"
                )

                result["status_updated"] = True

                await self.db_store.increment_monthly_counter(
                    'csopm_status_updates_success', month_key, 1
                )

            except Exception as e:
                self.logger.warning(f"Failed to update status: {e}")
                result["errors"].append(f"Status update failed: {e}")

        # Step 5: Store follow-up record in DynamoDB
        try:
            timestamp = int(time.time())
            # NOTE: DynamoDB client requires type descriptors {"S": "value"}, {"N": "123"}
            await self.db_store.client.put_item(
                item={
                    "PK": {"S": f"CSOPM_TICKET#{csopm_ticket_id}"},
                    "SK": {"S": f"FOLLOWUP#{timestamp}#{result['ticket_id']}"},
                    "followup_ticket_id": {"S": result["ticket_id"]},
                    "followup_project": {"S": ticket_data["project"]},
                    "followup_issue_type": {"S": ticket_data["issue_type"]},
                    "summary": {"S": ticket_data["summary"]},
                    "priority": {"S": ticket_data["priority"]},
                    "severity": {"S": ticket_data["severity"]},
                    "created_at": {"N": str(timestamp)},
                    "created_by_slack_id": {"S": user_id},
                    "linked_to_csopm": {"BOOL": result["linked"]},
                    "comment_added": {"BOOL": result["comment_added"]},
                    "status_updated": {"BOOL": result["status_updated"]},
                    "ttl": {"N": str(timestamp + (90 * 86400))}
                },
                table_name=self.db_store.table_name
            )
        except Exception as e:
            self.logger.error(f"Failed to store follow-up record: {e}", exc_info=True)
            result["errors"].append(f"DB storage failed: {e}")

        self.logger.info(
            f"Follow-up creation completed: "
            f"created={result['ticket_created']}, "
            f"linked={result['linked']}, "
            f"comment={result['comment_added']}, "
            f"status={result['status_updated']}"
        )

        return result

    async def _is_first_followup(self, csopm_ticket_id: str) -> bool:
        """Check if this is the first follow-up ticket for CSOPM."""
        try:
            # Query for existing follow-ups
            # NOTE: DynamoDB client.query requires proper key conditions with type descriptors
            response = await self.db_store.client.query(
                table_name=self.db_store.table_name,
                key_condition_expression="PK = :pk AND begins_with(SK, :sk_prefix)",
                expression_attribute_values={
                    ":pk": {"S": f"CSOPM_TICKET#{csopm_ticket_id}"},
                    ":sk_prefix": {"S": "FOLLOWUP#"}
                },
                select="COUNT"  # Only count, don't fetch data
            )

            count = response.get("Count", 0)
            return count == 0

        except Exception as e:
            self.logger.warning(f"Failed to check first follow-up: {e}")
            return False  # Assume not first to avoid accidental status updates
```

**Key points**:
- Create ticket first (most critical - if this fails, abort)
- Link/comment/status operations are best-effort (continue on failure)
- Store result of each operation separately
- Custom fields: `customfield_15900` (Priority), `customfield_15901` (Severity)
- Check if first follow-up before updating status

**Integration points**:
- Use `mcp_client.create_jira_issue(fields={...})`
- Use `mcp_client.link_issues()` with linkType="relates to"
- Use `mcp_client.transition_jira_status_by_name()` for status update
- Use `db_store.client.query()` with proper key conditions to count existing follow-ups
- DynamoDB operations require type descriptors: `{"S": "string"}`, `{"N": "number"}`, `{"BOOL": true/false}`

### Verification

**Manual testing**:
Test with real CSOPM ticket - create follow-up via Slack modal, verify ticket created, linked, status updated.

**Automated tests**:
```bash
pytest tests/unit/services/test_csopm_link_service.py::test_create_followup_ticket_success -v
pytest tests/unit/services/test_csopm_link_service.py::test_create_followup_partial_success_link_fails -v
```

**Expected output**:
```
test_csopm_link_service.py::test_create_followup_ticket_success PASSED
test_csopm_link_service.py::test_create_followup_partial_success_link_fails PASSED
```

### Commit

**Commit message**:
```
feat: Implement follow-up ticket creation with partial success

Complete create_followup_ticket() method:
- Create ticket first (abort if fails)
- Link to CSOPM (best effort)
- Add comment to CSOPM (best effort)
- Update status to Complete (first follow-up only)
- Store follow-up record in DynamoDB with TTL

Returns detailed result dict with per-operation status.
Handles partial success gracefully.
```

**Files to commit**:
- `packages/services/csopm_link_service.py`
- `tests/unit/services/test_csopm_link_service.py`

---

## Task 6: Implement Metrics Collection Method

**File(s)**: `packages/services/csopm_link_service.py` (add method)
**Depends on**: Task 1 (Protocol)
**Estimated time**: 1-1.5 hours

### 🤖 Agent Assignment

- **Agent**: `1x python-backend-tdd-agent` (different from Tasks 3-5)
- **Parallel**: ✅ **YES** - Can run with Tasks 3, 4, 5, 17, 22, 25
- **Phase**: Phase 2
- **Launch Command**: `/task python-backend-tdd-agent "Implement Metrics Collection per Task 6"`

**Implementation**: Complete `get_metrics()` method stub with DynamoDB counter aggregation logic, period filtering (Q1, Q2, YTD, custom), and metric rollups. Tests first!

---

## Task 17: Create requirements.txt

**File(s)**: `csopm_link_service/requirements.txt`
**Depends on**: Task 1 (knows tech stack)
**Estimated time**: 30-45 minutes

### 🤖 Agent Assignment

- **Agent**: `1x backend-developer`
- **Parallel**: ✅ **YES** - Can run with Tasks 3-6, 22, 25
- **Phase**: Phase 2
- **Launch Command**: `/task backend-developer "Create requirements.txt per Task 17"`

**Implementation**: List all Python dependencies (FastAPI, boto3, pydantic, etc.) with pinned versions. Reference existing service requirements files.

---

## Task 22: Create User Acceptance Test Checklist (DRAFT)

**File(s)**: `docs/csopm-link-service-uat.md`
**Depends on**: Task 1 (knows feature scope)
**Estimated time**: 1 hour

### 🤖 Agent Assignment

- **Agent**: `1x technical-documentation-specialist`
- **Parallel**: ✅ **YES** - Can run with Tasks 3-6, 17, 25
- **Phase**: Phase 2 (draft), Phase 9 (finalize)
- **Launch Command**: `/task technical-documentation-specialist "Draft UAT checklist per Task 22"`

**Implementation**: Draft acceptance criteria based on protocol and plan. Will be refined in Phase 9 after implementation.

---

## Task 25: Create Deployment Documentation (DRAFT)

**File(s)**: `docs/csopm-link-service-deployment.md`
**Depends on**: Task 22 (same agent, sequential)
**Estimated time**: 1 hour

### 🤖 Agent Assignment

- **Agent**: `1x technical-documentation-specialist` (same as Task 22)
- **Parallel**: ❌ Follows Task 22 (same agent continues)
- **Phase**: Phase 2 (draft), Phase 9 (finalize)

**Implementation**: Draft deployment procedures based on protocol and plan. Will be refined in Phase 9 after implementation.

---

## ✅ QA CHECKPOINT: Phase 2 Complete

**QA Agents**: `1x code-reviewer` + `1x quality-control`
**Duration**: 1-1.5 hours
**Critical**: ⚠️ **HIGH** - Batch review of core service methods

### Verification Criteria
- [ ] All service method tests pass (Tasks 3-6)
- [ ] Test coverage >80% for each method
- [ ] Deduplication logic correct (Task 3)
- [ ] DB-first user resolution pattern followed (Task 4)
- [ ] Partial success handling correct (Task 5)
- [ ] Metrics aggregation logic correct (Task 6)
- [ ] requirements.txt complete and accurate (Task 17)
- [ ] TDD discipline maintained throughout

### Launch Command
```bash
/task code-reviewer "Review Phase 2: All service methods for TDD adherence, coverage, quality" &
/task quality-control "Validate Phase 2: All 4 service methods work correctly"
```

### Action if RED
🚨 **BLOCK Phase 3** - Fix issues before integration

---

# PHASE 3: Service Integration (Sequential - Day 2)

**Duration**: 1-2 hours
**Parallelization**: ❌ Sequential (integration point)
**Why Sequential**: Must wait for all core methods before DI registration

---

## Task 7: Create TypedDI Service Registration

**File(s)**: `packages/core/typed_di/service_registrations/registrations/csopm_link_registration.py`
**Depends on**: Tasks 3-6 (all service methods must exist)
**Estimated time**: 1-2 hours

### 🤖 Agent Assignment

- **Agent**: `1x python-integration-specialist`
- **Parallel**: ❌ Must wait for Phase 2 completion
- **Phase**: Phase 3
- **Launch Command**: `/task python-integration-specialist "Create TypedDI Service Registration per Task 7"`

**Implementation**: Integrate all service methods into DI container. Single integration specialist ensures consistency. Reference existing registrations in `packages/core/typed_di/service_registrations/registrations/`.

---

# PHASE 4: FastAPI Foundation (Sequential - Day 2)

**Duration**: 2-3 hours
**Parallelization**: ❌ Sequential (app foundation)
**Why Sequential**: All FastAPI features depend on this foundation

---

## Task 8: Create FastAPI Microservice App

**File(s)**: `csopm_link_service/main.py`
**Depends on**: Task 7 (needs service registration)
**Estimated time**: 2-3 hours

### 🤖 Agent Assignment

- **Agent**: `1x fastapi-pro`
- **Parallel**: ❌ Must wait for Phase 3 completion
- **Phase**: Phase 4
- **Launch Command**: `/task fastapi-pro "Create FastAPI Microservice App per Task 8"`

**Implementation**: Create FastAPI app with DI setup, basic endpoints, health checks. Reference `jira_reporter/main.py` for patterns.

---

## ✅ QA CHECKPOINT: Phase 4 Complete

**QA Agent**: `1x architect-review`
**Duration**: 30-45 minutes
**Critical**: ✅ **YES** - Architecture for all features

### Verification Criteria
- [ ] App structure follows ketchup patterns
- [ ] DI container properly configured
- [ ] Service registration works correctly
- [ ] Health endpoints respond
- [ ] Async patterns implemented correctly

### Launch Command
```bash
/task architect-review "Review Phase 4: FastAPI app structure, routing, DI setup"
```

### Action if RED
🚨 **BLOCK Phase 5** - Fix architectural issues

---

# PHASE 5: FastAPI Features & Infrastructure (4-way Parallel - Day 2-3)

**Duration**: 4-6 hours wall time
**Parallelization**: ✅ **4 agents simultaneously**
**Why Parallel**: Tasks 9, 10-11, 12, 18 depend on Task 8 but are independent of each other

### Launch All 4 Agents in Parallel:
```bash
/task fastapi-pro "Add Background Polling Task per Task 9" &
/task fastapi-pro "Create Slack Interaction Handlers (Task 10) then Modal Builders (Task 11)" &
/task backend-developer "Add Dynamic Issue Type Loading per Task 12" &
/task backend-developer "Create Health Check Script per Task 18"
```

---

## Task 9: Add Background Polling Task

**File(s)**: `csopm_link_service/main.py` (add background task)
**Depends on**: Task 8 (FastAPI app foundation)
**Estimated time**: 1.5-2 hours

### 🤖 Agent Assignment

- **Agent**: `1x fastapi-pro`
- **Parallel**: ✅ **YES** - Can run with Tasks 10-12, 18
- **Phase**: Phase 5
- **Launch Command**: `/task fastapi-pro "Add Background Polling Task per Task 9"`

**Implementation**: 15-minute polling cycle using FastAPI BackgroundTasks. Environment variable for interval. Reference `jira_reporter/` polling pattern.

---

## Task 10: Create Slack Interaction Handlers

**File(s)**: `csopm_link_service/main.py` (add endpoint)
**Depends on**: Task 8 (FastAPI app foundation)
**Estimated time**: 1.5-2 hours

### 🤖 Agent Assignment

- **Agent**: `1x fastapi-pro` (different from Task 9)
- **Parallel**: ✅ **YES** - Can run with Tasks 9, 12, 18
- **Phase**: Phase 5
- **Sequential Next**: Task 11 (same agent continues with modals)
- **Launch Command**: `/task fastapi-pro "Create Slack Interaction Handlers (Task 10) then Modal Builders (Task 11)"`

**Implementation**: `/slack/interactions` endpoint for button clicks. Handle "open_followup_modal" action. Parse interaction payload.

---

## Task 11: Implement Modal View Builders

**File(s)**: `csopm_link_service/modal_builders.py`
**Depends on**: Task 10 (needs handlers first)
**Estimated time**: 1.5-2 hours

### 🤖 Agent Assignment

- **Agent**: `1x fastapi-pro` (same as Task 10)
- **Parallel**: ❌ Follows Task 10 (same agent continues)
- **Phase**: Phase 5

**Implementation**: Modal builder functions with project/issue type dropdowns. Reference Slack Block Kit documentation.

---

## Task 12: Add Dynamic Issue Type Loading

**File(s)**: `csopm_link_service/main.py` (add endpoint)
**Depends on**: Task 8 (FastAPI app foundation)
**Estimated time**: 1-1.5 hours

### 🤖 Agent Assignment

- **Agent**: `1x backend-developer`
- **Parallel**: ✅ **YES** - Can run with Tasks 9, 10-11, 18
- **Phase**: Phase 5
- **Launch Command**: `/task backend-developer "Add Dynamic Issue Type Loading per Task 12"`

**Implementation**: Endpoint for project → issue types lookup via MCP-JIRA. Cache results for performance.

---

## Task 18: Create Health Check Script

**File(s)**: `csopm_link_service/health_check.sh`
**Depends on**: Task 8 (needs endpoints)
**Estimated time**: 45 minutes

### 🤖 Agent Assignment

- **Agent**: `1x backend-developer` (different from Task 12)
- **Parallel**: ✅ **YES** - Can run with Tasks 9, 10-12
- **Phase**: Phase 5
- **Launch Command**: `/task backend-developer "Create Health Check Script per Task 18"`

**Implementation**: Shell script to validate all critical endpoints. Exit codes for CI/CD integration.

---

## ✅ QA CHECKPOINT: Phase 5 Complete

**QA Agents**: `1x code-reviewer` + `1x quality-control`
**Duration**: 1 hour

### Verification Criteria
- [ ] Background task runs correctly every 15 minutes
- [ ] Interaction handlers process button clicks
- [ ] Modals render with correct fields
- [ ] Dynamic loading fetches issue types correctly
- [ ] Health check validates all critical components
- [ ] All endpoint tests pass

### Launch Command
```bash
/task code-reviewer "Review Phase 5: Async patterns, endpoints, feature completeness" &
/task quality-control "Validate Phase 5: All features work correctly"
```

### Action if RED
Fix issues before workflow integration

---

# PHASE 6: Workflow & Error Handling (Sequential - Day 3)

**Duration**: 3-4 hours
**Parallelization**: ❌ Sequential (workflow orchestration)

---

## Task 13: Implement Post-Submission Workflow

**File(s)**: `csopm_link_service/main.py`
**Depends on**: Tasks 9 (polling), 11 (modals)
**Estimated time**: 1.5-2 hours

### 🤖 Agent Assignment

- **Agent**: `1x backend-developer`
- **Parallel**: ❌ Needs both polling and modals to exist
- **Phase**: Phase 6
- **Launch Command**: `/task backend-developer "Implement Post-Submission Workflow per Task 13"`

**Implementation**: Complete workflow orchestration: modal submission → ticket creation → response message.

---

## Task 14: Add Error Handling with Data Dump

**File(s)**: `csopm_link_service/main.py`
**Depends on**: Tasks 9-13 (all workflows)
**Estimated time**: 1.5-2 hours

### 🤖 Agent Assignment

- **Agent**: `1x backend-developer` (same as Task 13)
- **Parallel**: ❌ Must wait for workflow completion
- **Phase**: Phase 6

**Implementation**: Comprehensive error handling across all endpoints. Formatted data dump for debugging. Error recovery logic.

---

# PHASE 7: Containerization & Testing (3-way Parallel - Day 3)

**Duration**: 4-5 hours wall time
**Parallelization**: ✅ **3 agents simultaneously**

### Launch All 3 Streams in Parallel:
```bash
# Docker stream
/task docker-infrastructure-specialist "Create Dockerfile (Task 15), then docker-compose (Task 16)" &
/task deployment-engineer "Update deploy-ketchup.sh per Task 19" &
# Testing streams
/task test-automator "Add Integration Tests per Task 20" &
/task test-automator "Add E2E Workflow Tests per Task 21"
```

---

## Task 15: Create Dockerfile

**File(s)**: `csopm_link_service/Dockerfile`
**Depends on**: Task 17 (requirements.txt)
**Estimated time**: 1 hour

### 🤖 Agent Assignment

- **Agent**: `1x docker-infrastructure-specialist`
- **Parallel**: ✅ **YES** - Can run with Tasks 19-21
- **Phase**: Phase 7
- **Sequential Next**: Task 16

---

## Task 16: Add to docker-compose.yml

**File(s)**: `docker-compose.yml`
**Depends on**: Task 15 (Dockerfile)
**Estimated time**: 45 minutes

### 🤖 Agent Assignment

- **Agent**: `1x docker-infrastructure-specialist` (same as Task 15)
- **Parallel**: ❌ Follows Task 15
- **Phase**: Phase 7
- **Sequential Next**: Task 19 handoff

---

## Task 19: Update deploy-ketchup.sh

**File(s)**: `scripts/deploy-ketchup.sh`
**Depends on**: Task 16 (docker-compose updated)
**Estimated time**: 1 hour

### 🤖 Agent Assignment

- **Agent**: `1x deployment-engineer`
- **Parallel**: ✅ **YES** - Can run with Tasks 20-21
- **Phase**: Phase 7

---

## Task 20: Add Integration Tests

**File(s)**: `tests/integration/test_csopm_link_service_integration.py`
**Depends on**: Phase 6 completion (all implementation done)
**Estimated time**: 2-3 hours

### 🤖 Agent Assignment

- **Agent**: `1x test-automator`
- **Parallel**: ✅ **YES** - Can run with Tasks 15-16, 19, 21
- **Phase**: Phase 7

---

## Task 21: Add E2E Workflow Tests

**File(s)**: `tests/e2e/test_csopm_complete_workflows.py`
**Depends on**: Phase 6 completion (all implementation done)
**Estimated time**: 2-3 hours

### 🤖 Agent Assignment

- **Agent**: `1x test-automator` (different from Task 20)
- **Parallel**: ✅ **YES** - Can run with Tasks 15-16, 19, 20
- **Phase**: Phase 7

---

## ✅ QA CHECKPOINT: Phase 7 Complete

**QA Agent**: `1x test-automator` (test coverage review)
**Duration**: 30 minutes

### Verification Criteria
- [ ] Overall test coverage >80%
- [ ] All integration tests pass
- [ ] All E2E workflows pass
- [ ] Docker container builds successfully
- [ ] docker-compose brings up service correctly
- [ ] Health check passes in containerized environment

### Launch Command
```bash
/task test-automator "Review Phase 7: Test coverage metrics (target >80%), test quality"
```

### Action if RED
Fix test failures before metrics integration

---

# PHASE 8: Metrics Integration (Sequential - Day 3)

**Duration**: 2 hours
**Parallelization**: ❌ Sequential (metrics wiring)

---

## Task 23: Update metrics_data_collector.py

**File(s)**: `packages/slack/services/metrics_data_collector.py`
**Depends on**: Task 6 (metrics method exists)
**Estimated time**: 1 hour

### 🤖 Agent Assignment

- **Agent**: `1x python-integration-specialist`
- **Parallel**: ❌ Sequential (tightly coupled with Task 24)
- **Phase**: Phase 8
- **Launch Command**: `/task python-integration-specialist "Update metrics_data_collector (Task 23) and /ketchup command (Task 24)"`

---

## Task 24: Add CSOPM Metrics to /ketchup Command

**File(s)**: Slack command handler
**Depends on**: Task 23 (metrics collector updated)
**Estimated time**: 1 hour

### 🤖 Agent Assignment

- **Agent**: `1x python-integration-specialist` (same as Task 23)
- **Parallel**: ❌ Follows Task 23
- **Phase**: Phase 8

---

## ✅ QA CHECKPOINT: Phase 8 Complete

**QA Agent**: `1x quality-control`
**Duration**: 30 minutes

### Verification Criteria
- [ ] Metrics collector fetches CSOPM data correctly
- [ ] `/ketchup` command displays CSOPM section
- [ ] Metrics aggregation logic correct
- [ ] Period filtering works (Q1, Q2, etc.)

---

# PHASE 9: Documentation Finalization (Sequential - Day 3-4)

**Duration**: 3-4 hours
**Parallelization**: ❌ Sequential (documentation polish)

---

## Task 22: Finalize User Acceptance Test Checklist

**Depends on**: Phase 7 (testing complete), Task 22 draft (Phase 2)
**Estimated time**: 1 hour

### 🤖 Agent Assignment

- **Agent**: `1x technical-documentation-specialist`
- **Phase**: Phase 9
- **Launch Command**: `/task technical-documentation-specialist "Finalize UAT checklist (Task 22), Deployment docs (Task 25), Create Troubleshooting guide (Task 26)"`

---

## Task 25: Finalize Deployment Documentation

**Depends on**: Phase 7 (deployment setup complete), Task 25 draft (Phase 2)
**Estimated time**: 1 hour

### 🤖 Agent Assignment

- **Agent**: `1x technical-documentation-specialist` (same as Task 22)
- **Phase**: Phase 9

---

## Task 26: Create Troubleshooting Guide

**File(s)**: `docs/csopm-link-service-troubleshooting.md`
**Depends on**: Phase 7 (testing revealed common issues)
**Estimated time**: 1-2 hours

### 🤖 Agent Assignment

- **Agent**: `1x technical-documentation-specialist` (same as Task 22, 25)
- **Phase**: Phase 9

---

# PHASE 10: Pre-Production Validation (Sequential - Day 4)

**Duration**: 2-3 hours
**Parallelization**: ❌ Sequential (final gates)

---

## Task 27: Run Pre-Deployment Tests

**Depends on**: All previous phases complete
**Estimated time**: 1-1.5 hours

### 🤖 Agent Assignment

- **Agent**: `1x production-readiness-validator`
- **Parallel**: ❌ Final quality gate
- **Phase**: Phase 10
- **Launch Command**: `/task production-readiness-validator "Run Pre-Deployment Tests per Task 27"`

---

## Task 28: Deploy to prod1 with Feature Flag Disabled

**Depends on**: Task 27 (validation passed)
**Estimated time**: 1-1.5 hours

### 🤖 Agent Assignment

- **Agent**: `1x deployment-engineer`
- **Parallel**: ❌ Only deploy after validation passes
- **Phase**: Phase 10
- **Launch Command**: `/task deployment-engineer "Deploy to prod1 with feature flag disabled per Task 28"`

---

## ✅ FINAL QA CHECKPOINT: Production Deployment

**QA Agent**: `1x production-readiness-validator` (continues monitoring)
**Duration**: 30+ minutes

### Verification Criteria
- [ ] Service running on prod1
- [ ] Health checks green
- [ ] No errors in logs
- [ ] Feature flag confirmed disabled
- [ ] Monitoring dashboards available
- [ ] Documentation accurate

---

## Testing Strategy

### Unit Tests
- **Location**: `tests/unit/services/`
- **Naming**: `test_<module_name>.py`
- **Run command**: `pytest tests/unit/ -v --cov=packages/services`
- **Coverage target**: 60%+

### Integration Tests
- **Location**: `tests/integration/`
- **What to test**: MCP-JIRA, Slack API, DynamoDB operations
- **Setup required**: Real MCP server running on port 8081

### E2E Tests
- **Location**: `tests/e2e/`
- **Critical flows**: Poll → Notify → Create Follow-up

### Test Design Principles for This Feature

**Use these patterns**:
1. **Mock all external dependencies** - Use `AsyncMock` for async methods
2. **Test deduplication thoroughly** - Critical for preventing duplicate notifications
3. **Test partial success scenarios** - Ticket creation succeeds but linking fails
4. **Use fixtures for common setup** - `mock_dependencies` fixture pattern

**Avoid these anti-patterns**:
1. Don't mock what you don't own - Don't mock `datetime.now()`, use test time
2. Don't test implementation details - Test behavior, not internal methods
3. Don't create interdependent tests - Each test should be independent

**Mocking guidelines**:
- Mock external services: MCPAsyncClient, Slack API, DynamoDB
- Don't mock: Protocol classes, data structures, utility functions
- Use project's mocking pattern: Reference `tests/unit/test_jira_reporter/test_jira_service.py`

---

## Commit Strategy

Break this work into 29 commits following this sequence:

1. **feat**: Add CSOPMLinkServiceProtocol interface
2. **feat**: Add CSOPMSlackClient for DM notifications
3. **feat**: Add email-to-user-ID resolution to SlackUserOps ← NEW (Task 2.5)
4. **feat**: Implement CSOPM ticket polling with deduplication (corrected DynamoDB API)
5. **feat**: Implement notification sending with Slack DM (corrected DynamoDB API)
6. **feat**: Implement follow-up ticket creation with partial success (corrected DynamoDB API)
7. **feat**: Implement metrics collection method
8. **feat**: Register CSOPM services with TypedDI
9. **feat**: Create FastAPI microservice for CSOPM link
10. **feat**: Add background polling task with 15-minute cycle
11. **feat**: Add Slack interaction handlers for button clicks
12. **feat**: Implement modal view builders for follow-up form
13. **feat**: Add dynamic issue type loading on project select
14. **feat**: Implement "Create Another Follow-up" workflow
15. **feat**: Add error handling with formatted data dump
16. **build**: Add Dockerfile for CSOPM link service
17. **build**: Add CSOPM link service to docker-compose.yml
18. **build**: Add requirements.txt for CSOPM link service
19. **build**: Add health check script for CSOPM link
20. **build**: Update deploy-ketchup.sh with CSOPM service
21. **test**: Add integration tests for MCP-JIRA operations
22. **test**: Add E2E workflow tests for complete flows
23. **docs**: Add user acceptance test checklist
24. **feat**: Update metrics_data_collector with CSOPM metrics
25. **feat**: Add CSOPM link section to /ketchup metrics command
26. **docs**: Add deployment documentation
27. **docs**: Add troubleshooting guide for common issues
28. **chore**: Run pre-deployment test suite
29. **deploy**: Deploy to prod1 with feature flag disabled

**Commit message format**:
```
type: Brief description (50 chars or less)

Optional body explaining why this change was made.
Can include multiple paragraphs.

References: #issue-number
```

---

## Common Pitfalls & How to Avoid Them

### 1. **Forgetting to check feature flag**
- Why it happens: Easy to forget in methods called by external triggers
- How to avoid: Check `self.enabled` at start of every public method
- Reference: `jira_reporter/services/jira_posting_service.py` checks flag in every method

### 2. **Not handling partial success correctly**
- Why it happens: Assuming all operations succeed or all fail
- How to avoid: Use result dict with per-operation status, continue on non-critical failures
- Reference: Pattern shown in Task 5 implementation

### 3. **Incorrect JIRA username format**
- Why it happens: Including @adobe.com in JIRA mentions
- How to avoid: Use `[~username]` not `[~username@adobe.com]`
- Reference: Section 5.1 in design document

### 4. **Missing month_key in metrics**
- Why it happens: Forgetting to get current month for counter increments
- How to avoid: Get month_key once at start: `month_key = datetime.now().strftime("%Y_%m")`
- Reference: `packages/slack/services/metrics_data_collector.py`

### 5. **Not using DB-first user resolution**
- Why it happens: Calling Slack API directly without checking DB first
- How to avoid: Always use `user_ops.get_slack_id_by_email()` - it checks DB first
- Reference: `packages/slack/user_operations/user_ops.py:get_user_names()`

### 6. **Hardcoding 15-minute interval**
- Why it happens: Not using environment variable
- How to avoid: Use `CSOPM_POLLING_INTERVAL` env var (in seconds), default 900
- Reference: docker-compose.yml environment section

### 7. **Missing TTL on DynamoDB records**
- Why it happens: Forgetting to set TTL field
- How to avoid: Always add: `ttl=int(time.time()) + (90 * 86400)`
- Reference: All DynamoDB put_item calls in service

### 8. **Not incrementing both success and failure metrics**
- Why it happens: Only tracking successes
- How to avoid: Increment failure counter in except blocks
- Reference: Every try/except in notification/follow-up methods

---

## Resources & References

### Existing Code to Reference
- Similar polling service: `jira_reporter/main.py`
- MCP client usage: `packages/integrations/async_mcp_client.py`
- User resolution pattern: `packages/slack/user_operations/user_ops.py`
- DynamoDB operations: `packages/db/dynamodb_store.py`
- TypedDI registration: `packages/core/typed_di/service_registrations/registrations/`
- Slack client base: `packages/slack/core/slack_async_client.py`
- Metrics collection: `packages/slack/services/metrics_data_collector.py`
- Test examples: `tests/unit/test_jira_reporter/test_jira_service.py`

### Documentation
- TypedDI pattern: Internal codebase uses protocol-first DI
- Slack Block Kit: https://api.slack.com/block-kit
- MCP-JIRA API: Local server on port 8081 (HTTP JSON-RPC)
- DynamoDB single-table: PK/SK pattern throughout codebase

### Validation Checklist
- [ ] All tests pass: `pytest tests/ -v`
- [ ] Coverage target met: `pytest --cov=packages/services --cov-report=term`
- [ ] Linter passes: `flake8 packages/services/ --max-line-length=120`
- [ ] No debug print statements left
- [ ] Feature flag checked in all public methods
- [ ] Metrics incremented on success AND failure
- [ ] DynamoDB records have TTL set
- [ ] JIRA usernames use `[~username]` format
- [ ] Error handling includes exc_info=True for logging
- [ ] Documentation updated (if adding new patterns)

---

## Getting Started

1. **Checkout feature branch**:
   ```bash
   git checkout -b feature/csopm-link-service
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install pytest pytest-asyncio pytest-cov
   ```

3. **Start MCP-JIRA server**:
   ```bash
   cd infrastructure
   docker-compose up -d mcp-jira
   ```

4. **Begin with Task 1**: Create protocol definition and tests
   - Write tests first (TDD)
   - Implement to pass tests
   - Commit with descriptive message

5. **Continue sequentially through tasks 2-29**

---

## Success Criteria

- [ ] All 29 tasks completed (includes new Task 2.5 for email resolution)
- [ ] Test coverage ≥60%
- [ ] Service deploys successfully with feature flag disabled
- [ ] Health checks pass
- [ ] No errors in logs during 48-hour soak test
- [ ] Manual smoke tests pass
- [ ] Code review approved
- [ ] Merged to main branch

---

**Estimated total time**: 3-4 days for experienced engineer
**Estimated commits**: 29
**Lines of code**: ~2100 (including tests and native email resolution)

This plan has been empirically validated against the Ketchup codebase (2025-11-03) and provides implementation-ready specifications with correct API patterns, eliminating ambiguity around DynamoDB operations and email-to-user-ID resolution.
