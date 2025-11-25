# CLAUDE.md - Ketchup Status Updater Service

This file provides guidance to Claude Code (claude.ai/code) when working with the **ketchup_status_updater** service.

**Related Documentation**: See parent [/ketchup/CLAUDE.md](../CLAUDE.md) for shared patterns, TypedDI system, deployment workflows, and logging architecture.

---

## Service Overview

The **ketchup_status_updater** is a sophisticated scheduler service that automatically generates and posts status updates to Slack channels on an hourly basis. Unlike traditional cron-based schedulers, this service uses a Python-native async scheduler for reliable execution in Docker containers.

### Key Characteristics
- **Total Lines of Code**: ~1,600 LOC across 5 files
- **Deployment**: Singleton service (prod1 only)
- **Runtime**: Python 3.12 with asyncio
- **Execution Model**: Long-running scheduler with 55-minute intervals
- **Coordination**: Distributed locking via DynamoDB to prevent duplicate posts across servers

### Primary Functions
1. **Activity Detection**: Monitors Slack messages, thread replies, and JIRA comments
2. **AI Generation**: Uses Azure OpenAI (GPT-4) to generate contextual status updates
3. **Smart Posting**: Posts only when activity is detected (prevents spam)
4. **Multi-Stage Verification**: Re-checks activity before posting to prevent false positives
5. **Health Monitoring**: Self-monitoring with file-based health checks

---

## Architecture

### File Structure
```
ketchup_status_updater/
├── __init__.py                 # Empty init file
├── main.py                     # Entry point (117 LOC)
├── scheduler.py                # Scheduler loop (129 LOC)
├── processor.py                # Channel orchestration (351 LOC)
└── status_generator.py         # AI generation logic (1,003 LOC)
```

### Component Responsibilities

#### 1. **scheduler.py** - Scheduler Loop (129 LOC)
The primary entry point when running as a Docker container.

**Key Features**:
- Runs immediately on startup, then every 55 minutes
- Updates health status every minute during idle periods
- Graceful shutdown handling (SIGTERM, SIGINT)
- Creates health monitoring files in `/tmp/`

**Entry Point**:
```python
# Docker CMD runs this:
python /app/ketchup_status_updater/scheduler.py
```

**Main Loop**:
```python
async def start(self):
    # Run immediately on startup
    await self.run_status_update()

    # Main scheduler loop
    while self.running:
        # Wait 55 minutes (update health every minute)
        for i in range(55):
            self._update_health_status("idle")
            await asyncio.sleep(60)

        # Run status update
        await self.run_status_update()
```

#### 2. **main.py** - Entry Point (117 LOC)
Contains the core `run_auto_status()` function that orchestrates a single execution cycle.

**Key Features**:
- Initializes TypedDI container
- Acquires distributed lock (120-second timeout)
- Resolves 9-11 protocol dependencies
- Gracefully handles optional `FeatureServiceProtocol`
- Delegates to `AutoStatusProcessor`

**TypedDI Protocols Used**:
```python
# Core protocols (required)
DynamoDBStoreProtocol
SecretsManagerProtocol
SlackConfigProtocol
SlackPostingHandlerProtocol
OpenAIHandlerProtocol

# Slack protocols (required)
ChannelInfoOpsProtocol
SlackChannelMessageOpsProtocol
ChannelOperationsProtocol
ChannelMembershipOpsProtocol

# MCP protocols (required)
MCPClientProtocol

# Feature protocols (optional)
FeatureServiceProtocol  # Gracefully handled with try/except
```

**Distributed Lock**:
```python
# Use distributed lock to prevent duplicate posts across prod1/prod2
async with distributed_lock.acquire_lock("AUTO_STATUS_GLOBAL", timeout_seconds=120) as lock_acquired:
    if not lock_acquired:
        logger.warning("Another server is running auto-status, exiting")
        return

    # Process channels...
```

#### 3. **processor.py** - Channel Orchestration (351 LOC)
Handles the logic for selecting and processing channels.

**Key Features**:
- Implements 30-minute per-channel frequency check
- Supports test mode (single channel ID)
- Global vs per-channel feature flags
- Activity verification with multi-stage checks
- Attempt count tracking (skip after 5 failures)
- Timestamp precision handling (decimal → integer conversion)

**Channel Selection Logic**:
```python
# Priority order:
1. TEST_CHANNEL_ID (if set) - for debugging
2. KETCHUP_STATUS_UPDATER_GLOBAL=true - all active channels
3. Per-channel feature flags - enabled channels only
4. Fallback to TEST_CHANNEL - backward compatibility
```

**Activity Verification**:
```python
# ALWAYS check for activity first, regardless of attempt count
activity_check = await generator.check_for_activity(
    channel_id=channel_id,
    channel_config=channel
)

if not activity_check["has_activity"] and not is_first_run:
    logger.info("No activity detected, skipping status post")
    return True  # Skip posting
```

#### 4. **status_generator.py** - AI Generation (1,003 LOC)
The largest component, responsible for activity detection, AI prompt generation, and Slack posting.

