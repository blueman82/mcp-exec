# Feature Flag Decision Tree

This flowchart shows the three-tier feature flag evaluation system used by Ketchup. Each feature (status_updater, jira_reporter, trust_endorsement) follows the same evaluation logic: environment variable check → global flag check → channel-specific flag check. Admins manage flags via `/ketchup feature` commands.

```mermaid
graph TB
    Start([Feature Evaluation<br/>Request]) --> WhichFeature{"Which Feature?"}
    
    WhichFeature -->|"status_updater"| StatusStart["🔍 Evaluate:<br/>status_updater"]
    WhichFeature -->|"jira_reporter"| JiraStart["🔍 Evaluate:<br/>jira_reporter"]
    WhichFeature -->|"trust_endorsement"| TrustStart["🔍 Evaluate:<br/>trust_endorsement"]
    
    subgraph StatusUpdaterFlow["📊 STATUS UPDATER FEATURE"]
        StatusStart --> StatusEnv{"Check Environment:<br/>KETCHUP_STATUS_UPDATER_FEATURE"}
        
        StatusEnv -->|"false ❌"| StatusDisabled1["🚫 DISABLED<br/>Skip all processing"]
        StatusEnv -->|"true ✅"| StatusGlobal{"Check Global Flag:<br/>KETCHUP_STATUS_UPDATER_GLOBAL"}
        
        StatusGlobal -->|"true ✅"| StatusEnabledAll["✅ ENABLED FOR ALL<br/>Process ALL channels"]
        StatusGlobal -->|"false ❌"| StatusChannel{"Check DynamoDB:<br/>features.status_updater_enabled<br/>for channel C123"}
        
        StatusChannel -->|"true ✅"| StatusEnabledChannel["✅ ENABLED FOR CHANNEL<br/>Process channel C123"]
        StatusChannel -->|"false or missing ❌"| StatusDisabled2["🚫 DISABLED FOR CHANNEL<br/>Skip channel C123"]
    end
    
    subgraph JiraReporterFlow["🎫 JIRA REPORTER FEATURE"]
        JiraStart --> JiraEnv{"Check Environment:<br/>KETCHUP_JIRA_REPORTER_FEATURE"}
        
        JiraEnv -->|"false ❌"| JiraDisabled1["🚫 DISABLED<br/>Skip all processing"]
        JiraEnv -->|"true ✅"| JiraGlobal{"Check Global Flag:<br/>KETCHUP_JIRA_REPORTER_GLOBAL"}
        
        JiraGlobal -->|"true ✅"| JiraEnabledAll["✅ ENABLED FOR ALL<br/>Process ALL channels"]
        JiraGlobal -->|"false ❌"| JiraChannel{"Check DynamoDB:<br/>features.jira_reporter_enabled<br/>for channel C123"}
        
        JiraChannel -->|"true ✅"| JiraEnabledChannel["✅ ENABLED FOR CHANNEL<br/>Process channel C123"]
        JiraChannel -->|"false or missing ❌"| JiraDisabled2["🚫 DISABLED FOR CHANNEL<br/>Skip channel C123"]
    end
    
    subgraph TrustEndorsementFlow["🤝 TRUST ENDORSEMENT FEATURE"]
        TrustStart --> TrustEnv{"Check Environment:<br/>KETCHUP_TRUST_ENDORSEMENT_FEATURE"}
        
        TrustEnv -->|"false ❌"| TrustDisabled1["🚫 DISABLED<br/>Skip all processing"]
        TrustEnv -->|"true ✅"| TrustGlobal{"Check Global Flag:<br/>KETCHUP_TRUST_ENDORSEMENT_GLOBAL"}
        
        TrustGlobal -->|"true ✅"| TrustEnabledAll["✅ ENABLED FOR ALL<br/>Process ALL channels"]
        TrustGlobal -->|"false ❌"| TrustChannel{"Check DynamoDB:<br/>features.trust_endorsement_enabled<br/>for channel C123"}
        
        TrustChannel -->|"true ✅"| TrustEnabledChannel["✅ ENABLED FOR CHANNEL<br/>Process channel C123"]
        TrustChannel -->|"false or missing ❌"| TrustDisabled2["🚫 DISABLED FOR CHANNEL<br/>Skip channel C123"]
    end
    
    subgraph AdminManagement["🔧 ADMIN MANAGEMENT (via /ketchup feature)"]
        AdminStart(["/ketchup feature<br/>&lt;subcommand&gt;"]) --> AdminAuth{"Admin<br/>Authorization?"}
        
        AdminAuth -->|"❌ Not Admin"| AdminDeny["🚫 Access Denied"]
        AdminAuth -->|"✅ Is Admin"| AdminCmd{"Which<br/>Subcommand?"}
        
        AdminCmd -->|"enable"| CmdEnable["Enable Feature<br/>for Channel<br/>━━━━━━━━━━━━━━━<br/>/ketchup feature<br/>status_updater enable C123"]
        AdminCmd -->|"disable"| CmdDisable["Disable Feature<br/>for Channel<br/>━━━━━━━━━━━━━━━<br/>/ketchup feature<br/>status_updater disable C123"]
        AdminCmd -->|"list"| CmdList["List Enabled<br/>Channels<br/>━━━━━━━━━━━━━━━<br/>/ketchup feature<br/>status_updater list"]
        AdminCmd -->|"status"| CmdStatus["Show Feature<br/>Status<br/>━━━━━━━━━━━━━━━<br/>/ketchup feature<br/>status_updater status"]
        AdminCmd -->|"global-on"| CmdGlobalOn["Enable Global<br/>Flag<br/>━━━━━━━━━━━━━━━<br/>/ketchup feature<br/>status_updater global-on"]
        AdminCmd -->|"global-off"| CmdGlobalOff["Disable Global<br/>Flag<br/>━━━━━━━━━━━━━━━<br/>/ketchup feature<br/>status_updater global-off"]
        
        CmdEnable --> DBUpdate1["Update DynamoDB:<br/>SET features.<br/>status_updater_enabled<br/>= true"]
        CmdDisable --> DBUpdate2["Update DynamoDB:<br/>REMOVE features.<br/>status_updater_enabled"]
        CmdList --> DBQuery["Query DynamoDB:<br/>Scan all channels<br/>WHERE features.<br/>status_updater_enabled<br/>= true"]
        CmdStatus --> EnvCheck["Read Environment:<br/>1. KETCHUP_*_FEATURE<br/>2. KETCHUP_*_GLOBAL<br/>3. Count DynamoDB<br/>   enabled channels"]
        CmdGlobalOn --> EnvUpdate1["Set Environment:<br/>KETCHUP_*_GLOBAL=true<br/>(Requires restart)"]
        CmdGlobalOff --> EnvUpdate2["Set Environment:<br/>KETCHUP_*_GLOBAL=false<br/>(Requires restart)"]
        
        DBUpdate1 --> AdminSuccess["✅ Confirmation<br/>Posted to Slack"]
        DBUpdate2 --> AdminSuccess
        DBQuery --> AdminSuccess
        EnvCheck --> AdminSuccess
        EnvUpdate1 --> AdminRestart["⚠️ Restart Required<br/>to Apply Changes"]
        EnvUpdate2 --> AdminRestart
    end
    
    subgraph EvaluationLogic["💡 EVALUATION LOGIC"]
        Logic1["Priority Order:<br/>1️⃣ Environment Variable<br/>   (KETCHUP_*_FEATURE)<br/><br/>2️⃣ Global Flag<br/>   (KETCHUP_*_GLOBAL)<br/><br/>3️⃣ Channel-Specific Flag<br/>   (DynamoDB)"]
        
        Logic2["Short-Circuit Logic:<br/>━━━━━━━━━━━━━━━<br/>If env var = false<br/>  → DISABLED (stop)<br/><br/>If global flag = true<br/>  → ENABLED FOR ALL (stop)<br/><br/>If channel flag = true<br/>  → ENABLED FOR CHANNEL<br/><br/>Otherwise<br/>  → DISABLED"]
    end
    
    subgraph DataSources["📊 DATA SOURCES"]
        EnvVars["🔧 Environment Variables<br/>(docker-compose.yml)<br/>━━━━━━━━━━━━━━━<br/>KETCHUP_STATUS_UPDATER_FEATURE=true<br/>KETCHUP_STATUS_UPDATER_GLOBAL=true<br/>KETCHUP_JIRA_REPORTER_FEATURE=true<br/>KETCHUP_JIRA_REPORTER_GLOBAL=false<br/>KETCHUP_TRUST_ENDORSEMENT_FEATURE=true<br/>KETCHUP_TRUST_ENDORSEMENT_GLOBAL=true"]
        
        DDBFlags["💾 DynamoDB<br/>(ketchup_channel_information)<br/>━━━━━━━━━━━━━━━<br/>{<br/>  'channel_id': 'C123',<br/>  'features': {<br/>    'status_updater_enabled': true,<br/>    'jira_reporter_enabled': false,<br/>    'trust_endorsement_enabled': true<br/>  }<br/>}"]
    end
    
    classDef evalNode fill:#9B59B6,stroke:#6C3483,stroke-width:2px,color:#fff
    classDef enabledNode fill:#27AE60,stroke:#1E8449,stroke-width:3px,color:#fff
    classDef disabledNode fill:#E74C3C,stroke:#A93226,stroke-width:3px,color:#fff
    classDef adminNode fill:#3498DB,stroke:#2471A3,stroke-width:2px,color:#fff
    classDef dataNode fill:#F39C12,stroke:#CA7E0A,stroke-width:2px,color:#fff
    classDef logicNode fill:#ECF0F1,stroke:#95A5A6,stroke-width:1px
    
    class StatusStart,JiraStart,TrustStart,StatusEnv,StatusGlobal,StatusChannel,JiraEnv,JiraGlobal,JiraChannel,TrustEnv,TrustGlobal,TrustChannel evalNode
    class StatusEnabledAll,StatusEnabledChannel,JiraEnabledAll,JiraEnabledChannel,TrustEnabledAll,TrustEnabledChannel,AdminSuccess enabledNode
    class StatusDisabled1,StatusDisabled2,JiraDisabled1,JiraDisabled2,TrustDisabled1,TrustDisabled2,AdminDeny disabledNode
    class AdminStart,AdminAuth,AdminCmd,CmdEnable,CmdDisable,CmdList,CmdStatus,CmdGlobalOn,CmdGlobalOff,DBUpdate1,DBUpdate2,DBQuery,EnvCheck,EnvUpdate1,EnvUpdate2,AdminRestart adminNode
    class EnvVars,DDBFlags dataNode
```

