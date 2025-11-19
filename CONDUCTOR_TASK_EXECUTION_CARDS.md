# JIRA PAT Migration: Conductor Task Execution Cards

**Document Type**: Detailed Execution Reference for Each Completed Task
**Purpose**: Quick-reference cards with specific implementation details, file paths, and test requirements
**Total Cards**: 17 tasks
**Date**: 2025-11-19

---

## Quick Navigation

- [typescript-pro Tasks (1-6, 19-21)](#typescript-pro-tasks)
- [backend-developer Tasks (9-10)](#backend-developer-tasks)
- [python-pro Tasks (11-14, 22)](#python-pro-tasks)
- [technical-documentation-specialist Tasks (24)](#technical-documentation-specialist-tasks)

---

## TypeScript Pro Tasks

### TASK 1: Update env-aws.ts to map PAT from AWS Secrets

**Status**: COMPLETED | **Estimated**: 15m | **Worktree**: chain-1

**Description**:
Add PAT and expiry mappings to the AWS Secrets Manager configuration. Map 'ketchup_jira_pat' → 'JIRA_PAT' and 'ketchup_jira_pat_expiry' → 'JIRA_PAT_EXPIRY'.

**Files Modified**:
- Primary: `ketchup/corp_jira_mcp/corp_jira_mcp/env-aws.ts`
- Tests: `ketchup/corp_jira_mcp/corp_jira_mcp/tests/config.test.ts`

**Key Implementation Details**:
- Add two new mappings to the secrets object in loadSecretsFromAWS() function
- Ensure PAT is logged as [REDACTED] for security
- JIRA_PAT_EXPIRY can be logged as plain ISO date
- Mappings follow existing pattern for consistency

**Test Requirements**:
- [ ] Should load JIRA_PAT from AWS Secrets
- [ ] Should load JIRA_PAT_EXPIRY from AWS Secrets
- [ ] Should handle missing PAT gracefully
- [ ] Should log PAT presence without exposing value

**Validation Commands**:
```bash
cd ketchup/corp_jira_mcp
npx jest tests/config.test.ts --testNamePattern='PAT mappings'
```

**Dependencies**: None (starting task)

**Related Tasks**: Task 2 (config.ts builds on this)

---

### TASK 2: Update config.ts to add PAT configuration fields

**Status**: COMPLETED | **Estimated**: 20m | **Worktree**: chain-1

**Description**:
Add PAT fields to JiraConfig interface and load them from environment variables. Add usePat flag to control which authentication method is used (feature flag).

**Files Modified**:
- Primary: `ketchup/corp_jira_mcp/corp_jira_mcp/common/config.ts`
- Tests: `ketchup/corp_jira_mcp/corp_jira_mcp/tests/config.test.ts`

**Key Implementation Details**:
- Add JiraAuthConfig interface with pat, patExpiry fields
- Add usePat boolean flag (defaults to false for safety)
- Load from environment: JIRA_PAT, JIRA_PAT_EXPIRY, JIRA_USE_PAT_AUTH
- Parse JIRA_PAT_EXPIRY as ISO Date if present
- Validate: if usePat is true, pat must exist

**Configuration Structure**:
```typescript
interface JiraAuthConfig {
  pat?: string;                    // JIRA PAT token
  patExpiry?: Date;               // Token expiry date
  usePat: boolean;                // Feature flag (defaults false)
  basicAuth?: {                   // Existing basic auth
    username?: string;
    password?: string;
  };
}
```

**Test Requirements**:
- [ ] Should load PAT from environment
- [ ] Should load PAT expiry from environment
- [ ] Should default usePat to false
- [ ] Should enable usePat only when flag is 'true'
- [ ] Should validate PAT exists when usePat is enabled

**Validation Commands**:
```bash
cd ketchup/corp_jira_mcp
npx jest tests/config.test.ts --testNamePattern='PAT configuration'
```

**Dependencies**: Task 1 (env-aws.ts mappings)

**Related Tasks**: Task 3 (uses this config), Task 19 (extends with backup PAT)

---

### TASK 3: Create buildJiraAuthHeaders utility function

**Status**: COMPLETED | **Estimated**: 30m | **Worktree**: chain-1

**Description**:
Create centralized buildJiraAuthHeaders() function that returns appropriate headers based on configuration (PAT Bearer token, iPaaS proxy, or Basic Auth). This single function becomes the source of truth for all auth header construction.

**Files Modified**:
- Primary: `ketchup/corp_jira_mcp/corp_jira_mcp/common/utils.ts`
- Tests: `ketchup/corp_jira_mcp/corp_jira_mcp/tests/utils.test.ts`

**Key Implementation Details**:
- Function signature: `buildJiraAuthHeaders(config: JiraConfig): Record<string, string>`
- Check config.usePat first → Bearer token
- Then check config.useIpaas → iPaaS headers
- Fall back to → Basic Auth
- Always include Content-Type and Accept headers

**Implementation Logic**:
```typescript
function buildJiraAuthHeaders(config: JiraConfig): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  };

  if (config.usePat && config.auth.pat) {
    headers['Authorization'] = `Bearer ${config.auth.pat}`;
  } else if (config.useIpaas && config.ipaasApiKey) {
    headers['Api_key'] = config.ipaasApiKey;
    headers['Authorization'] = `Bearer ${config.ipaasToken}`;
  } else if (config.auth.basicAuth?.username && config.auth.basicAuth?.password) {
    const creds = Buffer.from(`${config.auth.basicAuth.username}:${config.auth.basicAuth.password}`).toString('base64');
    headers['Authorization'] = `Basic ${creds}`;
  } else {
    throw new Error('No valid authentication configuration found');
  }

  return headers;
}
```

**Test Requirements**:
- [ ] Returns Bearer token when usePat=true
- [ ] Returns iPaaS headers when useIpaas=true
- [ ] Returns Basic Auth when both false
- [ ] Throws error if required config missing
- [ ] Includes Content-Type and Accept headers

**Validation Commands**:
```bash
cd ketchup/corp_jira_mcp
npx jest tests/utils.test.ts --testNamePattern='buildJiraAuthHeaders'
```

**Dependencies**: Task 2 (config.ts interface)

**Related Tasks**: Task 4 (integrates into jiraRequest), Task 21 (extends with fallback)

---

### TASK 4: Update jiraRequest to use buildJiraAuthHeaders with feature flag

**Status**: COMPLETED | **Estimated**: 25m | **Worktree**: chain-1

**Description**:
Integrate the buildJiraAuthHeaders utility into the jiraRequest function. Use feature flag to control authentication method, with fallback to existing authentication if flag is off.

**Files Modified**:
- Primary: `ketchup/corp_jira_mcp/corp_jira_mcp/common/utils.ts` (update jiraRequest function)
- Tests: `ketchup/corp_jira_mcp/corp_jira_mcp/tests/utils.test.ts`

**Key Implementation Details**:
- Update jiraRequest() function to call buildJiraAuthHeaders()
- Pass resulting headers to fetch() call
- Feature flag OFF (usePat=false) → uses existing Basic Auth
- Feature flag ON (usePat=true) → uses PAT Bearer token
- Add try-catch for header building errors

**Integration Pattern**:
```typescript
export async function jiraRequest(
  method: string,
  endpoint: string,
  body?: unknown,
  config?: JiraConfig
): Promise<unknown> {
  const cfg = config || createConfig();

  const headers = buildJiraAuthHeaders(cfg);

  const response = await fetch(`${cfg.host}${endpoint}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined
  });

  if (!response.ok) {
    throw new Error(`JIRA request failed: ${response.status} ${response.statusText}`);
  }

  return response.json();
}
```

**Test Requirements**:
- [ ] Feature flag OFF uses existing authentication
- [ ] Feature flag ON uses PAT Bearer token
- [ ] Proper error handling for invalid config
- [ ] Headers properly passed to fetch()
- [ ] Response handling unchanged

**Validation Commands**:
```bash
cd ketchup/corp_jira_mcp
npx jest tests/utils.test.ts --testNamePattern='jiraRequest'
npm run test
```

**Dependencies**: Task 3 (buildJiraAuthHeaders utility)

**Related Tasks**: Task 5 (uses jiraRequest for createPAT), Task 21 (extends with fallback)

---

### TASK 5: Add createPAT operation to MCP service

**Status**: COMPLETED | **Estimated**: 35m | **Worktree**: chain-2

**Description**:
Add createPAT operation to MCP service. This operation creates new JIRA PAT tokens via the MCP protocol, enabling the rotation service to generate replacement tokens.

**Files Modified**:
- Primary: `ketchup/corp_jira_mcp/corp_jira_mcp/operations/createPAT.ts`
- Tests: `ketchup/corp_jira_mcp/corp_jira_mcp/tests/operations.test.ts`

**Key Implementation Details**:
- MCP operation signature: `createPAT(expiryDays?: number): Promise<{token: string, expiresAt: string}>`
- Call JIRA API endpoint: POST /rest/api/3/tokens
- Default expiry: 90 days
- Return token and expiry timestamp
- Handle rate limiting and API errors
- Log operation (without token value) for audit trail

**MCP Operation Definition**:
```typescript
export const createPATOperation = {
  name: 'createPAT',
  description: 'Create a new JIRA Personal Access Token',
  inputSchema: {
    type: 'object',
    properties: {
      expiryDays: {
        type: 'number',
        description: 'Token expiry in days (default: 90)',
        default: 90
      }
    }
  },
  handler: async (input: {expiryDays?: number}) => {
    const expiryDays = input.expiryDays || 90;
    const response = await jiraRequest(
      'POST',
      '/rest/api/3/tokens',
      { expiryDays }
    );
    return {
      token: response.token,
      expiresAt: response.expiresAt,
      message: 'PAT created successfully'
    };
  }
};
```

**Test Requirements**:
- [ ] Successfully creates PAT with default expiry (90 days)
- [ ] Accepts custom expiry days parameter
- [ ] Returns token and expiresAt timestamp
- [ ] Handles JIRA API errors gracefully
- [ ] Logs operation without exposing token

**Validation Commands**:
```bash
cd ketchup/corp_jira_mcp
npx jest tests/operations.test.ts --testNamePattern='createPAT'
```

**Dependencies**: Task 4 (jiraRequest integration)

**Related Tasks**: Task 6 (revokePAT), Task 13 (rotator.py uses this)

---

### TASK 6: Add revokePAT operation to MCP service

**Status**: IN-PROGRESS | **Estimated**: 20m | **Worktree**: chain-2

**Description**:
Add revokePAT operation to MCP service. This operation revokes/deletes JIRA PAT tokens via the MCP protocol, enabling safe token cleanup during rotation.

**Files Modified**:
- Primary: `ketchup/corp_jira_mcp/corp_jira_mcp/operations/revokePAT.ts`
- Tests: `ketchup/corp_jira_mcp/corp_jira_mcp/tests/operations.test.ts`

**Key Implementation Details**:
- MCP operation signature: `revokePAT(tokenId: string): Promise<{success: boolean, message: string}>`
- Call JIRA API endpoint: DELETE /rest/api/3/tokens/{tokenId}
- Validate token ID format before attempting deletion
- Handle "token not found" as success (idempotent)
- Log operation for audit trail
- Return success status

**MCP Operation Definition**:
```typescript
export const revokePATOperation = {
  name: 'revokePAT',
  description: 'Revoke/delete a JIRA Personal Access Token',
  inputSchema: {
    type: 'object',
    properties: {
      tokenId: {
        type: 'string',
        description: 'The token ID to revoke'
      }
    },
    required: ['tokenId']
  },
  handler: async (input: {tokenId: string}) => {
    if (!input.tokenId || typeof input.tokenId !== 'string') {
      throw new Error('Invalid token ID format');
    }

    try {
      await jiraRequest(
        'DELETE',
        `/rest/api/3/tokens/${input.tokenId}`
      );
      return {
        success: true,
        message: `Token ${input.tokenId} revoked successfully`
      };
    } catch (error: unknown) {
      if (error instanceof Error && error.message.includes('404')) {
        // Token already deleted - idempotent success
        return {
          success: true,
          message: `Token ${input.tokenId} already revoked`
        };
      }
      throw error;
    }
  }
};
```

**Test Requirements**:
- [ ] Successfully revokes PAT by token ID
- [ ] Requires tokenId parameter
- [ ] Handles "token not found" as success (idempotent)
- [ ] Validates token ID format
- [ ] Logs operation for audit trail
- [ ] Handles JIRA API errors appropriately

**Validation Commands**:
```bash
cd ketchup/corp_jira_mcp
npx jest tests/operations.test.ts --testNamePattern='revokePAT'
```

**Dependencies**: Task 4 (jiraRequest integration)

**Related Tasks**: Task 5 (createPAT), Task 13 (rotator.py uses this)

**Blockers**: Currently IN-PROGRESS - needs completion

---

### TASK 19: Add backup PAT configuration schema

**Status**: COMPLETED | **Estimated**: 30m | **Worktree**: chain-1

**Description**:
Add backup PAT configuration schema to support resilient PAT rotation. Extends JiraConfig to include backup token fields for fallback scenarios.

**Files Modified**:
- Primary: `ketchup/corp_jira_mcp/corp_jira_mcp/common/config.ts`
- Secondary: `ketchup/corp_jira_mcp/corp_jira_mcp/common/types/backup-pat.types.ts`
- Tests: `tests/unit/test_backup_pat/test_config.test.ts`

**Key Implementation Details**:
- Add backup PAT fields to JiraAuthConfig interface
- Support backup token independent rotation schedule
- Add useBackupPat flag for fallback control
- Track backup PAT creation timestamp for age validation
- Load from environment: JIRA_BACKUP_PAT, JIRA_BACKUP_PAT_EXPIRY, JIRA_USE_BACKUP_PAT

**Configuration Extension**:
```typescript
interface JiraAuthConfig {
  // Primary PAT
  pat?: string;
  patExpiry?: Date;
  usePat: boolean;

  // Backup PAT (new)
  backupPat?: string;
  backupPatExpiry?: Date;
  useBackupPat: boolean;
  backupPatCreatedAt?: Date;
}
```

**Backup PAT Types**:
```typescript
// backup-pat.types.ts
export interface BackupPATConfig {
  token: string;
  expiresAt: Date;
  createdAt: Date;
  isActive: boolean;
}

export interface BackupPATRotationPolicy {
  enabled: boolean;
  rotationIntervalDays: number;
  expiryThresholdDays: number;
}
```

**Test Requirements**:
- [ ] Loads backup PAT from environment
- [ ] Loads backup PAT expiry from environment
- [ ] Defaults useBackupPat to false
- [ ] Validates backup PAT when useBackupPat is enabled
- [ ] Tracks backup PAT creation timestamp
- [ ] Independent of primary PAT configuration

**Validation Commands**:
```bash
cd ketchup/corp_jira_mcp
npx jest tests/test_backup_pat/test_config.test.ts
```

**Dependencies**: Task 2 (extends JiraConfig)

**Related Tasks**: Task 20 (backup PAT service), Task 21 (fallback logic)

---

### TASK 20: Implement backup PAT creation and validation operations

**Status**: COMPLETED | **Estimated**: 1h | **Worktree**: chain-1

**Description**:
Implement backup PAT creation and validation operations. Creates a backup token and validates both primary and backup tokens are functional.

**Files Modified**:
- Primary: `ketchup/corp_jira_mcp/corp_jira_mcp/services/backup-pat.service.ts`
- Tests: `tests/unit/test_backup_pat/test_backup_pat_service.test.ts`

**Key Implementation Details**:
- Service class: BackupPATService
- Methods: createBackupPAT(), validatePAT(), validateBackupPAT()
- Handles token validation via JIRA API
- Stores backup token in AWS Secrets Manager
- Tracks creation timestamp for age validation
- Comprehensive error handling

**Service Implementation**:
```typescript
export class BackupPATService {
  async createBackupPAT(config: JiraConfig): Promise<{
    token: string;
    expiresAt: Date;
    createdAt: Date;
  }> {
    // Create new backup token via JIRA API
    const newToken = await jiraRequest('POST', '/rest/api/3/tokens', {
      expiryDays: 90
    });

    // Store in AWS Secrets
    await storeInSecretsManager('ketchup_jira_backup_pat', newToken.token);

    return {
      token: newToken.token,
      expiresAt: new Date(newToken.expiresAt),
      createdAt: new Date()
    };
  }

  async validatePAT(token: string): Promise<boolean> {
    try {
      const response = await fetch(`${config.host}/rest/api/3/myself`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      return response.ok;
    } catch {
      return false;
    }
  }

  async validateBackupPAT(config: JiraConfig): Promise<boolean> {
    if (!config.auth.backupPat) return false;
    return this.validatePAT(config.auth.backupPat);
  }
}
```

**Test Requirements**:
- [ ] Creates backup PAT with 90-day expiry
- [ ] Stores backup token in AWS Secrets
- [ ] Validates primary PAT successfully
- [ ] Validates backup PAT successfully
- [ ] Handles validation failures gracefully
- [ ] Logs operations without exposing tokens

**Validation Commands**:
```bash
cd ketchup/corp_jira_mcp
npx jest tests/test_backup_pat/test_backup_pat_service.test.ts
```

**Dependencies**: Task 19 (backup PAT config schema)

**Related Tasks**: Task 21 (uses in fallback logic), Task 13 (rotator calls validation)

---

### TASK 21: Implement PAT fallback logic in MCP service

**Status**: COMPLETED | **Estimated**: 1h | **Worktree**: chain-1

**Description**:
Implement PAT fallback logic in buildJiraAuthHeaders utility. When primary PAT fails or is unavailable, automatically fall back to backup PAT, then to iPaaS/Basic Auth.

**Files Modified**:
- Primary: `ketchup/corp_jira_mcp/corp_jira_mcp/common/utils.ts` (update buildJiraAuthHeaders)
- Tests: `tests/unit/test_backup_pat/test_fallback_logic.test.ts`

**Key Implementation Details**:
- Enhanced buildJiraAuthHeaders with fallback chain
- Try primary PAT first
- Fall back to backup PAT if primary unavailable
- Then to iPaaS headers
- Finally to Basic Auth
- Log fallback events for monitoring
- Don't expose actual tokens in logs

**Enhanced Function with Fallback**:
```typescript
export function buildJiraAuthHeaders(
  config: JiraConfig,
  backupPATService?: BackupPATService
): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  };

  // Try primary PAT first
  if (config.usePat && config.auth.pat) {
    headers['Authorization'] = `Bearer ${config.auth.pat}`;
    return headers;
  }

  // Fall back to backup PAT
  if (config.auth.backupPat && backupPATService) {
    const isValid = backupPATService.validatePAT(config.auth.backupPat);
    if (isValid) {
      logger.warn('Using backup PAT - primary PAT unavailable');
      headers['Authorization'] = `Bearer ${config.auth.backupPat}`;
      return headers;
    }
  }

  // Fall back to iPaaS
  if (config.useIpaas && config.ipaasApiKey) {
    logger.warn('Using iPaaS - primary and backup PAT unavailable');
    headers['Api_key'] = config.ipaasApiKey;
    headers['Authorization'] = `Bearer ${config.ipaasToken}`;
    return headers;
  }

  // Fall back to Basic Auth
  if (config.auth.basicAuth?.username && config.auth.basicAuth?.password) {
    logger.warn('Using Basic Auth - all PAT options exhausted');
    const creds = Buffer.from(
      `${config.auth.basicAuth.username}:${config.auth.basicAuth.password}`
    ).toString('base64');
    headers['Authorization'] = `Basic ${creds}`;
    return headers;
  }

  throw new Error('No valid authentication configuration found');
}
```

**Test Requirements**:
- [ ] Uses primary PAT when available
- [ ] Falls back to backup PAT when primary unavailable
- [ ] Falls back to iPaaS when both PATs unavailable
- [ ] Falls back to Basic Auth as last resort
- [ ] Logs fallback events appropriately
- [ ] Doesn't expose tokens in logs
- [ ] Throws error when all options exhausted

**Validation Commands**:
```bash
cd ketchup/corp_jira_mcp
npx jest tests/test_backup_pat/test_fallback_logic.test.ts
```

**Dependencies**: Task 20 (backup PAT validation)

**Related Tasks**: Task 4 (extends jiraRequest), Task 3 (builds on buildJiraAuthHeaders)

---

## Backend Developer Tasks

### TASK 9: Add JIRA_USE_PAT_AUTH feature flag to docker-compose.yml

**Status**: COMPLETED | **Estimated**: 10m | **Worktree**: independent-3

**Description**:
Add JIRA_USE_PAT_AUTH feature flag to docker-compose.yml and docker-compose.local.yml. Controls whether the MCP service uses PAT or falls back to Basic Auth.

**Files Modified**:
- Primary: `ketchup/infrastructure/docker-compose.yml`
- Secondary: `ketchup/infrastructure/docker-compose.local.yml`

**Key Implementation Details**:
- Add JIRA_USE_PAT_AUTH environment variable to mcp service
- Default value: "false" (safe default for rollout)
- Separate configuration for local vs production
- Add configuration documentation comments

**Docker Compose Updates**:
```yaml
services:
  mcp:
    image: corp-jira-mcp:latest
    environment:
      # ... existing env vars ...
      JIRA_USE_PAT_AUTH: "false"  # Feature flag for PAT authentication
      JIRA_PAT: ${JIRA_PAT}
      JIRA_PAT_EXPIRY: ${JIRA_PAT_EXPIRY}
      # Backup PAT for fallback
      JIRA_BACKUP_PAT: ${JIRA_BACKUP_PAT}
      JIRA_BACKUP_PAT_EXPIRY: ${JIRA_BACKUP_PAT_EXPIRY}
      JIRA_USE_BACKUP_PAT: "false"