**Key Features**:
- Multi-stage activity detection (Slack + JIRA)
- Incremental message fetching (only new messages since last run)
- AI prompt generation with activity indicators
- Activity source tracking (`:slack:`, `:thread:`, `:jira-logo:`)
- Trust endorsement button integration
- JIRA ticket extraction and formatting
- Previous post deletion logic

**Activity Detection**:
```python
async def check_for_activity(self, channel_id: str, channel_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns:
        - has_activity: bool (overall activity flag)
        - has_new_messages: bool (new Slack channel messages)
        - has_thread_activity: bool (new thread replies)
        - has_jira_updates: bool (new JIRA comments)
        - latest_message_ts: str (latest message timestamp)
        - latest_thread_ts: str (latest thread timestamp)
    """
```

**Activity Source Indicators**:
```python
# Activity indicators in status update header:
:slack:        # New Slack channel messages
:thread:       # New thread replies
:jira-logo:    # New JIRA comments

# Example header:
Activity source: :slack: :jira-logo:
```

---

## Two-Level Timing System

The service uses a sophisticated two-level timing system to optimize execution and respect rate limits.

### Level 1: Scheduler Interval (55 minutes)
- **Location**: `scheduler.py:89-102`
- **Purpose**: How often the scheduler wakes up to check all channels
- **Value**: 55 minutes
- **Rationale**: Slightly less than 1 hour to ensure at least hourly checks

```python
# Wait 55 minutes before next run
for i in range(55):  # 55 minutes
    if not self.running:
        break
    self._update_health_status("idle")
    await asyncio.sleep(60)  # Wait 1 minute
```

### Level 2: Per-Channel Frequency (30 minutes)
- **Location**: `processor.py:193-218`
- **Purpose**: Minimum time between status posts for a specific channel
- **Value**: 30 minutes
- **Rationale**: Prevents overwhelming channels with too-frequent updates

```python
async def _should_process_channel(self, channel: Dict[str, Any]) -> bool:
    """Check if channel is due for status update."""
    last_run = channel.get("auto_status_last_run", 0)

    # Use 30-minute frequency
    frequency_minutes = 30

    last_run_time = datetime.fromtimestamp(last_run)
    next_run_time = last_run_time + timedelta(minutes=frequency_minutes)

    return datetime.now() >= next_run_time
```

### Bypass Conditions
The 30-minute frequency is bypassed in these cases:
1. **Global Mode**: `KETCHUP_STATUS_UPDATER_GLOBAL=true` processes all channels every cycle
2. **First Run**: `auto_status_last_run == 0` triggers immediate posting
3. **Test Mode**: `TEST_CHANNEL_ID` set for debugging

---

## Environment Variables

### Production Configuration
All environment variables are defined in `infrastructure/docker-compose.yml`.

#### Core Service Control
```bash
# Enable/disable entire service on this server
KETCHUP_STATUS_UPDATER_ENABLED=true  # prod1: true, prod2: false (singleton)

# Feature flag (can disable without stopping container)
KETCHUP_STATUS_UPDATER_FEATURE=true

# Global mode (process all channels vs per-channel feature flags)
KETCHUP_STATUS_UPDATER_GLOBAL=true
```

#### Performance Tuning
```bash
# Pipeline processing (59% performance improvement)
USE_PIPELINE_PROCESSING=true

# HTTP/2 optimization (5-8% performance gain)
KETCHUP_USE_HTTPX=true
KETCHUP_HTTP2_ENABLED=true
KETCHUP_HTTPX_POOL_LIMITS=50

# Keep-alive tuning (2-3% performance gain)
KETCHUP_KEEPALIVE_ENABLED=true
KETCHUP_KEEPALIVE_TIMEOUT=60
KETCHUP_DNS_CACHE_TTL=300

# Structured JSON output (10-20% faster AI responses)
KETCHUP_STRUCTURED_JSON_OUTPUT=true

# Concurrency limits
MAX_CONCURRENT_REQUESTS=20
```

#### AWS Configuration
```bash
AWS_REGION=eu-west-1
DYNAMODB_TABLE_NAME=ketchup_channel_information
AWS_SECRET_NAME=Ketchup_Token_Secrets
```

#### AI Configuration
```bash
OPENAI_API_VERSION=2025-01-01-preview
AZURE_OPENAI_ENDPOINT=https://ketchup-prod1.openai.azure.com/openai/deployments/gpt-4.1/chat/completions?api-version=2025-01-01-preview
```

#### Feature Flags
```bash
# Trust endorsement buttons
KETCHUP_TRUST_ENDORSEMENT_FEATURE=true
KETCHUP_TRUST_ENDORSEMENT_GLOBAL=true
```

#### Logging & Runtime
```bash
LOG_LEVEL=INFO
PYTHONPATH=/app
TZ=Europe/London
```

---

## Distributed Locking