## Feature Flag Evaluation Algorithm

### Three-Tier Hierarchy

```
1. Environment Variable Check (Master Kill Switch)
   ↓
2. Global Flag Check (Enable for ALL channels)
   ↓
3. Channel-Specific Flag Check (Enable for specific channel)
```

**Short-Circuit Logic**: Evaluation stops at first decisive check:
- If environment variable is `false` → **DISABLED** (stop)
- If global flag is `true` → **ENABLED FOR ALL** (stop)
- If channel-specific flag is `true` → **ENABLED FOR CHANNEL**
- Otherwise → **DISABLED**

### Example Evaluation

**Scenario 1: Global Feature Enabled**
```
Environment: KETCHUP_STATUS_UPDATER_FEATURE=true ✅
Global Flag: KETCHUP_STATUS_UPDATER_GLOBAL=true ✅
Result: ENABLED FOR ALL CHANNELS (don't check DynamoDB)
```

**Scenario 2: Channel-Specific Feature**
```
Environment: KETCHUP_JIRA_REPORTER_FEATURE=true ✅
Global Flag: KETCHUP_JIRA_REPORTER_GLOBAL=false ❌
Channel Flag (C123): features.jira_reporter_enabled=true ✅
Result: ENABLED FOR C123 (but not other channels)
```

