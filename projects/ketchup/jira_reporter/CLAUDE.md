# CLAUDE.md - JIRA Reporter Service

This file provides guidance to Claude Code when working with the **jira_reporter** service codebase.

**Parent Documentation**: See [/projects/ketchup/CLAUDE.md](../CLAUDE.md) for shared patterns, TypedDI system, deployment, and repository structure.

---

## Service Overview

The **JIRA Reporter** is Ketchup's most complex service (1,772 LOC, 8 files), providing **automated incident report generation and JIRA posting** for CSO (Customer Support Operations) war room channels.

### Core Capabilities
- **Dual-Mode Processing**: SQS event-driven + 15-minute scheduled polling
- **AI-Powered Report Generation**: OpenAI API generates structured JIRA-formatted incident reports
- **Intelligent Channel Discovery**: Exigence ID extraction and reverse JIRA ticket lookup
- **Dual-Ticket Posting**: Primary ticket + CSOPM fallback with deduplication
- **Stateful Archive Management**: Temporary unarchive with 180-second TTL and bot membership handling
- **Retry Logic**: 24-hour retry cooldown, max 3 attempts per channel

### When Reports Are Generated
1. **SQS Event Trigger**: When a CSO channel is archived (real-time)
2. **Scheduled Polling**: Every 15 minutes for channels quiet for 24+ hours
3. **Eligibility Criteria**:
   - Channel name contains "cso" (case-insensitive)
   - Valid JIRA ticket exists (not "NOT YET AVAILABLE")
   - Not already processed (`jira_report_status != "PROCESSED"`)
   - Feature flag enabled for channel

---

## Architecture

### File Structure (8 files)
```
jira_reporter/
├── main.py                      # Entry point, orchestration, SQS processing (551 lines)
├── report_generator.py          # AI report generation, JIRA formatting (239 lines)
├── jira_service.py             # MCP JIRA API integration (153 lines)
├── channel_monitor.py          # Channel eligibility & activity checks (202 lines)
├── jira_ticket_discovery.py    # Exigence ID extraction, CSOPM lookup (249 lines)
├── archive_handler.py          # Archive/unarchive with bot membership (339 lines)
├── constants.py                # Status constants, retry config (42 lines)
└── __init__.py                 # Package initialization (81 lines)

Total: 1,772 lines
```

### Service Dependencies
```python
# TypedDI Protocol imports (9 protocols)
DynamoDBStoreProtocol           # Channel metadata storage
SecretsManagerProtocol          # AWS Secrets Manager access
OpenAIHandlerProtocol           # AI report generation
SlackChannelMessageOpsProtocol  # Message retrieval
SlackChannelArchiveOpsProtocol  # Archive/unarchive operations
SlackChannelBotMembershipOpsProtocol  # Bot channel joining
MCPClientProtocol               # MCP JIRA integration
IMSTokenManagerProtocol         # IMS authentication
FeatureServiceProtocol          # Feature flag checks
```

### Data Flow
```
┌─────────────────────────────────────────────────────────────────┐
│                    DUAL-MODE PROCESSING                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  MODE 1: SQS Event-Driven (Real-time)                         │
│  ┌──────────────────────────────────────────────────────┐     │
│  │ Channel Archived → SQS Event → process_sqs_messages() │     │
│  │ (event_type: channel_archived, service: jira_reporter)│     │
│  └──────────────────────────────────────────────────────┘     │
│                                                                 │
│  MODE 2: Scheduled Polling (15-minute intervals)               │
│  ┌──────────────────────────────────────────────────────┐     │
│  │ Timer → get_channels_needing_reports() → Filter CSO   │     │
│  │ channels quiet for 24+ hours                          │     │
│  └──────────────────────────────────────────────────────┘     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│                   CHANNEL PROCESSING                            │
├─────────────────────────────────────────────────────────────────┤
│  1. Archive Handler: Temporarily unarchive (180s TTL)          │
│  2. Report Generator: Fetch messages → AI generation           │
│  3. JIRA Discovery: Extract Exigence ID → Find CSOPM ticket   │
│  4. JIRA Service: Post to primary ticket + CSOPM (if found)   │
│  5. Archive Handler: Re-archive channel                        │
│  6. DynamoDB: Update jira_report_status = PROCESSED            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Dual Processing Model

### Mode 1: SQS Event Consumption
**Queue**: `KETCHUP_EVENTS_QUEUE_URL` (https://sqs.eu-west-1.amazonaws.com/483013340174/ketchup-events-queue)

```python
# Event format
{
    "event_type": "channel_archived",
    "service": "jira_reporter",
    "channel_id": "C01234567",
    "timestamp": 1234567890
}

# Processing in main.py:254-341
async def process_sqs_messages(...) -> int:
    sqs_client = SQSClient(queue_url=queue_url)
    messages = await sqs_client.receive_messages(max_messages=10)

    for message in messages:
        body = json.loads(message['Body'])
        if (body.get('event_type') == 'channel_archived' and
            body.get('service') == 'jira_reporter'):

            # Process channel with skip_activity_check=True
            success = await process_channel(
                channel_data=channel_data,
                skip_activity_check=True  # Already archived
            )
```

**Why SQS?**: Guarantees reports are generated immediately upon archiving, even if scheduled polling hasn't run yet.

### Mode 2: Scheduled Polling (15-minute intervals)
```python
# main.py:507-543
async def main_loop() -> None:
    interval_minutes = int(os.environ.get("CHECK_INTERVAL_MINUTES", "15"))

    while True:
        await run_reporting_cycle()  # Processes active CSO channels
        await asyncio.sleep(interval_minutes * 60)