The service uses DynamoDB-based distributed locking to prevent duplicate status posts when multiple containers are running (e.g., during deployments or failover scenarios).

### Implementation Details
- **Lock Key**: `LOCK#AUTO_STATUS_GLOBAL`
- **Timeout**: 120 seconds
- **Owner ID**: UUID generated per container instance
- **TTL**: Auto-cleanup after 1 hour
- **Location**: `packages/core/distributed_lock.py`

### Lock Behavior
```python
# Lock acquisition (main.py:57-62)
async with distributed_lock.acquire_lock("AUTO_STATUS_GLOBAL", timeout_seconds=120) as lock_acquired:
    if not lock_acquired:
        logger.warning("Another server is running auto-status, exiting")
        return

    logger.info("Distributed lock acquired, proceeding with status update")
    # Process all channels...
```

### DynamoDB Lock Schema
```python
{
    "PK": "LOCK#AUTO_STATUS_GLOBAL",
    "SK": "LOCK",
    "owner_id": "uuid-of-container-instance",
    "acquired_at": 1698765432,
    "expires_at": 1698765552,  # acquired_at + 120 seconds
    "ttl": 1698769152          # expires_at + 3600 seconds
}
```

### Lock Expiry Handling
If a lock expires (120 seconds), other instances can acquire it:
```python
# Check if lock is expired (distributed_lock.py:100-130)
if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
    # Lock exists, check if expired
    existing_lock = await self._get_existing_lock(lock_key)
    if existing_lock and int(existing_lock.get("expires_at", 0)) < current_time:
        # Lock expired, delete and retry
        await self._release_lock(lock_key)
        return await self._try_acquire_lock(lock_key, timeout_seconds)
```

### Why 120 Seconds?
- Typical execution: 30-90 seconds for all channels
- Safety buffer: 30-90 seconds for edge cases
- Fail-safe: Ensures lock releases even if container crashes

---

## Multi-Stage Activity Verification

To prevent false positives on container restarts or API errors, the service uses a **two-stage activity verification** process.

### Problem
When the container restarts, timestamp fields may be stale, leading to false "activity detected" results. This caused status posts even when no actual activity occurred.

### Solution
The service performs activity checks at **two different stages**:

#### Stage 1: Initial Detection (processor.py:255-278)
Check for activity **before** deciding whether to post.

```python
# ALWAYS check for activity first, regardless of attempt count
activity_check = await generator.check_for_activity(
    channel_id=channel_id,
    channel_config=channel
)

# Update timestamps to the latest message we've seen
latest_message_ts = activity_check.get("latest_message_ts", channel.get("auto_status_last_message_ts", "0"))
latest_thread_ts = activity_check.get("latest_thread_ts", channel.get("auto_status_last_thread_ts", "0"))

# Store timestamps as integers to avoid precision mismatches
latest_message_ts_int = int(float(latest_message_ts)) if latest_message_ts != "0" else "0"
latest_thread_ts_int = int(float(latest_thread_ts)) if latest_thread_ts != "0" else "0"

await self.channel_operations.update_channel_fields(
    channel_id=channel_id,
    updates={
        "auto_status_last_message_ts": latest_message_ts_int,
        "auto_status_last_thread_ts": latest_thread_ts_int
    }
)
```

#### Stage 2: Final Re-Verification (status_generator.py:151-192)
Re-check activity using **original timestamps** to prevent race conditions.

```python
# Store original timestamps BEFORE any updates
original_last_message_ts = channel_config.get("auto_status_last_message_ts", "0")
original_last_thread_ts = channel_config.get("auto_status_last_thread_ts", "0")

# Use ORIGINAL timestamp for incremental fetching
is_first_run = original_last_message_ts == "0"
prepared_messages, channel_metadata = await message_preparer.prepare_messages_for_auto_status(
    channel_id=channel_id,
    since_ts=None if is_first_run else original_last_message_ts  # Use ORIGINAL timestamp
)
```

### Error Handling Strategy
```python
# Conservative approach on API errors (status_generator.py:110-113)
except Exception as e:
    logger.error(f"Error checking for new messages in {channel_id}: {e}")
    has_new_messages = False  # DON'T assume activity on errors
```

### First Run Handling
```python
# On first run (auto_status_last_message_ts not set), post regardless of activity
is_first_run = "auto_status_last_message_ts" not in channel

if is_first_run:
    logger.info(f"First run for channel {channel_id} - posting status regardless of activity detection")
```

---

## Health Monitoring

The service implements a dual-file health monitoring system for Docker health checks.

### Health Files

#### 1. `/tmp/scheduler_health` - Scheduler Health Status
**Format**: `<timestamp>:<status>`

**Status Values**:
- `starting` - Container initializing
- `running` - Currently processing channels
- `idle` - Waiting for next run
- `error` - Error occurred during last run
- `stopped` - Graceful shutdown

**Update Frequency**: Every minute during idle, on status changes