```

**Environment Variable Reference**:
| Variable | Value | Purpose |
|----------|-------|---------|
| JIRA_USE_PAT_AUTH | "false" | Enable/disable PAT authentication |
| JIRA_PAT | (from AWS Secrets) | Primary JIRA PAT token |
| JIRA_PAT_EXPIRY | (from AWS Secrets) | PAT expiry timestamp |
| JIRA_BACKUP_PAT | (from AWS Secrets) | Backup PAT token |
| JIRA_BACKUP_PAT_EXPIRY | (from AWS Secrets) | Backup PAT expiry |
| JIRA_USE_BACKUP_PAT | "false" | Enable/disable backup PAT |

**Validation Steps**:
- [ ] Feature flag correctly exposed to mcp service
- [ ] Default value is "false" (safe)
- [ ] PAT environment variables available
- [ ] Configuration works in local and production
- [ ] Can toggle flag to enable PAT auth

**Validation Commands**:
```bash
cd infrastructure
docker-compose config | grep -A5 "JIRA_USE_PAT_AUTH"
docker-compose -f docker-compose.local.yml up --no-start
```

**Dependencies**: None (parallel with chain-1 and chain-2)

**Related Tasks**: Task 10 (adds rotation service to same compose)

---

### TASK 10: Create jira-pat-rotator service stubs in docker-compose

**Status**: COMPLETED | **Estimated**: 15m | **Worktree**: independent-3

**Description**:
Create jira-pat-rotator service definition stubs in docker-compose.yml. Defines the Python rotation service container with environment variables and dependencies.

**Files Modified**:
- Primary: `ketchup/infrastructure/docker-compose.yml`

**Key Implementation Details**:
- Create jira-pat-rotator service definition
- Specify Python image with correct version
- Mount necessary volumes for code and config
- Set up environment variables for AWS Secrets access
- Configure dependencies on mcp service
- Add health checks for service monitoring

**Docker Service Definition**:
```yaml
services:
  jira-pat-rotator:
    build:
      context: ../ketchup/ketchup_jira_pat_rotator
      dockerfile: Dockerfile
    image: jira-pat-rotator:latest
    container_name: jira-pat-rotator

    # Environment for PAT rotation
    environment:
      PYTHONUNBUFFERED: "1"
      AWS_REGION: ${AWS_REGION:-eu-west-1}
      AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID}
      AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY}

      # Secrets Manager credentials
      JIRA_PAT_SECRET_ID: "ketchup_jira_pat"
      JIRA_BACKUP_PAT_SECRET_ID: "ketchup_jira_backup_pat"

      # Rotation configuration
      ROTATION_INTERVAL_HOURS: "24"
      EXPIRY_THRESHOLD_DAYS: "75"

      # MCP service connection
      MCP_HOST: "mcp"
      MCP_PORT: "5000"

    # Volume mounts
    volumes:
      - ../ketchup/ketchup_jira_pat_rotator:/app/rotator
      - ../ketchup/logs:/app/logs

    # Dependencies
    depends_on:
      mcp:
        condition: service_healthy

    # Health check
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s

    # Restart policy
    restart: unless-stopped

    # Logging
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