```

**Eligibility Check** (channel_monitor.py:43-154):
```python
async def get_channels_needing_reports(self) -> List[Dict[str, Any]]:
    # 1. Channel must have valid JIRA ticket
    if not jira_ticket or jira_ticket == "NOT YET AVAILABLE":
        continue

    # 2. Channel name must contain "cso"
    if "cso" not in channel_name.lower():
        continue

    # 3. Skip if already processed (permanent)
    if jira_report_status == "PROCESSED":
        continue

    # 4. Retry logic for FAILED status
    if jira_report_status == "FAILED":
        retry_count = channel_data.get("jira_report_retry_count", 0)
        if retry_count >= 3:  # Max retries exceeded
            continue

        # Check 24-hour cooldown
        hours_since_last = (time.time() - last_attempt_ts) / 3600
        if hours_since_last < 24:
            continue

    # 5. Skip archived channels (handled by SQS)
    if channel_data.get("archived", False):
        continue

    # 6. Check 24-hour activity threshold
    last_activity_hours = await self._get_hours_since_last_activity(channel_id)
    if last_activity_hours < 24:  # Still active
        continue
```

**Why Polling?**: Catches edge cases where SQS events are missed or channels become stale without being archived.

---

## Environment Variables

### Required Configuration
```yaml
# Main service
CHECK_INTERVAL_MINUTES=15        # Polling frequency (default: 15)
LOOKBACK_HOURS=24                # Activity threshold (default: 24)
BATCH_SIZE=5                     # Concurrent channel processing (default: 5)

# MCP JIRA Integration
MCP_BASE_URL=http://mcp-jira:8081  # MCP JIRA server URL

# SQS Event Processing
KETCHUP_EVENTS_QUEUE_URL=https://sqs.eu-west-1.amazonaws.com/483013340174/ketchup-events-queue

# Feature Flags
KETCHUP_JIRA_REPORTER_FEATURE=true  # Global feature flag
```

### Optional Configuration
```yaml
# Pipeline Processing (59% performance improvement)
USE_PIPELINE_PROCESSING=true

# Structured JSON Output (Azure OpenAI)
STRUCTURED_JSON_OUTPUT_ENABLED=true

# JIRA Project Filter
VALID_JIRA_PROJECTS=CSO Problem Management,CPGNREQ,CSOPM  # Comma-separated
```

---

## Archive Management

### The Challenge
**Problem**: Cannot read messages from archived Slack channels without unarchiving them first.

**Solution**: Temporary unarchive → read messages → re-archive, with bot membership handling.

### Implementation (archive_handler.py)

#### Temporary Unarchive with Bot Membership
```python
# archive_handler.py:45-129
async def temporarily_unarchive_channel(self, channel_id: str) -> bool:
    # 1. Check real-time archive status (not DynamoDB)
    channel_info = await self.archive_ops.get_channel_info(channel_id)
    is_archived = channel_data.get("is_archived", False)

    if not is_archived:
        return True  # Already unarchived

    # 2. Unarchive the channel
    success = await self.archive_ops.unarchive_channel(channel_id)

    # 3. Check bot membership and join if needed
    is_member = await self.bot_membership_ops.check_bot_channel_membership(channel_id)
    if not is_member:
        join_result = await self._join_channel(channel_id, channel_name, bot_user_id)
        if not join_result:
            # Re-archive if can't join
            await self.archive_ops.archive_channel(channel_id, skip_status_check=True)
            return False

    # 4. Update DynamoDB with TTL tracking
    ttl_timestamp = int(time.time()) + 180  # 180 seconds (3 minutes)
    await self.dynamodb_store.update_channel_fields(
        channel_id=channel_id,
        updates={
            "archived": False,
            "temporary_unarchive": True,
            "unarchive_reason": "jira_reporter_processing",
            "temp_unarchive_expiry": ttl_timestamp
        }
    )
    return True
```

#### Stale Cleanup on Service Startup
```python
# archive_handler.py:275-315
async def cleanup_stale_unarchives(self) -> int:
    """Clean up channels left unarchived from previous crashes."""
    current_time = int(time.time())
    cleaned_count = 0

    all_channels = await self.dynamodb_store.get_all_channel_details()

    for channel_id, channel_data in all_channels.items():
        if (channel_data.get("temporary_unarchive") and
            channel_data.get("temp_unarchive_expiry")):

            ttl = channel_data["temp_unarchive_expiry"]
            if current_time > ttl:  # TTL expired
                success = await self.rearchive_channel(channel_id)
                if success:
                    cleaned_count += 1

    return cleaned_count

# Called in main.py:388-391
cleaned_count = await archive_handler.cleanup_stale_unarchives()
if cleaned_count > 0:
    logger.info(f"Cleaned up {cleaned_count} stale unarchived channels")