```python
# scheduler.py:36-41
def _update_health_status(self, status: str):
    """Update health check file with current status."""
    try:
        self.health_file.write_text(f"{int(time.time())}:{status}")
    except Exception as e:
        logger.error(f"Failed to update health status: {e}")
```

#### 2. `/tmp/last_run` - Last Successful Execution
**Format**: `<timestamp>` (integer)

**Purpose**: Tracks when the last successful execution completed

**Update**: After each successful run

```python
# scheduler.py:43-48
def _update_last_run(self):
    """Update last run timestamp for health checks."""
    try:
        self.last_run_file.write_text(str(int(time.time())))
    except Exception as e:
        logger.error(f"Failed to update last run timestamp: {e}")
```

### Health Check Script
**Location**: `infrastructure/healthcheck-public-status-message-scheduler.sh`

**Checks Performed**:
1. **Health File Exists**: `/tmp/scheduler_health` must exist
2. **Health Freshness**: Updated within last 5 minutes (300 seconds)
3. **Status Not Error**: Status field is not `error`
4. **Last Run Exists**: `/tmp/last_run` exists (after grace period)
5. **Last Run Recency**: Last run within 70 minutes (4200 seconds)

**Thresholds**:
```bash
# Health status staleness
MAX_HEALTH_AGE=300       # 5 minutes

# Last run staleness
MAX_RUN_AGE=4200         # 70 minutes (55-min interval + 15-min buffer)

# Startup grace period
GRACE_PERIOD=900         # 15 minutes
```

**Example Health Check**:
```bash
#!/bin/bash
# Check health status is recent (within 5 minutes)
current_time=$(date +%s)
health_age=$((current_time - health_time))

if [ $health_age -gt 300 ]; then
    echo "ERROR: Health status is stale (${health_age} seconds old)"
    exit 1
fi

# Check last run was recent (within 70 minutes)
run_age=$((current_time - last_run))
if [ $run_age -gt 4200 ]; then
    echo "ERROR: Last run was ${run_age} seconds ago (threshold: 4200 seconds)"
    exit 1
fi
```

### Monitoring Best Practices
- **Health File**: Indicates scheduler loop is alive
- **Last Run**: Indicates successful executions are occurring
- **Grace Period**: 15 minutes after startup before enforcing last_run checks
- **Buffer**: 70-minute threshold accounts for 55-minute interval + processing time

---

## TypedDI Integration

The service uses the repository's modern TypedDI dependency injection system. All dependencies are resolved via protocol interfaces.

### Protocol Dependencies

#### Required Protocols (9)
```python
# Core protocols (packages/core/typed_di/protocols.py)
DynamoDBStoreProtocol           # Database operations
SecretsManagerProtocol          # AWS Secrets Manager
SlackConfigProtocol             # Slack configuration
SlackPostingHandlerProtocol     # Posting to Slack

# Handler protocols
OpenAIHandlerProtocol           # Azure OpenAI API calls

# Slack protocols
ChannelInfoOpsProtocol          # Channel metadata
SlackChannelMessageOpsProtocol  # Message retrieval
ChannelOperationsProtocol       # Channel CRUD operations
ChannelMembershipOpsProtocol    # Bot membership checks

# MCP protocols
MCPClientProtocol               # JIRA MCP integration
```

#### Optional Protocols (1)
```python
# Feature protocols (gracefully handled)
FeatureServiceProtocol          # Per-channel feature flags
```

### Graceful Degradation
The service handles missing optional dependencies gracefully:

```python
# main.py:76-83
feature_service = None
if FeatureFlags.is_status_updater_enabled():
    try:
        feature_service = await container.aget(FeatureServiceProtocol)
    except MissingDependencyError:
        logger.info("Feature service not available - using default settings")
    except Exception as e:
        logger.warning(f"Could not get feature_service: {e}")
```

### Container Initialization
```python
# main.py:48-54
# Initialize DI container first (needed for distributed lock)
logger.info("Initializing DI container...")
container = await get_unified_container()

# Get DynamoDB store using TypedDI
db_store = await container.aget(DynamoDBStoreProtocol)
distributed_lock = DistributedLock(db_store.client, db_store.table_name)
```

### Dependency Injection Flow
```
scheduler.py
    ↓
main.py::run_auto_status()
    ↓
get_unified_container()  # Initialize TypedDI
    ↓
container.aget(Protocol)  # Resolve dependencies
    ↓
AutoStatusProcessor(dependencies)
    ↓
AutoStatusGenerator(dependencies)
```

---

## Activity Source Tracking

The service tracks activity from **three independent sources**: Slack messages, thread replies, and JIRA comments. Each source is tracked separately to provide granular activity indicators.

### Activity Sources

#### 1. Slack Channel Messages (`:slack:`)
- **Tracked Field**: `auto_status_last_message_ts`
- **Detection**: New messages in the channel (not threads)
- **Indicator**: `:slack:` emoji in status header
- **Logic**: `status_generator.py:68-100`

```python
has_new_messages = metadata.get("has_channel_messages", False)
latest_message_ts = metadata.get("latest_ts", last_message_ts)
```

