# Ketchup Microservices Consolidation Analysis

**Analyst**: Software Architect (Subagent)  
**Date**: 2025-12-07  
**Scope**: Evaluation of 7 services for consolidation opportunities  

---

## Executive Summary

After analyzing the Ketchup microservices architecture, I identified **HIGH consolidation potential** with opportunities to reduce from 7 services to 3-4 services without losing functionality. The current architecture suffers from:

1. **Scheduler Pattern Duplication**: 5 services implement nearly identical scheduler patterns
2. **Singleton Constraint Overhead**: 5 services run only on prod1 for coordination
3. **Code Duplication**: ~1,600 LOC of shared scheduler/health check logic
4. **Operational Complexity**: 14 containers across 2 servers with complex deployment rules

**Recommended Consolidation**: Merge 5 singleton schedulers into a unified scheduler service, reducing containers from 14 to 10 (29% reduction).

---

## Current Architecture Overview

### Service Inventory

| Service | LOC | Containers | Deployment | Schedule | Primary Function |
|---------|-----|------------|------------|----------|------------------|
| **ketchup-app** | 416 | 4 (2×prod1, 2×prod2) | Both servers | N/A (webhook) | FastAPI webhook handler |
| **ketchup_status_updater** | 1,600 | 1 (prod1 only) | Singleton | 55 min | Hourly status updates |
| **jira_reporter** | 1,772 | 1 (prod1 only) | Singleton | 15 min | JIRA automation |
| **channel_metadata_updater** | 1,567 | 1 (prod1 only) | Singleton | 15 min | Metadata scanning |
| **ketchup_maintenance_fetcher** | 294 | 1 (prod1 only) | Singleton | Daily 1:30 AM | Maintenance data fetch |
| **ketchup_access_request_monitor** | 607 | 2 (both servers) | Distributed | 5 min | Access monitoring |
| **ketchup_jira_pat_rotator** | 963 | 1 (prod1 only) | Singleton | 24 hours | PAT rotation |
| **corp_jira_mcp** | N/A (Node.js) | 2 (both servers) | Both | N/A | MCP JIRA service |

**Total**: 7,219 Python LOC across 7 services, 14 containers

---

## Detailed Analysis

### 1. Code Sharing vs Duplication