```

### DynamoDB State Tracking
```python
# State fields
{
    "archived": False,                           # Current archive status
    "temporary_unarchive": True,                 # Flag for temp unarchive
    "unarchive_reason": "jira_reporter_processing",
    "unarchive_timestamp": 1234567890,           # When unarchived
    "temp_unarchive_expiry": 1234567890 + 180,   # TTL (3 minutes)
    "rearchive_timestamp": 1234567891,           # When re-archived
    "archived_at": 1234567800                    # Original archive time (preserved)
}
```

**Key Design Decision**: Use `temp_unarchive_expiry` instead of relying on DynamoDB TTL for immediate cleanup on service restart.

---

## TypedDI Integration

### Protocol Dependencies (9 protocols)
```python
# main.py:18-39
from packages.core.typed_di.service_registrations.protocols.core_protocols import (
    DynamoDBStoreProtocol,        # Channel metadata CRUD
    SecretsManagerProtocol,        # Bot tokens, API keys
)
from packages.core.typed_di.service_registrations.protocols.handler_protocols import (
    OpenAIHandlerProtocol,         # AI report generation
)
from packages.core.typed_di.service_registrations.protocols.slack_protocols import (
    SlackChannelMessageOpsProtocol,        # Message fetching
    SlackChannelArchiveOpsProtocol,        # Archive operations
    SlackChannelBotMembershipOpsProtocol,  # Bot joining
)
from packages.core.typed_di.service_registrations.protocols.mcp_protocols import (
    MCPClientProtocol,             # JIRA API access
)
from packages.core.typed_di.service_registrations.protocols.infrastructure_protocols import (
    IMSTokenManagerProtocol,       # IMS authentication
)
from packages.core.typed_di.service_registrations.protocols.command_protocols import (
    FeatureServiceProtocol,        # Feature flag checks
)
```

### Service Initialization Pattern
```python
# main.py:362-408
async def run_reporting_cycle() -> None:
    # 1. Initialize unified DI container
    container = await get_unified_container()

    # 2. Resolve TypedDI dependencies
    dynamodb_store = await container.aget(DynamoDBStoreProtocol)
    openai_handler = await container.aget(OpenAIHandlerProtocol)
    msg_ops = await container.aget(SlackChannelMessageOpsProtocol)
    secrets_manager = await container.aget(SecretsManagerProtocol)
    mcp_client = await container.aget(MCPClientProtocol)
    ims_token_manager = await container.aget(IMSTokenManagerProtocol)
    feature_service = await container.aget(FeatureServiceProtocol)
    archive_ops = await container.aget(SlackChannelArchiveOpsProtocol)
    bot_membership_ops = await container.aget(SlackChannelBotMembershipOpsProtocol)

    # 3. Create service-specific components (not in DI)
    jira_discovery = JiraTicketDiscovery(mcp_client=mcp_client)
    archive_handler = JiraReporterArchiveHandler(
        archive_ops=archive_ops,
        dynamodb_store=dynamodb_store,
        bot_membership_ops=bot_membership_ops,
        secrets_manager=secrets_manager
    )
    channel_monitor = ChannelMonitor(
        dynamodb_store=dynamodb_store,
        jira_discovery=jira_discovery,
        lookback_hours=int(os.environ.get("LOOKBACK_HOURS", "24")),
        msg_ops=msg_ops
    )
    report_generator = ReportGenerator(
        openai_handler=openai_handler,
        channel_msg_ops=msg_ops,
        archive_handler=archive_handler
    )
    jira_service = JiraService(
        secrets_manager=secrets_manager,
        ims_token_manager=ims_token_manager
    )

    # 4. Process channels...

    # 5. Cleanup
    finally:
        await cleanup_unified_container()
```

**Why Not Register Everything?**: `JiraTicketDiscovery`, `ArchiveHandler`, `ChannelMonitor`, `ReportGenerator`, and `JiraService` are service-specific and not shared across services.

---

## Health Monitoring

### File-Based Health Checks
```python
# main.py:60-81
def write_health_status(status: str) -> None:
    """Write health status for Docker health check."""
    timestamp = int(time.time())
    health_data = f"{timestamp}:{status}"
    with open("/tmp/jira_reporter_health", "w") as f:
        f.write(health_data)

def write_last_successful_run() -> None:
    """Write timestamp of last successful run."""
    timestamp = int(time.time())
    with open("/tmp/jira_reporter_last_run", "w") as f:
        f.write(str(timestamp))

# Called at key points in main.py
write_health_status("running")   # Start of cycle
write_health_status("idle")      # No work to do
write_health_status("error")     # Exception occurred
write_last_successful_run()      # After successful cycle
```

### Docker Health Check (infrastructure/docker-compose.yml)
```yaml
ketchup-jira-reporter:
  healthcheck:
    test: ["CMD", "python", "-c", "import os; exit(0 if os.path.exists('/tmp/jira_reporter_health') else 1)"]
    interval: 60s
    timeout: 10s
    retries: 3
```

### Statistics Tracking
```python
# main.py:49-58
stats = {
    "total_processed": 0,    # Total channels attempted
    "successful": 0,         # Successfully posted to JIRA
    "failed": 0,             # Failed to post
    "skipped": 0,            # Feature flag disabled
    "discovered": 0,         # CSOPM tickets found
    "last_run": None,        # ISO timestamp
    "sqs_processed": 0       # Channels from SQS
}

# Logged every 12 cycles (~1 hour)
logger.info(
    f"Hourly summary - Total processed: {stats['total_processed']}, "
    f"Successful: {stats['successful']}, Failed: {stats['failed']}"
)
```

---

## AI Integration

### Report Generation Pipeline

#### 1. Message Retrieval (report_generator.py:72-86)
```python
# Fetch channel messages (supports pipeline processing)
if USE_PIPELINE_PROCESSING:
    messages = await self.channel_msg_ops.fetch_channel_messages_collected(
        channel_id=channel_id,
        limit=500  # Balance between context and token usage
    )
else:
    messages = await self.channel_msg_ops.fetch_channel_messages(
        channel_id=channel_id,
        limit=500
    )
