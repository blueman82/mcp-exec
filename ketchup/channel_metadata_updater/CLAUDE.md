# Channel Metadata Updater - CLAUDE.md

Service-specific documentation for the channel metadata updater. For shared patterns, see [parent CLAUDE.md](../CLAUDE.md).

## Service Overview

The channel metadata updater is a singleton scheduled service that scans Slack channels for incomplete metadata and uses AI to extract customer names and JIRA ticket IDs from channel conversations. Runs every 15 minutes on prod1 only.

**Key Responsibilities**:
- Scan DynamoDB for channels with missing `customer_name` or `jira_ticket`
- Fetch recent channel messages via Slack API
- Extract metadata using OpenAI (GPT-4) with structured prompts
- Update DynamoDB with extracted metadata
- Handle channel cleanup (delete records for non-existent channels)

**Metrics**:
- ~800 channels scanned per run (active channels only, skips archived)
- 15-minute execution interval
- Concurrent processing: 10 channels (configurable via `max_concurrency`)
- AI model: GPT-4 with structured JSON output enabled

## Architecture

### File Structure
```
channel_metadata_updater/
├── __init__.py                 # Package marker
├── scheduler.py               # [MAIN ENTRY POINT] Production scheduler (15-min loop)
├── async_runner.py            # Async wrapper for metadata update
├── metadata_processor.py      # Lambda-style handler + TypedDI integration
├── metadata_updater.py        # Orchestrator service (main logic)
├── channel_processor.py       # Batch processing with concurrency control
├── metadata_extractor.py      # AI extraction + JIRA parsing
├── metadata_storage.py        # DynamoDB storage operations
└── main.py                    # One-off run entry point (legacy, not used in prod)
```

**Total LOC**: ~1567 lines

### Main Entry Point

**Production**: `scheduler.py`
- Runs as Docker CMD in container
- Executes immediately on startup, then every 15 minutes
- Writes health status to `/tmp/metadata_scheduler_health`
- Writes last run timestamp to `/tmp/metadata_last_run`
- Gracefully handles SIGTERM/SIGINT for container shutdown

**One-off**: `main.py` (not used in production)
- Creates Lambda-like event structure
- Useful for manual testing/debugging

### Component Responsibilities

**metadata_updater.py** (ChannelMetadataUpdater):
- Orchestrates the entire update process
- Manages dependencies (AI handler, storage, processor)
- Initializes async components
- Handles cleanup of all client connections

**channel_processor.py** (ChannelProcessor):
- Fetches channel messages from Slack
- Manages concurrent batch processing with asyncio.TaskGroup
- Implements retry logic with exponential backoff (MAX_RETRIES from constants)
- Handles channel deletion for `channel_not_found` errors

**metadata_extractor.py** (MetadataExtractor):
- Formats messages for AI processing
- Calls OpenAI API with customer extraction prompt
- Parses AI responses to extract customer_name and jira_ticket
- Normalizes JIRA ticket formats (Slack links, Markdown, URLs → plain IDs)

**metadata_storage.py** (MetadataStorage):
- Scans for incomplete metadata (channels with "NOT YET AVAILABLE")
- Checks if channels need updates
- Stores extracted metadata in DynamoDB
- Preserves existing values if new extraction fails

**metadata_processor.py**:
- Lambda-style handler (compatible with both Lambda and Docker)
- TypedDI container initialization
- Dependency injection for all components
- Centralized session cleanup

## Environment Variables

Configured in `infrastructure/docker-compose.yml`:

### AWS Configuration
```bash
AWS_REGION=eu-west-1                           # AWS region
DYNAMODB_TABLE_NAME=ketchup_channel_information # DynamoDB table
AWS_SECRET_NAME=Ketchup_Token_Secrets          # Secrets Manager
```

### Service Configuration
```bash
LOG_LEVEL=INFO                      # Logging level
PYTHONPATH=/app                     # Python module path
MAX_CONCURRENT_REQUESTS=20          # Global concurrency limit
```