#### 2. Thread Replies (`:thread:`)
- **Tracked Field**: `auto_status_last_thread_ts`
- **Detection**: New replies in existing threads
- **Indicator**: `:thread:` emoji in status header
- **Logic**: `status_generator.py:91-98`

```python
has_thread_activity = metadata.get("has_thread_activity", False)
_, latest_thread_ts, _ = await self.channel_msg_ops.check_recent_thread_activity(
    channel_id, last_thread_ts
)
```

#### 3. JIRA Comments (`:jira-logo:`)
- **Tracked Field**: `auto_status_last_jira_comment_ts`
- **Detection**: New comments on associated JIRA ticket
- **Indicator**: `:jira-logo:` emoji in status header
- **Logic**: `status_generator.py:116-128`

```python
if jira_ticket and jira_ticket != "NOT YET AVAILABLE" and last_jira_comment_ts != "0":
    latest_jira_ts = await self._get_latest_jira_comment_timestamp(jira_ticket)
    if latest_jira_ts and latest_jira_ts > last_jira_comment_ts:
        has_jira_updates = True
```

### Combined Activity Check
```python
# status_generator.py:130-137
return {
    "has_activity": has_new_messages or has_thread_activity or has_jira_updates,
    "has_new_messages": has_new_messages,
    "has_thread_activity": has_thread_activity,
    "has_jira_updates": has_jira_updates,
    "latest_message_ts": latest_message_ts,
    "latest_thread_ts": latest_thread_ts
}
```

### Status Update Header
The header shows which sources triggered the update:

```
*Ketchup Automated Status Update*
Channel: #channel-name
Activity source: :slack: :thread: :jira-logo:
Status checked hourly: Updates posted only when activity detected
Note: This automated status update is a test feature and may not be final.
────────────────────────────────────────────
```

**Examples**:
- `Activity source: :slack:` - Only new channel messages
- `Activity source: :thread:` - Only new thread replies
- `Activity source: :jira-logo:` - Only new JIRA comments
- `Activity source: :slack: :jira-logo:` - Both Slack and JIRA activity

---

## Trust Endorsement

The service integrates with the Trust Endorsement feature to allow users to "trust" automated status updates.

### Implementation
When posting status updates, the service includes a "Trust this update?" button with interactive block actions.

**Location**: `status_generator.py:520-564`

```python
# Add trust endorsement button if feature is enabled
if FeatureFlags.is_trust_endorsement_enabled():
    blocks = orjson.loads(content)  # Parse existing blocks

    # Add trust endorsement block
    blocks.append({
        "type": "actions",
        "block_id": f"trust_endorsement_{status_update_id}",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "✓ Trust this update?"},
                "value": f"trust_{channel_id}_{status_update_id}",
                "action_id": "trust_endorsement_button"
            }
        ]
    })

    content = orjson.dumps(blocks)
```

### Metadata Storage
After posting, the service stores metadata about the status update:

```python
# Store metadata in DynamoDB
metadata = {
    "channel_id": channel_id,
    "message_ts": response["ts"],
    "status_update_id": status_update_id,
    "posted_at": int(datetime.now(timezone.utc).timestamp()),
    "trust_count": 0  # Initialize trust count
}

await self.db_store.put_item({
    "PK": f"STATUS_UPDATE#{channel_id}",
    "SK": f"UPDATE#{status_update_id}",
    **metadata
})
```

### Feature Flags
```bash
# Global feature flag (docker-compose.yml)
KETCHUP_TRUST_ENDORSEMENT_FEATURE=true
KETCHUP_TRUST_ENDORSEMENT_GLOBAL=true
```

### Trust Endorsement Flow
```
1. Status update posted with "Trust this update?" button
2. User clicks button → Slack sends interaction payload
3. FastAPI webhook handler receives payload
4. Trust count incremented in DynamoDB
5. Button text updates: "✓ Trust this update? (3)"
```

---

## Timestamp Precision Handling

One of the most subtle bugs in the service was timestamp precision mismatches between DynamoDB storage and Slack API comparisons. This caused status updates to be posted even when no new activity occurred.

### The Problem
1. **Slack API**: Returns message timestamps as strings like `"1698765432.123456"` (decimal)
2. **DynamoDB Storage**: Stored as strings like `"1698765432"` (integer) or `"1698765432.123456"` (decimal)
3. **Comparison Logic**: Used string/numeric comparison, which failed when precision differed

**Example Bug**:
```python
# Stored in DB (integer)
last_message_ts = "1698765432"

# Slack API returns (decimal)
latest_message_ts = "1698765432.000000"

# String comparison
if latest_message_ts > last_message_ts:
    # ALWAYS TRUE because "1698765432.000000" > "1698765432"
    has_activity = True  # FALSE POSITIVE!
```

### The Solution
Convert all timestamps to **integers** before storing in DynamoDB. This eliminates precision mismatches.