**Scenario 3: Feature Disabled**
```
Environment: KETCHUP_STATUS_UPDATER_FEATURE=false ❌
Result: DISABLED FOR ALL (don't check global or channel flags)
```

---

## Available Features

### 1. Status Updater (`status_updater`)

**Purpose**: Automated hourly channel status updates

**Environment Variables**:
- `KETCHUP_STATUS_UPDATER_FEATURE=true` (master switch)
- `KETCHUP_STATUS_UPDATER_GLOBAL=true` (global enable)

**DynamoDB Field**: `features.status_updater_enabled`

**Default Configuration**: 
- Feature: ✅ Enabled
- Global: ✅ Enabled for all channels

---

### 2. JIRA Reporter (`jira_reporter`)

**Purpose**: Automated JIRA ticket creation for incidents

**Environment Variables**:
- `KETCHUP_JIRA_REPORTER_FEATURE=true` (master switch)
- `KETCHUP_JIRA_REPORTER_GLOBAL=false` (global disabled)

**DynamoDB Field**: `features.jira_reporter_enabled`

**Default Configuration**: 
- Feature: ✅ Enabled
- Global: ❌ Disabled (requires per-channel opt-in)

**Rationale**: JIRA integration is opt-in to prevent unwanted ticket creation

---

### 3. Trust Endorsement (`trust_endorsement`)