**Required Dockerfile** (if not exists):
```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

**Environment Variables Configuration**:
| Variable | Source | Purpose |
|----------|--------|---------|
| AWS_REGION | System env | AWS region for Secrets Manager |
| AWS_ACCESS_KEY_ID | System env | AWS credentials |
| AWS_SECRET_ACCESS_KEY | System env | AWS credentials |
| JIRA_PAT_SECRET_ID | Config | Secret name for primary PAT |
| JIRA_BACKUP_PAT_SECRET_ID | Config | Secret name for backup PAT |
| ROTATION_INTERVAL_HOURS | Config | Hours between rotations (24h) |
| EXPIRY_THRESHOLD_DAYS | Config | Days before expiry to trigger rotation (75d) |
| MCP_HOST | Config | MCP service hostname |
| MCP_PORT | Config | MCP service port |

**Validation Steps**:
- [ ] Service definition syntactically correct YAML
- [ ] All environment variables exposed
- [ ] Volume mounts accessible
- [ ] Depends_on correctly references mcp service
- [ ] Health check command works
- [ ] Can build image without errors
- [ ] Can start service container

**Validation Commands**:
```bash
cd infrastructure
docker-compose config | grep -A30 "jira-pat-rotator:"
docker-compose -f docker-compose.local.yml build jira-pat-rotator
docker-compose -f docker-compose.local.yml up jira-pat-rotator --no-start
```

**Dependencies**: Task 9 (adds feature flag to mcp in same file)

**Related Tasks**: Tasks 11-14 (provide Python service implementation)

---

## Python Pro Tasks

### TASK 11: Create ketchup_jira_pat_rotator/scheduler.py

**Status**: COMPLETED | **Estimated**: 40m | **Worktree**: chain-4

**Description**:
Create scheduler.py for the PAT rotation service. Implements 24-hour scheduling with distributed locking to prevent concurrent rotations across multiple instances.

**Files Modified**:
- Primary: `ketchup/ketchup_jira_pat_rotator/scheduler.py`
- Tests: Integration tests in rotation service test suite

**Key Implementation Details**:
- Use APScheduler for scheduling
- 24-hour rotation interval
- Distributed locking via DynamoDB (existing pattern)
- Async/await pattern for Python 3.12
- Comprehensive logging without exposing tokens
- Graceful shutdown handling

**Scheduler Implementation**:
```python
import asyncio
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .pat_monitor import PATMonitor
from .rotator import PATRotator

