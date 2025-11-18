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

**Total Containers**: 14 across 2 servers

**prod1 (ketchup-prod1.campaign.adobe.com)** - 7 containers:
1. `nginx` - Reverse proxy (port 80)
2. `ketchup-app-1` - FastAPI app replica 1 (port 8001)
3. `ketchup-app-2` - FastAPI app replica 2 (port 8001)
4. `mcp-jira` - JIRA MCP service (port 8081)
5. `ketchup-metadata-updater` - Channel metadata scanner (singleton)
6. `ketchup-status-updater` - Hourly status updates (singleton)
7. `ketchup-jira-reporter` - JIRA automation (singleton)
8. `ketchup-maintenance-fetcher` - Maintenance detection (singleton)
9. `ketchup-access-monitor` - Access request monitoring

**prod2 (ketchup-prod2.campaign.adobe.com)** - 5 containers:
1. `nginx` - Reverse proxy (port 80)
2. `ketchup-app-1` - FastAPI app replica 1 (port 8001)
3. `ketchup-app-2` - FastAPI app replica 2 (port 8001)
4. `mcp-jira` - JIRA MCP service (port 8081)
5. `ketchup-access-monitor` - Access request monitoring

**Singleton Services** (prod1 only): `ketchup-status-updater`, `ketchup-metadata-updater`, `ketchup-jira-reporter`, `ketchup-maintenance-fetcher`
- These are explicitly stopped/removed on prod2 during deployment (see deploy-ketchup.sh:505-506)
- Prevents duplicate scheduled jobs and conflicting operations

## Common Development Commands

### Setup and Testing
All commands run from the `tests/setup/` directory:

```bash
# Initial setup
make setup                 # Create venv and install dependencies

# Testing
make test-unit            # Unit tests (preferred for development)
make test-integration     # Integration tests (requires AWS profile)
make test-typed-di        # TypedDI validation tests
make pylint               # Code quality: ruff, black, isort, pylint

# JIRA Reporter Testing
make test-jira-reporter-unit
make test-jira-reporter-integration
```

**Critical**: Always run `make pylint` and `make test-unit` after code changes.

### Deployment
From the `infrastructure/` directory:

```bash
./deploy-ketchup.sh              # Deploy to both production servers
./deploy-ketchup.sh --prod1-only # Deploy to prod1 only
./deploy-ketchup.sh --prod2-only # Deploy to prod2 only
./deploy-ketchup.sh --verify     # Verify deployment status
./deploy-ketchup.sh --rollback vX.XXX.XXX  # Rollback to specific version
```

The deployment script:
1. Auto-increments version from latest in ECR
2. Builds Docker images locally
3. Pushes to ECR
4. Updates docker-compose.yml on servers
5. Deploys with zero-downtime sequential rollout

### Local Development
```bash
# Start local services
cd infrastructure
docker-compose -f docker-compose.local.yml up -d

# View logs
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
│   ├── db/               # DynamoDB operations
│   ├── integrations/     # Third-party integrations
│   ├── secrets/          # AWS Secrets Manager
│   └── slack/            # Slack API handlers
│
├── ketchup-app/          # Main FastAPI webhook service
│   └── main.py           # Entry point for ketchup-app containers
│
├── ketchup_status_updater/      # Hourly status update service
│   ├── main.py
│   └── scheduler.py
│
├── jira_reporter/               # JIRA ticket automation service
│   ├── main.py
│   ├── channel_monitor.py
│   └── jira_service.py
│
├── channel_metadata_updater/    # Metadata scanning service
│   └── main.py
│
├── ketchup_maintenance_fetcher/ # Maintenance event service
│   └── main.py
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
│   ├── Dockerfile.status-updater
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
- See `docs/TYPEDDI_MIGRATION_SUMMARY.md` for complete migration details

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

- **[High-Level Architecture Guide](./code_docs/ketchup_high_level.md)** - Complete system design and event flow (83KB)
- **[TypedDI Migration Summary](./docs/TYPEDDI_MIGRATION_SUMMARY.md)** - Modern DI system architecture (400+ lines)
- **[Code Walkthrough](./code_docs/ketchup_code_walkthrough_documentation.md)** - Component-by-component reference (595KB)

**When updating architecture or features**: Always check `infrastructure/docker-compose.yml` as the source of truth for deployed services and enabled feature flags.

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
- **Import errors**: Verify PYTHONPATH and package structure

## Version Management

- Version format: `vX.Y.Z` (e.g., `v2.360.344`)
- Deploy script auto-increments patch version
- All service images use same version tag
- Rollback capability built into deployment script

## Recent Major Changes

- **October 2025**: 300-400% performance optimization complete
- **September 2025**: TypedDI migration complete (100% coverage)
- **Architecture Migration**: Lambda → EC2 Docker (cost reduction $450-800/mo → ~$150/mo)