**Purpose**: Trust endorsement system for channel members

**Environment Variables**:
- `KETCHUP_TRUST_ENDORSEMENT_FEATURE=true` (master switch)
- `KETCHUP_TRUST_ENDORSEMENT_GLOBAL=true` (global enable)

**DynamoDB Field**: `features.trust_endorsement_enabled`

**Default Configuration**: 
- Feature: ✅ Enabled
- Global: ✅ Enabled for all channels

---

## Admin Management Commands

### Enable Feature for Channel

```bash
/ketchup feature status_updater enable C0LQEJGCB
```

**Action**: Sets `features.status_updater_enabled = true` in DynamoDB for channel C0LQEJGCB

**Result**: Channel C0LQEJGCB now receives status updates (if global is disabled)

---

### Disable Feature for Channel

```bash
/ketchup feature jira_reporter disable C0LQEJGCB
```

**Action**: Removes `features.jira_reporter_enabled` from DynamoDB for channel C0LQEJGCB

**Result**: Channel C0LQEJGCB no longer creates JIRA tickets

---

### List Enabled Channels

```bash
/ketchup feature status_updater list
```

**Action**: Scans DynamoDB for all channels where `features.status_updater_enabled = true`

**Response**:
```
Status Updater - Enabled Channels:
• C0LQEJGCB - #campaign-ops-team
• C0M5N3P2Q - #incident-response
• C0N7R4S1T - #platform-alerts
Total: 3 channels
```

---

### Show Feature Status

```bash
/ketchup feature status_updater status
```

**Response**:
```
Status Updater Configuration:

Environment Variables:
• KETCHUP_STATUS_UPDATER_FEATURE: true ✅
• KETCHUP_STATUS_UPDATER_GLOBAL: true ✅

DynamoDB:
• Explicitly enabled channels: 0
• Explicitly disabled channels: 0

Current Behavior:
✅ ENABLED FOR ALL CHANNELS (global flag is true)

Note: Global flag overrides channel-specific settings.
```

---

### Enable Global Flag

```bash
/ketchup feature status_updater global-on
```

**Action**: Sets `KETCHUP_STATUS_UPDATER_GLOBAL=true` in docker-compose.yml

**Result**: Feature enabled for ALL channels, regardless of DynamoDB settings

**⚠️ Requires Restart**: Container must be restarted to apply environment variable change

---

### Disable Global Flag

```bash
/ketchup feature jira_reporter global-off
```

**Action**: Sets `KETCHUP_JIRA_REPORTER_GLOBAL=false` in docker-compose.yml

**Result**: Feature respects per-channel DynamoDB settings

**⚠️ Requires Restart**: Container must be restarted to apply environment variable change

---

### Clear Disabled Channels List

