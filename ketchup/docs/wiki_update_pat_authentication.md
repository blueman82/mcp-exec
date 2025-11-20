# Ketchup Wiki Content: PAT Authentication

## Part 1: Section Updates for Existing Content

### Section 13 Update (Production Services - Singleton Services List)

Add to the existing singleton services list:

```markdown
**Singleton Services** (prod1 only):
- `ketchup-status-updater` - Hourly status updates
- `ketchup-metadata-updater` - Channel metadata scanner
- `ketchup-jira-reporter` - JIRA automation
- `ketchup-maintenance-fetcher` - Maintenance detection
- **`ketchup-jira-pat-rotator` - JIRA PAT token rotation (checks every 24 hours)**

These services are explicitly stopped/removed on prod2 during deployment to prevent duplicate scheduled jobs and conflicting operations.
```

### Section 14 Update (Feature Flags Table)

Add to the existing feature flags table:

```markdown
| Feature | Environment Variables | Description | Status |
|---------|----------------------|-------------|--------|
| JIRA PAT Auth | `JIRA_USE_PAT_AUTH=true` | Personal Access Token authentication for JIRA (replaces Basic Auth) | **Enabled** (line 152 docker-compose.yml) |
```

---

## Part 2: New Section 25 - JIRA Authentication (PAT)

```markdown
## 25. JIRA Authentication (PAT)

### Overview

Ketchup uses **Personal Access Tokens (PATs)** for JIRA authentication, replacing the deprecated Basic Authentication (username/password) method. JIRA will fully deprecate Basic Auth on **November 30, 2025**.

**Why PATs?**
- **Security**: Token-based authentication is more secure than username/password
- **Compliance**: Aligns with Adobe's enterprise security standards
- **Mandatory**: JIRA API will reject Basic Auth after Nov 30, 2025
- **Automated rotation**: System automatically rotates tokens before expiry

**Key Constraint**: PATs have a maximum 90-day expiry (mandatory, cannot be extended). This requires automated rotation to maintain continuous JIRA access.

---

### Production Configuration

PAT configuration is stored in **AWS Secrets Manager** under `Ketchup_Token_Secrets`:

| Secret Key | Purpose | Example Value |
|-----------|---------|---------------|
| `ketchup_jira_pat` | Primary PAT token | `ATAT1234567890ABCDEF...` |
| `ketchup_jira_pat_expiry` | Token expiry date (ISO 8601) | `2025-12-15T10:30:00Z` |
| `ketchup_jira_pat_id` | Token ID for revocation tracking | `649e9d1c1234` |

**Note**: There are NO backup PAT fields. The system maintains only one active PAT at a time with automated rotation before expiry.

**Feature Flag** (docker-compose.yml line 152):
```yaml
JIRA_USE_PAT_AUTH=true  # Enabled in production
```

---

### Operational Notes

#### Automatic Rotation Schedule

The `ketchup-jira-pat-rotator` service runs as a **singleton on prod1** and performs the following:

| Check | Frequency | Action |
|-------|-----------|--------|
| Rotation check | Every 24 hours | Checks if PAT needs rotation |
| Health file update | Every minute | Updates `/tmp/jira_pat_rotator_health` |
| Rotation trigger | 15 days before expiry | Creates new PAT when <75 days remain |

**Rotation Flow**:
1. Check if PAT is within 15 days of expiry (90 - 15 = 75 days)
2. Create new PAT via MCP JIRA service
3. Validate new PAT works with JIRA API
4. Update AWS Secrets Manager with new token
5. Revoke old PAT
6. Send success alert to #ketchup-alerts

**Safety**: Failed rotations do NOT break JIRA access. The old PAT remains active and an alert is sent to #ketchup-alerts.

#### Monitoring & Alerts

All rotation events are reported to **#ketchup-alerts** (Channel ID: C0957H8ASH2):

**Success Alert**:
```
✅ JIRA PAT rotation successful
Old token ID: 649e9d1c1234
New token created: 2025-11-19T10:30:00Z
New expiry: 2026-02-17T10:30:00Z
Next rotation check: 2025-12-03
```

**Failure Alert**:
```
❌ JIRA PAT rotation failed
Error: AWS Secrets Manager connection timeout
Stage: secrets_update
Old PAT: Still active and valid (65 days remaining)
Action: Verify AWS network connectivity, escalate if persistent
```

**Alert Cooldown**: 1 hour per alert category (prevents spam during repeated failures)

#### Health Checks

**Health File**: `/tmp/jira_pat_rotator_health`
- Updated every minute by the rotation service
- Format: `timestamp:status:last_rotation:next_rotation`
- Status values: `healthy`, `failed`, `critical`

**Docker Health Check** (docker-compose.yml line 342):
```bash
test: ["CMD", "/app/scripts/healthcheck-jira-pat-rotator.sh"]
interval: 300s  # Check every 5 minutes
```

---

### Troubleshooting

#### Scenario 1: JIRA Operations Failing with 401 Unauthorized

**Symptoms**: JIRA requests return 401 errors in application logs

**Diagnosis**:
```bash
# Check current PAT in AWS Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id Ketchup_Token_Secrets \
  --region eu-west-1 \
  --query 'SecretString' | jq -r | jq '.ketchup_jira_pat_expiry'