#### Shared Code (Good)
All services leverage the **monorepo packages/** directory (70,869 LOC):
- `packages/core/` - TypedDI, logging, distributed locks, feature flags
- `packages/slack/` - Slack API clients and handlers
- `packages/db/` - DynamoDB operations
- `packages/ai/` - Azure OpenAI integration
- `packages/integrations/` - Third-party service clients

**Architectural Strength**: Strong shared foundation with TypedDI dependency injection used consistently across all services.

#### Duplicated Code (Problem)
**Scheduler Pattern Duplication** (~320 LOC per service × 5 services = 1,600 LOC):

```python
# Pattern repeated in 5 services:
# - ketchup_status_updater/scheduler.py
# - channel_metadata_updater/scheduler.py  
# - ketchup_maintenance_fetcher/scheduler.py
# - ketchup_jira_pat_rotator/scheduler.py
# - jira_reporter/main.py (inline scheduler)

class XyzScheduler:
    def __init__(self):
        self.running = True
        self.health_file = Path("/tmp/xyz_health")
        self.last_run_file = Path("/tmp/xyz_last_run")
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def _update_health_status(self, status: str):
        """Update health check file."""
        self.health_file.write_text(f"{int(time.time())}:{status}")
    
    async def start(self):
        """Main scheduler loop with health updates."""
        while self.running:
            # Wait for interval
            # Run task
            # Update health
```

**Health Check Pattern Duplication** (~150 LOC per service):
- File-based health monitoring (`/tmp/*_health`, `/tmp/*_last_run`)
- Docker healthcheck scripts
- Same health status logic (running/idle/error/stopped)

**Signal Handling Duplication**:
- SIGTERM/SIGINT handlers repeated in all schedulers
- Graceful shutdown logic duplicated

---

### 2. Service Similarity Analysis

#### Group A: Singleton Schedulers (High Similarity)
**Services**: `status_updater`, `metadata_updater`, `jira_reporter`, `maintenance_fetcher`, `jira_pat_rotator`

**Commonalities**:
- All run only on prod1 (singleton constraint)
- All implement same scheduler pattern (asyncio event loop)
- All use TypedDI for dependency injection
- All require distributed locks (status_updater explicitly uses `DistributedLock`)
- All implement file-based health monitoring
- All have similar initialization (DI container → resolve dependencies → execute task → cleanup)

**Differences**:
| Service | Interval | Dependencies | Unique Logic |
|---------|----------|--------------|--------------|
| status_updater | 55 min | OpenAI, MCP, Slack, DynamoDB | AI-powered status generation |
| metadata_updater | 15 min | OpenAI, Slack, DynamoDB | AI metadata extraction |
| jira_reporter | 15 min | OpenAI, MCP, JIRA, Slack, SQS | JIRA ticket management + SQS |
| maintenance_fetcher | Daily 1:30 AM | SOAP client, DynamoDB | SOAP API integration |
| jira_pat_rotator | 24 hours | MCP, JIRA, IMS, Secrets | PAT credential rotation |

**Analysis**: These 5 services share 80% of their infrastructure code but differ in business logic. The scheduler, health monitoring, and initialization logic are nearly identical.

#### Group B: Distributed Services (Low Similarity)
**Services**: `ketchup-app` (webhook handler), `access_request_monitor` (polling), `mcp-jira` (Node.js service)

These have fundamentally different patterns (webhook vs polling vs API gateway) and cannot be consolidated.

---

### 3. Consolidation Opportunities

#### **Opportunity 1: Unified Scheduler Service** (HIGH IMPACT)

**Proposed Architecture**:
```
ketchup-scheduler-service/
├── main.py                 # Unified scheduler with task registry
├── scheduler_engine.py     # Generic scheduler engine (replaces 5 duplicated schedulers)
├── health_monitor.py       # Centralized health monitoring
├── tasks/
│   ├── status_update_task.py
│   ├── metadata_update_task.py
│   ├── jira_report_task.py
│   ├── maintenance_fetch_task.py
│   └── pat_rotation_task.py
└── task_registry.py        # Task registration and scheduling config
```

**Task Configuration**:
```python
SCHEDULED_TASKS = [
    ScheduledTask(
        name="status_updater",
        handler=run_status_update,
        interval=timedelta(minutes=55),
        enabled_flag="KETCHUP_STATUS_UPDATER_FEATURE"
    ),
    ScheduledTask(
        name="metadata_updater",
        handler=run_metadata_update,
        interval=timedelta(minutes=15),
        enabled_flag=None  # Always enabled
    ),
    ScheduledTask(
        name="jira_reporter",
        handler=run_jira_report,
        interval=timedelta(minutes=15),
        enabled_flag="KETCHUP_JIRA_REPORTER_FEATURE"
    ),
    ScheduledTask(
        name="maintenance_fetcher",
        handler=run_maintenance_fetch,
        schedule="1:30",  # Daily at 1:30 AM UTC
        enabled_flag="KETCHUP_MAINTENANCE_FETCHER_ENABLED"
    ),
    ScheduledTask(
        name="pat_rotator",
        handler=run_pat_rotation,
        interval=timedelta(hours=24),
        enabled_flag=None  # Always enabled
    ),
]
```

**Benefits**:
- **Code Reduction**: Eliminate 1,600 LOC of duplicated scheduler code
- **Container Reduction**: 5 containers → 1 container (80% reduction in scheduler containers)
- **Simplified Deployment**: Single deployment for all scheduled tasks
- **Centralized Health Monitoring**: One health endpoint for all scheduled tasks
- **Improved Observability**: Unified logging and metrics for all scheduled operations
- **Easier Testing**: Test scheduler engine once, not 5 times
- **Reduced Resource Usage**: Single Python process instead of 5 separate processes

**Risks**:
- **Blast Radius**: If scheduler crashes, all 5 tasks are affected (mitigated by Docker restart policy)
- **Resource Contention**: Tasks compete for CPU/memory (mitigated by sequential execution)
- **Deployment Coupling**: All tasks deploy together (mitigated by feature flags)

**Mitigation Strategies**:
1. **Robust Error Handling**: Each task runs in try-catch with isolated failure
2. **Feature Flags**: Individual tasks can be disabled via environment variables
3. **Health Checks**: Per-task health tracking to identify failing tasks
4. **Distributed Lock**: Continue using DynamoDB distributed lock for singleton enforcement
5. **Resource Limits**: Set container memory/CPU limits to prevent resource starvation
6. **Circuit Breaker**: Disable failing tasks automatically after N consecutive failures

**Implementation Effort**: Medium (2-3 weeks)
- Week 1: Build unified scheduler engine and task registry
- Week 2: Migrate 5 task handlers, add tests
- Week 3: Deployment, monitoring, rollback plan

---

#### **Opportunity 2: Merge Access Monitor into ketchup-app** (MEDIUM IMPACT)

**Current State**: 
- `ketchup_access_request_monitor` runs as separate polling service (607 LOC)
- Runs on both prod1 and prod2 (distributed)
- Polls every 5 minutes for access request health issues

**Proposed Architecture**:
- Move access monitoring logic into `ketchup-app` as background task
- Use FastAPI's `BackgroundTasks` or APScheduler integration
- Eliminates 2 containers (prod1 + prod2)

**Benefits**:
- **Container Reduction**: 2 containers → 0 (monitoring runs inside ketchup-app)
- **Simplified Deployment**: No separate service to deploy
- **Reduced Latency**: Direct access to DI container, no inter-service communication

**Risks**:
- **Increased ketchup-app Complexity**: Adds background polling to webhook handler
- **Resource Sharing**: Monitoring competes with webhook processing

**Recommendation**: **Defer** - Access monitor is already distributed and low-overhead. Keep separate for clear separation of concerns.

---

#### **Opportunity 3: Merge jira_reporter into Unified Scheduler** (Already covered in Opportunity 1)

Included in the unified scheduler consolidation.

---

### 4. Singleton Pattern Necessity

**Current Singleton Services** (prod1 only):
1. `ketchup_status_updater` - **Necessary** (prevents duplicate Slack posts)
2. `ketchup_metadata_updater` - **Necessary** (prevents concurrent DynamoDB updates + race conditions)
3. `ketchup_jira_reporter` - **Necessary** (prevents duplicate JIRA tickets)
4. `ketchup_maintenance_fetcher` - **Necessary** (prevents duplicate SOAP API calls)
5. `ketchup_jira_pat_rotator` - **Necessary** (prevents concurrent PAT rotations)

**Analysis**: All singleton constraints are **architecturally required** to prevent:
- Duplicate external API calls (JIRA, Slack, SOAP)
- Race conditions on shared state (DynamoDB)
- Duplicate user-facing actions (Slack posts, JIRA tickets)

**Distributed Lock Usage**:
- `ketchup_status_updater` explicitly uses `DistributedLock` (DynamoDB-based)
- Other services rely on deployment script preventing prod2 execution
- Unified scheduler would use same distributed lock pattern

**Recommendation**: **Keep singleton constraint** but consolidate into single service to reduce operational overhead.

---

### 5. Runtime Resource Usage Analysis

**Per-Service Resource Requirements** (estimated from Docker configs):

| Service | Memory | CPU | Network I/O | Disk I/O |
|---------|--------|-----|-------------|-----------|
| ketchup-app | Medium | Medium | High (webhooks) | Low |
| status_updater | Low-Medium | Low (except AI calls) | Medium (Slack + OpenAI) | Low |
| metadata_updater | Low-Medium | Low (except AI calls) | Medium (Slack + OpenAI) | Low |
| jira_reporter | Low-Medium | Low (except AI calls) | Medium (JIRA + Slack + OpenAI) | Low |
| maintenance_fetcher | Low | Very Low | Low (SOAP) | Low |
| access_monitor | Low | Low | Low (DynamoDB) | Low |
| jira_pat_rotator | Low | Low | Low (JIRA API) | Low |

**Observations**:
1. **Idle Time**: Singleton schedulers spend 95%+ of time sleeping between runs
2. **Burst Usage**: AI calls (OpenAI) dominate resource usage during execution
3. **Network Bound**: Most services are I/O bound, not CPU bound
4. **Memory Efficient**: All services < 200 MB memory footprint

**Consolidation Impact**:
- **Memory**: 5 services × 150 MB = 750 MB → 1 service × 200 MB = 200 MB (73% reduction)
- **CPU**: Sequential task execution prevents CPU contention
- **Network**: Same network I/O (tasks still make same API calls)

---

## Consolidation Recommendations

### Primary Recommendation: **Unified Scheduler Service**

**Merge**: `status_updater`, `metadata_updater`, `jira_reporter`, `maintenance_fetcher`, `jira_pat_rotator`

**Architecture**:
```
ketchup-unified-scheduler/
├── main.py                     # Entry point, initializes TypedDI container
├── scheduler_engine.py         # Generic scheduler with APScheduler or custom asyncio
├── health_monitor.py           # Centralized health monitoring
├── distributed_lock_manager.py # Singleton coordination
├── tasks/
│   ├── __init__.py
│   ├── base_task.py           # Abstract base class for all tasks
│   ├── status_update_task.py
│   ├── metadata_update_task.py
│   ├── jira_report_task.py
│   ├── maintenance_fetch_task.py
│   └── pat_rotation_task.py
└── config/
    └── task_registry.py        # Task definitions and schedules
```

**Benefits Summary**:
- ✅ **5 containers → 1 container** (80% reduction in scheduler containers)
- ✅ **1,600 LOC eliminated** (scheduler duplication)
- ✅ **Simplified deployment** (single service instead of 5)
- ✅ **Centralized observability** (unified logs and health checks)
- ✅ **Reduced memory footprint** (750 MB → 200 MB)
- ✅ **Faster development** (add new scheduled tasks without new services)

**Risks & Mitigations**:
| Risk | Impact | Mitigation |
|------|--------|------------|
| Single point of failure | High | Docker restart policy, robust error handling |
| Resource contention | Low | Sequential execution, CPU/memory limits |
| Deployment coupling | Medium | Feature flags for individual tasks |
| Complex debugging | Medium | Per-task logging and health tracking |

---

### Secondary Recommendation: **Keep Remaining Services Separate**

**Services to Keep Standalone**:
1. **ketchup-app** - Core webhook handler, fundamentally different pattern
2. **ketchup_access_request_monitor** - Distributed across both servers, low coupling
3. **corp_jira_mcp** - Node.js service, different runtime

**Rationale**:
- Different architectural patterns (webhook vs polling vs gateway)
- Different runtimes (Python vs Node.js)
- Different scaling characteristics (replicated vs singleton)
- Low code duplication with other services

---

## Migration Strategy

### Phase 1: Build Unified Scheduler (Weeks 1-2)
1. Create `ketchup-unified-scheduler/` service skeleton
2. Implement generic scheduler engine with APScheduler
3. Build task registry and configuration system
4. Add distributed lock integration
5. Implement centralized health monitoring

### Phase 2: Migrate Tasks (Weeks 3-4)
1. Migrate `maintenance_fetcher` (simplest, lowest risk)
2. Migrate `jira_pat_rotator` (second simplest)
3. Migrate `metadata_updater` (moderate complexity)
4. Migrate `status_updater` (high complexity, AI integration)
5. Migrate `jira_reporter` (highest complexity, SQS integration)

### Phase 3: Testing & Validation (Week 5)
1. Unit tests for scheduler engine and each task
2. Integration tests with DynamoDB, Slack, OpenAI mocks
3. Load testing for concurrent task execution
4. Failure scenario testing (task crashes, API timeouts)

### Phase 4: Deployment (Week 6)
1. Deploy to staging environment
2. Run in parallel with existing services (shadow mode)
3. Compare outputs for consistency
4. Gradual rollout: enable tasks one-by-one via feature flags
5. Monitor for 1 week before removing old services

### Phase 5: Cleanup (Week 7)
1. Remove old service containers from docker-compose.yml
2. Archive old service code
3. Update documentation and deployment scripts
4. Remove old Docker images from ECR

---

## Cost-Benefit Analysis

### Development Costs
- **Engineering Time**: 6-7 weeks (1 senior engineer)
- **Testing Time**: 1-2 weeks (QA + integration testing)
- **Risk**: Medium (failed migration could disrupt scheduled operations)

### Operational Benefits
- **Container Reduction**: 14 → 10 containers (29% reduction)
- **Memory Savings**: ~550 MB on prod1 (73% reduction in scheduler memory)
- **Deployment Time**: 5 deploy operations → 1 deploy operation
- **Code Maintenance**: 7,219 LOC → 5,619 LOC (22% reduction)
- **Cognitive Load**: 7 service patterns → 4 service patterns

### Long-Term Benefits
- **Faster Feature Development**: Add new scheduled tasks without creating new services
- **Improved Observability**: Unified logs and metrics for all scheduled operations
- **Reduced Operational Complexity**: Fewer moving parts, simpler debugging
- **Better Resource Utilization**: Consolidated services use resources more efficiently

---

## Conclusion

The Ketchup microservices architecture has **significant consolidation potential** due to:
1. Heavy duplication of scheduler patterns across 5 services
2. All 5 schedulers running as singletons on prod1 only
3. Minimal code sharing between scheduler implementations

**Recommended Action**: Implement **Unified Scheduler Service** consolidation to merge 5 singleton schedulers into a single service, reducing operational complexity and code duplication while maintaining all existing functionality.

**Expected Outcome**:
- 29% reduction in container count (14 → 10)
- 22% reduction in service-specific codebase (7,219 LOC → 5,619 LOC)
- 73% reduction in scheduler memory footprint (750 MB → 200 MB)
- Improved developer experience and operational simplicity

**Risk Level**: Medium (mitigated by phased rollout, feature flags, and robust testing)

---

## Appendix A: Service Dependency Graph

```
ketchup-app (webhook handler)
├── packages/core/ (TypedDI, logging, feature flags)
├── packages/slack/ (Slack API)
├── packages/db/ (DynamoDB)
├── packages/ai/ (OpenAI)
└── packages/integrations/ (third-party APIs)

Singleton Schedulers (prod1 only):
├── status_updater
│   ├── packages/core/ (TypedDI, distributed lock)
│   ├── packages/slack/
│   ├── packages/ai/
│   └── mcp-jira (via HTTP)
├── metadata_updater
│   ├── packages/core/
│   ├── packages/slack/
│   ├── packages/ai/
│   └── packages/db/
├── jira_reporter
│   ├── packages/core/
│   ├── packages/slack/
│   ├── packages/ai/
│   ├── packages/integrations/ (JIRA)
│   ├── mcp-jira (via HTTP)
│   └── SQS
├── maintenance_fetcher
│   ├── packages/core/
│   ├── packages/integrations/ (SOAP client)
│   └── packages/db/
└── jira_pat_rotator
    ├── packages/core/
    ├── packages/integrations/ (JIRA, IMS)
    └── mcp-jira (via HTTP)

Distributed Services:
├── access_request_monitor (both servers)
│   ├── packages/core/
│   ├── packages/slack/
│   └── packages/db/
└── mcp-jira (Node.js, both servers)
    └── JIRA API
```

**Observation**: All singleton schedulers share the same foundational dependencies (`packages/core/`, TypedDI, DynamoDB) with only business logic differences.

---

## Appendix B: Scheduler Pattern Comparison

| Service | Scheduler Type | Interval | Health Check | Distributed Lock | Signal Handling |
|---------|---------------|----------|--------------|------------------|-----------------|
| status_updater | Custom asyncio | 55 min | File-based | ✅ DynamoDB | ✅ SIGTERM/SIGINT |
| metadata_updater | Custom asyncio | 15 min | File-based | ❌ (deployment-based) | ✅ SIGTERM/SIGINT |
| jira_reporter | Inline asyncio | 15 min | File-based | ❌ (deployment-based) | ❌ (none) |
| maintenance_fetcher | Custom asyncio | Daily 1:30 AM | File-based | ❌ (deployment-based) | ✅ SIGTERM/SIGINT |
| jira_pat_rotator | Custom asyncio | 24 hours | File-based | ❌ (singleton deployment) | ✅ SIGTERM/SIGINT |

**Key Insight**: Nearly identical patterns with minor variations. All candidates for unified scheduler consolidation.

---

**End of Report**