logger = logging.getLogger(__name__)

class PATRotationScheduler:
    """Manages scheduled PAT rotation with distributed locking"""

    def __init__(self, pat_monitor: PATMonitor, rotator: PATRotator):
        self.pat_monitor = pat_monitor
        self.rotator = rotator
        self.scheduler = AsyncIOScheduler()

    async def start(self) -> None:
        """Start the 24-hour rotation scheduler"""
        # Add job to run every 24 hours
        self.scheduler.add_job(
            self.rotation_job,
            trigger=IntervalTrigger(hours=24),
            id='pat-rotation',
            name='PAT Rotation Job',
            replace_existing=True
        )

        self.scheduler.start()
        logger.info("PAT rotation scheduler started (24-hour interval)")

    async def stop(self) -> None:
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("PAT rotation scheduler stopped")

    async def rotation_job(self) -> None:
        """Main rotation job - called every 24 hours"""
        logger.info("Starting scheduled PAT rotation job")

        try:
            # Check if rotation is needed
            needs_rotation = await self.pat_monitor.check_expiry()

            if needs_rotation:
                logger.info("PAT rotation needed - initiating rotation")
                result = await self.rotator.rotate()

                if result['success']:
                    logger.info("PAT rotation completed successfully")
                else:
                    logger.error(f"PAT rotation failed: {result['error']}")
            else:
                logger.info("PAT still valid - no rotation needed")

        except Exception as e:
            logger.error(f"Error during PAT rotation job: {e}", exc_info=True)
            # Don't re-raise - let scheduler continue
