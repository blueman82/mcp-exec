# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Ketchup is a multi-service Slack application providing automated workflows, JIRA integration, and intelligent channel management for Adobe's internal teams. Built on AWS infrastructure using Docker containers on EC2, it provides AI-powered summarization, automated status reporting, and access management.

## Infrastructure

### AWS Configuration
- **Profile**: `campaign_prod_v7`
- **Region**: `eu-west-1`
- **ECR**: `483013340174.dkr.ecr.eu-west-1.amazonaws.com`

### Production Servers
- **prod1**: `ketchup-prod1.campaign.adobe.com` (runs all services including singletons)
- **prod2**: `ketchup-prod2.campaign.adobe.com` (core services only, excluding singletons)
- **Load Balancer**: Application Load Balancer routing traffic to both servers
- **Deployment Path**: `/opt/ketchup` on both servers

### AWS Resources
- **DynamoDB Table**: `ketchup_channel_information`
- **Secrets Manager**: `Ketchup_Token_Secrets`
- **SQS Queue**: `ketchup-events-queue` (https://sqs.eu-west-1.amazonaws.com/483013340174/ketchup-events-queue)

### Docker Containers in Production

**Total Containers**: 11 across 2 servers

**prod1 (ketchup-prod1.campaign.adobe.com)** - 6 containers:
1. `nginx` - Reverse proxy (port 80)
2. `ketchup-app-1` - FastAPI app replica 1 (port 8001)
3. `ketchup-app-2` - FastAPI app replica 2 (port 8001)
4. `mcp-jira` - JIRA MCP service (port 8081)
5. `ketchup-unified-scheduler` - Unified scheduler running 5 tasks (singleton):
   - `metadata_updater` (every 15 min)
   - `status_updater` (every 55 min)
   - `jira_reporter` (continuous monitoring)
   - `maintenance_fetcher` (daily at 1:30 UTC)
   - `pat_rotator` (every 24 hours)
6. `ketchup-access-monitor` - Access request monitoring

**prod2 (ketchup-prod2.campaign.adobe.com)** - 5 containers:
1. `nginx` - Reverse proxy (port 80)
2. `ketchup-app-1` - FastAPI app replica 1 (port 8001)
3. `ketchup-app-2` - FastAPI app replica 2 (port 8001)
4. `mcp-jira` - JIRA MCP service (port 8081)
5. `ketchup-access-monitor` - Access request monitoring

**Singleton Services** (prod1 only): `ketchup-unified-scheduler`
- This is explicitly stopped/removed on prod2 during deployment (see deploy-ketchup.sh)
- Prevents duplicate scheduled jobs and conflicting operations

## Developer Setup

### Package Management
This project uses **uv** for Python dependency management (not pip).

**First time setup** (run once from project root):
```bash
./setup      # Sets up test venv + git hooks
uv sync      # Installs project dependencies to .venv/
```

### Virtual Environments
Two venvs exist for different purposes:
- `.venv/` (root) - Project runtime dependencies, managed by `uv sync`
- `tests/setup/.venv/` - Linting/testing tools, managed by pip

**When to use each:**
```bash
uv sync                    # Install/update project dependencies
. .venv/bin/activate       # For running project code, imports
cd tests/setup && make ... # For running tests (uses its own venv)
```

## Developer Workflow

**Daily workflow is automated via git hooks:**
- **Pre-commit**: Quick lint check (ruff) ~5s
- **Pre-push**: Full lint check (ruff, black, isort) ~10s
- **Deploy**: Validation gate built-in

**You rarely need manual commands.** Just code, commit, and push.

### Manual Commands (if needed)

From project root:
```bash
./check              # Run lint checks
./check --fix        # Auto-fix lint issues
./deploy             # Deploy to production
```

### Testing

From `tests/setup/` directory:
```bash
make test-fast       # Critical tests (~10s) - during development
make test-parallel   # All unit tests (~15s) - before PR
make test-typed-di   # TypedDI validation
make test-integration # AWS tests (requires AWS_PROFILE)
```

### Deployment

```bash
./deploy                         # Deploy to both servers
./deploy --prod1-only            # Deploy to prod1 only
./deploy --prod2-only            # Deploy to prod2 only
./deploy --verify                # Verify deployment status
./deploy --rollback vX.XXX.XXX   # Rollback to specific version
```

The deployment script:
1. Runs validation checks automatically
2. Auto-increments version from latest in ECR
3. Builds Docker images locally
4. Pushes to ECR
5. Deploys with zero-downtime sequential rollout

### Local Development
```bash
cd infrastructure
docker-compose -f docker-compose.local.yml up -d
docker-compose logs -f ketchup-app
```

## Repository Structure

### This is a Monorepo
All Ketchup services share the same repository and the `packages/` directory:

```
ketchup/
├── packages/              # Shared code used by ALL services
│   ├── ai/               # Azure OpenAI integration
│   ├── core/             # Core utilities, TypedDI, HTTP clients
│   │   └── schedulers/   # BaseScheduler pattern for background services
│   ├── db/               # DynamoDB operations
│   ├── integrations/     # Third-party integrations
│   ├── secrets/          # AWS Secrets Manager
│   └── slack/            # Slack API handlers
│
├── ketchup-app/          # Main FastAPI webhook service
│   └── main.py           # Entry point for ketchup-app containers
│
├── ketchup_unified_scheduler/   # Unified scheduler orchestrating all background tasks
│   ├── main.py
│   ├── engine.py                # UnifiedSchedulerEngine
│   ├── task_config.py           # TaskConfig dataclass
│   ├── task_registry.py         # TaskRegistry for task management
│   ├── health_monitor.py        # PerTaskHealthMonitor
│   └── tasks/                   # Individual task handlers
│       ├── metadata_updater_task.py
│       ├── status_updater_task.py
│       ├── jira_reporter_task.py
│       ├── maintenance_fetcher_task.py
│       └── pat_rotator_task.py
│
├── ketchup_status_updater/      # [Legacy] Hourly status update service
│   ├── main.py
│   └── scheduler.py
│
├── jira_reporter/               # [Legacy] JIRA ticket automation service
│   ├── main.py
│   ├── channel_monitor.py
│   └── jira_service.py
│
├── channel_metadata_updater/    # [Legacy] Metadata scanning service
│   └── main.py
│
├── ketchup_maintenance_fetcher/ # [Legacy] Maintenance event service
│   └── main.py
│
├── ketchup_jira_pat_rotator/    # [Legacy] JIRA PAT rotation service
│   ├── main.py
│   ├── scheduler.py
│   └── rotator.py
│
├── ketchup_access_request_monitor/ # Access monitoring service
│   └── main.py
│
├── corp_jira_mcp/              # MCP JIRA integration service
│   └── (Node.js service)
│
├── infrastructure/              # Docker configs & deployment
│   ├── docker-compose.yml
│   ├── deploy-ketchup.sh
│   ├── Dockerfile.app-multistage
│   ├── Dockerfile.unified-scheduler
│   └── ... (other Dockerfiles)
│
└── tests/                       # Shared test suite
    └── setup/Makefile           # All test commands run from here
```

**Key Point**: Each service imports from the shared `packages/` directory. There is ONE CLAUDE.md at the repository root covering all services.

### Key Architectural Patterns

#### TypedDI Dependency Injection System
- **Location**: `packages/core/typed_di/`
- Modern type-safe dependency injection replacing legacy string-based DI
- Protocol-first design with compile-time validation
- All 7 production services use pure TypedDI (no legacy DI)
- See `docs/diagrams/05-typeddi-resolution.md` and `docs/diagrams/3-typed-di-architecture.md` for visual reference

**Key Files**:
- `typed_service_registry.py` - Main DI container with topological sorting
- `protocols.py` - Protocol definitions for all services
- `service_registration.py` - Registration logic for all services

#### Two-Phase Processing
Slack requires responses within 3 seconds, but AI operations take longer. Solution:
1. **Quick Response Phase**: FastAPI endpoint immediately acknowledges (HTTP 200)
2. **Background Processing Phase**: FastAPI BackgroundTasks handles actual work asynchronously

#### Async Client Pattern
All external service communication uses async clients:
- Inherit from `core/async_client.py`
- Use `aiohttp` for HTTP requests
- Implement retry logic and connection pooling
- Always use `await` keyword when calling client methods

#### Unified Scheduler Architecture
- **Location**: `ketchup_unified_scheduler/`
- Single container orchestrating all 5 background tasks using a shared TypedDI container
- **Engine**: `UnifiedSchedulerEngine` manages task lifecycle and execution
- **Task Management**: `TaskRegistry` with `TaskConfig` dataclass for declarative task definitions
- **Health Monitoring**: `PerTaskHealthMonitor` tracks individual task health and execution metrics
- **Tasks Consolidated**:
  - `metadata_updater` (every 15 min)
  - `status_updater` (every 55 min)
  - `jira_reporter` (continuous monitoring)
  - `maintenance_fetcher` (daily at 1:30 UTC)
  - `pat_rotator` (every 24 hours)
- **Benefits**: Single DI container initialization, unified healthcheck endpoint, simplified deployment
- Legacy individual scheduler containers marked `[Legacy]` in repository structure, kept for rollback capability
- See `docs/diagrams/04-background-services.md` for visual reference

### Event Flow
```
Slack Event → ALB → Nginx → FastAPI Endpoint → Background Task → DI Container → Service Layer → Response to Slack
```

### Feature Flags
All features controlled via environment variables in `docker-compose.yml`:
- `KETCHUP_STATUS_UPDATER_FEATURE=true`
- `KETCHUP_JIRA_REPORTER_FEATURE=true`
- `KETCHUP_TRUST_ENDORSEMENT_FEATURE=true`
- `KETCHUP_ACCESS_REQUEST_AUTOMATION_FEATURE=true`
- `USE_PIPELINE_PROCESSING=true` (59% performance improvement)
- `KETCHUP_USE_HTTPX=true` / `KETCHUP_HTTP2_ENABLED=true` (5-8% performance gain)

**Source of Truth**: Always check `infrastructure/docker-compose.yml` for current feature flag states.

## Performance Optimizations (October 2025)

Recent performance initiative achieved 300-400% combined improvement:

**Phase 1 - Slack Message Retrieval** (PR #198):
- Pipeline processing with parallel execution
- 4 concurrent workers for batch operations
- 200-300% overall performance improvement

**Phase 2 - HTTP Connection Optimization** (PR #201):
- Keep-alive tuning: 94.7% connection reuse rate
- HTTP/2 migration via httpx library
- 7-11% additional performance gain

**Environment Variables**:
```yaml
USE_PIPELINE_PROCESSING=true
KETCHUP_KEEPALIVE_ENABLED=true
KETCHUP_KEEPALIVE_TIMEOUT=60
KETCHUP_DNS_CACHE_TTL=300
KETCHUP_USE_HTTPX=true
KETCHUP_HTTP2_ENABLED=true
```

## Code Standards

### Import Order
- Standard library
- Third-party packages
- Local/project imports

### Dependency Injection
- Use TypedDI protocols, not string-based lookups
- Define protocols in `packages/core/typed_di/protocols.py`
- Register services in `packages/core/typed_di/service_registration.py`

### Testing Strategy
Unit → Integration → E2E → Manual

## Important Documentation

- **[High-Level Architecture Guide](./docs/internal_documentation/ketchup_high_level.md)** - Complete system design and event flow
- **[Code Walkthrough](./docs/internal_documentation/ketchup_code_walkthrough_documentation.md)** - Component-by-component reference
- **[Diagram Index & Navigation](./docs/diagrams/README.md)** - Visual documentation of infrastructure, services, and workflows
- **[Feature Flags Reference](./docs/internal_documentation/ketchup_feature_flags.md)** - Comprehensive guide to all environment variables and feature controls

**When updating architecture or features**: Always check `infrastructure/docker-compose.yml` as the source of truth for deployed services and enabled feature flags.

**Documentation Maintenance**: During each release cycle, review and update CLAUDE.md and README.md to ensure all references remain accurate and aligned with production docker-compose.yml.

## Common Tasks

### Adding a New Slash Command
1. Create command handler in `packages/slack/commands/`
2. Implement `SlackCommandProtocol` interface
3. Register in TypedDI: `service_registration.py`
4. Add route in `ketchup-app/main.py`
5. Update eligibility checks if needed

### Adding a New Feature Flag
1. Add environment variable to `infrastructure/docker-compose.yml`
2. Create feature flag service in `packages/core/feature_flags/`
3. Implement flag checks in relevant handlers
4. Add tests for both enabled/disabled states
5. Document in README.md

### Adding a New Async Client
1. Create client in appropriate package (e.g., `packages/integrations/`)
2. Inherit from `AsyncClient` base class
3. Define protocol in `typed_di/protocols.py`
4. Implement required methods with proper error handling
5. Register in `typed_di/service_registration.py`
6. Add unit tests with mocked responses

## Security Notes

- Never commit AWS credentials or tokens
- Secrets managed via AWS Secrets Manager (`Ketchup_Token_Secrets`)
- Use `secrets` package for all credential access
- Be cautious of XSS, SQL injection, and command injection vulnerabilities

## Logging Architecture

### ⚠️ CloudWatch is NOT Used
**Important**: Ketchup does NOT use AWS CloudWatch for logging. All logs are handled locally.

### How Logs Work
All services use **Docker's json-file logging driver** with automatic rotation:
- **Driver**: `json-file`
- **Rotation**: `max-size: "10m"`, `max-file: "3"` (30MB per service)
- **Storage**: Local disk on EC2 instances at `/opt/ketchup/logs/`
- **Volume Mapping**: `./logs:/var/log` in docker-compose.yml

**Why Not CloudWatch?**
- Cost savings (no CloudWatch Logs fees)
- Faster log access (local storage)
- Better performance (no network calls)
- Custom log viewer provides superior UX

### Viewing Logs

**Option 1: Custom Log Viewer (Recommended)**
```bash
cd ketchup-log-viewer
npm install
npm run dev  # http://localhost:3000
```

Features:
- Real-time streaming via Server-Sent Events (SSE)
- Okta 2FA authentication for SSH access
- Monitor up to 9 containers simultaneously across prod1/prod2
- Advanced search with regex, saved searches, pattern alerts
- Virtual scrolling for 100k+ log lines
- ANSI color support, dark/light theme
- Export logs, jump to timestamps

**Option 2: Direct SSH Access**
```bash
# SSH to server and view logs
ssh ketchup-prod1.campaign.adobe.com
sudo docker-compose -f /opt/ketchup/docker-compose.yml logs -f ketchup-app

# View specific service
sudo docker logs -f ketchup-app-1

# View all logs
sudo docker-compose -f /opt/ketchup/docker-compose.yml logs -f
```

## Debugging

### Common Issues
- **DI resolution errors**: Check protocol is registered in `service_registration.py`
- **Feature not working**: Verify feature flag is enabled in docker-compose.yml
- **Slow responses**: Check HTTP/2 and pipeline processing flags
- **Import errors**: Run `uv sync` to install dependencies, verify PYTHONPATH and package structure

## Version Management

- Version format: `vX.Y.Z` (e.g., `v2.360.344`)
- Deploy script auto-increments patch version
- All service images use same version tag
- Rollback capability built into deployment script

## Recent Major Changes

- **December 2025**: Phase 1 Unified Scheduler Consolidation - 5 scheduler containers consolidated into 1 (`ketchup-unified-scheduler`) with shared TypedDI container, per-task health monitoring, and unified orchestration engine
- **October 2025**: 300-400% performance optimization complete
- **September 2025**: TypedDI migration complete (100% coverage)
- **Architecture Migration**: Lambda → EC2 Docker (cost reduction $450-800/mo → ~$150/mo)
