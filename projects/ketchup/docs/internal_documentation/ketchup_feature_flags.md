# Ketchup Feature Flags & Environment Variables

Complete reference for all feature flags and environment variables that control Ketchup behavior in production and development environments.

**Source of Truth**: The `infrastructure/docker-compose.yml` file is the authoritative source for all production feature flag values.

---

## Table of Contents

- [Feature Flags (Boolean Controls)](#feature-flags-boolean-controls)
- [Performance Tuning Variables](#performance-tuning-variables)
- [HTTP/2 & Connection Optimization](#http2--connection-optimization)
- [AI & Processing Variables](#ai--processing-variables)
- [Infrastructure & AWS Configuration](#infrastructure--aws-configuration)
- [Service-Specific Configuration](#service-specific-configuration)
- [How to Add a New Feature Flag](#how-to-add-a-new-feature-flag)

---

## Feature Flags (Boolean Controls)

Feature flags enable/disable functionality across Ketchup services. All flags follow a two-level hierarchy: global enable + scope-specific enable.

### Status Updater Feature

**Purpose**: Enable automated hourly status updates for tracked channels

- **Flag**: `KETCHUP_STATUS_UPDATER_FEATURE`
- **Global Enable**: `KETCHUP_STATUS_UPDATER_GLOBAL`
- **Instance Override**: `KETCHUP_STATUS_UPDATER_ENABLED` (prod1 only, singleton service)
- **Current Value**: `true`
- **Services**: ketchup-app, ketchup-status-updater
- **Details**: Enables the status updater service to run hourly background tasks that generate and post status updates to channels
- **Related PRs**: #165, #196

### JIRA Reporter Feature

**Purpose**: Enable automated JIRA ticket creation from Slack channel activity

- **Flag**: `KETCHUP_JIRA_REPORTER_FEATURE`
- **Global Enable**: `KETCHUP_JIRA_REPORTER_GLOBAL`
- **Current Value**: `true`
- **Services**: ketchup-app, ketchup-jira-reporter
- **Details**: Enables the JIRA reporter service to monitor channels for ticket-worthy activity and automatically create JIRA tickets
- **Dependencies**: MCP JIRA service (mcp-jira), Azure OpenAI for analysis
- **Related PRs**: #185, #192

### Trust Endorsement Feature

**Purpose**: Enable community-driven trust verification system

- **Flag**: `KETCHUP_TRUST_ENDORSEMENT_FEATURE`
- **Global Enable**: `KETCHUP_TRUST_ENDORSEMENT_GLOBAL`
- **Current Value**: `true`
- **Services**: ketchup-app, ketchup-status-updater, ketchup-jira-reporter
- **Details**: Enables trust endorsement buttons and tracking in interactive components
- **Added**: October 2025

### Access Request Automation Feature

**Purpose**: Enable automated access request processing and monitoring

- **Flag**: `KETCHUP_ACCESS_REQUEST_AUTOMATION_FEATURE`
- **Global Enable**: `KETCHUP_ACCESS_REQUEST_AUTOMATION_GLOBAL`
- **Current Value**: `true`
- **Services**: ketchup-app, ketchup-access-monitor
- **Details**: Enables automatic processing of access requests and the access monitor service
- **Details**: Enables automatic processing of access requests and the access monitor service
- **Related**: ketchup_access_request_monitor service

### User Join Notifications Feature

**Purpose**: Enable notifications when users join tracked channels

- **Flag**: `KETCHUP_USER_JOIN_NOTIFICATIONS_FEATURE`
- **Global Enable**: `KETCHUP_USER_JOIN_NOTIFICATIONS_GLOBAL`
- **Current Value**: `true`
- **Services**: ketchup-app
- **Details**: Enables welcome messages and join notifications for new channel members
- **Rollout**: Controlled rollout via global flag
- **Added**: October 2025

### Maintenance Detection Feature

**Purpose**: Enable detection of Adobe maintenance windows

- **Flag**: `KETCHUP_MAINTENANCE_DETECTION`
- **Current Value**: `true`
- **Services**: ketchup-app, ketchup-maintenance-fetcher
- **Details**: Enables the maintenance fetcher service to detect and alert about scheduled Adobe maintenance
- **Related**: ketchup_maintenance_fetcher service (singleton on prod1)

### CSOPM Notifier Feature

**Purpose**: Enable automated CSOPM ticket assignment notifications via Slack DMs

- **Flag**: `KETCHUP_CSOPM_NOTIFIER_ENABLED`
- **Current Value**: `true`
- **Services**: ketchup-csopm-notifier, ketchup-app (for button callbacks)
- **Details**: Enables the CSOPM notifier service to poll JIRA for CSOPM assignments and send Slack DM notifications to assignees
- **Schedule**: 08:00 and 16:00 UTC daily
- **Related Configuration**:
  - `CSOPM_JIRA_PROJECT=CSOPM` - JIRA project key
  - `CSOPM_RCA_REMINDER_DAYS=7` - Days before RCA reminder
  - `CSOPM_CLOSURE_REMINDER_DAYS=45` - Days before closure reminder
  - `CSOPM_MAX_PING_COUNT=3` - Maximum reminder pings
  - `CSOPM_SCHEDULE_TIMES=08:00,16:00` - UTC schedule times
- **Dependencies**: MCP JIRA service (mcp-jira), Slack API for DMs
- **Added**: January 2026

---

## Performance Tuning Variables

Performance optimization variables that improve throughput, latency, and resource efficiency.

### Pipeline Processing

**Purpose**: Enable parallel pipeline processing for improved throughput

- **Variable**: `USE_PIPELINE_PROCESSING`
- **Current Value**: `true`
- **Services**: ketchup-app, ketchup-status-updater, ketchup-jira-reporter, ketchup-metadata-updater
- **Performance Impact**: 59% throughput improvement proven in production (PR #198)
- **Details**: Enables 4 concurrent workers for batch operations on Slack API calls
- **Recommendation**: Always enable in production
- **Related PRs**: #198

### Structured JSON Output

**Purpose**: Enable JSON mode for AI responses (10-20% faster processing)

- **Variable**: `KETCHUP_STRUCTURED_JSON_OUTPUT`
- **Current Value**: `true`
- **Services**: ketchup-app, ketchup-status-updater, ketchup-jira-reporter
- **Performance Impact**: 10-20% faster AI response times when enabled
- **Details**: Uses Azure OpenAI's JSON mode for deterministic, structured responses
- **Added**: October 2025

---

## HTTP/2 & Connection Optimization

Variables controlling HTTP connection pooling, keep-alive, and HTTP/2 migration.

### HTTP/2 Migration (Phase 2)

**Purpose**: Enable HTTP/2 multiplexing for reduced latency

#### httpx Library

- **Variable**: `KETCHUP_USE_HTTPX`
- **Current Value**: `true`
- **Services**: All services (ketchup-app, status-updater, jira-reporter, metadata-updater, mcp-jira, access-monitor)
- **Performance Impact**: 5-8% improvement over aiohttp
- **Details**: Replaces aiohttp with httpx for HTTP/2 and multiplexing support
- **Related PR**: #201

#### HTTP/2 Enabled

- **Variable**: `KETCHUP_HTTP2_ENABLED`
- **Current Value**: `true`
- **Services**: All services
- **Details**: When httpx is enabled, activates HTTP/2 multiplexing protocol
- **Note**: Requires KETCHUP_USE_HTTPX=true to take effect

#### Connection Pool Limits

- **Variable**: `KETCHUP_HTTPX_POOL_LIMITS`
- **Current Value**: `50`
- **Services**: All services
- **Details**: Maximum concurrent connections in httpx pool
- **Tuning**: Increase for high-concurrency scenarios, decrease to limit resource usage

### Keep-Alive Tuning

**Purpose**: Optimize TCP connection reuse across requests

#### Keep-Alive Enabled

- **Variable**: `KETCHUP_KEEPALIVE_ENABLED`
- **Current Value**: `true`
- **Services**: All services
- **Performance Impact**: 2-3% improvement via connection reuse
- **Details**: Enables optimized keep-alive settings for connection pooling
- **Note**: Works alongside HTTP/2 for maximum efficiency

#### Keep-Alive Timeout

- **Variable**: `KETCHUP_KEEPALIVE_TIMEOUT`
- **Current Value**: `60` (seconds)
- **Services**: All services
- **Default**: 15 seconds
- **Details**: How long to keep TCP connections alive between requests
- **Tuning**:
  - Increase for sustained traffic workloads
  - Decrease to reduce memory usage in bursty patterns

#### DNS Cache TTL

- **Variable**: `KETCHUP_DNS_CACHE_TTL`
- **Current Value**: `300` (seconds / 5 minutes)
- **Services**: All services
- **Default**: 10 seconds
- **Details**: How long to cache DNS resolution results
- **Tuning**:
  - Increase to reduce DNS lookup overhead
  - Decrease if IP addresses change frequently

---

## AI & Processing Variables

Variables controlling Azure OpenAI integration and LLM behavior.

### Azure OpenAI Configuration

- **API Version**: `OPENAI_API_VERSION=2025-01-01-preview`
- **Endpoint**: `AZURE_OPENAI_ENDPOINT=https://ketchup-prod1.openai.azure.com/openai/deployments/gpt-4.1/chat/completions?api-version=2025-01-01-preview`
- **Model**: GPT-4.1 (with turbo mode)
- **Services**: ketchup-app, ketchup-status-updater, ketchup-jira-reporter
- **Details**: Azure OpenAI integration for intelligent channel analysis and status generation

### MCP (Model Context Protocol) Configuration

- **Base URL**: `MCP_BASE_URL=http://mcp-jira:8081`
- **Services**: ketchup-app, ketchup-status-updater, ketchup-jira-reporter
- **Details**: JIRA MCP service endpoint for ticket operations
- **Async Mode**: `KETCHUP_USE_ASYNC_MCP=true` (ketchup-jira-reporter only)

---

## Infrastructure & AWS Configuration

Variables for AWS connectivity and resource configuration.

### AWS Configuration

- **Region**: `AWS_REGION=eu-west-1`
- **Profile**: `campaign_prod_v7` (AWS CLI)
- **All Services**: Configured for eu-west-1 region

### DynamoDB Configuration

- **Table Name**: `DYNAMODB_TABLE_NAME=ketchup_channel_information`
- **Services**: All services requiring channel metadata
- **Details**: Stores channel metadata, user data, and service state

### Secrets Manager

- **Secret Name**: `AWS_SECRET_NAME=Ketchup_Token_Secrets`
- **Services**: All services
- **Contains**:
  - Slack bot tokens
  - JIRA API credentials
  - Azure OpenAI API keys
  - Third-party service credentials

### SQS Queue Configuration

- **Queue URL**: `KETCHUP_EVENTS_QUEUE_URL=https://sqs.eu-west-1.amazonaws.com/483013340174/ketchup-events-queue`
- **Services**: ketchup-app, ketchup-jira-reporter
- **Details**: Event queue for async event processing

### Container Registry (ECR)

- **Registry**: `483013340174.dkr.ecr.eu-west-1.amazonaws.com`
- **Image Naming**: `[service-name]:vX.Y.Z`
- **Example**: `483013340174.dkr.ecr.eu-west-1.amazonaws.com/ketchup-app:v2.360.347`

---

## Service-Specific Configuration

### ketchup-app (Main FastAPI Service)

```
PYTHONPATH=/app
LOG_LEVEL=INFO
MAX_CONCURRENT_REQUESTS=20
TZ=Europe/London
```

### ketchup-metadata-updater

```
PYTHONPATH=/app
LOG_LEVEL=INFO
MAX_CONCURRENT_REQUESTS=20
```

**Purpose**: Scans and updates channel metadata periodically

### ketchup-status-updater

```
PYTHONPATH=/app
LOG_LEVEL=INFO
MAX_CONCURRENT_REQUESTS=20
CHECK_INTERVAL_MINUTES=15
LOOKBACK_HOURS=24
BATCH_SIZE=5
TZ=Europe/London
```

**Purpose**: Generates and posts hourly status updates

### ketchup-jira-reporter

```
PYTHONPATH=/app
LOG_LEVEL=INFO
MAX_CONCURRENT_REQUESTS=20
CHECK_INTERVAL_MINUTES=15
LOOKBACK_HOURS=24
BATCH_SIZE=5
TZ=Europe/London
```

**Purpose**: Monitors channels and creates JIRA tickets automatically

### ketchup-access-monitor

```
PYTHONPATH=/app
LOG_LEVEL=INFO
MAX_CONCURRENT_REQUESTS=20
ACCESS_REQUEST_MONITOR_INTERVAL=300  # 5 minutes
ACCESS_REQUEST_ALERT_COOLDOWN=3600   # 1 hour
TZ=Europe/London
```

**Purpose**: Monitors and processes access requests

### ketchup-maintenance-fetcher

```
PYTHONPATH=/app
LOG_LEVEL=INFO
KETCHUP_MAINTENANCE_FETCHER_ENABLED=true
KETCHUP_MAINTENANCE_FETCHER_RUN_ON_START=true
TZ=UTC  # Note: Uses UTC unlike other services
```

**Purpose**: Detects and alerts about Adobe maintenance windows

### mcp-jira (JIRA MCP Service - Node.js)

```
PORT=8081
USE_IPAAS=true
MAX_CONCURRENT_REQUESTS=20
```

**Purpose**: Model Context Protocol service for JIRA operations

---

## How to Add a New Feature Flag

When implementing a new feature in Ketchup, follow these steps to add a feature flag:

### 1. Define the Flag in docker-compose.yml

```yaml
# In infrastructure/docker-compose.yml, add to relevant services:
ketchup-app:
  environment:
    - KETCHUP_NEW_FEATURE=true                    # Enable feature
    - KETCHUP_NEW_FEATURE_GLOBAL=true             # Global scope
    - KETCHUP_NEW_FEATURE_CHANNELS=channel1,channel2  # Optional: scope
```

### 2. Create Flag Service

Create a feature flag service in `packages/core/feature_flags/`:

```python
from packages.core.typed_di.protocols import FeatureFlagProtocol

class NewFeatureFlagService(FeatureFlagProtocol):
    def is_enabled(self, channel_id: str = None, user_id: str = None) -> bool:
        """Check if new feature is enabled"""
        # Implementation with environment variable checks
```

### 3. Register in TypedDI

Add to `packages/core/typed_di/service_registration.py`:

```python
from packages.core.feature_flags import NewFeatureFlagService

def register_services(container: TypedServiceRegistry):
    container.register(FeatureFlagProtocol, NewFeatureFlagService)
```

### 4. Use in Code

Inject and use the flag:

```python
async def handle_feature(
    flag_service: FeatureFlagProtocol,
    channel_id: str
) -> None:
    if flag_service.is_enabled(channel_id=channel_id):
        # New feature logic
        pass
```

### 5. Document the Flag

Add documentation to this file under the appropriate section

### 6. Test Both States

- Write tests for enabled state
- Write tests for disabled state
- Ensure graceful behavior when disabled

### 7. Update CLAUDE.md

Add reference in the Feature Flags section:

```markdown
### My New Feature

- **Flag**: `KETCHUP_NEW_FEATURE`
- **Global Enable**: `KETCHUP_NEW_FEATURE_GLOBAL`
- **Current Value**: `false` (controlled rollout)
- **Services**: [list services]
- **Details**: [description]
```

---

## Production Feature Flag Status (v2.360.369)

| Flag | Status | Services | Impact |
|------|--------|----------|--------|
| KETCHUP_STATUS_UPDATER_FEATURE | ✅ ENABLED | All | High |
| KETCHUP_JIRA_REPORTER_FEATURE | ✅ ENABLED | All | High |
| KETCHUP_TRUST_ENDORSEMENT_FEATURE | ✅ ENABLED | All | Medium |
| KETCHUP_ACCESS_REQUEST_AUTOMATION_FEATURE | ✅ ENABLED | All | High |
| KETCHUP_USER_JOIN_NOTIFICATIONS_FEATURE | ✅ ENABLED | All | Low |
| KETCHUP_MAINTENANCE_DETECTION | ✅ ENABLED | All | Medium |
| KETCHUP_CSOPM_NOTIFIER_ENABLED | ✅ ENABLED | csopm-notifier, app | High |
| USE_PIPELINE_PROCESSING | ✅ ENABLED | Most | High (Performance) |
| KETCHUP_USE_HTTPX | ✅ ENABLED | All | High (Performance) |
| KETCHUP_HTTP2_ENABLED | ✅ ENABLED | All | High (Performance) |
| KETCHUP_KEEPALIVE_ENABLED | ✅ ENABLED | All | Medium (Performance) |
| KETCHUP_STRUCTURED_JSON_OUTPUT | ✅ ENABLED | Most | Medium (Performance) |

---

## Testing Feature Flags Locally

To test feature flags in local development:

```bash
# Use docker-compose.local.yml with custom environment:
cd infrastructure

# Create override file with test flags
cat > docker-compose.override.yml <<EOF
version: '3.8'
services:
  ketchup-app:
    environment:
      - KETCHUP_NEW_FEATURE=false  # Test disabled
EOF

docker-compose up -d
```

---

## Performance Impact Summary (October 2025)

Combined optimizations achieved **300-400% overall improvement**:

| Phase | Optimization | Impact | PR |
|-------|---------------|--------|-----|
| Phase 1 | Pipeline processing (4 concurrent workers) | 200-300% | #198 |
| Phase 2 | HTTP/2 + httpx + keep-alive | 7-11% | #201 |
| **Total** | **Combined effect** | **300-400%** | **#198, #201** |

---

**Last Updated**: January 22, 2026
**Documentation Version**: v1.1
**Applicable to**: v2.360.369+