**Implementation** (processor.py:266-277):
```python
# Store timestamps as integers to avoid precision mismatches with Slack API
# This fixes the issue where decimal timestamps aren't properly compared with integer message timestamps
latest_message_ts_int = int(float(latest_message_ts)) if latest_message_ts != "0" else "0"
latest_thread_ts_int = int(float(latest_thread_ts)) if latest_thread_ts != "0" else "0"

logger.info(f"Updating timestamps for {channel_id} - message: {latest_message_ts} -> {latest_message_ts_int}, thread: {latest_thread_ts} -> {latest_thread_ts_int}")

await self.channel_operations.update_channel_fields(
    channel_id=channel_id,
    updates={
        "auto_status_last_message_ts": latest_message_ts_int,
        "auto_status_last_thread_ts": latest_thread_ts_int
    }
)
```

### 5-Second Buffer
In some cases, a 5-second buffer is used to account for clock skew between systems:

```python
# Add 5-second buffer to account for clock skew
since_ts = str(int(float(last_message_ts)) + 5) if last_message_ts != "0" else None
```

### Timestamp Storage Best Practices
1. **Always convert to integer**: `int(float(timestamp_str))`
2. **Handle "0" sentinel**: Check for `"0"` before conversion
3. **Log conversions**: Log before/after to debug issues
4. **Consistent format**: Use integers throughout the pipeline

---

## Testing

The service has comprehensive unit tests covering all major functionality.

### Test Files
```
tests/unit/test_ketchup_status_updater/
├── __init__.py
├── conftest.py                            # Shared fixtures
├── test_auto_status_delete_failure.py     # Previous post deletion
├── test_auto_status_prompt.py             # AI prompt generation
├── test_new_channel_verification.py       # First-run behavior
├── test_processor_dynamic_channels.py     # Channel selection logic
├── test_processor.py                      # Processor orchestration
├── test_status_generator_backup.py        # Backup tests
├── test_status_generator.py               # Main generator tests
└── test_thread_classification_indicators.py  # Activity classification
```

**Total Test Files**: 11 (including conftest.py)

### Running Tests

#### Unit Tests (Preferred)
```bash
cd tests/setup/
make test-unit
```

#### Specific Test Module
```bash
cd tests/setup/
pytest ../unit/test_ketchup_status_updater/test_processor.py -v
```

#### Test with Coverage
```bash
cd tests/setup/
pytest ../unit/test_ketchup_status_updater/ --cov=ketchup_status_updater --cov-report=term-missing
```

### Key Test Scenarios

#### 1. Activity Detection Tests
- **File**: `test_status_generator.py`
- **Coverage**: Slack messages, thread replies, JIRA comments
- **Edge Cases**: Container restart, API errors, timestamp precision

#### 2. Channel Processing Tests
- **File**: `test_processor.py`
- **Coverage**: Frequency checks, attempt counts, global mode
- **Edge Cases**: First run, 5-failure threshold, membership checks

#### 3. Thread Classification Tests
- **File**: `test_thread_classification_indicators.py`
- **Coverage**: Channel messages vs thread replies
- **Edge Cases**: Mixed activity, thread-only activity

#### 4. Previous Post Deletion Tests
- **File**: `test_auto_status_delete_failure.py`
- **Coverage**: Deleting previous status posts
- **Edge Cases**: Missing timestamp, API failures

#### 5. First-Run Verification Tests
- **File**: `test_new_channel_verification.py`
- **Coverage**: New channel initialization
- **Edge Cases**: Missing timestamps, empty activity

### Mock Dependencies
Tests use mocked TypedDI dependencies:

```python
# conftest.py
@pytest.fixture
def mock_db_store():
    mock = AsyncMock()
    mock.get_item = AsyncMock(return_value=None)
    mock.put_item = AsyncMock()
    return mock

@pytest.fixture
def mock_openai_handler():
    mock = AsyncMock()
    mock.execute_prompt = AsyncMock(return_value="Generated status content")
    return mock
```

### Test Best Practices
1. **Always mock external services**: Slack API, OpenAI, DynamoDB
2. **Test edge cases**: Container restart, API errors, missing data
3. **Verify logging**: Check log messages for debugging
4. **Use realistic data**: Real channel IDs, message timestamps
5. **Test activity indicators**: Verify `:slack:`, `:thread:`, `:jira-logo:` appear correctly

---

## Common Issues

### 1. Distributed Lock Timeout

**Symptom**: Logs show "Another server is running auto-status, exiting" repeatedly

**Cause**: Lock is held by another instance or expired lock wasn't cleaned up

**Solution**:
```python
# Check DynamoDB for stale locks
# PK = "LOCK#AUTO_STATUS_GLOBAL", SK = "LOCK"
# Delete if expires_at < current_time
```

**Prevention**: Ensure 120-second timeout is sufficient for processing all channels

---

### 2. Health File Staleness

**Symptom**: Docker health check fails with "Health status is stale"

**Cause**: Scheduler loop stopped updating `/tmp/scheduler_health`

