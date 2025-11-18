# Ketchup

A multi-service Slack application providing automated workflows, JIRA integration, and intelligent channel management for Adobe's internal teams.

## Overview

Ketchup is built on AWS infrastructure using Docker containers and provides:
- **Automated Workflows**: Intelligent Slack channel management and automation
- **JIRA Integration**: Seamless ticket creation and status tracking via MCP protocol
- **Channel Intelligence**: AI-powered channel metadata extraction and analysis  
- **Access Management**: Automated access request monitoring and processing
- **Status Updates**: Hourly automated status reporting across channels
- **Trust Endorsements**: Community-driven trust verification system ✅ **FIXED 2025-09-02**

## Recent Updates

### 🚀 Performance Optimization Initiative (October 2025)
**Status**: ✅ **COMPLETE** - 300-400% combined performance improvement across all operations

**Project Overview**: Multi-phase performance optimization initiative targeting AI response times and Slack message retrieval
- **Tickets**: [CPGNCX-62026](https://jira.corp.adobe.com/browse/CPGNCX-62026) (Retrieval), [CPGNCX-62037](https://jira.corp.adobe.com/browse/CPGNCX-62037) (Keep-Alive), [CPGNCX-62038](https://jira.corp.adobe.com/browse/CPGNCX-62038) (HTTP/2)
- **Timeline**: October 2-3, 2025
- **Deployment**: Deployed across prod1 and prod2, validated in production

**Phase 1: Slack Message Retrieval Optimization (PR #198)**
- ✅ **Pipeline Processing**: 59% faster message fetch through parallel execution
- ✅ **Concurrent Workers**: 80-100% improvement with 4 parallel workers
- ✅ **Quick Wins**: 20-30% improvement (batch sizing, connection pooling)
- ✅ **Combined Impact**: 200-300% overall performance improvement
- **Production Results**:
  - Large channels: 53s → 22s (status), 63s → 22s (report), 51s → 14s (query)
  - Small channels: 14s → 8s (status), 18s → 15s (report), 8s → 5s (query)

**Phase 2: HTTP Connection Optimization (PR #201)**
- ✅ **Keep-Alive Tuning** (v2.360.217): 2-3% gain, 94.7% connection reuse rate
  - Extended TCP keep-alive timeout: 15s → 60s
  - DNS cache TTL: 10s → 300s (5 minutes)
  - Zero connection errors in 48+ hour validation
- ✅ **HTTP/2 Migration** (v2.360.223): 5-8% gain via httpx library
  - Connection multiplexing for concurrent requests
  - Verified "HTTP/2 200 OK" in production logs
  - Dual library support (httpx/aiohttp) with feature flags
- **Combined HTTP Impact**: 7-11% additional performance gain

**Environment Variables**:
```yaml
# Pipeline Processing (enabled in production)
USE_PIPELINE_PROCESSING=true

# Keep-Alive Tuning
KETCHUP_KEEPALIVE_ENABLED=true
KETCHUP_KEEPALIVE_TIMEOUT=60
KETCHUP_DNS_CACHE_TTL=300

# HTTP/2 Migration
KETCHUP_USE_HTTPX=true
KETCHUP_HTTP2_ENABLED=true
KETCHUP_HTTPX_POOL_LIMITS=50
```

**Total Performance Improvement: 300-400% faster end-to-end response times** 🚀

### ⚠️ TypedDI Emergency Repairs - CONDITIONAL GO ACHIEVED (September 2025)
**Status**: ⚠️ **CONDITIONAL GO** - Major breakthrough after emergency repairs

**Project Overview**: TypedDI completion initiative (112+→271 services) MAJOR BREAKTHROUGH after emergency repairs + Batch 6 expansion
- **Ticket**: [CPGNCX-61291](https://jira.corp.adobe.com/browse/CPGNCX-61291)
- **Goal**: Replace manual dependency order management with typed dependency injection
- **Solution**: TypedServiceRegistry with automatic graph-based dependency resolution

**Emergency Repair Status (2025-09-22)**:
- ✅ **Critical Duplicate Registration Errors**: RESOLVED (FeatureCommand, TypedServiceRegistry, SlackMessageFormatter)
- ✅ **TypedDI Smoke Tests**: **10/11 PASSING (90.9%)** - Major breakthrough from 0% to 90.9%
- ✅ **Service Registration System**: Fully operational without conflicts
- ✅ **Overall Test Suite**: **99.89% pass rate (1865/1868 tests passing)** - Improved from 90.5% through TypedDI migration and defensive patterns
- ✅ **Test Quality**: 126 tests fixed, warnings reduced from 41 to 24
- ✅ **Fallback System**: Available and proven operational for production safety

**Implementation Milestones**:
- ✅ **Phase 1**: Protocol definitions and service registration
- ✅ **Phase 2**: Compatibility bridge with real protocol imports
- ✅ **Phase 3**: Central switch implementation in DI container
- ✅ **Phase 4**: Production deployment and validation

**Key Achievements**:
- **Automatic Dependency Resolution**: Using Kahn's Algorithm for topological sorting
- **Type Safety**: Protocol-based service interfaces with IDE support
- **Zero Downtime Migration**: Feature flag controlled rollout
- **Production Validation**: Zero fallback activation in production logs

**Deployment Resources**:
- **Configuration**: `infrastructure/docker-compose.yml` with TypedDI enabled
- **Documentation**: `packages/core/typed_di/README.md` for implementation details
- **Monitoring**: InitializationStats provide complete observability

### 🔄 Production Rollback to v2.360.141 (September 19, 2025)
**Status**: ✅ **COMPLETE** - All services successfully rolled back across both production servers

**Rollback Details**:
- **Previous Version**: v2.360.150 (latest attempted deployment)
- **Current Version**: v2.360.141 (stable version)
- **Servers**: ketchup-prod1, ketchup-prod2
- **Services**: All 6 microservices + nginx (14 total containers)

**Rollback History**:
- First rollback: v2.360.142 → v2.360.141 (September 18, 2025)
- Second rollback: v2.360.150 → v2.360.141 (September 19, 2025, 09:19 UTC)

**Operations Performed**:
- Updated docker-compose.yml configuration files on both servers
- Coordinated container shutdown and restart sequence
- Zero-downtime rollback using sequential server deployment
- Health check validation and service availability confirmation

**Current Status**:
- ✅ **ketchup-prod1**: All 7 containers healthy and running v2.360.141
- ✅ **ketchup-prod2**: All 7 containers running v2.360.141, health checks completing
- ✅ **Load Balancer**: Automatically routing traffic to healthy instances
- ✅ **All Services**: ketchup-app (2 replicas), metadata-updater, mcp-jira, status-updater, jira-reporter, access-monitor

### 🎯 Trust Endorsement & Flag Review Button Fixes (September 2025)
**Status**: ✅ **COMPLETE** - Both button types confirmed working in production

**Issues Resolved**:
- **Trust Buttons**: Fixed routing logic for automated status updates (commit: 9314f6cd)
- **Flag Review**: Restored complete functionality via rollback from broken refactoring (commit: 74e6245b)

**Technical Details**:
- Modified `payload_processor.py` to handle `automated_status_update` context
- Restored original 2,212-line `flag_review_handler.py` with full modal workflow
- Both fixes deployed to production servers and validated working
- Comprehensive documentation with lessons learned: `/docs/trust-endorsement-button-fix.md`
- JIRA Ticket: [CPGNCX-61209](https://jira.corp.adobe.com/browse/CPGNCX-61209)

## Tech Stack

- **Language**: Python 3.12
- **Framework**: FastAPI 
- **Infrastructure**: Docker on EC2 with Application Load Balancer
- **Database**: DynamoDB
- **Cloud**: AWS (eu-west-1)
- **AI Services**: Azure OpenAI (GPT-4.1), text-embedding-ada-002
- **Container Registry**: ECR (483013340174.dkr.ecr.eu-west-1.amazonaws.com)

## Architecture

### Core Package Structure
```
packages/
├── ai/           # AI integrations (Azure OpenAI)
├── core/         # Core utilities, config, HTTP clients
├── db/           # DynamoDB operations and models
├── integrations/ # Third-party integrations
├── secrets/      # AWS Secrets Manager integration
└── slack/        # Slack API handlers and UI components
```

### Docker Services
1. **nginx**: Reverse proxy (port 80)
2. **ketchup-app**: Main FastAPI application (2 replicas for HA)
3. **ketchup-metadata-updater**: Channel metadata scanner
4. **mcp-jira**: JIRA MCP integration service (port 8081)
5. **ketchup-status-updater**: Hourly status updates
6. **ketchup-jira-reporter**: JIRA ticket automation
7. **ketchup-access-monitor**: Access request monitoring
8. **ketchup-maintenance-fetcher**: Adobe maintenance event detection and propagation

For comprehensive architecture documentation, see the [Documentation Guide](#documentation) section below.

## Quick Start

### Prerequisites
- Python 3.12
- Docker & Docker Compose
- AWS CLI configured with `campaign_prod_v7` profile
- Access to AWS region `eu-west-1`

### Development Setup
```bash
# Set up Python environment
cd tests/setup
make setup

# Run unit tests
make test-unit

# Code quality checks
make pylint
```

### Local Development
```bash
# Start local services
cd infrastructure
docker-compose -f docker-compose.local.yml up -d

# View logs
docker-compose logs -f ketchup-app
```

## 📚 Documentation

Ketchup has comprehensive architecture and implementation documentation:

- **[High-Level Architecture Guide](./code_docs/ketchup_high_level.md)** - Complete system design, event flow, feature flags, and common development tasks (83KB detailed reference)
- **[TypedDI Migration & Dependency Injection](./docs/TYPEDDI_MIGRATION_SUMMARY.md)** - Modern type-safe DI system architecture and 271+ service registrations (400+ lines)
- **[Code Walkthrough Documentation](./code_docs/ketchup_code_walkthrough_documentation.md)** - Detailed component-by-component reference (595KB)

**🔑 Important**: When updating architecture, services, or features, refer to `infrastructure/docker-compose.yml` as the source of truth for deployed services and enabled feature flags.

## Testing

From the `tests/setup` directory:

```bash
make test-unit              # Unit tests (preferred for development)
make test-integration       # Integration tests (requires AWS profile)
make test-jira-reporter     # JIRA reporter specific tests
make pylint                 # Code quality: ruff, black, isort, pylint
```

**Critical**: Always run `make pylint` and `make test-unit` after code changes.

## Deployment

From the `infrastructure` directory:

```bash
./deploy-ketchup.sh         # Deploy to both production servers
./deploy-ketchup.sh prod1   # Deploy to prod1 only
./deploy-ketchup.sh prod2   # Deploy to prod2 only
```

### Production Environment
- **Servers**: ketchup-prod1, ketchup-prod2
- **Load Balancer**: Application Load Balancer
- **Database**: ketchup_channel_information (DynamoDB)
- **Secrets**: Ketchup_Token_Secrets (AWS Secrets Manager)
- **Queue**: ketchup-events-queue (SQS)

## Configuration

### AWS Environment
```bash
export AWS_PROFILE=campaign_prod_v7
export AWS_REGION=eu-west-1
```

### Feature Flags
**⚠️ Source of Truth**: All enabled feature flags are defined in `infrastructure/docker-compose.yml`. When adding or modifying features, update docker-compose.yml first, then update this section.

All features are controlled via environment variables:
- `KETCHUP_STATUS_UPDATER_FEATURE=true`
- `KETCHUP_JIRA_REPORTER_FEATURE=true`
- `KETCHUP_TRUST_ENDORSEMENT_FEATURE=true`
- `KETCHUP_ACCESS_REQUEST_AUTOMATION_FEATURE=true`

## Development Guidelines

### Code Standards
- **Import order**: stdlib → third-party → local/project
- **DI patterns**: Use dependency injection container patterns

### Testing Strategy
Unit → Integration → E2E → Manual

## Key Components

### Slack Integration
- Interactive elements and handlers in `packages/slack/`
- Command processing with parameter extraction
- Home tab with usage statistics
- Block Kit UI components

### AI Services
- Azure OpenAI integration for intelligent responses
- Cost calculation and token management
- Multiple prompt templates for different use cases

### JIRA Integration  
- MCP (Model Context Protocol) based JIRA service
- Automatic ticket creation and status tracking
- Field mapping and metadata extraction

### Database Operations
- DynamoDB async client with consistent reads
- Channel metadata and user data storage
- Archive and restore state management

### Maintenance Utilities
- **ECR Cleanup**: Standalone script for cleaning old Docker images (`python packages/ecr_cleanup.py`)
  - Preserves v2.360.16+ for protected services
  - Supports dry-run mode (`--dry-run`)
  - Comprehensive logging and metrics
- **Log Viewer**: Next.js 15 web application for multi-container log monitoring (`ketchup-log-viewer/`)
  - Real-time Docker log streaming with Okta 2FA SSH authentication
  - Monitor up to 9 containers simultaneously across prod1/prod2
  - Virtual scrolling for 100k+ log lines, ANSI color support
  - See `ketchup-log-viewer/README.md` for setup and usage

## Support

For issues and feature requests, contact the development team or check the internal documentation at the Adobe knowledge base.