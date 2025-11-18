# CLAUDE.md - ketchup_access_request_monitor

This file provides guidance for working with the **ketchup_access_request_monitor** service.

**Parent Documentation**: See `/ketchup/CLAUDE.md` for shared infrastructure, TypedDI, and deployment patterns.

## Service Overview

The ketchup_access_request_monitor is a **polling-based health monitoring service** that monitors the Ketchup system for operational issues and sends alerts to Slack.

**Key Characteristics**:
- **LOC**: ~608 lines (single file: `monitor.py`)
- **Pattern**: Polling service with configurable intervals
- **Deployment**: Runs on both prod1 and prod2 (non-singleton)
- **Alerts**: Posts to `#ketchup-alerts` channel with cooldown logic

**Monitors**:
1. Pending access requests
2. Error rates
3. Processing times
4. Stale locks
5. System availability

## Architecture

### File Structure

```
ketchup_access_request_monitor/
├── monitor.py          # Main monitoring logic (608 LOC)
├── .gitignore         # Standard Python ignores
└── CLAUDE.md          # This file
```

### Class Structure

**`AccessRequestMonitor`** class with 11 methods:

| Method | Purpose |
|--------|---------|
| `__init__()` | Initialize with TypedDI container |
| `run()` | Main polling loop |
| `_check_health()` | Run all health checks |
| `_check_pending_requests()` | Monitor pending requests |
| `_check_error_rates()` | Track error thresholds |
| `_check_processing_times()` | Detect slow operations |
| `_check_stale_locks()` | Find abandoned locks |
| `_check_system_availability()` | Verify service health |
| `_send_alert()` | Post to Slack with cooldown |
| `_should_send_alert()` | Cooldown logic |
| `_write_health_status()` | Update health file |

### Health Check Flow

```
Monitor Start
  ↓
Wait 5 minutes
  ↓
Run Health Checks
  ├─ Pending Requests (threshold: 10)
  ├─ Error Rate (threshold: 5%)
  ├─ Processing Time (threshold: 30s)
  ├─ Stale Locks (threshold: 1 hour)
  └─ System Availability
  ↓
Alert Decision (with cooldown)
  ├─ If critical → Send immediately
  ├─ If within cooldown → Skip
  └─ If cooldown expired → Send
  ↓
Update Health File
  ↓
Loop
```

## Environment Variables

### Core Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `ACCESS_REQUEST_MONITOR_INTERVAL` | `300` | Polling interval (5 minutes) |
| `ACCESS_REQUEST_ALERT_COOLDOWN` | `3600` | Alert cooldown (1 hour) |

### AWS Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `AWS_REGION` | `eu-west-1` | AWS region |
| `DYNAMODB_TABLE_NAME` | `ketchup_channel_information` | DynamoDB table |
| `AWS_SECRET_NAME` | `Ketchup_Token_Secrets` | Secrets Manager secret |

### Performance Configuration

| Variable | Purpose |
|----------|---------|
| `LOG_LEVEL` | Logging verbosity (INFO) |
| `PYTHONPATH` | `/app` |
| `TZ` | `Europe/London` |
| `MAX_CONCURRENT_REQUESTS` | `20` |
| `KETCHUP_USE_HTTPX` | `true` (HTTP/2 support) |
| `KETCHUP_HTTP2_ENABLED` | `true` (5-8% perf gain) |
| `KETCHUP_HTTPX_POOL_LIMITS` | `50` |

## Polling Pattern

### 5-Minute Interval

```python
async def run(self):
    while True:
        await self._check_health()
        await asyncio.sleep(self.interval)
```

### Cooldown Logic

**Category-Based Cooldowns**: Each alert category has independent 1-hour cooldown:
- Pending requests
- Error rates
- Processing times
- Stale locks
- System availability

**Bypass for Critical Issues**: Critical alerts bypass cooldown period.

```python
def _should_send_alert(self, category: str) -> bool:
    last_alert_time = self.last_alerts.get(category, 0)
    elapsed = time.time() - last_alert_time
    return elapsed >= self.cooldown
```

## TypedDI Integration

### Required Protocols

