# Feature Flag Control Flow & Architecture

## Feature Flags Overview

```mermaid
graph TB
    subgraph "Environment Configuration"
        DockerCompose["docker-compose.yml<br/>Source of Truth"]
    end

    subgraph "Feature Flags"
        FF1["KETCHUP_STATUS_UPDATER_FEATURE"]
        FF2["KETCHUP_JIRA_REPORTER_FEATURE"]
        FF3["KETCHUP_TRUST_ENDORSEMENT_FEATURE"]
        FF4["KETCHUP_ACCESS_REQUEST_AUTOMATION_FEATURE"]
        FF5["USE_PIPELINE_PROCESSING"]
        FF6["KETCHUP_USE_HTTPX"]
        FF7["KETCHUP_HTTP2_ENABLED"]
        FF8["KETCHUP_KEEPALIVE_ENABLED"]
    end

    subgraph "Services Using Flags"
        StatusSvc["Status Updater<br/>Service"]
        JiraSvc["JIRA Reporter<br/>Service"]
        TrustSvc["Trust & Endorsement<br/>Service"]
        AccessSvc["Access Request<br/>Service"]
        PipelineSvc["Message Processing<br/>Pipeline"]
        HttpSvc["HTTP Client<br/>Layer"]
    end

    DockerCompose -->|Defines| FF1
    DockerCompose -->|Defines| FF2
    DockerCompose -->|Defines| FF3
    DockerCompose -->|Defines| FF4
    DockerCompose -->|Defines| FF5
    DockerCompose -->|Defines| FF6
    DockerCompose -->|Defines| FF7
    DockerCompose -->|Defines| FF8

    FF1 -->|Controls| StatusSvc
    FF2 -->|Controls| JiraSvc
    FF3 -->|Controls| TrustSvc
    FF4 -->|Controls| AccessSvc
    FF5 -->|Controls| PipelineSvc
    FF6 -->|Controls| HttpSvc
    FF7 -->|Controls| HttpSvc
    FF8 -->|Controls| HttpSvc

    style DockerCompose fill:#ff9900
    style FF1 fill:#0099cc
    style FF2 fill:#0099cc
    style FF3 fill:#0099cc
    style FF4 fill:#0099cc
    style FF5 fill:#0099cc
    style FF6 fill:#0099cc
    style FF7 fill:#0099cc
    style FF8 fill:#0099cc
```

## Feature Flag Resolution Flow

```mermaid
sequenceDiagram
    participant Container as Docker<br/>Container<br/>Starts
    participant EnvLoad as Environment<br/>Loader
    participant Config as Feature Flag<br/>Configuration
    participant Cache as Flag<br/>Cache
    participant Service as Service<br/>Initialize
    participant Logic as Business<br/>Logic

    Container->>EnvLoad: 1. Load env vars<br/>from docker-compose

    EnvLoad->>EnvLoad: 2. Parse:<br/>KETCHUP_STATUS_UPDATER_FEATURE=true<br/>KETCHUP_JIRA_REPORTER_FEATURE=true<br/>etc

    EnvLoad->>Config: 3. Register in<br/>config service

    Config->>Cache: 4. Cache flags<br/>in memory

    Config->>Service: 5. Service ready<br/>to query flags

    Service->>Logic: 6. Initialize<br/>business logic

    Logic->>Cache: 7. Check flag<br/>before each<br/>operation

    Cache->>Logic: 8. Return flag<br/>value (true/false)

    Logic->>Logic: 9. Branch logic<br/>based on flag

    alt "Flag Enabled"
        Logic->>Logic: Execute new code path
        Logic->>Logic: Detailed logging
    else "Flag Disabled"
        Logic->>Logic: Execute fallback path
        Logic->>Logic: Normal logging
    end
```

## In-Service Feature Flag Check

```mermaid
graph TD
    RequestArrives["Request arrives<br/>to handler"]

    RequestArrives -->|Get instance| Handler["Handler executes"]

    Handler -->|Before logic| CheckFlag["Check feature<br/>flag value"]

    CheckFlag -->|Query| FlagService["FeatureFlagService<br/>from DI container"]

    FlagService -->|Lookup| Cache["In-memory<br/>cache"]

    Cache -->|Is 'FEATURE_X'<br/>enabled?| IsEnabled{{"Enabled<br/>?"}}

    IsEnabled -->|true| NewPath["Execute new<br/>code path"]
    IsEnabled -->|false| LegacyPath["Execute legacy<br/>code path"]

    NewPath -->|Run| NewLogic["New feature<br/>logic<br/>- New algorithms<br/>- New API calls<br/>- New data models"]

    LegacyPath -->|Run| OldLogic["Original logic<br/>- Proven code<br/>- Backward compatible<br/>- Safe fallback"]

    NewLogic -->|Result| Response["Generate<br/>response"]

    OldLogic -->|Result| Response

    Response -->|Return| Handler

    style Handler fill:#36c5f0
    style IsEnabled fill:#ffcc99
    style NewPath fill:#99ff99
    style LegacyPath fill:#99ff99
    style Response fill:#00cc99

    Note["Both code paths<br/>coexist in<br/>production code"]
```

