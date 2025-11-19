# JIRA PAT Rotation System - Comprehensive Documentation

## Table of Contents

1. [Quick Start for On-Call Engineers](#quick-start-for-on-call-engineers)
2. [Why PAT Rotation Exists](#why-pat-rotation-exists)
3. [System Architecture Overview](#system-architecture-overview)
4. [Happy Path: How Successful Rotation Works](#happy-path-how-successful-rotation-works)
5. [Failure Modes and Error Recovery](#failure-modes-and-error-recovery)
6. [Backup PAT Management Strategy](#backup-pat-management-strategy)
7. [Alerting Mechanism](#alerting-mechanism)
8. [Metrics Collection and Health Tracking](#metrics-collection-and-health-tracking)
9. [Integration with Ketchup Services](#integration-with-ketchup-services)
10. [Troubleshooting Guide](#troubleshooting-guide)
11. [Configuration Reference](#configuration-reference)
12. [Code Reference Map](#code-reference-map)

## Quick Start for On-Call Engineers

If you get an alert about JIRA PAT rotation failure, here's what to do:

**Alert comes in**: Check #ketchup-alerts for PAT rotation failure message

**What it means**: The system tried to rotate the JIRA authentication token and failed, but the old token is still active (system is safe)

**What to check**:
1. Is the old PAT still valid? Check AWS Secrets Manager `Ketchup_Token_Secrets` for `ketchup_jira_pat` and `ketchup_jira_pat_expiry`
2. When does it expire? Compare `ketchup_jira_pat_expiry` to today's date
3. How long until expiry? If more than 14 days left, you have time to investigate
4. Check rotation logs: SSH to prod1 and check `/tmp/jira_pat_rotator_health` file

**Quick fix options**:
- **If error is temporary (network, timeout)**: Wait 24 hours for next rotation attempt
- **If error is critical (no valid PAT)**: Create new PAT manually via iPaaS console, update secrets
- **If rotation keeps failing**: Escalate to platform team, may be AWS Secrets Manager access issue

## Why PAT Rotation Exists

JIRA is deprecating Basic Authentication (username/password) on November 30, 2025. The system needs to use Personal Access Tokens (PATs) instead.

**Key constraints**:
- PATs have maximum 90-day expiry (mandatory, cannot be extended)
- Each token must be rotated before it expires
- Failed rotations must not break JIRA access (fallback mechanism required)
- Rotations must not require manual intervention
- Operations team must be notified if automated rotation fails

**Timeline**: We need PAT rotation working before November 30, 2025

## System Architecture Overview

The JIRA PAT rotation system consists of four main components:

### 1. Configuration & Validation Layer (TypeScript/Node.js)

**Location**: `ketchup/corp_jira_mcp/corp_jira_mcp/common/`

**Files**:
- `config.ts` (lines 7-24): Defines `JiraAuthConfig` interface with primary and backup PAT fields
- `pat-validation.ts` (lines 3-61): Provides format validation, expiry checking, and decision logic
- `env-aws.ts` (lines 29-39): Maps AWS Secrets Manager keys to environment variables

**Responsibilities**:
- Load PAT configuration from environment variables
- Validate PAT format (alphanumeric, hyphens, underscores)
- Check PAT expiry dates
- Decide whether to use backup PAT (multi-factor logic)

**Key interfaces**:
```typescript
interface JiraAuthConfig {
  pat?: string;                    // Primary PAT token
  patExpiry?: Date;                // When primary expires
  usePat?: boolean;                // Feature flag for PAT auth
  backupPat?: string;              // Fallback token
  backupPatExpiry?: Date;          // When backup expires
  useBackupPat?: boolean;          // Explicitly use backup
  backupPatCreatedAt?: Date;       // When backup was created
}
```

### 2. Authentication & Request Layer (TypeScript/Node.js)

**Location**: `ketchup/corp_jira_mcp/corp_jira_mcp/utils.ts`

**Key functions**:
- `buildUrl()` (lines 44-55): Constructs JIRA API endpoint URLs
- `jiraRequest()` (lines 158-272): Main HTTP request function with three authentication modes
- `verifyAuthentication()` (lines 113-116): Tests auth with JIRA `/myself` endpoint

**Authentication modes**:
1. **iPaaS Mode** (lines 165-199): Sends request through Adobe's iPaaS proxy with IMS token
2. **Direct JIRA** (lines 200-216): Direct Basic Auth (currently deprecated, to be removed)
3. **Token Fallback** (future): Automatic fallback to backup PAT if primary expired

**Request error handling** (lines 265-271):
- Network errors are caught and logged
- HTTP errors are extracted from response
- Unknown errors are wrapped with context

### 3. MCP Operations (TypeScript/Node.js)

**Location**: `ketchup/corp_jira_mcp/corp_jira_mcp/operations/`

**Core rotation operations** (planned Phase 1):
- `createPAT.ts`: Creates new JIRA PAT via iPaaS proxy, returns token + 90-day expiry
- `revokePAT.ts`: Revokes/deletes old PAT by token ID
- `validatePAT.ts`: Tests if PAT token works by attempting authentication
- `listPATs.ts`: Lists all active PATs (useful for debugging)

**Existing operations** (9 files): Standard JIRA operations (search, create, update, etc.) that use the core authentication layer

### 4. Rotation Service (Python, Phase 1 planned)

**Location** (planned): `ketchup/ketchup_jira_pat_rotator/`

**Key components** (Phase 1 Tasks 11-14):
- `scheduler.py`: Runs rotation check every 24 hours, updates health file every minute
- `pat_monitor.py`: Checks if PAT is within 75 days of expiry
- `rotator.py`: Orchestrates safe rotation flow with distributed locking
- `main.py`: Entry point, service initialization, async scheduler startup

**Key characteristics**:
- Single instance only (runs on prod1, like `ketchup_status_updater`)
- Uses DynamoDB for distributed locking (prevents concurrent rotations)
- Sends alerts to #ketchup-alerts on success/failure
- Non-blocking on failures (keeps old PAT active)

## Happy Path: How Successful Rotation Works

### Step-by-Step Flow

```
24-hour scheduler triggers
    ↓
1. Check if rotation needed (PAT > 75 days to expiry?)
    ↓
2. Try to acquire distributed lock (DynamoDB)
    ↓
3. Create new PAT via MCP (returns token + 90-day expiry)
    ↓
4. Validate new PAT works (test against JIRA API)
    ↓
5. Update AWS Secrets Manager with new PAT
    ↓
6. Update backup PAT fields (move current backup to history)
    ↓
7. Revoke old PAT via MCP
    ↓
8. Release distributed lock
    ↓
9. Send success alert to #ketchup-alerts
    ↓
Sleep 24 hours, repeat
```

### Timeline Example

**Day 1**: System initializes, scheduler starts
- First rotation check happens immediately on startup
- Current PAT is valid for 85 days (created 5 days ago)
- No rotation needed, next check in 24 hours

**Day 8**: Second rotation check (24 hours later)
- Current PAT now valid for 78 days remaining
- Still above 75-day threshold, no rotation yet
- Next check in 24 hours

**Day 9**: Third rotation check
- Current PAT now valid for 77 days remaining
- Still above threshold... but let's fast forward

**Day 16**: Tenth rotation check
- Current PAT now valid for 70 days remaining
- Below 75-day threshold! Rotation needed
- Acquire lock (succeeds)
- Create new PAT: Returns `JIRA_PAT_NEW_ABC123` with expiry 2026-01-01
- Validate: POST to `/rest/api/3/myself` succeeds with new token
- Update Secrets Manager: `ketchup_jira_pat` = `JIRA_PAT_NEW_ABC123`
- Move old PAT to backup (Phase 2 feature)
- Revoke old PAT: POST to `/rest/pat/latest/tokens/{id}` succeeds
- Release lock
- Send success alert: "✅ JIRA PAT rotation successful"

**Day 17-40**: Next 24 rotations checks
- New PAT valid for 65-90 days, no rotation needed
- Cycle repeats every 24 hours

### Code Path Example

When `rotator.py` runs (simplified):

```python
# From plan-01:912-969 (rotator.py pseudocode)
async def perform_rotation(self) -> bool:
    # 1. Check if rotation needed
    needs_rotation = await pat_monitor.should_rotate()
    if not needs_rotation:
        logger.info("PAT rotation not needed yet")
        return True  # Success (no action needed)

    # 2. Acquire distributed lock
    async with distributed_lock.acquire_lock('PAT_ROTATION_GLOBAL', timeout_seconds=300):
        # 3. Create new PAT
        new_token_response = await mcp_client.createPAT()
        new_pat = new_token_response['token']
        new_expiry = new_token_response['expiresAt']

        # 4. Validate new PAT
        is_valid = await mcp_client.validatePAT(new_pat)
        if not is_valid:
            raise RuntimeError("New PAT validation failed")

        # 5. Update secrets (point of no return)
        await secrets_mgr.update_secret('ketchup_jira_pat', new_pat)
        await secrets_mgr.update_secret('ketchup_jira_pat_expiry', new_expiry)

        # 6. Revoke old PAT
        await mcp_client.revokePAT(old_token_id)

    # 7. Send success alert
    await slack_client.send_message(
        channel='#ketchup-alerts',
        text='✅ JIRA PAT rotation successful'
    )
    return True
```

### What Each Service Sees

**FastAPI app** (main Ketchup service):
- Loads PAT from environment on startup (via `config.ts`)
- Continues using current PAT without interruption
- Next restart picks up new PAT automatically
- Or: Uses new PAT immediately if env-aws.ts refreshes secrets

**JIRA API**:
- Receives requests with current valid PAT
- No service interruption during rotation
- Old PAT works until revoked
- New PAT activated after validation

**Ops/Monitoring**:
- Receives success alert in #ketchup-alerts
- Can verify in AWS Secrets Manager
- Audit trail shows old token ID and new token creation date
- Health file updated every minute: `/tmp/jira_pat_rotator_health`

## Failure Modes and Error Recovery

### Failure Mode 1: Primary PAT Expired

**How it fails**: Current PAT past 90-day expiry date

**System response**:
- JIRA API returns 401 Unauthorized on requests
- `jiraRequest()` catches error (lines 265-271 in utils.ts)
- Fallback logic checks if backup PAT available
- Uses backup PAT if valid (see Backup PAT section)
- Logs error with context for ops investigation

**Recovery**:
- Backup PAT fallback is automatic and transparent
- Rotation service should have created new PAT before expiry (75-day check)
- If backup also expired: System fails with clear error message
- On-call engineer must manually create new PAT via iPaaS console

**Code location**: `utils.ts:200-216` (request error handling) + fallback logic (future addition)

### Failure Mode 2: Rotation Service Crashes

**How it fails**:
- MCP service unreachable (network error)
- DynamoDB lock acquisition timeout
- AWS Secrets Manager unavailable
- Unexpected exception in rotation logic

**System response**:
- Exception caught in `rotator.py` main try/catch (plan-01:963-968)
- Old PAT remains unchanged (safe state)
- Alert sent to #ketchup-alerts with error details
- Service logs error and exits gracefully
- Next rotation check in 24 hours (or on restart)

**Recovery**:
- Check what failed (error in alert message)
- If MCP unreachable: Check mcp-jira container status
- If DynamoDB error: Verify AWS credentials and permissions
- If Secrets Manager error: Check IAM policy and network
- Wait 24 hours for automatic retry, or restart rotation service

**Code location**: `plan-01:951-968` (error handling and alerting)

### Failure Mode 3: New PAT Validation Fails

**How it fails**:
- New PAT created successfully but doesn't work with JIRA API
- Step 4 validation test fails (POST to `/rest/api/3/myself`)

**System response**:
- Exception thrown: "New PAT validation failed"
- Secrets Manager NOT updated (point of no return hasn't been reached)
- Old PAT remains active and valid
- Alert sent to #ketchup-alerts: "PAT creation failed: validation error"
- Root cause: Usually JIRA API misconfiguration or token generation error

**Recovery**:
- Check JIRA API status and connectivity
- Verify that iPaaS proxy is working correctly
- Check if token was actually created (may have succeeded but token is malformed)
- Manual intervention: Create new PAT via iPaaS console and update secrets manually
- Escalate if persistent

**Code location**: `plan-01:935-939` (validation step and error handling)

### Failure Mode 4: AWS Secrets Manager Update Fails

**How it fails**:
- New PAT created and validated, but Secrets Manager update fails
- Network error, timeout, permission error, or rate limiting

**System response**:
- Exception bubbles up from `update_secret()` call (plan-01:941)
- Old PAT remains in Secrets Manager (safe state)
- Alert sent to #ketchup-alerts with AWS error details
- Rotation marked as failed
- Next rotation attempt in 24 hours

**Recovery**:
- Check AWS Secrets Manager access and permissions
- Verify network connectivity to AWS API endpoint
- Check if rate limiting is happening (may need to exponential backoff)
- If persistent: Create new PAT manually and update secrets via AWS CLI

**Code location**: `plan-01:941-944` (secrets update step)

### Failure Mode 5: Distributed Lock Timeout

**How it fails**:
- Another instance is holding the rotation lock
- Current instance tries to acquire but times out after 300 seconds

**System response**:
- Lock acquisition fails gracefully (plan-01:915-921)
- Rotation skipped (no error, no change to PAT)
- Logged as info: "Another server rotating PAT, exiting"
- Next check in 24 hours
- No alert sent (this is expected behavior)

**Recovery**:
- No action needed - this is normal operation with multiple instances
- One instance will complete rotation, next check will see updated PAT
- If lock is held for days: Check if rotation service is stuck on another instance

**Code location**: `plan-01:915-921` (distributed lock acquisition with timeout)

### Failure Mode 6: MCP Service Unavailable

**How it fails**:
- TCP connection refused on port 8081
- MCP service crashed or not running

**System response**:
- MCP client fetch timeout after 30 seconds (from AsyncClient pattern)
- Exception thrown in `createPAT()` call
- Caught by main error handler, alert sent
- Old PAT remains active

**Recovery**:
- SSH to prod1: Check MCP container status
  ```bash
  docker ps | grep mcp-jira
  ```
- If not running: Restart container
  ```bash
  docker-compose -f infrastructure/docker-compose.yml restart mcp-jira
  ```
- Check MCP service logs for errors:
  ```bash
  docker logs mcp-jira | tail -100
  ```

**Code location**: `utils.ts:240` (timeout handling) + `utils.ts:265-271` (error catching)

### Error Recovery Principles

1. **Non-blocking failures**: Old PAT stays active, system doesn't crash
2. **Audit trail**: All failures logged with context and error messages
3. **Alerting**: Operations team notified via #ketchup-alerts
4. **Safe defaults**: System always maintains old PAT until new one verified
5. **Exponential backoff**: Consider retry logic on transient errors (Phase 2)

## Backup PAT Management Strategy

### Why We Need Backup PAT

- **Primary failure scenarios**: PAT creation failed, validation failed, network issue
- **Transition safety**: If rotation fails, backup PAT provides fallback access
- **Graceful degradation**: System continues working on backup while ops investigates

### Backup PAT Lifecycle

#### Phase 1 (Current): Configuration & Fallback

**Configuration** (config.ts lines 19-23):
```typescript
backupPat?: string;              // Secondary PAT for fallback
backupPatExpiry?: Date;          // When backup expires
useBackupPat?: boolean;          // Explicitly use backup
backupPatCreatedAt?: Date;       // When backup was created
```

**Fallback decision logic** (pat-validation.ts lines 46-61):
```
1. If useBackupPat flag is TRUE → Use backup
2. Else if primary PAT NOT expired → Use primary
3. Else if primary PAT expired AND backup available AND valid → Use backup (auto-fallback)
4. Else → Throw error "No PAT available"
```

**Loading from AWS Secrets Manager** (env-aws.ts lines 29-39):
```
ketchup_jira_backup_pat → JIRA_BACKUP_PAT
ketchup_jira_backup_pat_expiry → JIRA_BACKUP_PAT_EXPIRY
ketchup_jira_backup_pat_created → JIRA_BACKUP_PAT_CREATED
```

#### Phase 2 (Planned): Active Backup Rotation

**Task 20 - BackupPATService** (plan-02):
- Monitors backup PAT expiry
- Creates new backup when current backup is < 14 days to expiry
- Validates new backup works before storing
- Maintains history of PAT rotations

#### Phase 3 (Planned): Metrics & Alerting

**Task 22 - Metrics collection** (plan-02):
- Track rotation frequency
- Monitor backup PAT usage (how often fallback happens)
- Alert if backup being used (indicates primary rotation failed)

### Backup PAT Testing

**Test file**: `test_backup_pat_config.test.ts` (12 test cases)

**Key test scenarios**:

```typescript
// Test 1: Load primary + backup from environment
expect(config.auth.pat).toBe('primary-token');
expect(config.auth.backupPat).toBe('backup-token');

// Test 2: shouldUseBackupPat decision logic
expect(shouldUseBackupPat({
  useBackupPat: true,
  backupPat: 'valid-token-123',
  backupPatExpiry: new Date('2030-01-01Z')
})).toBe(true);  // Explicitly enabled

expect(shouldUseBackupPat({
  useBackupPat: false,
  pat: 'valid-primary-token',
  patExpiry: new Date('2030-01-01Z'),
  backupPat: 'valid-backup-token'
})).toBe(false);  // Primary still valid

expect(shouldUseBackupPat({
  useBackupPat: false,
  pat: 'expired-token',
  patExpiry: new Date('2020-01-01Z'),  // Expired
  backupPat: 'valid-backup-token',
  backupPatExpiry: new Date('2030-01-01Z')
})).toBe(true);  // Auto-fallback to backup

// Test 3: Reject if backup expired
expect(shouldUseBackupPat({
  useBackupPat: true,
  backupPat: 'expired-backup-token',
  backupPatExpiry: new Date('2020-01-01Z')
})).toBe(false);  // Can't use expired backup
```

### Backup PAT Creation (Phase 2 Task 20)

When backup rotation is implemented:

```python
# Simplified logic from plan-02
async def rotate_backup_pat_if_needed(self):
    # Check if backup needs rotation
    days_until_expiry = (backup_pat_expiry - now).days
    if days_until_expiry > 14:
        return  # Not yet time to rotate

    # Create new backup PAT
    new_backup = await mcp_client.createPAT()

    # Validate it works
    is_valid = await mcp_client.validatePAT(new_backup['token'])
    if not is_valid:
        raise RuntimeError("Backup PAT validation failed")

    # Store in secrets (old backup moves to history)
    await secrets_mgr.update_secret(
        'ketchup_jira_backup_pat',
        new_backup['token']
    )
    await secrets_mgr.update_secret(
        'ketchup_jira_backup_pat_expiry',
        new_backup['expiresAt']
    )
```

## Alerting Mechanism

### Alert Channel

**Slack Channel**: `#ketchup-alerts` (Channel ID: C0957H8ASH2)

**Alert pattern**: Uses same system as `ketchup_access_request_monitor` (reference: `ketchup_access_request_monitor/monitor.py`)

### Success Alerts

**When sent**: After successful PAT rotation completion

**Format**:
```
Channel: #ketchup-alerts
Text: "✅ JIRA PAT rotation successful
Details:
  Old token ID: {old_token_id}
  New token created: {creation_timestamp}
  New expiry: {new_expiry_date}
  Next rotation: 75 days before {new_expiry_date}"
```

**Example**:
```
✅ JIRA PAT rotation successful
Old token ID: 649e9d1c1234
New token created: 2025-11-19T10:30:00Z
New expiry: 2026-02-17T10:30:00Z
Next rotation check: 2025-12-03
```

### Failure Alerts

**When sent**: When rotation fails, but old PAT is still active

**Format**:
```
Channel: #ketchup-alerts
Text: "❌ JIRA PAT rotation failed
Error: {error_message}
Stage: {creation|validation|secrets_update|revoke}
Old PAT: Still active and valid
Expiry: {current_pat_expiry}
Days remaining: {days_to_expiry}
Action: Investigate error, next rotation attempt in 24 hours"
```

**Examples**:
```
❌ JIRA PAT rotation failed
Error: New PAT validation failed
Stage: validation
Old PAT: Still active and valid (70 days remaining)
Action: Check JIRA API status, next attempt in 24 hours

---

❌ JIRA PAT rotation failed
Error: AWS Secrets Manager connection timeout
Stage: secrets_update
Old PAT: Still active and valid (65 days remaining)
Action: Verify AWS network connectivity, escalate if persistent
```

### Critical Alerts

**When sent**: When BOTH primary and backup PATs are invalid

**Format**:
```
Channel: #ketchup-alerts (may be urgent/paged)
Text: "🚨 CRITICAL: No valid JIRA PAT available
Primary: Expired {days_ago} days ago
Backup: {missing|expired|invalid}
Service: JIRA operations failing
Action: Create new PAT immediately via iPaaS console"
```

### Alert Cooldown Logic

**Cooldown duration**: 1 hour per alert category (from `ketchup_access_request_monitor` pattern)

**Per-category cooldown**:
```python
self.last_alerts = {}  # category → last_alert_timestamp
self.cooldown = 3600  # 1 hour in seconds

def _should_send_alert(self, category: str) -> bool:
    last_alert_time = self.last_alerts.get(category, 0)
    elapsed = time.time() - last_alert_time

    if elapsed >= self.cooldown:
        self.last_alerts[category] = time.time()
        return True
    else:
        logger.info(f"Alert for {category} on cooldown, next in {self.cooldown - elapsed}s")
        return False
```

**Benefit**: Prevents alert spam if rotation fails repeatedly

**Implementation location**: Will be in `ketchup_jira_pat_rotator/main.py` (Phase 1 Task 14)

## Metrics Collection and Health Tracking

### Phase 1: Health File Tracking (Immediate)

**Health file location**: `/tmp/jira_pat_rotator_health`

**Update frequency**: Every minute (even if no rotation)

**Format**:
```
timestamp:status:last_rotation:next_rotation
2025-11-19T10:30:00Z:healthy:2025-11-19T09:15:00Z:2025-11-20T10:30:00Z
2025-11-19T10:31:00Z:healthy:2025-11-19T09:15:00Z:2025-11-20T10:30:00Z
2025-11-19T10:45:30Z:failed:2025-11-19T09:15:00Z:2025-11-20T10:30:00Z
```

**Status values**:
- `healthy`: Last rotation succeeded, or no rotation needed yet
- `failed`: Last rotation attempt failed, old PAT still active
- `critical`: No valid PAT available

**Monitoring**: Docker health check or external script can read this file to alert if status is `failed` or `critical`

**Code location**: `plan-01:906-910` (scheduler implementation)

### Phase 2: Detailed Metrics Storage (Planned)

**Storage location**: DynamoDB `ketchup_metrics` table

**Metrics to collect** (plan-02 Task 22):
- Rotation frequency (how often needed)
- Rotation success rate
- Backup PAT usage frequency (indicates failures)
- Time spent in each rotation step
- Error rates by failure mode
- Alert spam analysis

**Metrics schema** (planned):
```python
{
    'service': 'jira_pat_rotator',
    'timestamp': '2025-11-19T10:30:00Z',
    'metric_type': 'rotation_completed',
    'duration_seconds': 45,
    'success': True,
    'old_token_id': '649e9d1c1234',
    'new_expiry': '2026-02-17T10:30:00Z'
}

{
    'service': 'jira_pat_rotator',
    'timestamp': '2025-11-20T10:30:00Z',
    'metric_type': 'backup_pat_used',
    'reason': 'primary_expired',
    'days_remaining_on_backup': 45
}
```

**Collection interval**: Every 5 minutes (Phase 2)

**Visualization**: Dashboard in CloudWatch or custom Ketchup dashboard (future)

## Integration with Ketchup Services

### How PAT Auth Integrates with Existing Ketchup Services

#### 1. FastAPI App (Ketchup Main Service)

**Location**: `ketchup/main.py`

**How it uses JIRA**:
- Handles user commands via Slack endpoints
- Needs to call JIRA API for various operations (search, create issues, etc.)
- Currently uses Basic Auth (username/password) via iPaaS proxy

**PAT integration** (Phase 1 Task 1-4):
- Load PAT from config on startup
- Feature flag: `JIRA_USE_PAT_AUTH` (false by default, safe rollout)
- When flag enabled: Use PAT instead of username/password
- Auth header format: `x-authorization: Bearer {PAT}` (via iPaaS)
- No code changes needed in FastAPI app itself - handled by `buildJiraAuthHeaders()` utility

**Code path**:
```
FastAPI endpoint → needs JIRA data → calls MCP service
MCP service loads config.ts → reads JIRA_USE_PAT_AUTH flag
If true: Use PAT from config.ts lines 46-72
If false: Use username/password (current)
Request made with appropriate auth header (utils.ts:165-199)
```

#### 2. JIRA Reporter Service

**Location**: `ketchup/jira_reporter/`

**How it uses JIRA**:
- Listens for Slack events
- Reports JIRA-related information back to Slack
- Currently uses Slack-based operations

**PAT integration**:
- If calling JIRA API directly: Uses same config loading as FastAPI
- If calling MCP service: Already handled by MCP's auth layer
- No changes needed if using MCP operations

#### 3. MCP JIRA Service (Central Integration Point)

**Location**: `ketchup/corp_jira_mcp/`

**Responsibilities**:
- All JIRA API interactions go through here
- Loads PAT configuration (config.ts)
- Provides authentication headers (utils.ts)
- Handles both Primary and Backup PAT logic

**How authentication works** (utils.ts:158-272):
```
jiraRequest(endpoint, options)
  ├─ Load config (JiraAuthConfig from config.ts)
  ├─ Determine auth mode:
  │  ├─ If JIRA_USE_PAT_AUTH=true: Use PAT (lines 165-199)
  │  ├─ Else if USE_IPAAS=true: Use Basic Auth (lines 200-216)
  │  └─ Else: Direct JIRA
  ├─ Add appropriate auth headers
  ├─ Make fetch request (with 30s timeout)
  ├─ Handle response/errors (lines 265-271)
  └─ Return result or throw error
```

**Fallback logic** (planned addition to lines 200-216):
- If primary PAT expired: Automatically try backup PAT
- Transparent to callers (they don't need to handle it)
- Logged for audit trail

#### 4. PAT Rotation Service (New Phase 1)

**Location** (planned): `ketchup/ketchup_jira_pat_rotator/`

**Integration points**:
- Uses MCP JIRA service (createPAT, validatePAT, revokePAT operations)
- Updates AWS Secrets Manager directly
- Sends alerts to #ketchup-alerts via Slack API
- Uses DynamoDB for distributed locking

**Interaction diagram**:
```
Rotation Service
  ├─ MCP JIRA Service
  │  ├─ createPAT() → JIRA API via iPaaS
  │  ├─ validatePAT() → JIRA API via iPaaS
  │  └─ revokePAT() → JIRA API via iPaaS
  ├─ AWS Secrets Manager
  │  └─ Update ketchup_jira_pat, ketchup_jira_pat_expiry
  ├─ DynamoDB
  │  └─ Acquire/release PAT_ROTATION_GLOBAL lock
  └─ Slack API
     └─ Send alert to #ketchup-alerts
```

### Environment Variables Flow

**How PAT configuration propagates**:

```
1. Infrastructure Layer (AWS)
   ├─ AWS Secrets Manager: Ketchup_Token_Secrets
   │  ├─ ketchup_jira_pat
   │  ├─ ketchup_jira_pat_expiry
   │  ├─ ketchup_jira_backup_pat
   │  ├─ ketchup_jira_backup_pat_expiry
   │  └─ ketchup_jira_backup_pat_created

2. Docker Compose Environment (docker-compose.yml)
   ├─ JIRA_PAT (from secrets via env-aws.ts)
   ├─ JIRA_PAT_EXPIRY
   ├─ JIRA_BACKUP_PAT
   ├─ JIRA_BACKUP_PAT_EXPIRY
   ├─ JIRA_BACKUP_PAT_CREATED
   └─ JIRA_USE_PAT_AUTH (feature flag)

3. MCP Service Initialization (env-aws.ts)
   ├─ On startup: Fetch secrets from AWS
   ├─ Load into environment variables
   └─ Securely log (with token redaction)

4. Configuration Loading (config.ts)
   ├─ Read environment variables
   ├─ Parse dates (ISO 8601 format)
   ├─ Create JiraAuthConfig object
   └─ Available to all services

5. Request Authentication (utils.ts)
   ├─ Load config
   ├─ Check feature flags
   ├─ Build appropriate auth headers
   └─ Make JIRA request
```

### Feature Flag Rollout Strategy

**Feature flag**: `JIRA_USE_PAT_AUTH`

**Values**:
- `false` (default): Use Basic Auth (username/password)
- `true`: Use PAT (new behavior)

**Rollout phases** (plan-01):

1. **Phase 1a** (Week 1): Deploy code, feature flag disabled everywhere
   - All JIRA requests use Basic Auth
   - PAT configuration loaded but not used
   - No user-facing changes

2. **Phase 1b** (Week 2): Enable in docker-compose.local.yml
   - Local testing uses PAT
   - Production still uses Basic Auth
   - Verify rotation mechanism works

3. **Phase 1c** (Week 3): Enable for testing in docker-compose.yml
   - Small percentage of JIRA operations use PAT
   - Monitor for errors
   - Rollback if needed

4. **Phase 1d** (Week 4): Enable for all operations
   - All JIRA operations use PAT
   - Monitor for 1 week
   - Keep Basic Auth as fallback for 1 more week

5. **Phase 2** (After Nov 30): Remove Basic Auth
   - JIRA has deprecated username/password
   - PAT is only auth method
   - Remove old code

**Location**: `docker-compose.yml` environment section (lines TBD)

## Troubleshooting Guide

### Scenario 1: JIRA Operations Failing with 401 Unauthorized

**Symptoms**: JIRA requests return 401 errors in Ketchup service logs

**Root causes**:
1. PAT expired (check expiry date)
2. PAT invalid/malformed (check format)
3. Feature flag enabled but PAT not configured

**Troubleshooting steps**:
```bash
# 1. Check current PAT in secrets
aws secretsmanager get-secret-value \
  --secret-id Ketchup_Token_Secrets \
  --region eu-west-1

# Output: Look for ketchup_jira_pat and ketchup_jira_pat_expiry
# Example: ketchup_jira_pat_expiry: 2025-11-19T00:00:00Z

# 2. Check if PAT is expired
date  # Current date
# If ketchup_jira_pat_expiry < current date, PAT is expired

# 3. Check if backup PAT is available
# Look for ketchup_jira_backup_pat in same output

# 4. Check MCP service logs
docker logs mcp-jira | grep -i "pat\|401\|unauthorized" | tail -50

# 5. Check feature flag
echo $JIRA_USE_PAT_AUTH
# Should be "true" if PAT auth is enabled
```

**Resolution**:
- If PAT expired and backup invalid: Create new PAT immediately
- If backup PAT exists and valid: System should auto-fallback
- If 401 persists: Check token format and JIRA API connectivity

### Scenario 2: Rotation Service Crashed

**Symptoms**: Health file is stale (timestamp > 1 minute old), or no health file

**Root causes**:
1. Service exited abnormally
2. Service is stuck (hung process)
3. `/tmp` was cleared (health file lost)

**Troubleshooting steps**:
```bash
# 1. Check if rotation service is running
docker ps | grep pat-rotator
# If not listed, service is not running

# 2. Check recent logs
docker logs jira-pat-rotator | tail -100

# 3. Check health file
cat /tmp/jira_pat_rotator_health
# Should have recent timestamp (< 1 min ago)

# 4. Check if lock is stuck
aws dynamodb get-item \
  --table-name ketchup_channel_information \
  --key '{"channel_id": {"S": "PAT_ROTATION_GLOBAL"}}' \
  --region eu-west-1
# If item exists and is old, lock may be stuck
```

**Resolution**:
- Restart service: `docker-compose restart jira-pat-rotator`
- If persistent: Check AWS connectivity and permissions
- If lock stuck: Delete old lock item from DynamoDB

### Scenario 3: Rotation Alert Spam (Multiple Failures in Short Time)

**Symptoms**: Multiple failure alerts in #ketchup-alerts within minutes

**Root causes**:
1. Transient network error (will resolve on next attempt)
2. JIRA API down
3. AWS Secrets Manager permissions issue
4. Rotation service restarting repeatedly

**Troubleshooting steps**:
```bash
# 1. Check alert cooldown
# Alerts should be at least 1 hour apart for same category
# If multiple in < 1 hour: Either different error types, or cooldown bug

# 2. Check rotation service status
docker ps -a | grep pat-rotator
# Check restart count

# 3. Check JIRA API status
curl -H "Authorization: Bearer {test-token}" \
  https://jira.corp.example.com/rest/api/3/myself
# Should return 200 if API is healthy

# 4. Check AWS Secrets Manager access
aws secretsmanager list-secrets --region eu-west-1
# Should succeed without permission errors

# 5. Check rotation logs for error pattern
docker logs jira-pat-rotator | grep -i "error\|failed" | tail -20
```

**Resolution**:
- If transient (network timeout): Wait 24 hours for next attempt
- If JIRA down: Escalate to JIRA team, manual PAT creation if needed
- If permission error: Check IAM role and policy
- If service restarting: Check logs for crash reason, fix bug or restart manually

### Scenario 4: Backup PAT Being Used (Fallback Active)

**Symptoms**:
- Slack alerts mention backup PAT in use
- Or Ketchup logs show "Using backup PAT"
- Primary PAT is still valid but not being used

**Root causes**:
1. Primary PAT validation failed
2. Rotation created new PAT but validation failed
3. Feature flag toggled to useBackupPat=true

**Troubleshooting steps**:
```bash
# 1. Check which PAT is configured
aws secretsmanager get-secret-value \
  --secret-id Ketchup_Token_Secrets \
  --region eu-west-1 | grep -A2 "ketchup_jira.*pat"

# 2. Check backup PAT expiry
# If backup also near expiry: Create new PAT immediately

# 3. Check why primary failed validation
# Look in rotation service logs for validation errors

# 4. Check feature flag
docker-compose config | grep JIRA_USE_PAT_AUTH
docker-compose config | grep -A2 "useBackupPat"
```

**Resolution**:
- If primary expired: Rotation should create new one, next 24-hour check
- If backup is only option: Create new PAT immediately and update secrets
- If flag manually enabled: Review why (should be auto-fallback only)

### Scenario 5: Cannot Create New PAT (MCP createPAT Fails)

**Symptoms**: Rotation service logs show "createPAT failed" or "iPaaS proxy error"

**Root causes**:
1. iPaaS proxy is down
2. JIRA API endpoint not available
3. Authentication header malformed
4. Token already exists (too many tokens for account)

**Troubleshooting steps**:
```bash
# 1. Test MCP service directly
curl -X POST http://localhost:8081/mcp/jira/createPAT \
  -H "Content-Type: application/json" \
  -d '{}'

# 2. Check MCP service logs
docker logs mcp-jira | grep -i "createpat\|ipaas\|error" | tail -30

# 3. Check if too many tokens exist
# Count existing tokens in JIRA (manual JIRA console access)
# Max is 10 per account

# 4. Verify iPaaS configuration
# Check that JIRA_IMS_TOKEN and JIRA_API_KEY are set
echo $JIRA_IMS_TOKEN
echo $JIRA_API_KEY
```

**Resolution**:
- If iPaaS down: Wait for it to recover, next rotation attempt in 24 hours
- If too many tokens: Revoke old ones manually, then retry
- If configuration missing: Update docker-compose.yml with proper credentials

### Scenario 6: Lock Cannot Be Acquired (Timeout)

**Symptoms**: Rotation logs show "Failed to acquire distributed lock" or "Another server rotating PAT"

**Root causes**:
1. Another instance is actively rotating (expected, not an error)
2. Previous lock holder crashed (lock not released)
3. Lock timeout too short for actual rotation duration

**Troubleshooting steps**:
```bash
# 1. Check lock in DynamoDB
aws dynamodb scan \
  --table-name ketchup_channel_information \
  --filter-expression "contains(channel_id, :lock)" \
  --expression-attribute-values '{":lock": {"S": "PAT_ROTATION_GLOBAL"}}' \
  --region eu-west-1

# 2. Check lock age
# Lock should be < 300 seconds old if held by active process

# 3. Check how many instances are running
docker-compose ps | grep pat-rotator
# Should be 1 instance only (singleton on prod1)
```

**Resolution**:
- If another instance active: Wait, it will finish (normal operation)
- If lock is stale: Delete it from DynamoDB to allow next rotation
- If happening frequently: Increase lock timeout value

## Configuration Reference

### Environment Variables

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `JIRA_PAT` | Primary PAT token value | `ATAT12...` | Yes (if JIRA_USE_PAT_AUTH=true) |
| `JIRA_PAT_EXPIRY` | Primary PAT expiry date | `2025-12-15T10:30:00Z` | Yes (if JIRA_USE_PAT_AUTH=true) |
| `JIRA_BACKUP_PAT` | Backup PAT token value | `ATAT34...` | No |
| `JIRA_BACKUP_PAT_EXPIRY` | Backup PAT expiry date | `2026-01-15T10:30:00Z` | No |
| `JIRA_BACKUP_PAT_CREATED` | Backup PAT creation timestamp | `2025-11-15T10:30:00Z` | No |
| `JIRA_USE_PAT_AUTH` | Enable PAT authentication | `true` or `false` | No (default: false) |
| `USE_IPAAS` | Use iPaaS proxy for JIRA | `true` | No (default: true) |
| `JIRA_USERNAME` | JIRA username (deprecated) | `bot-user@corp` | No (for rollback) |
| `JIRA_PASSWORD` | JIRA password (deprecated) | `password-hash` | No (for rollback) |
| `JIRA_IMS_TOKEN` | iPaaS IMS token | `ims-token-value` | Yes (if USE_IPAAS=true) |
| `JIRA_API_KEY` | iPaaS API key | `api-key-value` | Yes (if USE_IPAAS=true) |
| `AWS_REGION` | AWS region | `eu-west-1` | Yes |
| `AWS_SECRET_NAME` | AWS Secrets Manager secret name | `Ketchup_Token_Secrets` | Yes |

### AWS Secrets Manager Keys

**Secret Name**: `Ketchup_Token_Secrets`

| Key | Value Type | Description | Example |
|-----|-----------|-------------|---------|
| `ketchup_jira_pat` | String | Primary PAT token | `ATAT1234567890ABCDEF...` |
| `ketchup_jira_pat_expiry` | String (ISO 8601) | Primary PAT expiry | `2025-12-15T10:30:00Z` |
| `ketchup_jira_backup_pat` | String | Backup PAT token | `ATAT0987654321FEDCBA...` |
| `ketchup_jira_backup_pat_expiry` | String (ISO 8601) | Backup PAT expiry | `2026-01-15T10:30:00Z` |
| `ketchup_jira_backup_pat_created` | String (ISO 8601) | When backup was created | `2025-11-15T10:30:00Z` |
| `ipaas_username` | String | iPaaS username (deprecated) | `bot@corp` |
| `ipaas_password` | String | iPaaS password (deprecated) | `password-hash` |
| `ipaas_api_key` | String | iPaaS API key | `api-key-value` |
| `ims_access_token` | String | iPaaS IMS token | `ims-token-value` |

### Configuration Code Locations

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| Interface definition | `config.ts` | 7-24 | JiraAuthConfig interface |
| Default values | `config.ts` | 46-72 | Environment variable loading |
| Config creation | `config.ts` | 99-149 | Validation and object creation |
| PAT validation | `pat-validation.ts` | 3-61 | Format/expiry checking |
| AWS loading | `env-aws.ts` | 29-39 | Secrets Manager to env vars |
| Auth headers | `utils.ts` | 118-156 | Header construction |
| Main request | `utils.ts` | 158-272 | Request with auth |

## Code Reference Map

### Core Components

**Configuration System** (`ketchup/corp_jira_mcp/corp_jira_mcp/common/`)
- `config.ts` (lines 1-160): Main configuration interface and creation logic
  - `JiraAuthConfig` interface (lines 7-24)
  - `createConfig()` function (lines 99-149)
  - Validation logic (lines 151-157)

**PAT Validation** (`ketchup/corp_jira_mcp/corp_jira_mcp/common/pat-validation.ts`)
- `isValidPatFormat()` (lines 3-9): Regex validation
- `isBackupPatExpired()` (lines 11-16): Expiry checking
- `shouldUseBackupPat()` (lines 46-61): Decision logic

**Authentication** (`ketchup/corp_jira_mcp/corp_jira_mcp/utils.ts`)
- `buildUrl()` (lines 44-55): URL construction
- `jiraRequest()` (lines 158-272): Main request function
  - iPaaS flow (lines 165-199)
  - Error handling (lines 265-271)

**AWS Integration** (`ketchup/corp_jira_mcp/corp_jira_mcp/env-aws.ts`)
- Secret mappings (lines 29-39)
- Loading logic (lines 49-53)
- Secure logging (lines 57-63)

### Test Files

**Configuration Tests** (`ketchup/corp_jira_mcp/tests/test_backup_pat_config.test.ts`)
- 12 test cases covering loading, format, expiry, and decision logic
- Key tests at lines: 25-31, 33-42, 44-49, 51-57, 88-96, 98-105, 116-164

### Rotation Service (Phase 1, planned)

**Location**: `ketchup/ketchup_jira_pat_rotator/`

**Files** (plan-01 Tasks 11-14):
- `scheduler.py`: 24-hour scheduler, health file updates
- `pat_monitor.py`: Expiry checking, 75-day threshold
- `rotator.py`: Main rotation orchestration (lines 912-969 in plan)
- `main.py`: Entry point and initialization

### Relevant Documentation

**Plans**: `docs/plans/jira-pat-migration/`
- `plan-01-pat-authentication.yaml`: Phase 1 implementation (14 tasks)
- `plan-02-advanced-rotation-features.yaml`: Phase 2 features (6 tasks)

**Research**: `docs/plans/jira-pat-migration/ketchup_pat_research.md`
- JIRA PAT policies and constraints
- Timeline and deprecation dates

**Existing patterns**:
- Scheduler pattern: `ketchup/ketchup_status_updater/scheduler.py` (reference)
- Alerting pattern: `ketchup/ketchup_access_request_monitor/monitor.py` (reference)
- DI pattern: `packages/core/typed_di/` (reference)

### Integration Points

**FastAPI App**: `ketchup/main.py`
- Loads config via MCP service
- Uses JIRA operations via MCP

**JIRA Reporter**: `ketchup/jira_reporter/`
- Uses PAT via MCP service integration

**Docker Compose**: `infrastructure/docker-compose.yml`
- Environment variable definitions
- Service configurations

---

## Summary

The JIRA PAT rotation system ensures continuous access to JIRA by:

1. **Automatic rotation**: Checks every 24 hours, rotates when PAT is 75+ days old (before 90-day max)
2. **Backup fallback**: Maintains backup PAT for transparent fallback if primary fails
3. **Safe failure handling**: Non-blocking failures keep old PAT active, alert operations
4. **Distributed locking**: Prevents concurrent rotations on multiple instances
5. **Comprehensive alerting**: Sends success/failure alerts to #ketchup-alerts for monitoring

**Key timeline**: JIRA Basic Auth deprecated Nov 30, 2025. PAT rotation must be working before then.

**Current status** (Phase 1):
- Configuration system and validation in place (TypeScript/Node.js)
- Tests cover all validation logic
- MCP operations planned for rotation service
- Python rotation service to be implemented
- Feature flag allows safe rollout

**Next phases** (Phase 2):
- Backup PAT rotation automation
- Detailed metrics collection
- Health dashboard
- Comprehensive documentation of all states