```

#### 2. AI Prompt Construction (report_generator.py:129-205)
```python
def _create_report_prompt(self, formatted_messages: str, channel_metadata: Dict[str, Any]) -> str:
    """Create AI prompt for incident report generation."""
    customer = channel_metadata.get("customer_name", "")
    jira_ticket = channel_metadata.get("jira_ticket", "Unknown")
    channel_name = channel_metadata.get("channel_name", "Unknown")

    prompt = f"""
You are an AI assistant specialized in summarizing incident response channels.
Your task is to create a comprehensive report of a Slack conversation from a CSO war room.

Customer: {customer}
JIRA Ticket: {jira_ticket}
Channel Name: {channel_name}

Analyze the provided Slack conversation and create a comprehensive incident summary report.
The report should be formatted using JIRA wiki formatting and include the following sections:

1. h3. Executive Summary
   Provide a brief overview of the incident, current status, CSO Phase, and business impacts.

2. h3. People Involved
   List the engineers and their roles/contributions during the incident.

3. h3. Incident Timeline
   Present key events in chronological order with timestamps (format: DD-MMM-YYYY, HH:MM UTC).

4. h3. Technical Analysis
   Describe the root cause analysis, systems affected, and error patterns observed.

5. h3. Impact Assessment
   Explain the customer experience impact, service availability, and affected metrics.

6. h3. Resolution & Mitigation
   Detail the actions taken, workarounds implemented, and fixes applied.

7. h3. JIRA Tickets & Work Done
   List related JIRA tickets with brief summaries of work completed.

8. h3. Next Steps
   Outline pending actions, ongoing investigations, and preventative measures.

9. h3. References
   Include links to support tickets, documentation, and case numbers.

Channel Messages:
{formatted_messages}

When creating the report:
1. Use JIRA wiki formatting (h3. for headers, * for bullets, etc.).
2. Keep the report concise but informative, focusing on key information for stakeholders.
3. Extract relevant information from the provided Slack conversation to populate each section.
4. Ensure that all timestamps are in the format DD-MMM-YYYY, HH:MM UTC.
5. Use bullet points where appropriate to improve readability.
6. If certain information is not available, indicate "Not specified".
"""

    # Add JSON format instruction for structured output
    if FeatureFlags.is_structured_json_output_enabled():
        prompt += """

IMPORTANT: Return your response as JSON with this exact structure:
{"response_text": "your complete JIRA-formatted report here"}
"""

    return prompt
```

#### 3. OpenAI API Call (report_generator.py:98-103)
```python
messages = [{"role": "user", "content": prompt}]
report_text = await self.openai_handler.execute_prompt(
    messages=messages,
    max_tokens=2000,    # Long enough for comprehensive reports
    temperature=0.3     # Low temperature for consistent, factual output
)
```

#### 4. JIRA Wiki Formatting (report_generator.py:207-238)
```python
def _format_for_jira(self, report_text: str, channel_metadata: Dict[str, Any]) -> str:
    """Add header and footer for JIRA posting."""
    customer = channel_metadata.get("customer_name", "")
    channel_name = channel_metadata.get("channel_name", "Unknown")
    channel_id = channel_metadata.get("channel_id", "Unknown")
    jira_ticket = channel_metadata.get("jira_ticket", "")

    header = f"""h2. Ketchup Automated Incident Report

*Channel*: {channel_name} (ID: {channel_id})
*Customer*: {customer}
*JIRA Ticket*: {jira_ticket}
*Generated*: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}

----

{report_text}

----

_This report was automatically generated by Ketchup._
"""
    return header
```

### JIRA Wiki Formatting Reference
```
h2. Header Level 2
h3. Header Level 3
*bold text*
_italic text_
* Bullet point
# Numbered list
---- Horizontal rule
{code}code block{code}
```

---

## Error Handling

### Primary Ticket Validation & CSOPM Fallback

#### The Problem
Many CSO channels have invalid or inaccessible primary JIRA tickets, causing infinite retry loops.

#### The Solution (main.py:146-216)
```python
# 1. Check if primary ticket was previously marked invalid
primary_invalid = channel_data.get("jira_report_primary_invalid", False)

if primary_invalid:
    logger.warning(f"Skipping primary ticket {jira_ticket} - previously marked invalid")
    primary_success = False  # Skip trying invalid ticket
else:
    # 2. Attempt to post to primary ticket
    primary_success = await jira_service.post_comment_to_ticket(
        jira_ticket_id=jira_ticket,
        comment_text=report_text
    )

    # 3. If failed, validate ticket exists
    if not primary_success:
        ticket_exists = await jira_service._validate_ticket_exists(jira_ticket)
        if not ticket_exists:
            # 4. Mark as permanently invalid
            await dynamodb_store.channel_ops.update_channel_fields(
                channel_id=channel_id,
                updates={"jira_report_primary_invalid": True}
            )

# 5. Discover and post to CSOPM ticket (if different from primary)
csopm_ticket = await jira_discovery.discover_csopm_ticket(channel_name, channel_data)

if csopm_ticket and csopm_ticket != jira_ticket:
    # 6. Check if already posted to CSOPM
    csopm_posted = channel_data.get("jira_report_csopm_posted", False)

    if not csopm_posted:
        csopm_success = await jira_service.post_comment_to_ticket(
            jira_ticket_id=csopm_ticket,
            comment_text=report_text
        )

        if csopm_success:
            # 7. Mark CSOPM as posted to prevent duplicates
            await dynamodb_store.channel_ops.update_channel_fields(
                channel_id=channel_id,
                updates={
                    "jira_report_csopm_posted": True,
                    "jira_report_csopm_ticket": csopm_ticket
                }
            )