## Safe Rollout Pattern: Gradual Feature Enablement

```mermaid
graph LR
    Phase0["Phase 0:<br/>Feature Disabled<br/>in docker-compose.yml<br/>FEATURE_X=false"]

    Phase1["Phase 1:<br/>Canary Deploy<br/>Enable on prod2<br/>Monitor metrics"]

    Phase2["Phase 2:<br/>Gradual Rollout<br/>Enable on prod1<br/>Watch error rates"]

    Phase3["Phase 3:<br/>Stable<br/>Enabled everywhere<br/>Remove old code"]

    Phase0 -->|Tested locally<br/>and staging| Phase1
    Phase1 -->|No errors<br/>for 24h| Phase2
    Phase2 -->|No errors<br/>for 48h| Phase3
    Phase3 -->|Ready| Cleanup["Remove legacy<br/>code path"]

    style Phase0 fill:#ff9999
    style Phase1 fill:#ffcc99
    style Phase2 fill:#ffff99
    style Phase3 fill:#99ff99
    style Cleanup fill:#00cc99
```

## Example: Pipeline Processing Feature Flag

```mermaid
graph TD
    MessageReceived["Message event<br/>received from Slack"]

    MessageReceived -->|Check flag| GetFlag["Check:<br/>USE_PIPELINE_PROCESSING"]

    GetFlag -->|Query cache| IsPipelineEnabled{"Pipeline<br/>enabled<br/>?"}

    IsPipelineEnabled -->|YES| PipelineLogic["Execute Pipeline<br/>Processing"]

    IsPipelineEnabled -->|NO| SerialLogic["Execute Serial<br/>Processing"]

    subgraph "Pipeline Path (4 workers, 200-300% faster)"
        PipelineLogic -->|Worker 1| Batch1["Batch 1<br/>Messages 1-50"]
        PipelineLogic -->|Worker 2| Batch2["Batch 2<br/>Messages 51-100"]
        PipelineLogic -->|Worker 3| Batch3["Batch 3<br/>Messages 101-150"]
        PipelineLogic -->|Worker 4| Batch4["Batch 4<br/>Messages 151-200"]

        Batch1 -->|Parallel| Process1["Process &<br/>index"]
        Batch2 -->|Parallel| Process2["Process &<br/>index"]
        Batch3 -->|Parallel| Process3["Process &<br/>index"]
        Batch4 -->|Parallel| Process4["Process &<br/>index"]

        Process1 -->|Gather| Results["Gather all<br/>results"]
        Process2 -->|Gather| Results
        Process3 -->|Gather| Results
        Process4 -->|Gather| Results
    end

    subgraph "Serial Path (single worker, proven, slow)"
        SerialLogic -->|Sequential| Message1["Message 1"]
        Message1 -->|Sequential| Message2["Message 2"]
        Message2 -->|Sequential| Message3["Message 3"]
        Message3 -->|Sequential| Results
    end

    Results -->|200-300%<br/>faster| Return["Return results"]

    style PipelineLogic fill:#99ff99
    style SerialLogic fill:#99ccff
    style Results fill:#00cc99
    style Return fill:#00cc99

    Note["Results identical<br/>regardless of<br/>code path"]
```

## Feature Flag Configuration: docker-compose.yml

```yaml
# Status & Reporting
KETCHUP_STATUS_UPDATER_FEATURE=true          # Enable hourly status reports
KETCHUP_JIRA_REPORTER_FEATURE=true           # Enable JIRA automation

# Access Control
KETCHUP_ACCESS_REQUEST_AUTOMATION_FEATURE=true
KETCHUP_TRUST_ENDORSEMENT_FEATURE=true       # Enable trust scoring

# Performance Optimizations
USE_PIPELINE_PROCESSING=true                  # 200-300% faster (PR #198)
KETCHUP_USE_HTTPX=true                        # HTTP/2 support
KETCHUP_HTTP2_ENABLED=true                    # Enable multiplexing
KETCHUP_KEEPALIVE_ENABLED=true                # Connection pooling
KETCHUP_KEEPALIVE_TIMEOUT=60                  # Seconds before reuse
KETCHUP_DNS_CACHE_TTL=300                     # Cache DNS 5 minutes

# Network Optimization
KETCHUP_HTTPX_POOL_SIZE=100                   # Connection pool size
KETCHUP_HTTPX_MAX_KEEPALIVE=50                # Max keepalive connections
```