**Debug Steps**:
```bash
# SSH to server
ssh ketchup-prod1.campaign.adobe.com

# Check health file
sudo docker exec ketchup-status-updater cat /tmp/scheduler_health
# Output: 1698765432:idle

# Check if timestamp is recent
date +%s  # Compare with health file timestamp
```

**Solution**: Restart the container
```bash
sudo docker-compose -f /opt/ketchup/docker-compose.yml restart ketchup-status-updater
```

---

### 3. Timestamp Precision Mismatches

**Symptom**: Status updates posted even when no activity occurred

**Cause**: Decimal vs integer timestamp comparison issues

**Debug Steps**:
```python
# Check stored timestamps in DynamoDB
# Look for decimal values like "1698765432.123456"
# Should be integers like "1698765432"
```

**Solution**: Timestamps are now converted to integers before storage (processor.py:266-277)

**Verification**:
```python
# Logs should show conversion
logger.info(f"Updating timestamps for {channel_id} - message: {latest_message_ts} -> {latest_message_ts_int}")
```

---

### 4. Container Restart False Positives

**Symptom**: Status updates posted immediately after container restart, even with no activity

**Cause**: Stale timestamps from before restart make activity checks return true

**Solution**: Multi-stage verification (see "Multi-Stage Activity Verification" section)

**Debug Steps**:
```python
# Check activity detection logs
# Should see: "Error checking for new messages" → has_new_messages = False
# Conservative approach prevents false positives
```

**Prevention**: Always use `original_last_message_ts` for incremental fetching (status_generator.py:176-180)

---

### 5. Feature Service Not Available

**Symptom**: Logs show "Feature service not available - using default settings"

**Cause**: `FeatureServiceProtocol` is optional and not registered in TypedDI

**Solution**: This is expected behavior. Service falls back to `TEST_CHANNEL` mode.

**Verification**:
```python
# main.py:76-83
feature_service = None
try:
    feature_service = await container.aget(FeatureServiceProtocol)
except MissingDependencyError:
    logger.info("Feature service not available - using default settings")
```

**Workaround**: Use `KETCHUP_STATUS_UPDATER_GLOBAL=true` to process all channels

---

### 6. AI Generation Failures

**Symptom**: Status updates fail with AI-related errors

**Cause**: Azure OpenAI API errors, rate limits, or network issues

**Debug Steps**:
```python
# Check OpenAI logs
# Look for "Error generating status with AI"
# Check Azure OpenAI endpoint health
```

**Solution**: Implement retry logic and fallback content

**Verification**:
```python
# status_generator.py:183-191
except Exception as e:
    logger.error(f"Error preparing messages: {e}")
    prepared_messages = "Error fetching messages"
    channel_metadata = {
        "latest_ts": original_last_message_ts,
        "has_thread_activity": False,
        "has_channel_messages": False
    }
```

---

### 7. Channel Membership Check Failures

**Symptom**: Channels skipped with "Bot not member of channel"

**Cause**: Bot was removed from channel or membership check failed

**Debug Steps**:
```python
# Check logs for membership warnings
# processor.py:233-240
try:
    all_channels = await self.channel_membership_ops.lookup_membership_of_channels()
    if channel_id not in [ch['id'] for ch in all_channels]:
        logger.warning(f"Bot not member of channel {channel_id}, skipping")
        return False
except Exception as e:
    logger.warning(f"Could not check channel membership for {channel_id}: {e}")
```

**Solution**: Re-invite bot to channel or fix membership check logic

---

### 8. Attempt Count Threshold Exceeded

**Symptom**: Logs show "Channel has 5 failed attempts, skipping status generation"

**Cause**: Channel failed 5 consecutive times, circuit breaker activated

**Debug Steps**:
```python
# Check DynamoDB for attempt count
# Field: "auto_status_attempt_count"
# Should reset to 0 on successful run
```

**Solution**: Reset attempt count manually or fix underlying issue
```python
# processor.py:301-316
if attempt_count >= 5:
    logger.warning(f"Channel has {attempt_count} failed attempts. Skipping status generation")
    # Update last run but DON'T increment attempt count
    await self.channel_operations.update_channel_fields(
        channel_id=channel_id,
        updates={"auto_status_last_run": int(time.time())}
    )
    return True
```

---

## Debugging Tips

### 1. Enable Test Mode
Set `TEST_CHANNEL_ID` in `processor.py` to process only one channel:

```python
# processor.py:21
TEST_CHANNEL_ID = "C07ABCD1234"  # Your test channel ID
```

### 2. Check Scheduler Health
```bash
# SSH to server
ssh ketchup-prod1.campaign.adobe.com

# Check health file
sudo docker exec ketchup-status-updater cat /tmp/scheduler_health

# Check last run
sudo docker exec ketchup-status-updater cat /tmp/last_run
```

### 3. View Logs
```bash
# Via Docker
sudo docker logs -f ketchup-status-updater

# Via Log Viewer (recommended)
cd ketchup-log-viewer
npm run dev
# Navigate to http://localhost:3000
```