1. **DynamoDBStoreProtocol** - Database operations
2. **SecretsManagerProtocol** - Credentials
3. **SlackPostingHandlerProtocol** - Alert posting
4. **ChannelInfoOpsProtocol** - Channel data
5. **ChannelOperationsProtocol** - Channel updates
6. **MetricsDataCollectorProtocol** - Metrics (optional)

### Service Resolution

```python
# In __init__
self.db_store = container.get_instance(DynamoDBStoreProtocol)
self.secrets_mgr = container.get_instance(SecretsManagerProtocol)
self.slack_poster = container.get_instance(SlackPostingHandlerProtocol)
```

### Graceful Degradation

```python
try:
    metrics = container.get_instance(MetricsDataCollectorProtocol)
except MissingDependencyError:
    logger.warning("Metrics collector unavailable")
    metrics = None
```

## Health Checks

### Health Check Script

**Location**: `/app/infrastructure/healthcheck-access-monitor.sh`

**Logic**:
1. Check if `/tmp/access_monitor_health` exists
2. Validate file age (< 8 minutes)
3. Read status from file
4. Verify status is not "error"

**File Format**: `timestamp:status`

**Valid Statuses**:
- `running` - Actively monitoring
- `idle` - Waiting between checks
- `monitoring` - Running health checks
- `error` - Failure occurred

**Thresholds**:
- **File age**: 8 minutes (5min interval + 3min buffer)
- **Check interval**: 5 minutes (300 seconds)
- **Timeout**: 10 seconds
- **Retries**: 3
- **Start period**: 60 seconds

### Status Update Pattern

```python
def _write_health_status(self, status: str):
    timestamp = int(time.time())
    with open('/tmp/access_monitor_health', 'w') as f:
        f.write(f"{timestamp}:{status}")
```

## Deployment

### Docker Image

**Dockerfile**: `infrastructure/Dockerfile.access-monitor`

**Multi-stage build**:
- Builder stage: Python 3.12-slim with gcc/g++
- Runtime stage: Minimal Python 3.12-slim

**Entry point**: `python /app/ketchup_access_request_monitor/monitor.py`

### Production Configuration

**Runs on**: Both prod1 and prod2 (non-singleton)

**Docker Compose**:
```yaml
ketchup-access-monitor:
  image: 483013340174.dkr.ecr.eu-west-1.amazonaws.com/ketchup-access-monitor:v2.360.344
  environment:
    - ACCESS_REQUEST_MONITOR_INTERVAL=300
    - ACCESS_REQUEST_ALERT_COOLDOWN=3600
    # ... (see Environment Variables section)
  volumes:
    - ./logs/access_monitor:/var/log/access_monitor
  restart: unless-stopped
  healthcheck:
    test: ["CMD", "/app/infrastructure/healthcheck-access-monitor.sh"]
    interval: 300s
    timeout: 10s
    retries: 3
    start_period: 60s
```

### Deployment Commands

```bash
# Deploy to both servers
cd infrastructure
./deploy-ketchup.sh

# Deploy to specific server
./deploy-ketchup.sh --prod1-only
./deploy-ketchup.sh --prod2-only

# Verify deployment
./deploy-ketchup.sh --verify
```

### View Logs

```bash
# On server
sudo docker logs -f ketchup-access-monitor

# Via docker-compose
sudo docker-compose -f /opt/ketchup/docker-compose.yml logs -f ketchup-access-monitor
```

## Testing

### Test Files

1. `tests/unit/test_access_monitor/test_monitor.py` - Unit tests
2. `tests/unit/test_access_monitor/test_health_checks.py` - Health logic
3. `tests/integration/test_access_monitor/` - Integration tests
4. `tests/deployment/test_access_monitor_deployment.py` - Deployment validation

### Running Tests

```bash
cd tests/setup

# Unit tests
make test-unit ARGS="-k test_access_monitor"

# All tests
make test ARGS="tests/unit/test_access_monitor tests/integration/test_access_monitor"
```

### Mocking TypedDI Container

```python
from unittest.mock import Mock

container = Mock()
container.get_instance.side_effect = lambda protocol: {
    DynamoDBStoreProtocol: mock_db_store,
    SecretsManagerProtocol: mock_secrets,
    SlackPostingHandlerProtocol: mock_slack_poster,
}[protocol]

monitor = AccessRequestMonitor(container)
```