### Performance Optimizations
```bash
# Pipeline Processing (59% improvement)
USE_PIPELINE_PROCESSING=true        # Enable pipeline message fetching

# HTTP Connection Tuning (2-3% improvement)
KETCHUP_KEEPALIVE_ENABLED=true      # Enable keep-alive optimization
KETCHUP_KEEPALIVE_TIMEOUT=60        # Keep connections alive 60s (vs 15s default)
KETCHUP_DNS_CACHE_TTL=300           # Cache DNS for 5 minutes

# HTTP/2 Migration (5-8% improvement)
KETCHUP_USE_HTTPX=true              # Use httpx instead of aiohttp
KETCHUP_HTTP2_ENABLED=true          # Enable HTTP/2 multiplexing
KETCHUP_HTTPX_POOL_LIMITS=50        # Max concurrent connections

# Structured JSON Output (10-20% faster AI responses)
KETCHUP_STRUCTURED_JSON_OUTPUT=true # Enable JSON mode for AI
```

## Scanning Logic

### Channel Discovery
1. **Scan Phase**: Call `metadata_storage.scan_for_incomplete_metadata()`
   - Fetches all channel details from DynamoDB
   - Filters channels where `customer_name == "NOT YET AVAILABLE"` OR `jira_ticket == "NOT YET AVAILABLE"`
   - Skips archived channels (`archived == True`)
   - Returns list of channel IDs needing updates

2. **Batch Processing**: Call `channel_processor.process_channels_batch()`
   - Removes duplicate channel IDs
   - Creates concurrent tasks using `asyncio.TaskGroup`
   - Limits concurrency with `asyncio.Semaphore(max_concurrency=10)`
   - Tracks statistics: `{total, success, failure, skipped}`

### Metadata Extraction Pattern

**Message Fetching**:
```python
# Fetch messages with system messages included (for topic changes)
messages = await channel_msg_ops.fetch_channel_messages_collected(
    channel_id=channel_id,
    include_bot_messages=True,      # Capture automation messages
    include_system_messages=True    # Capture topic changes (often contain customer names)
)
```

**AI Extraction**:
1. Format messages: Join with newlines, chronological order (oldest first)
2. Call OpenAI with system prompt from `get_customer_name_extraction_prompt()`
3. Expected AI response format:
   ```
   Customer Name
   JIRA-TICKET-ID
   ```
4. Parse response to extract both fields

**JIRA Parsing Logic** (in `metadata_extractor.py`):
- **Slack format**: `<https://jira.corp.adobe.com/browse/CPGNTT-12345|CPGNTT-12345>` → `CPGNTT-12345`
- **Markdown format**: `[CPGNTT-12345](https://jira.corp.adobe.com/...)` → `CPGNTT-12345`
- **Plain URL**: `https://jira.corp.adobe.com/browse/CPGNTT-12345` → `CPGNTT-12345`
- **Plain ID**: `CPGNTT-12345` → `CPGNTT-12345` (uppercase)

**Storage Logic**:
- Only update if new value is NOT "NOT YET AVAILABLE"
- Preserve existing values if new extraction fails
- Skip update if metadata hasn't changed (optimization)

### Error Handling

**Channel Not Found**:
```python
# Robust check for channel_not_found and not_in_channel
error_str = str(e).lower()
error_data = getattr(e, "response_data", {})
if "channel_not_found" in error_str or "not_in_channel" in error_str:
    # Delete from DynamoDB to maintain data consistency
    await dynamodb_store.delete_channel_if_exists(channel_id)
    return []  # Return empty list, mark as success
```

**Retry Logic** (in `channel_processor.py`):
- MAX_RETRIES attempts with exponential backoff: `await asyncio.sleep(2**retry_count)`
- Applies to message fetching only
- AI extraction failures return default: `{"customer_name": "NOT YET AVAILABLE", "jira_ticket": "NOT YET AVAILABLE"}`

## TypedDI Integration

The service requires 10 protocols from the TypedDI container:

### Core Protocols
```python
from packages.core.typed_di.service_registrations.protocols.core_protocols import (
    SecretsManagerProtocol,        # Secrets Manager
    SlackConfigProtocol,            # Slack configuration
    SlackPostingHandlerProtocol,    # Message posting
    DynamoDBStoreProtocol,          # Database operations
)
```

### Slack Protocols
```python
from packages.core.typed_di.service_registrations.protocols.slack_protocols import (
    ChannelInfoOpsProtocol,         # Channel info fetching
    ChannelMembershipOpsProtocol,   # Channel membership
    SlackChannelMessageOpsProtocol, # Message fetching
)
```

### Handler Protocols
```python
from packages.core.typed_di.service_registrations.protocols.handler_protocols import (
    OpenAIHandlerProtocol,          # AI handler for extraction
)
```

### Infrastructure Protocols
```python
from packages.core.typed_di.service_registrations.protocols.infrastructure_protocols import (
    TokenTrackerProtocol,           # Token tracking for AI cost
)
```

### Operation Protocols
```python
from packages.core.typed_di.service_registrations.protocols.operation_protocols import (
    RestoreStateManagerProtocol,    # State management for operations
)
```

### Initialization Pattern
```python
# Get unified container
container = await get_unified_container()

# Resolve all dependencies
dependencies = {
    "secrets_manager": await container.aget(SecretsManagerProtocol),
    "slack_config": await container.aget(SlackConfigProtocol),
    # ... all 10 protocols
}

# Create updater with dependencies
updater = ChannelMetadataUpdater(**dependencies)
await updater.initialize()  # Async initialization for AI handler
```

**Critical**: The `ChannelMetadataUpdater` must call `await initialize()` after construction to set up the OpenAI handler.

## Health Checks

Health check script: `infrastructure/healthcheck-customer-jira-metadata-scheduler.sh`

### Health Status File
**Path**: `/tmp/metadata_scheduler_health`

**Format**: `{timestamp}:{status}`
- `timestamp`: Unix epoch seconds
- `status`: One of `starting`, `idle`, `running`, `error`, `stopped`

### Health Check Logic
1. **File Age Check**: Health file must be < 5 minutes old (MAX_AGE=300)
2. **Status Validation**:
   - `error`: Immediate failure
   - `running`: Allow up to 20 minutes (1200s) before considering stuck
   - Other statuses: Normal operation
3. **Last Run Check**: If no successful run in 25 minutes (1500s), fail
   - Schedule is 15 minutes + 10 minute buffer

### Docker Healthcheck Configuration
```yaml
healthcheck:
  test: ["CMD", "/app/scripts/healthcheck-customer-jira-metadata-scheduler.sh"]
  interval: 60s        # Check every minute
  timeout: 10s         # 10 second timeout
  retries: 3           # 3 failed checks = unhealthy
  start_period: 120s   # 2 minute grace period on startup
```

### Health Status Updates
The scheduler updates health status:
- Every 60 seconds during idle wait periods
- At start of each run (`running`)
- After successful completion (`idle`)
- On error (`error`)
- On shutdown (`stopped`)

## Deployment

### Dockerfile
**File**: `infrastructure/Dockerfile.updater`

**Build Pattern**: Multi-stage build
1. **Builder stage** (python:3.12-slim):
   - Install Rust (required for tiktoken compilation)
   - Create virtual environment at `/opt/venv`
   - Install requirements from `requirements-updater.txt`

2. **Runtime stage** (python:3.12-slim):
   - Copy virtual environment from builder
   - Copy application code: `packages/` and `channel_metadata_updater/`
   - Copy health check script
   - Set PYTHONPATH=/app

**CMD**: `["python", "/app/channel_metadata_updater/scheduler.py"]`

### Production Configuration

**Singleton Service**: Runs ONLY on prod1
- Explicitly stopped/removed on prod2 during deployment (see deploy-ketchup.sh)
- Prevents duplicate scheduled jobs and race conditions

**Container Name**: `ketchup-metadata-updater`