```

**Test Requirements**:
- [ ] Scheduler starts without errors
- [ ] Rotation job runs on 24-hour interval
- [ ] Distributed lock prevents concurrent execution
- [ ] Graceful shutdown stops scheduler
- [ ] Logging works without exposing tokens
- [ ] Error handling doesn't crash scheduler

**Validation Commands**:
```bash
cd ketchup/ketchup_jira_pat_rotator
python -m pytest tests/ -v --testNamePattern='scheduler'
```

**Dependencies**: Task 10 (Docker service stubs), Task 4 (jiraRequest ready)

**Related Tasks**: Task 12 (PATMonitor), Task 13 (PATRotator), Task 14 (main entry point)

---

### TASK 12: Create ketchup_jira_pat_rotator/pat_monitor.py

**Status**: COMPLETED | **Estimated**: 30m | **Worktree**: chain-4

**Description**:
Create pat_monitor.py for monitoring PAT expiry dates. Checks expiry status daily, triggers alerts when PAT is within 75 days of expiration.

**Files Modified**:
- Primary: `ketchup/ketchup_jira_pat_rotator/pat_monitor.py`
- Tests: Unit tests for expiry checking logic

**Key Implementation Details**:
- Load PAT expiry from AWS Secrets Manager
- Calculate days until expiry
- Trigger rotation alert if < 75 days remaining
- Track expiry status in DynamoDB metrics
- Async/await pattern for Python 3.12
- Comprehensive logging

**Monitor Implementation**:
```python
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Tuple
from boto3.session import Session

logger = logging.getLogger(__name__)

class PATMonitor:
    """Monitors PAT expiry and triggers rotation when needed"""

    EXPIRY_THRESHOLD_DAYS = 75  # Trigger rotation if < 75 days left

    def __init__(self, secrets_client, metrics_store):
        self.secrets_client = secrets_client
        self.metrics_store = metrics_store

    async def check_expiry(self) -> bool:
        """
        Check PAT expiry and determine if rotation is needed.
        Returns True if rotation should be triggered.
        """
        try:
            # Get current PAT expiry from Secrets Manager
            secret_response = await self.secrets_client.get_secret_value(
                SecretId='ketchup_jira_pat'
            )

            secret_dict = json.loads(secret_response['SecretString'])
            expiry_str = secret_dict.get('expiry')

            if not expiry_str:
                logger.error("PAT expiry date not found in secrets")
                return False

            # Parse expiry date
            expiry_date = datetime.fromisoformat(expiry_str)
            now = datetime.utcnow()
            days_until_expiry = (expiry_date - now).days

            # Check if rotation is needed
            needs_rotation = days_until_expiry < self.EXPIRY_THRESHOLD_DAYS

            logger.info(
                f"PAT expiry check: {days_until_expiry} days remaining "
                f"(threshold: {self.EXPIRY_THRESHOLD_DAYS}d) "
                f"- rotation needed: {needs_rotation}"
            )

            # Store metrics
            await self.metrics_store.record_expiry_check(
                days_until_expiry=days_until_expiry,
                rotation_triggered=needs_rotation,
                timestamp=now
            )

            return needs_rotation

        except Exception as e:
            logger.error(f"Error checking PAT expiry: {e}", exc_info=True)
            return False

    async def get_expiry_status(self) -> dict:
        """Get detailed expiry status"""
        try:
            secret_response = await self.secrets_client.get_secret_value(
                SecretId='ketchup_jira_pat'
            )

            secret_dict = json.loads(secret_response['SecretString'])
            expiry_str = secret_dict.get('expiry')

            if not expiry_str:
                return {'status': 'unknown', 'error': 'No expiry date'}

            expiry_date = datetime.fromisoformat(expiry_str)
            now = datetime.utcnow()
            days_until_expiry = (expiry_date - now).days

            return {
                'status': 'valid' if days_until_expiry > 0 else 'expired',
                'expiresAt': expiry_str,
                'daysUntilExpiry': days_until_expiry,
                'rotationNeeded': days_until_expiry < self.EXPIRY_THRESHOLD_DAYS
            }

        except Exception as e:
            logger.error(f"Error getting expiry status: {e}")
            return {'status': 'error', 'error': str(e)}
```

**Test Requirements**:
- [ ] Correctly loads PAT expiry from AWS Secrets
- [ ] Calculates days until expiry accurately
- [ ] Returns True when < 75 days until expiry
- [ ] Returns False when > 75 days until expiry
- [ ] Handles missing expiry gracefully
- [ ] Records metrics for monitoring
- [ ] Logs without exposing tokens

**Validation Commands**:
```bash
cd ketchup/ketchup_jira_pat_rotator
python -m pytest tests/test_pat_monitor.py -v
```

**Dependencies**: Task 11 (scheduler calls this)

**Related Tasks**: Task 13 (rotator uses monitor), Task 22 (metrics storage)

---

### TASK 13: Create ketchup_jira_pat_rotator/rotator.py orchestrator

**Status**: COMPLETED | **Estimated**: 45m | **Worktree**: chain-4

**Description**:
Create rotator.py orchestrator for safe PAT rotation with fallback mechanisms. Handles token creation, validation, storage, and rollback on failure.

**Files Modified**:
- Primary: `ketchup/ketchup_jira_pat_rotator/rotator.py`
- Tests: Integration tests for rotation workflow

**Key Implementation Details**:
- Call createPAT operation via MCP to create new token
- Validate new token works before committing
- Store new token in AWS Secrets Manager
- Implement rollback if new token fails
- Maintain backup PAT for fallback scenarios
- Comprehensive error handling and logging
- Track rotation metrics

**Rotator Implementation**:
```python
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Tuple
import json

logger = logging.getLogger(__name__)