### 4. Check Distributed Lock
```python
# Query DynamoDB for active locks
import boto3
dynamodb = boto3.client('dynamodb', region_name='eu-west-1')
response = dynamodb.get_item(
    TableName='ketchup_channel_information',
    Key={
        'PK': {'S': 'LOCK#AUTO_STATUS_GLOBAL'},
        'SK': {'S': 'LOCK'}
    }
)
print(response)
```

### 5. Verify Timestamps
```python
# Check channel timestamps in DynamoDB
# PK = "CHANNEL#C07ABCD1234"
# Fields to check:
# - auto_status_last_run
# - auto_status_last_message_ts
# - auto_status_last_thread_ts
# - auto_status_last_jira_comment_ts
# - auto_status_attempt_count
```

### 6. Test Activity Detection Locally
```python
# Run activity check in isolation
from ketchup_status_updater.status_generator import AutoStatusGenerator

generator = AutoStatusGenerator(...)
activity_check = await generator.check_for_activity(
    channel_id="C07ABCD1234",
    channel_config=channel
)
print(activity_check)
```

---

## Code Standards

Follow the repository's code standards (see parent [CLAUDE.md](../CLAUDE.md)):

### Import Order
```python
# Standard library
import asyncio
import os
from datetime import datetime

# Third-party packages
import orjson
from botocore.exceptions import ClientError

# Local/project imports
from packages.core.logging import setup_logger
from packages.core.typed_di.protocols import DynamoDBStoreProtocol
```

### Logging
```python
# Use structured logging
logger.info(f"Processing channel {channel_id} ({channel_name})")
logger.error(f"Failed to process channel {channel_id}: {e}", exc_info=True)
```

### Async/Await
```python
# Always use await for async operations
result = await self.channel_msg_ops.get_messages(channel_id)

# Use async context managers for resources
async with distributed_lock.acquire_lock("AUTO_STATUS_GLOBAL", timeout_seconds=120) as lock_acquired:
    # Process...
```

### Error Handling
```python
# Be specific with exceptions
try:
    result = await risky_operation()
except ClientError as e:
    logger.error(f"DynamoDB error: {e}")
    raise
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    return False
```

---

## Deployment

The ketchup_status_updater service is deployed as part of the Ketchup monorepo deployment process.

### Docker Image
- **Base Image**: `python:3.12-slim`
- **Build Type**: Multi-stage build
- **Dockerfile**: `infrastructure/Dockerfile.status-updater`
- **ECR Repository**: `483013340174.dkr.ecr.eu-west-1.amazonaws.com/ketchup-status-updater`

### Deployment Commands
```bash
# Deploy to both servers (only runs on prod1)
cd infrastructure/
./deploy-ketchup.sh

# Deploy to prod1 only
./deploy-ketchup.sh --prod1-only

# Verify deployment
./deploy-ketchup.sh --verify

# Rollback to previous version
./deploy-ketchup.sh --rollback v2.360.343
```

### Singleton Service
The status updater is a **singleton service** that runs **only on prod1**:

```yaml
# docker-compose.yml (prod1)
ketchup-status-updater:
  image: ...:v2.360.344
  environment:
    - KETCHUP_STATUS_UPDATER_ENABLED=true  # prod1 only

# docker-compose.yml (prod2)
# ketchup-status-updater container is NOT present
```

**Reason**: Prevents duplicate status posts across servers. Distributed locking provides additional safety.

### Deployment Verification
```bash
# Check container is running
ssh ketchup-prod1.campaign.adobe.com
sudo docker ps | grep status-updater

# Check logs
sudo docker logs -f ketchup-status-updater

# Check health
sudo docker exec ketchup-status-updater /scripts/healthcheck-public-status-message-scheduler.sh
echo $?  # Should be 0
```

---

## Related Documentation

- **[Parent CLAUDE.md](../CLAUDE.md)** - Shared patterns, TypedDI, deployment, logging
- **[High-Level Architecture](../code_docs/ketchup_high_level.md)** - System design and event flow
- **[TypedDI Migration Summary](../docs/TYPEDDI_MIGRATION_SUMMARY.md)** - Modern DI system architecture
- **[Code Walkthrough](../code_docs/ketchup_code_walkthrough_documentation.md)** - Component-by-component reference

---

## Investigation Findings

This documentation is based on an agent investigation that found:
- **Custom scheduler**: Replaced cron with Python-native async scheduler (scheduler.py)
- **Distributed locking**: DynamoDB-based locking to prevent duplicate posts
- **Multi-stage verification**: Two-stage activity checks to prevent false positives on container restart
- **Activity source indicators**: Separate tracking for Slack messages, thread replies, JIRA comments
- **Timestamp precision fixes**: Integer conversion to avoid decimal vs integer comparison bugs
- **Sophisticated health monitoring**: Dual-file system with 5-minute and 70-minute thresholds

**Service Maturity**: Production-ready with comprehensive error handling, health monitoring, and distributed coordination.