**Image**: `483013340174.dkr.ecr.eu-west-1.amazonaws.com/ketchup-metadata-updater:v2.360.344`

**Volumes**:
```yaml
volumes:
  - ./logs:/var/log  # Persistent logs
```

**Restart Policy**: `unless-stopped`

### Deployment Commands
From `infrastructure/` directory:

```bash
# Deploy to both servers (will stop on prod2)
./deploy-ketchup.sh

# Deploy to prod1 only
./deploy-ketchup.sh --prod1-only

# Verify deployment
./deploy-ketchup.sh --verify

# View logs
ssh ketchup-prod1.campaign.adobe.com
docker logs -f ketchup-metadata-updater
```

### Version Management
- Version auto-incremented by deploy script
- Format: `vX.XXX.XXX` (e.g., v2.360.344)
- Stored in ECR and docker-compose.yml

## Testing

### Unit Tests
**Location**: `tests/unit/channel_metadata_updater/`

**Key Test Files**:
- `test_metadata_extractor_jira_parsing.py`: JIRA ID extraction from various formats
- Other tests in `tests/unit/slack/channel_operations/test_channel_metadata*.py`

**Run Unit Tests**:
```bash
cd tests/setup
make test-unit
```

### Test Pattern Example
```python
from unittest.mock import MagicMock
from channel_metadata_updater.metadata_extractor import MetadataExtractor

def test_parse_slack_formatted_jira():
    """Test extracting ID from Slack-formatted JIRA link."""
    mock_ai_handler = MagicMock()
    extractor = MetadataExtractor(ai_handler=mock_ai_handler)
    ai_response = "Acme Corp\n<https://jira.corp.adobe.com/browse/CPGNTT-125206|CPGNTT-125206>"

    result = extractor.parse_ai_response(ai_response)

    assert result["customer_name"] == "Acme Corp"
    assert result["jira_ticket"] == "CPGNTT-125206"
```

### Integration Tests
```bash
cd tests/setup
make test-integration  # Requires AWS profile: campaign_prod_v7
```

### Code Quality
```bash
cd tests/setup
make pylint  # Run ruff, black, isort, pylint
```

**Always run before committing**:
```bash
make pylint && make test-unit
```

## Common Issues

### 1. Scanning Failures

**Symptom**: No channels found or scan returns empty list

**Causes**:
- DynamoDB connectivity issues
- AWS credentials expired
- Table name mismatch

**Debug**:
```bash
# Check container logs
docker logs ketchup-metadata-updater

# Check AWS credentials
docker exec ketchup-metadata-updater env | grep AWS

# Verify table access
aws dynamodb describe-table --table-name ketchup_channel_information \
    --profile campaign_prod_v7 --region eu-west-1
```

### 2. Metadata Update Conflicts

**Symptom**: Metadata keeps reverting to "NOT YET AVAILABLE"

**Causes**:
- AI extraction failing consistently
- Concurrent updates from other services
- Messages don't contain extractable information

**Investigation**:
```bash
# Check AI responses in logs
docker logs ketchup-metadata-updater 2>&1 | grep "parse_ai_response"

# Check OpenAI API status
curl https://status.openai.com/api/v2/status.json

# Verify channel has messages
# (Check in Slack or via API manually)
```

**Resolution**:
- Review AI extraction prompt in `packages/ai/prompts/customer_extraction.py`
- Check if messages actually contain customer/JIRA information
- Consider manual metadata entry for edge cases

### 3. Channel Not Found Errors

**Symptom**: Logs show `channel_not_found` errors

**Expected Behavior**: Service should automatically delete these channels from DynamoDB

**Verify Cleanup**:
```python
# The service should log:
"Channel {channel_id} not found. Deleting from DB."
```

**Manual Cleanup** (if automatic fails):
```python
import asyncio
from packages.db.dynamodb_store import DynamoDBStore
from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient

async def cleanup_channel(channel_id):
    client = DynamoDBAsyncClient()
    store = DynamoDBStore(client, table_name="ketchup_channel_information")
    await store.delete_channel_if_exists(channel_id)
```