class PATRotator:
    """Orchestrates safe PAT rotation with validation and rollback"""

    def __init__(self, mcp_client, secrets_client, backup_pat_service):
        self.mcp_client = mcp_client
        self.secrets_client = secrets_client
        self.backup_pat_service = backup_pat_service

    async def rotate(self) -> Dict[str, Any]:
        """
        Execute safe PAT rotation with fallback.
        Returns: {success: bool, newToken: str?, oldToken: str?, error: str?}
        """
        logger.info("Starting PAT rotation process")

        try:
            # Step 1: Get current PAT
            current_pat = await self._get_current_pat()

            # Step 2: Create new PAT via MCP
            logger.info("Creating new PAT token")
            new_token = await self._create_new_pat()

            if not new_token:
                logger.error("Failed to create new PAT token")
                return {'success': False, 'error': 'Token creation failed'}

            # Step 3: Validate new token works
            logger.info("Validating new PAT token")
            is_valid = await self._validate_token(new_token)

            if not is_valid:
                logger.error("New token validation failed - rolling back")
                await self._revoke_token(new_token)
                return {'success': False, 'error': 'Token validation failed'}

            # Step 4: Store new token in secrets
            logger.info("Storing new PAT token in AWS Secrets")
            await self._store_token(new_token)

            # Step 5: Keep old token as backup for 24 hours
            logger.info("Storing old PAT as backup")
            await self._store_backup_token(current_pat)

            # Step 6: Revoke old token (optional - keep for safety)
            # await self._revoke_token(current_pat)

            logger.info("PAT rotation completed successfully")

            return {
                'success': True,
                'newToken': '****' + new_token[-4:],  # Redacted for logs
                'oldToken': '****' + current_pat[-4:] if current_pat else None,
                'rotatedAt': datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"PAT rotation failed: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    async def _create_new_pat(self) -> str:
        """Create new PAT via MCP"""
        try:
            result = await self.mcp_client.call_operation(
                'createPAT',
                {'expiryDays': 90}
            )
            return result.get('token')
        except Exception as e:
            logger.error(f"Error creating PAT via MCP: {e}")
            return None

    async def _validate_token(self, token: str) -> bool:
        """Test token validity against JIRA"""
        try:
            # Use token to call JIRA API
            headers = {'Authorization': f'Bearer {token}'}
            response = await self.mcp_client.jira_request(
                'GET',
                '/rest/api/3/myself',
                headers=headers
            )
            return response.ok
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return False

    async def _get_current_pat(self) -> str:
        """Get current PAT from AWS Secrets"""
        try:
            secret = await self.secrets_client.get_secret_value(
                SecretId='ketchup_jira_pat'
            )
            secret_dict = json.loads(secret['SecretString'])
            return secret_dict.get('token')
        except Exception as e:
            logger.error(f"Error retrieving current PAT: {e}")
            return None

    async def _store_token(self, token: str) -> None:
        """Store new token in AWS Secrets"""
        try:
            expiry = (datetime.utcnow() + timedelta(days=90)).isoformat()
            secret_dict = {
                'token': token,
                'expiry': expiry,
                'rotatedAt': datetime.utcnow().isoformat()
            }

            await self.secrets_client.update_secret(
                SecretId='ketchup_jira_pat',
                SecretString=json.dumps(secret_dict)
            )
            logger.info("New PAT stored in AWS Secrets")
        except Exception as e:
            logger.error(f"Error storing PAT: {e}")
            raise

    async def _store_backup_token(self, token: str) -> None:
        """Store token as backup"""
        try:
            expiry = (datetime.utcnow() + timedelta(days=90)).isoformat()
            secret_dict = {
                'token': token,
                'expiry': expiry,
                'createdAt': datetime.utcnow().isoformat()
            }

            await self.secrets_client.update_secret(
                SecretId='ketchup_jira_backup_pat',
                SecretString=json.dumps(secret_dict)
            )
            logger.info("Backup PAT stored in AWS Secrets")
        except Exception as e:
            logger.error(f"Error storing backup PAT: {e}")

    async def _revoke_token(self, token: str) -> None:
        """Revoke token (optional cleanup)"""
        try:
            # Get token ID first
            token_id = await self._get_token_id(token)
            if token_id:
                await self.mcp_client.call_operation(
                    'revokePAT',
                    {'tokenId': token_id}
                )
                logger.info(f"Token {token_id} revoked")
        except Exception as e:
            logger.error(f"Error revoking token: {e}")
```

**Test Requirements**:
- [ ] Creates new PAT successfully
- [ ] Validates new token works
- [ ] Stores token in AWS Secrets
- [ ] Maintains backup token
- [ ] Rolls back on validation failure
- [ ] Handles all error scenarios
- [ ] Logs without exposing tokens
- [ ] Tracks rotation metrics

**Validation Commands**:
```bash
cd ketchup/ketchup_jira_pat_rotator
python -m pytest tests/test_rotator.py -v
```

**Dependencies**: Task 12 (PATMonitor), Task 5-6 (MCP operations)

**Related Tasks**: Task 14 (main.py orchestrates this), Task 22 (metrics)

---

### TASK 14: Create main.py entry point and TypedDI integration

**Status**: COMPLETED | **Estimated**: 30m | **Worktree**: chain-4

**Description**:
Create main.py service entry point with TypedDI dependency injection integration. Initializes all rotation service components following existing Ketchup service patterns.

**Files Modified**:
- Primary: `ketchup/ketchup_jira_pat_rotator/main.py`
- Related: Service initialization, dependency container setup

**Key Implementation Details**:
- Use TypedDI for dependency injection (existing pattern in Ketchup)
- Initialize scheduler, monitor, rotator, and MCP client
- Set up AWS Secrets client
- Configure logging with proper levels
- Add health check endpoint
- Graceful shutdown handling
- Follow existing service patterns from ketchup_status_updater, etc.

**Main Entry Point**:
```python
"""
PAT Rotation Service Entry Point
Manages automated JIRA PAT rotation with distributed scheduling
"""

import asyncio
import logging
import os
import sys
from typing import Optional

from typedi import Container, Inject
from dotenv import load_dotenv

from .scheduler import PATRotationScheduler
from .pat_monitor import PATMonitor
from .rotator import PATRotator
from .mcp_client import MCPClient
from .aws_secrets import SecretsManagerClient
from .metrics_schema import MetricsStore

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PATRotationService:
    """Main service container for PAT rotation"""

    def __init__(self):
        self.scheduler: Optional[PATRotationScheduler] = None
        self.running = False

    async def initialize(self) -> None:
        """Initialize service dependencies using TypedDI"""
        logger.info("Initializing PAT Rotation Service")

        # Register dependencies in TypedDI container
        container = Container

        # Register AWS Secrets Manager client
        secrets_client = SecretsManagerClient(
            region=os.getenv('AWS_REGION', 'eu-west-1')
        )
        container.set(SecretsManagerClient, secrets_client)

        # Register MCP client
        mcp_client = MCPClient(
            host=os.getenv('MCP_HOST', 'localhost'),
            port=int(os.getenv('MCP_PORT', '5000'))
        )
        container.set(MCPClient, mcp_client)

        # Register metrics store
        metrics_store = MetricsStore(
            table_name=os.getenv('METRICS_TABLE', 'jira_pat_rotation_metrics'),
            region=os.getenv('AWS_REGION', 'eu-west-1')
        )
        container.set(MetricsStore, metrics_store)

        # Register PAT Monitor
        pat_monitor = PATMonitor(
            secrets_client=secrets_client,
            metrics_store=metrics_store
        )
        container.set(PATMonitor, pat_monitor)

        # Register PAT Rotator
        pat_rotator = PATRotator(
            mcp_client=mcp_client,
            secrets_client=secrets_client,
            backup_pat_service=None  # Will be injected if needed
        )
        container.set(PATRotator, pat_rotator)

        # Create scheduler with injected dependencies
        self.scheduler = PATRotationScheduler(
            pat_monitor=pat_monitor,
            rotator=pat_rotator
        )

        logger.info("Service initialization complete")

    async def start(self) -> None:
        """Start the service"""
        logger.info("Starting PAT Rotation Service")

        try:
            await self.initialize()
            await self.scheduler.start()
            self.running = True

            logger.info("PAT Rotation Service started successfully")

            # Keep service running
            await self._run_until_shutdown()

        except Exception as e:
            logger.error(f"Failed to start service: {e}", exc_info=True)
            sys.exit(1)

    async def stop(self) -> None:
        """Stop the service gracefully"""
        logger.info("Stopping PAT Rotation Service")

        if self.scheduler:
            await self.scheduler.stop()

        self.running = False
        logger.info("PAT Rotation Service stopped")

    async def _run_until_shutdown(self) -> None:
        """Keep service running until shutdown signal"""
        try:
            # Run indefinitely until interrupted
            while self.running:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
            await self.stop()
        except Exception as e:
            logger.error(f"Service error: {e}", exc_info=True)
            await self.stop()

async def main() -> None:
    """Main entry point"""
    service = PATRotationService()
    await service.start()

if __name__ == '__main__':
    asyncio.run(main())
```

**TypedDI Configuration**:
```python
# container.py - Dependency injection setup
from typedi import Container, Inject, Service

@Service()
class SecretsManagerClient:
    def __init__(self):
        self.client = boto3.client('secretsmanager')

@Service()
class MCPClient:
    @Inject()
    def __init__(self, secrets: SecretsManagerClient):
        self.secrets = secrets

@Service()
class PATMonitor:
    @Inject()
    def __init__(
        self,
        secrets: SecretsManagerClient,
        metrics: MetricsStore
    ):
        self.secrets = secrets
        self.metrics = metrics

@Service()
class PATRotator:
    @Inject()
    def __init__(
        self,
        mcp: MCPClient,
        secrets: SecretsManagerClient,
        monitor: PATMonitor
    ):
        self.mcp = mcp
        self.secrets = secrets
        self.monitor = monitor
```

**Environment Variables Required**:
| Variable | Default | Purpose |
|----------|---------|---------|
| AWS_REGION | eu-west-1 | AWS region for Secrets and DynamoDB |
| AWS_ACCESS_KEY_ID | (required) | AWS credentials |
| AWS_SECRET_ACCESS_KEY | (required) | AWS credentials |
| MCP_HOST | localhost | MCP service hostname |
| MCP_PORT | 5000 | MCP service port |
| METRICS_TABLE | jira_pat_rotation_metrics | DynamoDB metrics table |
| LOG_LEVEL | INFO | Logging level |

**Test Requirements**:
- [ ] Service initializes without errors
- [ ] All dependencies properly injected via TypedDI
- [ ] Scheduler starts on service start
- [ ] Graceful shutdown stops scheduler
- [ ] Health check endpoint responds
- [ ] Logging works with proper levels
- [ ] Follows existing Ketchup service patterns

**Validation Commands**:
```bash
cd ketchup/ketchup_jira_pat_rotator
python -m pytest tests/test_main.py -v
python main.py  # Should start without errors
```

**Dependencies**: Task 13 (PATRotator), Task 12 (PATMonitor), Task 11 (Scheduler)

**Related Tasks**: Task 10 (Docker runs this), Task 14 is the final task in chain-4

---

### TASK 22: Add metrics schema and DynamoDB storage

**Status**: COMPLETED | **Estimated**: 45m | **Worktree**: chain-2

**Description**:
Add metrics schema for DynamoDB storage and tracking PAT rotation success, failures, and performance metrics. Enables monitoring and observability of the rotation service.

**Files Modified**:
- Primary: `ketchup/ketchup_jira_pat_rotator/metrics_schema.py`
- Tests: `tests/unit/test_metrics/test_metrics_schema.test.py`

**Key Implementation Details**:
- Define DynamoDB schema for rotation events
- Track success/failure metrics
- Record token expiry checks
- Monitor rotation duration
- Implement async DynamoDB client
- Add metrics query methods for dashboards
- Support metrics aggregation for reporting

**Metrics Schema**:
```python
"""
Metrics schema for PAT rotation service
Stores rotation events, expiry checks, and performance metrics in DynamoDB
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
import boto3
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger(__name__)

@dataclass
class RotationMetric:
    """Represents a single rotation metric event"""
    timestamp: str  # ISO datetime
    metric_type: str  # 'rotation' | 'expiry_check' | 'validation'
    success: bool
    duration_ms: int
    error_message: str = None
    token_id: str = None
    days_until_expiry: int = None
    details: Dict[str, Any] = None

class MetricsStore:
    """Stores and retrieves PAT rotation metrics from DynamoDB"""

    TABLE_NAME = 'jira_pat_rotation_metrics'

    def __init__(self, table_name: str = None, region: str = 'eu-west-1'):
        self.table_name = table_name or self.TABLE_NAME
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.table = self.dynamodb.Table(self.table_name)

    async def record_rotation(
        self,
        success: bool,
        duration_ms: int,
        error: str = None,
        new_token_id: str = None,
        **kwargs
    ) -> None:
        """Record a rotation event"""
        try:
            metric = RotationMetric(
                timestamp=datetime.utcnow().isoformat(),
                metric_type='rotation',
                success=success,
                duration_ms=duration_ms,
                error_message=error,
                token_id=new_token_id,
                details=kwargs
            )

            self.table.put_item(
                Item={
                    'pk': 'ROTATION',
                    'sk': metric.timestamp,
                    'success': metric.success,
                    'duration_ms': metric.duration_ms,
                    'error_message': metric.error_message,
                    'token_id': metric.token_id,
                    'details': json.dumps(metric.details or {})
                }
            )

            logger.info(
                f"Recorded rotation metric: "
                f"success={success}, duration={duration_ms}ms"
            )

        except Exception as e:
            logger.error(f"Error recording rotation metric: {e}")

    async def record_expiry_check(
        self,
        days_until_expiry: int,
        rotation_triggered: bool,
        timestamp: datetime = None
    ) -> None:
        """Record an expiry check event"""
        try:
            ts = timestamp or datetime.utcnow()

            self.table.put_item(
                Item={
                    'pk': 'EXPIRY_CHECK',
                    'sk': ts.isoformat(),
                    'days_until_expiry': days_until_expiry,
                    'rotation_triggered': rotation_triggered,
                    'timestamp': ts.isoformat()
                }
            )

            logger.info(
                f"Recorded expiry check: "
                f"days_remaining={days_until_expiry}, "
                f"rotation_triggered={rotation_triggered}"
            )

        except Exception as e:
            logger.error(f"Error recording expiry check: {e}")

    async def get_rotation_metrics(
        self,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """Retrieve rotation metrics for the last N days"""
        try:
            from_timestamp = (
                datetime.utcnow() - timedelta(days=days)
            ).isoformat()

            response = self.table.query(
                KeyConditionExpression=Key('pk').eq('ROTATION') &
                                     Key('sk').gte(from_timestamp),
                ScanIndexForward=False
            )

            return response.get('Items', [])

        except Exception as e:
            logger.error(f"Error retrieving rotation metrics: {e}")
            return []

    async def get_success_rate(self, days: int = 7) -> float:
        """Calculate rotation success rate for last N days"""
        try:
            metrics = await self.get_rotation_metrics(days)

            if not metrics:
                return 0.0

            successful = sum(1 for m in metrics if m.get('success'))
            total = len(metrics)

            return (successful / total) * 100

        except Exception as e:
            logger.error(f"Error calculating success rate: {e}")
            return 0.0

    async def get_average_duration(self, days: int = 7) -> int:
        """Calculate average rotation duration in milliseconds"""
        try:
            metrics = await self.get_rotation_metrics(days)

            if not metrics:
                return 0

            durations = [m.get('duration_ms', 0) for m in metrics]
            return int(sum(durations) / len(durations))

        except Exception as e:
            logger.error(f"Error calculating average duration: {e}")
            return 0
```

**DynamoDB Table Schema**:
```yaml
TableName: jira_pat_rotation_metrics
AttributeDefinitions:
  - AttributeName: pk
    AttributeType: S
  - AttributeName: sk
    AttributeType: S

KeySchema:
  - AttributeName: pk
    KeyType: HASH
  - AttributeName: sk
    KeyType: RANGE

BillingMode: PAY_PER_REQUEST

TTL:
  AttributeName: ttl
  Enabled: true  # Auto-delete old metrics after 90 days
```

**Test Requirements**:
- [ ] Records rotation success events
- [ ] Records rotation failure events
- [ ] Records expiry check events
- [ ] Queries metrics by date range
- [ ] Calculates success rate accurately
- [ ] Calculates average duration
- [ ] Handles DynamoDB errors gracefully
- [ ] Logs without exposing tokens

**Validation Commands**:
```bash
cd ketchup/ketchup_jira_pat_rotator
python -m pytest tests/test_metrics/test_metrics_schema.test.py -v
```

**Dependencies**: Task 10 (DynamoDB available), Task 12 (PATMonitor calls this)

**Related Tasks**: Task 13 (PATRotator calls for metrics), Task 24 (documentation includes metrics)

---

## Technical Documentation Specialist Tasks

### TASK 24: Document PAT rotation system comprehensively

**Status**: COMPLETED | **Estimated**: 3h | **Worktree**: independent-1

**Description**:
Create comprehensive documentation for the PAT rotation system. Includes architecture diagrams, operational runbooks, configuration guides, troubleshooting procedures, and deployment strategies.

**Files Modified**:
- Primary: `ketchup/docs/internal_documentation/jira_pat_rotation_system.md`

**Documentation Sections**:

1. **System Overview** (45min)
   - Architecture diagram showing MCP service, rotation service, AWS Secrets
   - Component relationships and data flows
   - Feature flag rollout strategy
   - Security considerations

2. **Configuration Guide** (45min)
   - Environment variables reference table
   - Feature flag settings and effects
   - AWS Secrets configuration
   - Docker Compose setup
   - Local development environment setup

3. **Operational Procedures** (30min)
   - Normal PAT rotation workflow
   - Backup PAT failover procedure
   - Manual token management (if needed)
   - Monitoring and alerting setup
   - Emergency procedures

4. **Troubleshooting Guide** (20min)
   - Common errors and solutions
   - Log analysis techniques
   - Performance tuning
   - Testing token validity
   - Fallback mechanism validation

5. **Deployment Strategy** (20min)
   - Feature flag rollout phases
   - Pre-deployment validation checklist
   - Production deployment steps
   - Rollback procedures
   - Nov 30 migration timeline

**Documentation Output**:
File: `/ketchup/docs/internal_documentation/jira_pat_rotation_system.md`

Table of Contents:
```
# JIRA PAT Rotation System Documentation

## 1. System Overview
   1.1 Architecture Diagram
   1.2 Component Descriptions
   1.3 Data Flows
   1.4 Feature Flag Strategy
   1.5 Security Model

## 2. Configuration Reference
   2.1 Environment Variables
   2.2 AWS Secrets Configuration
   2.3 Docker Compose Setup
   2.4 Local Development Environment
   2.5 Production Configuration

## 3. Operational Procedures
   3.1 Normal Rotation Workflow
   3.2 Backup PAT Failover
   3.3 Manual Token Management
   3.4 Monitoring & Alerting
   3.5 Emergency Procedures

## 4. Troubleshooting Guide
   4.1 Common Errors
   4.2 Log Analysis
   4.3 Performance Tuning
   4.4 Testing & Validation
   4.5 Fallback Mechanism

## 5. Deployment & Migration
   5.1 Feature Flag Rollout Phases
   5.2 Pre-Deployment Checklist
   5.3 Production Deployment Steps
   5.4 Rollback Procedures
   5.5 Nov 30 Migration Plan

## 6. Monitoring & Metrics
   6.1 Key Metrics Dashboard
   6.2 Alert Thresholds
   6.3 Health Checks
   6.4 Success Rate Tracking

## 7. FAQ & Best Practices
   7.1 Frequently Asked Questions
   7.2 Best Practices
   7.3 Anti-Patterns to Avoid
   7.4 Related Services
```

**Key Documentation Artifacts**:
- ASCII architecture diagram
- Configuration reference table (20+ variables)
- Workflow diagrams (Mermaid format)
- Troubleshooting decision tree
- Checklist for deployment phases
- Sample log output with annotations
- Emergency contact procedures

**Test Requirements** (for documentation):
- [ ] All code examples are correct and tested
- [ ] Configuration references match implementation
- [ ] Environment variable names are accurate
- [ ] Deployment steps are validated
- [ ] Troubleshooting procedures are realistic
- [ ] Architecture diagrams match actual code
- [ ] Links to relevant files are correct

**Validation**:
- [ ] Documentation builds without errors
- [ ] No broken internal links
- [ ] All referenced files exist
- [ ] Code examples match actual implementation
- [ ] Diagrams are readable and clear
- [ ] Procedures tested and validated
- [ ] Documentation reviewed by technical stakeholders

**Related Files**:
- Plan documents: `/docs/plans/jira-pat-migration/`
- Implementation files: `/ketchup/corp_jira_mcp/`, `/ketchup/ketchup_jira_pat_rotator/`
- Configuration: `/infrastructure/docker-compose.yml`
- Tests: `/tests/unit/test_*` directories

**Dependencies**: Depends on all implementation tasks (1-23) for accurate documentation

**Related Tasks**: All other tasks - documents the entire implementation

---

## Summary of Task Execution Cards

**Total Cards Created**: 17 tasks
**Total Estimated Duration**: 12h 05m
**Agent Distribution**: 4 specialists (typescript-pro, backend-developer, python-pro, technical-documentation-specialist)

**Key Interdependencies**:
- chain-1 (Tasks 1-4, 19-21): Sequential MCP foundation
- chain-2 (Tasks 5-6, 22): Sequential operations and metrics
- independent-3 (Tasks 9-10): Parallel Docker configuration
- chain-4 (Tasks 11-14): Sequential Python rotation service
- independent-1 (Task 24): Parallel documentation

**Critical Path**: chain-1 → chain-2 → chain-4 (dependencies must complete in order for later groups)

---

**Generated**: 2025-11-19
**Document Type**: Task Execution Reference Cards
**Status**: Ready for Implementation Team Reference