# 8. Consider success if EITHER primary OR CSOPM succeeded
if primary_invalid and csopm_success:
    success = True  # Primary invalid but CSOPM worked
else:
    success = primary_success  # Normal case
```

### Retry Logic with Cooldown

#### Configuration (constants.py:23-26)
```python
MAX_RETRY_ATTEMPTS = 3
BASE_RETRY_DELAY = 60        # 1 minute
MAX_RETRY_DELAY = 3600       # 1 hour
RETRY_COOLDOWN_HOURS = 24    # 24-hour cooldown between retries
```

#### Implementation (channel_monitor.py:82-110)
```python
if jira_report_status == "FAILED":
    retry_count = channel_data.get("jira_report_retry_count", 0)
    max_retries = 3
    retry_cooldown_hours = 24

    # Skip if max retries exceeded
    if retry_count >= max_retries:
        logger.info(f"Channel {channel_id} exceeded max retries, skipping permanently")
        continue

    # Check 24-hour cooldown
    last_attempt_ts = channel_data.get("jira_report_timestamp", 0)
    hours_since_last = (time.time() - last_attempt_ts) / 3600

    if hours_since_last < retry_cooldown_hours:
        logger.info(f"Channel {channel_id} in cooldown ({hours_since_last:.1f}h < 24h)")
        continue

    logger.info(f"Channel {channel_id} FAILED - retry {retry_count + 1}/3")
```

#### Retry Count Update (main.py:229-242)
```python
if not success:
    current_retry_count = channel_data.get("jira_report_retry_count", 0)
    new_retry_count = current_retry_count + 1

    await dynamodb_store.channel_ops.update_jira_report_status(
        channel_id=channel_id,
        status="FAILED",
        retry_count=new_retry_count
    )
```

### JIRA Ticket Validation (jira_service.py:103-143)
```python
async def _validate_ticket_exists(self, ticket_id: str) -> bool:
    """Validate ticket exists using MCP search."""
    payload = {
        "jsonrpc": "2.0",
        "id": f"validate-{ticket_id}",
        "method": "tools/call",
        "params": {
            "name": "search_jira_issues",
            "arguments": {
                "jql": f"key = {ticket_id}",
                "maxResults": 1
            }
        }
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{self.mcp_base_url}/message",
            json=payload,
            headers=await self._get_headers()
        )

        if response.status_code != 200:
            return False

        # Check if ticket found in search results
        result = response.json()
        if result.get("result", {}).get("content"):
            content = json.loads(result["result"]["content"][0]["text"])
            return content.get("total", 0) > 0

    return False
```

---

## Testing

### Test Coverage Summary
- **Unit Tests**: 8 files, ~1,757 lines
- **Integration Tests**: 5 files, ~1,683 lines
- **Total Test LOC**: ~3,440 lines (194% test-to-code ratio)

### Unit Test Files (tests/unit/test_jira_reporter/)
```
test_archive_handler.py       # Archive/unarchive logic, TTL tracking
test_archive_monitor.py        # Channel eligibility (legacy name)
test_config.py                 # Test fixtures and constants
test_feature_flag.py           # Feature flag integration
test_jira_service.py           # MCP JIRA API calls
test_jira_ticket_discovery.py  # Exigence ID extraction, CSOPM search
test_report_generator.py       # AI report generation, formatting
```

### Integration Test Files (tests/integration/test_jira_reporter/)
```
test_direct_token_refresh.py           # IMS token refresh
test_end_to_end_flow.py                # Complete processing flow
test_final_jira_post.py                # Real JIRA posting
test_jira_discovery_mcp_integration.py # MCP JIRA search
test_jira_posting.py                   # JIRA comment posting
test_jira_reporter_auth.py             # MCP authentication
test_jira_with_fresh_token.py          # Token management
test_mcp_direct.py                     # Direct MCP calls
test_real_jira_posting.py              # Production JIRA API
```

### Running Tests
```bash
# From tests/setup/
make test-jira-reporter-unit          # Unit tests only (fast)
make test-jira-reporter-integration   # Integration tests (requires AWS profile)
make test-jira-reporter                # All tests
```

### Test Fixtures (test_config.py)
```python
TEST_CHANNELS = {
    "with_existing_ticket": {
        "channel_id": "C01234567",
        "channel_name": "cso_202401010001_testcustomer_12345",
        "jira_ticket": "CPGNREQ-180248",
        "archived": True,
        "jira_report_status": ""
    },
    "with_exigence_id": {
        "channel_id": "C01234568",
        "channel_name": "cso_202401020001_customer2_67890",
        "jira_ticket": "NOT YET AVAILABLE",
        "archived": True
    }
}

TEST_JIRA_TICKETS = {
    "CPGNREQ": "CPGNREQ-180248",  # Real test ticket
    "CSOPM": "CSOPM-59374"         # Real CSOPM test ticket
}
```

### Test Naming Conventions
```python
# CSO channel naming pattern
"cso_{YYYYMMDD}_{sequence}_{customer}_{exigence_id}"

