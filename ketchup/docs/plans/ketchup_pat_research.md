🔐 JIRA Personal Access Tokens (PAT) Migration Research Report

Executive Summary

Ketchup currently authenticates with Adobe's JIRA instance via the iPaaS proxy using username/password authentication, which will be DEPRECATED at the end of November 2025. This report provides comprehensive research on JIRA Personal Access Tokens (PATs), the required migration
strategy, and implementation considerations for Ketchup's multi-service architecture.

★ Insight ─────────────────────────────────────
- Critical Timeline: Basic authentication deprecation deadline is November 30, 2025 - less than 20 days away
- Current Gap: Ketchup's MCP JIRA service uses username/password in iPaaS mode (config.ts:89-90, utils.js:115-120)
- Service Account Complexity: Generic accounts require manual browser-based PAT generation with Okta 2FA or MFA exemption
─────────────────────────────────────────────────

---
1. Current Authentication Architecture

1.1 Authentication Flow

┌──────────────────────────────────────────────────────────────────┐
│                   CURRENT AUTHENTICATION FLOW                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Ketchup Service (Python)                                       │
│       ↓                                                          │
│  IMSTokenManager                                                │
│       ↓                                                          │
│  MCP JIRA Service (Node.js) - Port 8081                        │
│   [USE_IPAAS=true mode]                                         │
│       ↓                                                          │
│   Headers sent to iPaaS:                                        │
│   • Authorization: <IMS_TOKEN>                                  │
│   • Api_key: <API_KEY>                                          │
│   • Username: <JIRA_USERNAME>  ← WILL BE DEPRECATED            │
│   • Password: <JIRA_PASSWORD>  ← WILL BE DEPRECATED            │
│       ↓                                                          │
│  iPaaS Proxy (https://ipaasapi.adobe-services.com)            │
│       ↓                                                          │
│  JIRA API (https://jira.corp.adobe.com)                        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

1.2 Key Files & Configuration

MCP JIRA Service (corp_jira_mcp/):
- common/config.ts:40-46 - Auth configuration with username/password
- common/utils.js:108-123 - iPaaS header construction
- env-aws.ts:30-33 - AWS Secrets Manager credential mapping
- operations/auth.js:10-25 - Authentication test endpoint

Python Services:
- packages/integrations/async_mcp_client.py:192-203 - IMS token header builder
- jira_reporter/jira_service.py:145-153 - Bearer token authentication

Docker Configuration:
- infrastructure/docker-compose.yml:143-152 - MCP JIRA environment variables

AWS Secrets Manager:
- Secret Name: Ketchup_Token_Secrets
- Current Keys: ipaas_username, ipaas_password, ipaas_api_key, ims_access_token

---
2. JIRA PAT Requirements & Policies

2.1 PAT Fundamentals

| Aspect        | Details                                                             |
|---------------|---------------------------------------------------------------------|
| Purpose       | Secure alternative to username/password for REST API authentication |
| Scope         | Required ONLY for REST API calls (not manual browser usage)         |
| Availability  | All environments (DEV, STAGE, PROD)                                 |
| Account Types | Human users AND generic/service accounts                            |
| Deprecation   | Basic auth (username/password) deprecated November 30, 2025         |

2.2 PAT Policies & Limitations

| Policy                     | Value                       | Enforcement                         |
|----------------------------|-----------------------------|-------------------------------------|
| Maximum Expiry             | 90 days                     | Mandatory, cannot be extended       |
| Maximum Tokens             | 10 per account              | Hard limit                          |
| Expired Token Cleanup      | Automatic daily at midnight | Confirmed by Jira team (Keith Shaw) |
| No-Expiry Tokens           | Oversight, being fixed      | Will enforce 90-day max             |
| Minimum Tokens Recommended | 2 with staggered expiration | Best practice for backup            |

★ Insight ─────────────────────────────────────
- Token Limit Pitfall: The 10-token limit can cause creation failures if old tokens aren't cleaned up (Juliette Lemaitre's feedback)
- Rotation Timing: Create new tokens every 30-60 days, well before 90-day expiry
- Backup Strategy: Stagger expiration dates (e.g., Token1 expires Day 90, Token2 expires Day 95) to avoid simultaneous expiration
─────────────────────────────────────────────────

2.3 Service Account Considerations for Ketchup

Challenge: Ketchup uses a generic/service account for JIRA operations.

Initial PAT Generation Requirements:
1. Manual Browser Login: Must login via browser at least once to generate first PAT
2. Okta 2FA Options:
  - Option A: Set up authenticator for the service account (shared team access risk)
  - Option B: Request MFA exemption via ServiceDesk ticket (recommended for Ketchup)
3. Service Account Best Practices:
  - Multiple admins in IAM (https://iam.corp.adobe.com)
  - Email address for account (will be required for Atlassian Cloud migration)
  - Documented ownership in wiki/git

Service Account Setup Process:
# 1. Open service account settings in IAM
https://adobe.okta.com/enduser/settings  # Production
https://adobe.oktapreview.com/enduser/settings  # Preview

# 2. Login as service account via Opera browser trick
# At Okta prompt, click "back to sign in"
# Enter service account username → Next
# Enter service account password → Next
# Set up authenticator (if no MFA exemption)

# 3. Navigate to JIRA PAT management
https://jira.corp.adobe.com/secure/ViewProfile.jspa
# Profile → Personal Access Tokens → Create Token

---
3. PAT Authentication Formats

3.1 Direct JIRA API Authentication

Current (Basic Auth - DEPRECATED):
// corp_jira_mcp/common/utils.js:94-98
const authString = `${email}:${token}`;
headers["Authorization"] = `Basic ${Buffer.from(authString).toString('base64')}`;

Required (PAT Bearer Token):
// NEW FORMAT - Replace lines 94-98
headers["Authorization"] = `Bearer ${PAT_TOKEN}`;

cURL Example:
# Old (deprecated):
curl -H "Authorization: Basic $(echo -n 'email:password' | base64)" \
  https://jira.corp.adobe.com/rest/api/2/myself

# New (PAT):
curl -H "Authorization: Bearer <YOUR_PAT_TOKEN>" \
  https://jira.corp.adobe.com/rest/api/2/myself

3.2 iPaaS Proxy Authentication (Ketchup's Current Mode)

Current (username/password - DEPRECATED):
// corp_jira_mcp/common/utils.js:108-123
const headers = {
  "Authorization": `${imsToken}`,          // IMS token for iPaaS
  "Api_key": apiKey,                       // iPaaS routing key
  "Username": username,                    // ← DEPRECATED
  "Password": password                     // ← DEPRECATED
};

Required (PAT + iPaaS):
// NEW FORMAT - Replace Username/Password headers
const headers = {
  "Authorization": `${imsToken}`,          // IMS token for iPaaS (keep)
  "Api_key": apiKey,                       // iPaaS routing key (keep)
  "x-authorization": `Bearer ${PAT_TOKEN}` // PAT for JIRA auth (NEW)
};

Source: Don Imfeld's Slack message (July 29, 2025):
"For those going through iPaaS you need to wrap the PAT into an x-authorization header."

cURL Example:
# Old (deprecated):
curl -X GET "https://ipaasapi.adobe-services.com/jira/rest/api/2/myself" \
  -H "Authorization: ${IMS_TOKEN}" \
  -H "api_key: ${API_KEY}" \
  -H "Username: ${JIRA_USERNAME}" \
  -H "Password: ${JIRA_PASSWORD}"

# New (PAT):
curl -X GET "https://ipaasapi.adobe-services.com/jira/rest/api/2/myself" \
  -H "Authorization: ${IMS_TOKEN}" \
  -H "api_key: ${API_KEY}" \
  -H "x-authorization: Bearer ${PAT_TOKEN}"

---
4. PAT Lifecycle Management

4.1 PAT Creation (Manual - First Time)

Via Browser UI (https://jira.corp.adobe.com/secure/ViewProfile.jspa):
1. Navigate to Profile → Personal Access Tokens
2. Click Create token
3. Enter token name (e.g., ketchup-prod-token-1)
4. Set expiration: 90 days (maximum)
5. Click Create and copy token immediately (won't be shown again)
6. Store in AWS Secrets Manager

Screenshot Reference: See wiki https://wiki.corp.adobe.com/display/JIRA/PAT+-+Personal+Access+Tokens

4.2 PAT Creation (Programmatic)

API Endpoint: POST /rest/pat/latest/tokens

Authentication Required: Existing PAT or username/password (during transition period)

Request Example:
# Using existing PAT:
curl -X POST https://jira.corp.adobe.com/rest/pat/latest/tokens \
  -H "Authorization: Bearer ${EXISTING_PAT}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ketchup-prod-token-2",
    "expirationDuration": 90
  }'

# Using username/password (only during transition):
curl -X POST https://jira.corp.adobe.com/rest/pat/latest/tokens \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ketchup-prod-token-2",
    "expirationDuration": 90
  }' \
  --user "username:password"

Response:
{
  "id": "682",
  "name": "ketchup-prod-token-2",
  "createdAt": "2025-11-12T10:30:00Z",
  "expiresAt": "2026-02-10T10:30:00Z",
  "token": "NDcxMjg5NzYyODU5Oj5rz..."  // Copy this value!
}

4.3 PAT Validation

Test Endpoint: GET /rest/api/2/myself

curl -H "Authorization: Bearer ${NEW_PAT}" \
  https://jira.corp.adobe.com/rest/api/2/myself

Expected Response (200 OK):
{
  "self": "https://jira.corp.adobe.com/rest/api/2/user?username=jiracjm",
  "name": "jiracjm",
  "emailAddress": "service-account@adobe.com",
  "displayName": "Ketchup Service Account",
  "active": true
}

4.4 PAT Listing

API Endpoint: GET /rest/pat/latest/tokens

curl -H "Authorization: Bearer ${PAT}" \
  https://jira.corp.adobe.com/rest/pat/latest/tokens

Response:
[
  {
    "id": "682",
    "name": "ketchup-prod-token-1",
    "createdAt": "2025-10-15T10:00:00Z",
    "expiresAt": "2026-01-13T10:00:00Z",
    "lastAccessed": "2025-11-12T09:45:00Z"
  },
  {
    "id": "683",
    "name": "ketchup-prod-token-2",
    "createdAt": "2025-10-20T10:00:00Z",
    "expiresAt": "2026-01-18T10:00:00Z",
    "lastAccessed": null
  }
]

4.5 PAT Deletion/Revocation

API Endpoint: DELETE /rest/pat/latest/tokens/{tokenId}

# Get token ID first:
TOKEN_ID=$(curl -s -H "Authorization: Bearer ${PAT}" \
  https://jira.corp.adobe.com/rest/pat/latest/tokens | \
  jq -r '.[0].id')

# Delete old token:
curl -X DELETE \
  https://jira.corp.adobe.com/rest/pat/latest/tokens/${TOKEN_ID} \
  -H "Authorization: Bearer ${PAT}"

Success Response: 204 No Content

---
5. PAT Rotation Strategy

5.1 Recommended Rotation Pattern

┌────────────────────────────────────────────────────────────────┐
│              PAT ROTATION STRATEGY (90-DAY CYCLE)              │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Day 0: Initial Setup                                         │
│    • Create Token1 (expires Day 90)                           │
│    • Update AWS Secrets: JIRA_PRIMARY_PAT=Token1              │
│    • Deploy to production                                     │
│                                                                │
│  Day 7: Create Backup                                         │
│    • Create Token2 (expires Day 97)                           │
│    • Update AWS Secrets: JIRA_BACKUP_PAT=Token2               │
│    • Keep Token1 as primary                                   │
│                                                                │
│  Day 60: Create Next Primary                                  │
│    • Create Token3 (expires Day 150)                          │
│    • Validate Token3 works                                    │
│    • Update AWS Secrets: JIRA_PRIMARY_PAT=Token3              │
│    • Deploy to production                                     │
│    • Delete Token1 (old primary)                              │
│                                                                │
│  Day 67: Create Next Backup                                   │
│    • Create Token4 (expires Day 157)                          │
│    • Update AWS Secrets: JIRA_BACKUP_PAT=Token4               │
│    • Delete Token2 (old backup)                               │
│                                                                │
│  Repeat cycle every 60 days...                                │
│                                                                │
└────────────────────────────────────────────────────────────────┘

5.2 Rotation Implementation (Python)

Based on Don Imfeld's script from Slack conversation:

#!/usr/bin/env python3
"""
JIRA PAT Rotation Script for Ketchup
Rotates PAT tokens every 60 days with 90-day expiration
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional
import httpx

from packages.secrets.manager import SecretsManager
from packages.core.logging import setup_logger

logger = setup_logger(__name__)

JIRA_API_BASE = "https://jira.corp.adobe.com"
PAT_ENDPOINT = f"{JIRA_API_BASE}/rest/pat/latest/tokens"


class PATRotationManager:
    """Manages JIRA PAT rotation lifecycle."""

    def __init__(self, secrets_manager: SecretsManager):
        self.secrets_manager = secrets_manager

    async def rotate_pat(
        self,
        token_name: str = "ketchup-prod",
        expiration_days: int = 90
    ) -> dict:
        """
        Rotate PAT token by creating new one and deleting old one.

        Args:
            token_name: Name prefix for the token
            expiration_days: Days until expiration (max 90)

        Returns:
            dict with new token info and rotation status
        """
        # 1. Get current PAT from secrets
        secrets = await self.secrets_manager.get_all_secrets()
        current_pat = secrets.get("jira_primary_pat")

        if not current_pat:
            raise ValueError("No current PAT found in secrets")

        # 2. Create new PAT
        new_token_name = f"{token_name}-{datetime.now().strftime('%Y%m%d')}"
        logger.info(f"Creating new PAT: {new_token_name}")

        new_pat = await self._create_pat(
            current_pat=current_pat,
            name=new_token_name,
            expiration_days=expiration_days
        )

        # 3. Validate new PAT works
        logger.info("Validating new PAT...")
        is_valid = await self._validate_pat(new_pat["token"])

        if not is_valid:
            raise Exception("New PAT validation failed!")

        # 4. Update AWS Secrets Manager
        logger.info("Updating AWS Secrets Manager...")
        await self.secrets_manager.update_secret(
            key="jira_primary_pat",
            value=new_pat["token"]
        )

        # 5. Delete old PAT tokens (keep only newest 2)
        logger.info("Cleaning up old PAT tokens...")
        await self._cleanup_old_tokens(current_pat, keep_count=2)

        return {
            "success": True,
            "new_token_id": new_pat["id"],
            "new_token_name": new_pat["name"],
            "expires_at": new_pat["expiresAt"],
            "rotation_timestamp": datetime.now().isoformat()
        }

    async def _create_pat(
        self,
        current_pat: str,
        name: str,
        expiration_days: int
    ) -> dict:
        """Create new PAT using existing PAT for auth."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                PAT_ENDPOINT,
                headers={
                    "Authorization": f"Bearer {current_pat}",
                    "Content-Type": "application/json"
                },
                json={
                    "name": name,
                    "expirationDuration": expiration_days
                },
                timeout=30.0
            )

            if response.status_code != 201:
                raise Exception(
                    f"Failed to create PAT: {response.status_code} - {response.text}"
                )

            return response.json()

    async def _validate_pat(self, pat: str) -> bool:
        """Validate PAT by calling /myself endpoint."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{JIRA_API_BASE}/rest/api/2/myself",
                    headers={"Authorization": f"Bearer {pat}"},
                    timeout=10.0
                )
                return response.status_code == 200
            except Exception as e:
                logger.error(f"PAT validation failed: {e}")
                return False

    async def _cleanup_old_tokens(
        self,
        current_pat: str,
        keep_count: int = 2
    ) -> None:
        """Delete old PAT tokens, keeping only the newest N tokens."""
        async with httpx.AsyncClient() as client:
            # List all tokens
            response = await client.get(
                PAT_ENDPOINT,
                headers={"Authorization": f"Bearer {current_pat}"},
                timeout=10.0
            )

            if response.status_code != 200:
                logger.warning("Failed to list tokens for cleanup")
                return

            tokens = response.json()

            # Sort by creation date (newest first)
            tokens.sort(
                key=lambda t: t.get("createdAt", ""),
                reverse=True
            )

            # Delete tokens beyond keep_count
            for token in tokens[keep_count:]:
                token_id = token.get("id")
                token_name = token.get("name")

                logger.info(f"Deleting old token: {token_name} (ID: {token_id})")

                delete_response = await client.delete(
                    f"{PAT_ENDPOINT}/{token_id}",
                    headers={"Authorization": f"Bearer {current_pat}"},
                    timeout=10.0
                )

                if delete_response.status_code == 204:
                    logger.info(f"Successfully deleted token {token_id}")
                else:
                    logger.warning(
                        f"Failed to delete token {token_id}: "
                        f"{delete_response.status_code}"
                    )


async def main():
    """Main rotation script."""
    logger.info("Starting JIRA PAT rotation")

    secrets_manager = SecretsManager()
    await secrets_manager.setup()

    rotation_manager = PATRotationManager(secrets_manager)

    result = await rotation_manager.rotate_pat()

    logger.info(f"PAT rotation complete: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())

★ Insight ─────────────────────────────────────
- Automated Rotation: The script above can be triggered via cron job or AWS Lambda on a 60-day schedule
- Failsafe Design: Validates new PAT before deleting old one, maintains backup token
- AWS Secrets Integration: Leverages existing SecretsManager class used throughout Ketchup
─────────────────────────────────────────────────

5.3 Secrets Manager Schema Update

Current AWS Secrets (Ketchup_Token_Secrets):
{
  "ipaas_username": "service-account",
  "ipaas_password": "...",  // ← Remove after migration
  "ipaas_api_key": "...",
  "ims_access_token": "..."
}

Updated Schema with PATs:
{
  "ipaas_username": "service-account",  // Keep for reference
  "ipaas_api_key": "...",               // Keep (still needed for iPaaS)
  "ims_access_token": "...",            // Keep (still needed for iPaaS)
  "jira_primary_pat": "NDcxMjg5...",   // NEW - Primary PAT
  "jira_backup_pat": "OTYyMzQ1...",    // NEW - Backup PAT
  "jira_pat_rotation_date": "2025-11-12",  // NEW - Last rotation
  "jira_pat_expiry_date": "2026-02-10"     // NEW - Primary expiry
}

---
6. Implementation Changes Required

6.1 MCP JIRA Service Changes

File: corp_jira_mcp/common/config.ts

Current (lines 40-46):
auth: {
  email: process.env.JIRA_EMAIL || '',
  token: process.env.JIRA_PERSONAL_ACCESS_TOKEN || '',
  imsToken: process.env.JIRA_IMS_TOKEN || '',
  apiKey: process.env.JIRA_API_KEY || '',
  username: process.env.JIRA_USERNAME || '',
  password: process.env.JIRA_PASSWORD || ''
}

Updated:
auth: {
  email: process.env.JIRA_EMAIL || '',
  token: process.env.JIRA_PERSONAL_ACCESS_TOKEN || '', // For direct mode
  pat: process.env.JIRA_PAT || '', // NEW - PAT token
  imsToken: process.env.JIRA_IMS_TOKEN || '',
  apiKey: process.env.JIRA_API_KEY || '',
  // Deprecated - remove after migration:
  username: process.env.JIRA_USERNAME || '',
  password: process.env.JIRA_PASSWORD || ''
}

File: corp_jira_mcp/common/utils.js

Current iPaaS Headers (lines 108-123):
function constructIpaasHeaders(imsToken, apiKey, username, password) {
  const headers = {
    "Authorization": `${imsToken}`,
    "Api_key": apiKey,
    "Content-Type": "application/json"
  };

  if (username) {
    headers["Username"] = username;  // ← DEPRECATED
  }
  if (password) {
    headers["Password"] = password;  // ← DEPRECATED
  }

  return headers;
}

Updated iPaaS Headers:
function constructIpaasHeaders(imsToken, apiKey, pat) {
  const headers = {
    "Authorization": `${imsToken}`,      // IMS token for iPaaS
    "Api_key": apiKey,                   // iPaaS routing
    "Content-Type": "application/json"
  };

  // Add PAT in x-authorization header
  if (pat) {
    headers["x-authorization"] = `Bearer ${pat}`;  // NEW
  }

  return headers;
}

Updated jiraRequest Function (lines 127-152):
export async function jiraRequest(path, options = {}) {
  let headers;

  if (config.useIpaas) {
    // iPaaS authentication with PAT
    if (currentAuthToken) {
      // Use incoming IMS token
      const imsToken = currentAuthToken.startsWith('Bearer ')
        ? currentAuthToken.substring(7)
        : currentAuthToken;

      // Get PAT from config
      const pat = config.auth.pat;
      if (!pat) {
        throw new Error("JIRA_PAT is required for iPaaS authentication");
      }

      headers = {
        ...constructIpaasHeaders(imsToken, config.auth.apiKey || '', pat),
        ...options.headers
      };
    } else {
      // Fallback to env variables
      const { imsToken, apiKey, pat } = config.auth;
      if (!imsToken || !apiKey || !pat) {
        throw new Error("IMS token, API key, and PAT are required");
      }

      headers = {
        ...constructIpaasHeaders(imsToken, apiKey, pat),
        ...options.headers
      };
    }
  } else {
    // Direct Jira authentication with PAT
    const { pat } = config.auth;
    if (!pat) {
      throw new Error("JIRA_PAT is required for direct authentication");
    }

    headers = {
      "Authorization": `Bearer ${pat}`,  // NEW - PAT bearer token
      "Content-Type": "application/json",
      "Accept": "application/json",
      ...options.headers
    };
  }

  // ... rest of function unchanged
}

6.2 AWS Secrets Manager Integration

File: corp_jira_mcp/env-aws.ts

Current (lines 29-33):
const mappings = {
  'ipaas_username': 'JIRA_USERNAME',
  'ipaas_password': 'JIRA_PASSWORD',
  'ipaas_api_key': 'JIRA_API_KEY',
  'ims_access_token': 'JIRA_IMS_TOKEN'
};

Updated:
const mappings = {
  'ipaas_username': 'JIRA_USERNAME',  // Keep for logging/reference
  'ipaas_password': 'JIRA_PASSWORD',  // Deprecated - remove after migration
  'ipaas_api_key': 'JIRA_API_KEY',    // Keep - still needed
  'ims_access_token': 'JIRA_IMS_TOKEN', // Keep - still needed
  'jira_primary_pat': 'JIRA_PAT',      // NEW - Primary PAT
  'jira_backup_pat': 'JIRA_BACKUP_PAT' // NEW - Backup PAT (optional)
};

6.3 Docker Compose Configuration

File: infrastructure/docker-compose.yml

Current (lines 142-152):
mcp-jira:
  environment:
    - USE_IPAAS=true
    - AWS_REGION=eu-west-1
    - PORT=8081
    - JIRA_API_KEY=
    - JIRA_USERNAME=
    - JIRA_PASSWORD=   # ← DEPRECATED
    - JIRA_IMS_TOKEN=

Updated:
mcp-jira:
  environment:
    - USE_IPAAS=true
    - AWS_REGION=eu-west-1
    - PORT=8081
    - JIRA_API_KEY=    # Still needed for iPaaS
    - JIRA_PAT=        # NEW - Primary PAT from AWS Secrets
    - JIRA_IMS_TOKEN=  # Still needed for iPaaS
    # Deprecated - remove after migration:
    # - JIRA_USERNAME=
    # - JIRA_PASSWORD=

---
7. Migration Timeline & Risk Mitigation

7.1 Proposed Migration Timeline

Week 1 (Nov 11-17, 2025): Preparation
├── Day 1: Generate initial PAT via browser UI
├── Day 2: Store PAT in AWS Secrets Manager (dev/stage)
├── Day 3: Update MCP JIRA code (config.ts, utils.js, env-aws.ts)
├── Day 4: Test in dev environment
└── Day 5: Test in stage environment

Week 2 (Nov 18-24, 2025): Production Deployment
├── Day 1: Generate production PAT via browser UI
├── Day 2: Store PAT in AWS Secrets Manager (production)
├── Day 3: Deploy to prod1 (singleton services)
├── Day 4: Monitor for 24 hours, validate all JIRA operations
├── Day 5: Deploy to prod2
└── Weekend: Monitor production health

Week 3 (Nov 25-30, 2025): Validation & Backup
├── Day 1: Generate backup PAT (expires 7 days after primary)
├── Day 2: Implement PAT rotation script
├── Day 3: Test rotation script in dev/stage
├── Day 4: Deploy rotation script to production
└── Day 5: DEPRECATION DEADLINE (Nov 30, 2025)

7.2 Rollback Strategy

Scenario: PAT authentication fails in production

Rollback Steps:
1. Immediate: Revert docker-compose.yml to use JIRA_USERNAME + JIRA_PASSWORD
2. Immediate: Deploy previous ECR image version:
cd infrastructure/
./deploy-ketchup.sh --rollback v2.360.346
3. Within 1 hour: Investigate PAT failure (check logs, test PAT manually)
4. Within 4 hours: Generate new PAT if expired/revoked

Rollback Window: Until November 30, 2025 (deprecation deadline)

7.3 Risk Assessment

| Risk                                     | Likelihood | Impact   | Mitigation                                                     |
|------------------------------------------|------------|----------|----------------------------------------------------------------|
| PAT creation fails (service account MFA) | Medium     | High     | Request MFA exemption via ServiceDesk 2 weeks before migration |
| PAT expires unexpectedly                 | Low        | High     | Implement backup PAT + automated rotation                      |
| iPaaS rejects x-authorization header     | Low        | Critical | Test in dev/stage first; validate with iPaaS team              |
| AWS Secrets Manager update fails         | Low        | High     | Manual secret update as backup; document procedure             |
| Production downtime during deployment    | Medium     | Medium   | Deploy to prod1 first, monitor 24h before prod2                |
| Rotation script fails                    | Medium     | Medium   | Keep backup PAT with staggered expiration                      |

★ Insight ─────────────────────────────────────
- Critical Path Item: Service account MFA exemption (or authenticator setup) is the biggest blocker
- Testing Strategy: Validate iPaaS + PAT in lower environments BEFORE production (iPaaS might have subtle differences)
- Monitoring: Set up CloudWatch alarms for MCP JIRA 401/403 errors before migration
─────────────────────────────────────────────────

---
8. Testing Plan

8.1 Pre-Deployment Testing (Dev/Stage)

Test Suite:
# 1. MCP JIRA Health Check
curl -H "Authorization: Bearer ${IMS_TOKEN}" \
  http://mcp-jira:8081/health

# 2. Auth Test Endpoint
curl -X POST http://mcp-jira:8081/message \
  -H "Authorization: Bearer ${IMS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-auth",
    "method": "tools/call",
    "params": {
      "name": "test_jira_auth",
      "arguments": {}
    }
  }'

# 3. Search Issues (via iPaaS + PAT)
curl -X POST http://mcp-jira:8081/message \
  -H "Authorization: Bearer ${IMS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-search",
    "method": "tools/call",
    "params": {
      "name": "search_jira_issues",
      "arguments": {
        "jql": "project = CPGNREQ AND status = Open",
        "maxResults": 1
      }
    }
  }'

# 4. Create Comment (write operation)
curl -X POST http://mcp-jira:8081/message \
  -H "Authorization: Bearer ${IMS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-comment",
    "method": "tools/call",
    "params": {
      "name": "add_jira_comment",
      "arguments": {
        "issueIdOrKey": "CPGNREQ-180375",
        "comment": {
          "body": "PAT authentication test - successful"
        }
      }
    }
  }'

Expected Results:
- ✅ Health check: 200 OK
- ✅ Auth test: {"success": true, "user": {...}}
- ✅ Search: Returns issue list
- ✅ Comment: Successfully posts to ticket

8.2 Integration Test Updates

File: tests/integration/test_jira_reporter/test_jira_reporter_auth.py

Add PAT Validation Tests:
@pytest.mark.asyncio
@pytest.mark.integration
async def test_mcp_jira_pat_authentication():
    """Test MCP JIRA service with PAT authentication."""
    container = await get_container()
    mcp_client = await container.aget(MCPClientProtocol)

    # Test auth
    result = await mcp_client.test_jira_auth()
    assert result["success"] is True
    assert "user" in result

    # Test search with PAT
    issues = await mcp_client.search_issues(
        jql="project = CPGNREQ AND key = CPGNREQ-180375",
        max_results=1
    )
    assert issues["total"] > 0

@pytest.mark.asyncio
async def test_pat_rotation_simulation():
    """Test PAT rotation without actually rotating."""
    rotation_manager = PATRotationManager(secrets_manager)

    # Mock rotation
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {
            "id": "999",
            "name": "test-token",
            "token": "test123",
            "expiresAt": "2026-02-10T00:00:00Z"
        }

        result = await rotation_manager.rotate_pat(token_name="test")
        assert result["success"] is True

8.3 Post-Deployment Validation (Production)

Validation Checklist:
- JIRA Reporter: Successfully posts comments to CSO tickets
- Status Updater: AI-generated status updates with JIRA enrichment work
- Ketchup App: /status, /report, /query commands with JIRA context work
- MCP Health: http://mcp-jira:8081/health returns 200 OK
- No 401/403 errors in logs: docker logs mcp-jira | grep -E "401|403"
- AWS Secrets: PAT values are correct in Secrets Manager

Monitoring Queries (first 48 hours):
# 1. Check for auth failures
docker logs mcp-jira | grep -i "authentication failed"

# 2. Check for PAT-related errors
docker logs mcp-jira | grep -i "pat\|token"

# 3. Validate successful JIRA operations
docker logs ketchup-jira-reporter | grep "Successfully posted comment"

# 4. Check MCP request success rate
docker logs mcp-jira | grep "Response status: 200" | wc -l
docker logs mcp-jira | grep "Response status: 4" | wc -l

---
9. Key Takeaways & Next Steps

9.1 Critical Success Factors

1. ✅ Service Account MFA Setup: Complete BEFORE migration deadline
2. ✅ Backup PAT Creation: Create 2 PATs with staggered expiration (Day 0 + Day 7)
3. ✅ iPaaS Header Format: Use x-authorization: Bearer <PAT> (validated with iPaaS team)
4. ✅ Secrets Manager Update: Add jira_primary_pat and jira_backup_pat keys
5. ✅ Automated Rotation: Deploy rotation script by Dec 1, 2025 (schedule for every 60 days)

9.2 Immediate Action Items

This Week (Nov 11-17):
1. Request MFA exemption for service account via ServiceDesk (or set up authenticator)
2. Generate first PAT via browser UI (manual, one-time)
3. Store PAT in AWS Secrets Manager (dev/stage)
4. Update MCP JIRA code (3 files: config.ts, utils.js, env-aws.ts)
5. Test in dev environment

Next Week (Nov 18-24):
1. Generate production PAT
2. Deploy to production (prod1 → monitor → prod2)
3. Validate all JIRA operations work

Week 3 (Nov 25-30):
1. Create backup PAT
2. Deploy rotation script
3. Monitor through deprecation deadline (Nov 30)

9.3 Open Questions for Team Discussion

1. Service Account Ownership: Who are the backup admins for the Ketchup service account in IAM?
2. MFA Strategy: Prefer authenticator setup or ServiceDesk exemption request?
3. Rotation Cadence: 60 days (recommended) or 30 days (more aggressive)?
4. Monitoring: Should we add CloudWatch alarms for PAT expiry warnings?
5. iPaaS Validation: Do we need iPaaS team approval for header format change?

---
10. Reference Links

Adobe JIRA Wiki:
- PAT Overview: https://wiki.corp.adobe.com/display/JIRA/PAT+-+Personal+Access+Tokens
- API Guides: https://wiki.corp.adobe.com/display/JIRA/API+Guides
- iPaaS Integration: https://wiki.corp.adobe.com/display/JIRA/PAT+Alignment+with+JiraProxyV2+REST+Endpoint

Atlassian Documentation:
- PAT Usage: https://confluence.atlassian.com/enterprise/using-personal-access-tokens-1026032365.html
- JIRA REST API: https://docs.atlassian.com/software/jira/docs/api/REST/8.20.14/

Slack Conversations (Cloud Technology #jira_users):
- Don Imfeld's iPaaS solution: July 29, 2025 (20:59)
- Keith Shaw's auto-cleanup confirmation: Nov 11, 2025 (16:43)
- Jacob Zufelt's DELETE endpoint: July 21, 2025 (21:39)

Ketchup Codebase:
- MCP JIRA Config: corp_jira_mcp/common/config.ts
- MCP JIRA Utils: corp_jira_mcp/common/utils.js
- Docker Compose: infrastructure/docker-compose.yml
- JIRA Reporter: jira_reporter/jira_service.py