# Compare expiry date to current date
date -u +"%Y-%m-%dT%H:%M:%SZ"
```

**Resolution**:
1. **If PAT expired**: Create new PAT immediately via iPaaS console and update secrets
2. **If not expired**: Check JIRA API connectivity and token format
3. **Check feature flag**: Verify `JIRA_USE_PAT_AUTH=true` in docker-compose.yml

**Emergency Fix**:
```bash
# SSH to prod1
ssh ketchup-prod1.campaign.adobe.com

# Restart MCP JIRA service to reload secrets
sudo docker-compose -f /opt/ketchup/docker-compose.yml restart mcp-jira
```

#### Scenario 2: Rotation Alert Received

**What it means**: Automated rotation failed, but **old PAT is still valid**

**Immediate actions**:
1. Check the alert message for specific error (creation, validation, secrets_update, revoke)
2. Verify days remaining on current PAT (check alert or AWS Secrets Manager)
3. If >14 days remaining: Wait 24 hours for automatic retry
4. If <14 days remaining: Investigate immediately

**Common causes**:
- **Network timeout**: Temporary, will retry in 24 hours
- **MCP service down**: Check `docker ps | grep mcp-jira`
- **AWS Secrets Manager access**: Verify IAM permissions
- **JIRA API down**: Check JIRA status page

**Escalation criteria**:
- PAT expires in <7 days and rotation still failing
- Multiple rotation failures across 3+ days
- Critical alert received ("No valid JIRA PAT available")

#### Scenario 3: Rotation Service Not Running

**Diagnosis**:
```bash
# SSH to prod1 (singleton deployment)
ssh ketchup-prod1.campaign.adobe.com

# Check if service is running
sudo docker ps | grep pat-rotator

# Check service logs
sudo docker logs ketchup-jira-pat-rotator | tail -100

# Check health file (should update every minute)
cat /tmp/jira_pat_rotator_health
```

**Resolution**:
```bash
# Restart service
sudo docker-compose -f /opt/ketchup/docker-compose.yml restart ketchup-jira-pat-rotator

# Verify it's running
sudo docker ps | grep pat-rotator

# Monitor logs for errors
sudo docker logs -f ketchup-jira-pat-rotator
```

#### Scenario 4: Manual PAT Creation Required

**When needed**:
- Rotation service failed repeatedly and PAT expires in <7 days
- Emergency recovery after PAT expiry
- Initial system setup

**Steps**:
1. Access iPaaS console (Adobe internal authentication required)
2. Navigate to JIRA PAT management
3. Create new PAT with 90-day expiry
4. Copy token value, expiry date, and token ID
5. Update AWS Secrets Manager:
   ```bash
   aws secretsmanager update-secret \
     --secret-id Ketchup_Token_Secrets \
     --region eu-west-1 \
     --secret-string '{
       "ketchup_jira_pat": "ATAT...",
       "ketchup_jira_pat_expiry": "2026-02-17T10:30:00Z",
       "ketchup_jira_pat_id": "649e9d1c1234"
     }'
   ```
6. Restart MCP JIRA service to reload secrets
7. Verify JIRA operations work correctly

---

### Technical Documentation

For detailed technical implementation, see:

- **[JIRA PAT Rotation System Documentation](https://github.com/OneAdobe/ketchup/blob/main/docs/internal_documentation/jira_pat_rotation_system.md)** - Complete system architecture, failure modes, and code references
- **[KETCHUP.md - Section on Infrastructure](https://github.com/OneAdobe/ketchup/blob/main/KETCHUP.md#infrastructure)** - Docker container configuration and deployment details
- **[docker-compose.yml (line 152)](https://github.com/OneAdobe/ketchup/blob/main/infrastructure/docker-compose.yml#L152)** - Feature flag and environment configuration

**Key Code Locations**:
- Configuration: `corp_jira_mcp/corp_jira_mcp/common/config.ts`
- Authentication: `corp_jira_mcp/corp_jira_mcp/utils.ts`
- Rotation Service: `ketchup_jira_pat_rotator/` (singleton on prod1)
- Deployment Script: `infrastructure/deploy-ketchup.sh` (line 518: excludes rotator from prod2)

**Related Services**:
- MCP JIRA service handles all JIRA API authentication
- FastAPI app loads PAT configuration on startup
- All JIRA operations use PAT when `JIRA_USE_PAT_AUTH=true`
```

---

## Instructions for Wiki Update

1. **Update Section 13** - Add PAT rotator to singleton services list
2. **Update Section 14** - Add JIRA_USE_PAT_AUTH to feature flags table
3. **Add Section 25** - Copy entire "JIRA Authentication (PAT)" section

This content matches the existing Ketchup wiki style and provides operational guidance for on-call engineers.