# Example:
"cso_20240101_0001_adobe_12345"
#    └─date─┘ └seq┘ └cust─┘ └exig┘
```

---

## JIRA Ticket Discovery

### Exigence Integration
**Exigence**: Adobe's incident management platform that creates CSO war room channels.

**Channel Naming Pattern**: `cso_YYYYMMDD_NNNN_customer_XXXXX`
- `XXXXX` = 5-digit Exigence event ID

### Discovery Flow (jira_ticket_discovery.py)

#### 1. Extract Exigence ID (lines 36-61)
```python
def extract_exigence_id(self, channel_name: str) -> Optional[str]:
    """Extract 5-digit Exigence event ID from channel name."""
    # Pattern: 5 digits NOT part of YYYYMMDD date
    pattern = r'(?<!\d)(\d{5})(?!\d)'
    matches = re.findall(pattern, channel_name)

    if not matches:
        return None

    # Return last match (usually at end of name)
    return matches[-1]

# Example:
# "cso_20240101_0001_adobe_12345" → "12345"
```

#### 2. Build Exigence URL (lines 63-73)
```python
def build_exigence_url(self, event_id: str) -> str:
    """Build Exigence situation room URL."""
    return f"https://adobe.app.exigence.io/secure/index.html#/events/{event_id}/situationroom"

# Example:
# "12345" → "https://adobe.app.exigence.io/secure/index.html#/events/12345/situationroom"
```

#### 3. Search JIRA for Exigence URL (lines 75-151)
```python
async def search_jira_by_exigence_url(self, exigence_url: str, customer_name: Optional[str]) -> Optional[str]:
    """Search JIRA for tickets containing Exigence URL."""

    # Primary search: CSOPM project descriptions
    jql = f'project = "CSO Problem Management" AND description ~ "{exigence_url}"'
    results = await self.mcp_client.search_issues(jql, max_results=50)

    if results and results.get('issues'):
        ticket_id = results['issues'][0].get("key")
        return ticket_id  # Return CSOPM-XXXXX

    # Extended search: All valid projects (descriptions + comments)
    projects_list = ", ".join([f'"{p}"' for p in self.valid_projects])
    jql = (
        f'project IN ({projects_list}) '
        f'AND (description ~ "{exigence_url}" OR comment ~ "{exigence_url}")'
    )

    if customer_name and customer_name != "NOT YET AVAILABLE":
        jql += f' AND summary ~ "{customer_name}"'

    results = await self.mcp_client.search_issues(jql, max_results=50)

    if results and results.get('issues'):
        # Prefer CSOPM tickets if multiple results
        for issue in results['issues']:
            if issue.get("key", "").startswith("CSOPM-"):
                return issue.get("key")

        # Otherwise return first result
        return results['issues'][0].get("key")

    return None  # No ticket found
```

#### 4. Discover CSOPM Ticket (lines 195-249)
```python
async def discover_csopm_ticket(self, channel_name: str, channel_metadata: Dict[str, Any]) -> Optional[str]:
    """Discover CSOPM ticket specifically for dual posting."""
    event_id = self.extract_exigence_id(channel_name)
    if not event_id:
        return None

    exigence_url = self.build_exigence_url(event_id)

    # Direct CSOPM search (descriptions + comments)
    jql = f'project = "CSO Problem Management" AND description ~ "{exigence_url}" OR comment ~ "{exigence_url}"'
    results = await self.mcp_client.search_issues(jql, max_results=50)

    if results and results.get('issues'):
        ticket_id = results['issues'][0].get("key")
        if ticket_id and ticket_id.startswith("CSOPM-"):
            return ticket_id

    return None
```

### Valid JIRA Projects
```python
# packages/core/jira_constants.py
VALID_JIRA_PROJECTS = [
    "CSO Problem Management",  # CSOPM-XXXXX (preferred)
    "CPGNREQ",                 # Campaign requests
    # ... (configured via VALID_JIRA_PROJECTS env var)
]
```

---

## Common Issues

### 1. MCP JIRA Authentication Failures
**Symptom**: `401 Unauthorized` errors when posting to JIRA

**Root Cause**: IMS token expired or invalid

**Solution**:
```python
# jira_service.py:145-153
async def _get_headers(self) -> Dict[str, str]:
    # Always get fresh token from IMSTokenManager
    token = await self.ims_token_manager.get_valid_token()

    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
```

**Debug Steps**:
1. Check MCP JIRA server logs: `docker logs mcp-jira`
2. Verify IMS token: `docker exec ketchup-jira-reporter python -c "from packages.integrations.ims_token_manager import IMSTokenManager; import asyncio; asyncio.run(IMSTokenManager().get_valid_token())"`
3. Test MCP endpoint: `curl -H "Authorization: Bearer $TOKEN" http://mcp-jira:8081/health`

### 2. Stale Unarchived Channels
**Symptom**: Channels remain unarchived after service crash

**Root Cause**: Service stopped before re-archiving completed

**Solution**: Stale cleanup runs on every service startup
```python
# main.py:388-391
cleaned_count = await archive_handler.cleanup_stale_unarchives()
if cleaned_count > 0:
    logger.info(f"Cleaned up {cleaned_count} stale unarchived channels")
```

**Manual Cleanup**:
```python
# Run in Python shell with AWS credentials
from packages.db.dynamodb_store import DynamoDBStore
import asyncio

async def cleanup():
    store = DynamoDBStore()
    channels = await store.get_all_channel_details()

    for channel_id, data in channels.items():
        if data.get("temporary_unarchive"):
            print(f"Stale unarchive: {channel_id} - {data.get('channel_name')}")
            # Re-archive using Slack API...

asyncio.run(cleanup())
```

### 3. SQS Message Processing Failures
**Symptom**: Archived channels not processed in real-time

**Debug Steps**:
1. Check SQS queue: `aws sqs get-queue-attributes --queue-url $QUEUE_URL --attribute-names All`
2. Check dead-letter queue (if configured)
3. Verify message format:
   ```json
   {
       "event_type": "channel_archived",
       "service": "jira_reporter",
       "channel_id": "C01234567"
   }
   ```