## Feature Flag Lifecycle

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant Git as Git<br/>Repository
    participant Compose as docker-compose.yml
    participant Deploy as Deployment<br/>Script
    participant Prod as Production<br/>Container

    Dev->>Dev: 1. Write feature<br/>with flag<br/>if (USE_FEATURE):

    Dev->>Git: 2. Commit code<br/>+ flag checks

    Dev->>Compose: 3. Set flag<br/>default to false

    Dev->>Git: 4. Commit<br/>docker-compose.yml

    Git->>Deploy: 5. Run<br/>deploy-ketchup.sh

    Deploy->>Prod: 6. Deploy image<br/>with flag disabled

    Deploy->>Prod: 7. Verify logs<br/>New code not running

    Note over Dev,Prod: Feature disabled<br/>in production

    Dev->>Compose: 8. Enable flag<br/>on staging

    Compose->>Prod: 9. Redeploy staging<br/>with flag=true

    Note over Dev,Prod: Test on staging

    Compose->>Prod: 10. Monitor staging<br/>for 24h

    Note over Dev,Prod: Staging stable

    Compose->>Prod: 11. Enable on prod2<br/>canary

    Compose->>Prod: 12. Monitor prod2<br/>for 24h

    Note over Dev,Prod: Canary stable

    Compose->>Prod: 13. Enable on prod1<br/>full rollout

    Compose->>Prod: 14. Monitor prod1<br/>for 48h

    Note over Dev,Prod: Production stable

    Dev->>Git: 15. Remove<br/>legacy code path

    Dev->>Git: 16. Remove<br/>flag checks

    Git->>Deploy: 17. Redeploy<br/>cleaned up code
```

## Performance Impact of Feature Flags

| Feature | Enabled | Disabled | Impact |
|---------|---------|----------|--------|
| **Pipeline Processing** | Concurrent 4x workers | Single worker | 200-300% faster |
| **HTTP/2** | Multiplexing | HTTP/1.1 | 5-8% faster |
| **Keep-Alive** | Connection reuse | New connection | 94.7% reuse rate |
| **DNS Cache** | 5min TTL | Each request | Fewer lookups |
| **Status Updater** | Hourly reports | Manual only | Saves 5+ hours/week |
| **JIRA Reporter** | Auto-sync | Manual | 100% accuracy |
| **Access Automation** | Auto-approve | Manual review | Fast onboarding |

## Adding a New Feature Flag

### Step 1: Define the flag
```python
# packages/core/feature_flags.py
class FeatureFlagConfig:
    MY_NEW_FEATURE = 'KETCHUP_MY_NEW_FEATURE'
```

### Step 2: Use in code with guard
```python
# In handler or service
if self.feature_flag_service.is_enabled(FeatureFlagConfig.MY_NEW_FEATURE):
    # New code path
    result = new_implementation()
else:
    # Legacy code path
    result = legacy_implementation()
```

### Step 3: Add to docker-compose.yml
```yaml
environment:
  KETCHUP_MY_NEW_FEATURE=false  # Start disabled
```

### Step 4: Deploy and enable gradually
```bash
# Stage 1: Deployed but disabled (safe)
./deploy-ketchup.sh

# Stage 2: Enable on prod2 for testing
# Edit docker-compose.yml on prod2, set to true
# Monitor for 24h

# Stage 3: Enable on prod1
# Edit docker-compose.yml on prod1, set to true
# Monitor for 48h

# Stage 4: Remove old code path
# Delete legacy implementation
```

---

## Best Practices

✅ **Always start disabled** - Deploy with flag=false for safety
✅ **Test extensively** - Both enabled and disabled paths
✅ **Monitor metrics** - Error rates, latency, throughput
✅ **Gradual rollout** - Staging → prod2 canary → prod1
✅ **Keep legacy code** - Until 100% stable in production
✅ **Document decisions** - Why feature exists, when to remove
✅ **Timeline awareness** - Remove legacy code after 2-4 weeks stable

---

**Source of Truth**: Always check `infrastructure/docker-compose.yml` for current feature flag state