```bash
/ketchup feature status_updater clear-disabled
```

**Action**: Removes ALL `features.status_updater_enabled = false` entries from DynamoDB

**Use Case**: Cleanup after testing or bulk re-enabling

---

### Flag Review (Interactive Form)

```bash
/ketchup feature flag-review
```

**Action**: Posts interactive form with all feature flags and current states

**Response**: Modal dialog with:
- Current environment variable values
- Global flag states
- Channel-specific flag counts
- Quick enable/disable buttons

---

### Set Review Notification Channel

```bash
/ketchup feature set-review-channel C0LQEJGCB
```

**Action**: Sets notification channel for feature flag changes

**Use Case**: Admins receive notifications when flags are changed

---

### Get Review Notification Channel

```bash
/ketchup feature get-review-channel
```

**Response**: Current notification channel ID and name

---

## Implementation Details

### Feature Service (`packages/core/feature_flags/feature_service.py`)

```python
class FeatureService:
    async def is_feature_enabled(
        self,
        feature_name: str,
        channel_id: str
    ) -> bool:
        # 1. Check environment variable (master switch)
        env_var = f"KETCHUP_{feature_name.upper()}_FEATURE"
        if not os.getenv(env_var, "false").lower() == "true":
            return False  # DISABLED
        
        # 2. Check global flag
        global_var = f"KETCHUP_{feature_name.upper()}_GLOBAL"
        if os.getenv(global_var, "false").lower() == "true":
            return True  # ENABLED FOR ALL
        
        # 3. Check channel-specific flag in DynamoDB
        channel = await self.db.get_channel(channel_id)
        feature_key = f"{feature_name}_enabled"
        return channel.get("features", {}).get(feature_key, False)
```

### DynamoDB Schema

```json
{
  "channel_id": "C0LQEJGCB",
  "channel_name": "campaign-ops-team",
  "features": {
    "status_updater_enabled": true,
    "jira_reporter_enabled": false,
    "trust_endorsement_enabled": true
  }
}
```

### Environment Variables (docker-compose.yml)

```yaml
services:
  ketchup-app:
    environment:
      # Status Updater
      - KETCHUP_STATUS_UPDATER_FEATURE=true
      - KETCHUP_STATUS_UPDATER_GLOBAL=true
      
      # JIRA Reporter
      - KETCHUP_JIRA_REPORTER_FEATURE=true
      - KETCHUP_JIRA_REPORTER_GLOBAL=false
      
      # Trust Endorsement
      - KETCHUP_TRUST_ENDORSEMENT_FEATURE=true
      - KETCHUP_TRUST_ENDORSEMENT_GLOBAL=true
```

---

## Authorization

### Admin Users Only

**Requirement**: User must be in `admin_slack_user_ids` list in Secrets Manager

**Enforcement**: 
1. Extract user_id from Slack command payload
2. Fetch admin list from Secrets Manager
3. Check if user_id in admin list
4. Deny if not admin

**Error Response**: 
```
❌ Access Denied

This command requires admin privileges.
Contact @ketchup-admins to request access.
```

---

## Performance Optimizations

### Caching

**Feature Flag Cache**: 
- Cache feature evaluations for 5 minutes
- Reduces DynamoDB queries
- Invalidate cache on flag updates

**Admin List Cache**:
- Cache admin user list for 10 minutes
- Reduces Secrets Manager API calls

### Short-Circuit Evaluation

**Benefit**: Avoid unnecessary checks
- If environment variable is false, skip global and DynamoDB checks
- If global flag is true, skip DynamoDB query
- Reduces latency and API costs

---

## Monitoring and Logging

**Logged Events**:
- Feature flag evaluations (channel, feature, result)
- Admin command executions (user, action, target)
- Flag changes (old value → new value)
- Cache hits/misses

**Metrics**:
- Feature flag evaluation rate
- Enabled channel counts per feature
- Admin command frequency
- Cache hit ratio

**Alerting**:
- Notify admin channel when flags are changed
- Alert on unexpected feature behavior
- Monitor for unauthorized access attempts