4. Check service logs: `docker logs ketchup-jira-reporter | grep SQS`

**Common Causes**:
- Wrong `event_type` or `service` field
- Missing `KETCHUP_EVENTS_QUEUE_URL` environment variable
- SQS permissions issue (IAM role)

### 4. Archive State Consistency Issues
**Symptom**: DynamoDB `archived` field doesn't match Slack reality

**Root Cause**: Async operations between Slack API and DynamoDB

**Solution**: Always check real-time Slack status, not DynamoDB
```python
# archive_handler.py:60-68
# Don't trust DynamoDB - check Slack API
channel_info = await self.archive_ops.get_channel_info(channel_id)
is_archived = channel_data.get("is_archived", False)

if not is_archived:
    return True  # Already unarchived, no action needed
```

**Debugging**:
```bash
# Check Slack API directly
curl -X POST https://slack.com/api/conversations.info \
  -H "Authorization: Bearer $BOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"channel": "C01234567"}'
```

### 5. AI Report Generation Failures
**Symptom**: Reports contain "Not specified" for all sections

**Root Causes**:
- **No messages in channel**: Check `fetch_channel_messages` returns data
- **Token limit exceeded**: Reduce message limit (currently 500)
- **OpenAI API error**: Check Azure OpenAI quota/limits

**Debug Steps**:
1. Check message count:
   ```python
   messages = await msg_ops.fetch_channel_messages(channel_id, limit=500)
   print(f"Retrieved {len(messages)} messages")
   ```

2. Check OpenAI response:
   ```python
   # Enable debug logging
   import logging
   logging.getLogger("packages.ai").setLevel(logging.DEBUG)
   ```

3. Verify Azure OpenAI configuration:
   ```bash
   # Check environment variables
   echo $AZURE_OPENAI_API_KEY
   echo $AZURE_OPENAI_ENDPOINT
   echo $AZURE_OPENAI_DEPLOYMENT_NAME
   ```

### 6. Duplicate JIRA Comments
**Symptom**: Same report posted multiple times to CSOPM ticket

**Root Cause**: Missing or lost `jira_report_csopm_posted` flag

**Prevention** (main.py:176-199):
```python
# Check if already posted to CSOPM
csopm_posted = channel_data.get("jira_report_csopm_posted", False)

if csopm_posted:
    logger.info(f"Skipping CSOPM ticket - already posted")
    csopm_success = True
else:
    csopm_success = await jira_service.post_comment_to_ticket(...)

    if csopm_success:
        # Mark as posted
        await dynamodb_store.channel_ops.update_channel_fields(
            channel_id=channel_id,
            updates={"jira_report_csopm_posted": True}
        )
```

**Manual Fix**:
```python
# Mark channel as already posted
await dynamodb_store.update_channel_fields(
    channel_id="C01234567",
    updates={"jira_report_csopm_posted": True}
)
```

---

## Development Guidelines

### Adding New Report Sections
1. Update AI prompt in `report_generator.py:_create_report_prompt()`
2. Add new section header (e.g., `10. h3. New Section`)
3. Provide clear instructions for AI to extract data
4. Test with real channel data
5. Update JIRA wiki formatting if needed

### Modifying Retry Logic
1. Update constants in `constants.py`
2. Adjust eligibility checks in `channel_monitor.py:get_channels_needing_reports()`
3. Update retry count in `main.py:process_channel()`
4. Add tests for new retry behavior

### Changing Archive TTL
```python
# archive_handler.py:110
ttl_timestamp = int(time.time()) + 180  # Current: 3 minutes

# Considerations:
# - Longer TTL = more risk of leaving channels unarchived
# - Shorter TTL = more risk of TTL expiring during processing
# - Current 180s is tuned for typical report generation time (60-120s)
```

### Adding New JIRA Projects
```python
# Option 1: Environment variable
VALID_JIRA_PROJECTS=CSO Problem Management,CPGNREQ,CSOPM,NEW_PROJECT

# Option 2: Update jira_constants.py
VALID_JIRA_PROJECTS = [
    "CSO Problem Management",
    "CPGNREQ",
    "CSOPM",
    "NEW_PROJECT"  # Add here
]
```

### Performance Tuning
```python
# Current settings (docker-compose.yml)
CHECK_INTERVAL_MINUTES=15  # Lower = more frequent checks, higher CPU
BATCH_SIZE=5               # Higher = more parallelism, more memory
LOOKBACK_HOURS=24          # Lower = more aggressive reporting

# Trade-offs:
# - Faster polling = higher AWS costs (DynamoDB reads)
# - Larger batches = faster processing but higher memory usage
# - Shorter lookback = may report on active channels
```

---

## Metrics & Monitoring

### Key Metrics to Track
1. **Processing Rate**: Channels processed per hour
2. **Success Rate**: `successful / total_processed`
3. **CSOPM Discovery Rate**: `discovered / total_processed`
4. **SQS Processing**: Messages processed from queue
5. **Retry Rate**: Channels with `retry_count > 0`
6. **Archive Operation Time**: Time to unarchive + process + re-archive