## Common Issues

### 1. Polling Failures

**Symptoms**:
- Health checks not running
- Health file stale
- No alerts being sent

**Causes**:
- Container crashed
- TypedDI resolution failure
- AWS credentials expired

**Debug**:
```bash
# Check container status
docker ps | grep access-monitor

# Check logs
docker logs ketchup-access-monitor --tail 100

# Check health file
docker exec ketchup-access-monitor cat /tmp/access_monitor_health
```

**Resolution**:
- Restart container: `docker-compose restart ketchup-access-monitor`
- Verify AWS credentials: Check IAM role permissions
- Check TypedDI initialization in logs

### 2. Alert Delivery Failures

**Symptoms**:
- Alerts not appearing in #ketchup-alerts
- Errors in logs about Slack posting

**Causes**:
- Invalid Slack webhook/token
- Channel doesn't exist
- Bot lacks permissions
- Alert suppressed by cooldown

**Debug**:
```bash
# Check recent alert attempts
docker logs ketchup-access-monitor | grep "send_alert"

# Verify cooldown state (in-memory, check logs for "cooldown")
docker logs ketchup-access-monitor | grep "cooldown"

# Test Slack posting manually
docker exec -it ketchup-access-monitor python -c "
from packages.core.typed_di_integration import get_unified_container
container = get_unified_container()
await container.initialize_all()
slack_poster = container.get_instance(SlackPostingHandlerProtocol)
await slack_poster.post_message('#ketchup-alerts', 'Test alert')
"
```

**Resolution**:
- Verify Slack token in AWS Secrets Manager
- Check bot permissions in #ketchup-alerts
- Review cooldown logic in logs

### 3. Cooldown Tracking

**Symptoms**:
- Too many alerts for same issue
- Alerts not respecting 1-hour cooldown

**Causes**:
- In-memory state lost on container restart
- Cooldown logic bug
- Category key mismatch

**Debug**:
```bash
# Check last alert times in logs
docker logs ketchup-access-monitor | grep "last_alerts"

# Verify restart times
docker ps -a | grep access-monitor
```

**Resolution**:
- Cooldown is **in-memory only** - resets on container restart (expected)
- Consider persisting cooldown state to DynamoDB if needed
- Review category keys in `_should_send_alert()` logic

### 4. Error Rate False Positives

**Symptoms**:
- Alerts about high error rates when system is healthy
- Error rate threshold too sensitive

**Causes**:
- Metrics not up to date
- Threshold too low (5%)
- Sample size too small

**Debug**:
```bash
# Check metrics
docker exec ketchup-access-monitor python -c "
from packages.core.typed_di_integration import get_unified_container
container = get_unified_container()
await container.initialize_all()
metrics = container.get_instance(MetricsDataCollectorProtocol)
print(await metrics.get_error_rate())
"
```

**Resolution**:
- Adjust threshold in code (currently 5%)
- Increase sample size for error rate calculation
- Add minimum request count before alerting

### 5. Stale Lock Detection

**Symptoms**:
- Alerts about stale locks when no locks exist
- Lock detection not working

**Causes**:
- Lock detection is **placeholder implementation** (needs work)
- Lock table schema not finalized

**Resolution**:
- Review `_check_stale_locks()` implementation
- Implement proper lock table queries
- Define lock TTL and staleness criteria

## Quick Reference

**Polling Interval**: 5 minutes (300 seconds)
**Alert Cooldown**: 1 hour (3600 seconds)
**Health File**: `/tmp/access_monitor_health`
**Health Staleness**: 8 minutes (5min + 3min buffer)
**Deployment**: Both prod1 and prod2
**Docker Image**: `ketchup-access-monitor:v2.360.344`
**Entry Point**: `python /app/ketchup_access_request_monitor/monitor.py`

## Related Documentation

- **Parent CLAUDE.md**: `/ketchup/CLAUDE.md` - Shared infrastructure and TypedDI
- **High-Level Architecture**: `/ketchup/code_docs/ketchup_high_level.md`
- **TypedDI Migration**: `/ketchup/docs/TYPEDDI_MIGRATION_SUMMARY.md`
- **Deployment Guide**: `/ketchup/infrastructure/deploy-ketchup.sh`