### 4. High Memory Usage

**Symptom**: Container OOM killed or high memory consumption

**Causes**:
- Unclosed aiohttp sessions
- Too many concurrent channels
- Large message histories

**Investigation**:
```bash
# Check container memory
docker stats ketchup-metadata-updater

# Check session cleanup logs
docker logs ketchup-metadata-updater 2>&1 | grep "cleanup"
```

**Resolution**:
- Service includes comprehensive cleanup in `metadata_processor.py:cleanup_sessions()`
- All components implement `.cleanup()` methods
- Reduce `max_concurrency` from 10 to 5 if needed:
  ```python
  # In metadata_updater.py initialization
  max_concurrency=5  # Lower concurrency
  ```

### 5. AI Extraction Errors

**Symptom**: All metadata returns "NOT YET AVAILABLE" or "ERROR"

**Causes**:
- OpenAI API key expired/invalid
- Rate limiting
- Model unavailable
- Prompt issues

**Debug**:
```bash
# Check OpenAI handler logs
docker logs ketchup-metadata-updater 2>&1 | grep "OpenAI"

# Verify secrets
docker exec ketchup-metadata-updater python3 -c "
from packages.secrets.manager import SecretsManager
import asyncio
async def check():
    sm = SecretsManager()
    await sm.initialize()
    secrets = await sm.get_slack_secrets()
    print('OPENAI_API_KEY' in secrets)
asyncio.run(check())
"
```

**Resolution**:
- Rotate OpenAI API key in AWS Secrets Manager
- Check token usage/billing at platform.openai.com
- Verify prompt format in `metadata_extractor.py`

### 6. Scheduler Not Running

**Symptom**: Health check fails, no logs for 15+ minutes

**Causes**:
- Container crashed
- Scheduler loop exited
- Python error during initialization

**Debug**:
```bash
# Check container status
docker ps -a | grep metadata-updater

# Check recent logs
docker logs --tail 100 ketchup-metadata-updater

# Check health files
docker exec ketchup-metadata-updater cat /tmp/metadata_scheduler_health
docker exec ketchup-metadata-updater cat /tmp/metadata_last_run
```

**Resolution**:
```bash
# Restart container
docker restart ketchup-metadata-updater

# If restart fails, check for code errors and redeploy
cd /opt/ketchup/infrastructure
docker-compose pull ketchup-metadata-updater
docker-compose up -d ketchup-metadata-updater
```

### 7. JIRA Ticket Parsing Issues

**Symptom**: JIRA tickets stored incorrectly or as URLs

**Expected**: All JIRA tickets stored as plain IDs (e.g., `CPGNTT-12345`)

**Debug**:
```bash
# Check parsing logs
docker logs ketchup-metadata-updater 2>&1 | grep "parse_ai_response"
```

**Common Issues**:
- AI returning unexpected format
- Regex pattern not matching new JIRA project codes

**Resolution**:
- Review parsing logic in `metadata_extractor.py:parse_ai_response()`
- Update JIRA ID pattern if new project codes added:
  ```python
  jira_id_pattern = r"^[A-Z]{2,10}-[0-9]{1,7}(?![0-9])$"
  ```

## Performance Metrics

**Typical Run Statistics**:
```json
{
  "processed": 45,
  "successful": 42,
  "skipped": 0,
  "failed": 3
}
```

**Execution Time**: 3-8 minutes per run (depends on channel count)

**AI Cost**: ~$0.10-0.50 per run (GPT-4, varies by message volume)

**Success Rate**: >90% (failures typically channel_not_found)

## Related Documentation

- [Parent CLAUDE.md](../CLAUDE.md) - Overall Ketchup architecture
- [TypedDI Migration](../docs/TYPEDDI_MIGRATION_SUMMARY.md) - Dependency injection patterns
- [AI Prompts](../packages/ai/prompts/customer_extraction.py) - Customer extraction prompt
- [Channel Operations](../packages/slack/channel_operations/) - Slack API wrappers