### Log Analysis Queries
```bash
# Success rate
docker logs ketchup-jira-reporter | grep "Successfully processed" | wc -l

# Failed channels
docker logs ketchup-jira-reporter | grep "Failed to post report" | wc -l

# CSOPM discoveries
docker logs ketchup-jira-reporter | grep "Discovered CSOPM ticket" | wc -l

# Average processing time
docker logs ketchup-jira-reporter | grep "Cycle statistics" | grep -oP 'Duration: \K[0-9.]+' | awk '{sum+=$1; count++} END {print sum/count}'

# Archive cleanup events
docker logs ketchup-jira-reporter | grep "Cleaned up.*stale" | tail -10
```

### Alerting Thresholds
```yaml
# Suggested CloudWatch alarms (if migrating from file-based logging)
- metric: SuccessRate
  threshold: < 80%
  period: 1 hour

- metric: ProcessingTime
  threshold: > 300s
  period: 5 minutes

- metric: RetryRate
  threshold: > 30%
  period: 1 hour

- metric: StaleCleanupCount
  threshold: > 5
  period: 1 hour (indicates frequent crashes)
```

---

## Deployment Considerations

### Pre-Deployment Checklist
- [ ] Run `make test-jira-reporter` - all tests pass
- [ ] Run `make pylint` - no linting errors
- [ ] Verify feature flag state in `docker-compose.yml`
- [ ] Check MCP JIRA service is running: `docker ps | grep mcp-jira`
- [ ] Verify SQS queue is accessible: `aws sqs get-queue-url --queue-name ketchup-events-queue`
- [ ] Backup DynamoDB table (optional): `aws dynamodb create-backup --table-name ketchup_channel_information`

### Deployment Steps
```bash
cd infrastructure/
./deploy-ketchup.sh  # Deploys to both prod1 and prod2

# Singleton service deployment (prod1 only)
./deploy-ketchup.sh --prod1-only
```

### Post-Deployment Verification
```bash
# 1. Check service started
ssh ketchup-prod1.campaign.adobe.com
sudo docker ps | grep jira-reporter

# 2. Check health status
sudo docker exec ketchup-jira-reporter cat /tmp/jira_reporter_health
# Expected: <timestamp>:idle or <timestamp>:running

# 3. Check logs for errors
sudo docker logs --since 5m ketchup-jira-reporter | grep ERROR

# 4. Verify stale cleanup ran
sudo docker logs --since 5m ketchup-jira-reporter | grep "cleanup"

# 5. Test manual trigger (optional)
# Force a reporting cycle by temporarily lowering CHECK_INTERVAL_MINUTES
```

### Rollback Procedure
```bash
# Identify last good version
aws ecr describe-images --repository-name ketchup-jira-reporter --region eu-west-1

# Rollback
cd infrastructure/
./deploy-ketchup.sh --rollback v2.360.344  # Replace with last good version
```

---

## Future Enhancements

### Planned Improvements
1. **CloudWatch Metrics Integration**: Replace file-based health checks with CloudWatch metrics
2. **Report Templates**: Multiple report formats (executive summary, technical deep dive)
3. **Configurable AI Models**: Support for different OpenAI models (GPT-4, etc.)
4. **Batch SQS Processing**: Process multiple SQS messages in parallel
5. **Report Preview**: Generate preview in Slack before posting to JIRA
6. **Custom Report Sections**: Per-customer report section configuration

### Known Limitations
1. **500 Message Limit**: May miss context in very long incidents (OpenAI token limit)
2. **No Report Editing**: Once posted to JIRA, cannot edit (would need JIRA edit API)
3. **Single Language**: AI prompts only in English
4. **No Attachment Support**: Reports don't include Slack attachments/images
5. **Sequential Processing**: Channels processed one at a time (by design for API rate limiting)

---

## Related Documentation

- **[Parent CLAUDE.md](../CLAUDE.md)** - Shared patterns, TypedDI, deployment
- **[High-Level Architecture](../code_docs/ketchup_high_level.md)** - Complete system design
- **[TypedDI Migration Summary](../docs/TYPEDDI_MIGRATION_SUMMARY.md)** - DI system reference
- **[Ketchup App CLAUDE.md](../ketchup-app/CLAUDE.md)** - Main FastAPI service
- **[Status Updater CLAUDE.md](../ketchup_status_updater/CLAUDE.md)** - Status automation patterns

---

## Quick Reference

### Key Files
```
main.py                   - Orchestration, SQS, scheduled polling
report_generator.py       - AI report generation
jira_service.py          - MCP JIRA API
channel_monitor.py       - Eligibility checks
jira_ticket_discovery.py - Exigence/CSOPM lookup
archive_handler.py       - Archive management
constants.py             - Configuration constants
```

### Key Commands
```bash
# Testing
make test-jira-reporter-unit          # Fast unit tests
make test-jira-reporter-integration   # Integration tests (requires AWS)

# Debugging
docker logs -f ketchup-jira-reporter                     # Live logs
docker exec ketchup-jira-reporter cat /tmp/jira_reporter_health  # Health status

# Deployment
cd infrastructure/ && ./deploy-ketchup.sh --prod1-only   # Deploy singleton service
```

### Environment Variables
```yaml
CHECK_INTERVAL_MINUTES=15        # Polling frequency
LOOKBACK_HOURS=24                # Activity threshold
BATCH_SIZE=5                     # Concurrent processing
MCP_BASE_URL=http://mcp-jira:8081
KETCHUP_EVENTS_QUEUE_URL=https://sqs.eu-west-1.amazonaws.com/483013340174/ketchup-events-queue
KETCHUP_JIRA_REPORTER_FEATURE=true
```

---

**Last Updated**: 2025-11-04
**Service Version**: v2.360.344
**Codebase Stats**: 1,772 LOC (production) + ~3,440 LOC (tests)
