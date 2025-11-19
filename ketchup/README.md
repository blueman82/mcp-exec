# Ketchup

A multi-service Slack application providing automated workflows, JIRA integration, and intelligent channel management for Adobe's internal teams.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Development](#development)
  - [Setup](#setup)
  - [Code Standards](#code-standards)
  - [Testing](#testing)
- [Deployment](#deployment)
- [Configuration](#configuration)
- [Documentation](#documentation)
  - [Technical Diagrams](#-technical-diagrams)
- [Key Components](#key-components)
- [Support](#support)

## Overview

Ketchup is built on AWS infrastructure using Docker containers and provides:

- **Automated Workflows**: Intelligent Slack channel management and automation
- **JIRA Integration**: Seamless ticket creation and status tracking via MCP protocol
- **Channel Intelligence**: AI-powered channel metadata extraction and analysis
- **Access Management**: Automated access request monitoring and processing
- **Status Updates**: Hourly automated status reporting across channels
- **Trust Endorsements**: Community-driven trust verification system

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

For comprehensive architecture documentation, see the [Documentation](#documentation) section below.

## Development

### Setup

```bash
# Set up Python environment
cd tests/setup
make setup

# Run unit tests
make test-unit

# Code quality checks
make pylint
```

### Code Standards

- **Import order**: stdlib → third-party → local/project
- **Dependency Injection**: Use TypedDI protocols, not string-based lookups
- **Protocols**: Define in `packages/core/typed_di/protocols.py`
- **Service Registration**: Register in `packages/core/typed_di/service_registration.py`

### Testing

From the `tests/setup` directory:

```bash
make test-unit              # Unit tests (preferred for development)
make test-integration       # Integration tests (requires AWS profile)
make test-jira-reporter     # JIRA reporter specific tests
make pylint                 # Code quality: ruff, black, isort, pylint
```

**Critical**: Always run `make pylint` and `make test-unit` after code changes.

**Testing Strategy**: Unit → Integration → E2E → Manual

## Deployment

From the `infrastructure` directory:

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

### Production Environment

- **Servers**: ketchup-prod1, ketchup-prod2
- **Load Balancer**: Application Load Balancer
- **Database**: ketchup_channel_information (DynamoDB)
- **Secrets**: Ketchup_Token_Secrets (AWS Secrets Manager)
- **Queue**: ketchup-events-queue (SQS)
- **Current Version**: v2.360.347

## Configuration

### AWS Environment

```bash
export AWS_PROFILE=campaign_prod_v7
export AWS_REGION=eu-west-1
```

### Feature Flags

**⚠️ Source of Truth**: All enabled feature flags are defined in `infrastructure/docker-compose.yml`. When adding or modifying features, update docker-compose.yml first.

Common feature flags:
- `KETCHUP_STATUS_UPDATER_FEATURE=true`
- `KETCHUP_JIRA_REPORTER_FEATURE=true`
- `KETCHUP_TRUST_ENDORSEMENT_FEATURE=true`
- `KETCHUP_ACCESS_REQUEST_AUTOMATION_FEATURE=true`
- `USE_PIPELINE_PROCESSING=true` (performance optimization)
- `KETCHUP_USE_HTTPX=true` (HTTP/2 support)

## Documentation

Ketchup has comprehensive architecture and implementation documentation:

- **[High-Level Architecture Guide](./docs/internal_documentation/ketchup_high_level.md)** - Complete system design, event flow, and feature flags
- **[Code Walkthrough Documentation](./docs/internal_documentation/ketchup_code_walkthrough_documentation.md)** - Detailed component-by-component reference
- **[Diagram Index & Navigation](./docs/diagrams/README.md)** - Visual documentation of infrastructure, event flows, services, and workflows
- **[Feature Flags Reference](./docs/feature_flags.md)** - Comprehensive guide to all 40+ environment variables and feature controls

**🔑 Important**: When updating architecture, services, or features, refer to `infrastructure/docker-compose.yml` as the source of truth for deployed services and enabled feature flags.

**📋 Documentation Maintenance**: Review and update documentation links and version numbers during each deployment cycle to maintain accuracy with production configuration.

### 📊 Technical Diagrams

Visual documentation of Ketchup's infrastructure, event processing, and workflows. All diagrams are in Mermaid format and render natively in GitHub.

**[📁 View All Diagrams](./docs/diagrams/)** | **[📋 Diagram Index & Navigation](./docs/diagrams/README.md)**

**Core Architecture Diagrams:**
- **[Infrastructure Architecture](./docs/diagrams/01-infrastructure-architecture.md)** - AWS infrastructure, ALB, prod1/prod2 servers, 14 containers, singleton services
- **[Slack Event Flow](./docs/diagrams/02-slack-event-flow.md)** - Complete request-response lifecycle from Slack webhooks to service responses
- **[Slash Command Processing](./docs/diagrams/03-slash-command-processing.md)** - Command routing, authorization, parameter extraction, all 10 subcommands
- **[Background Services](./docs/diagrams/04-background-services.md)** - 5 scheduled services: status updater, JIRA reporter, metadata scanner, maintenance fetcher, access monitor
- **[TypedDI Resolution](./docs/diagrams/05-typeddi-resolution.md)** - Modern dependency injection with protocol-first design and topological sorting
- **[Feature Flag Decision Tree](./docs/diagrams/06-feature-flag-decision.md)** - 3-tier flag evaluation: environment → global → channel/user specific
- **[Interactive Components](./docs/diagrams/07-interactive-components.md)** - Button interactions, access requests, trust endorsements, modals

**Additional System Diagrams:**
- **[System Architecture](./docs/diagrams/1-system-architecture.md)** - Complete AWS topology with container distribution
- **[Container Topology](./docs/diagrams/5-container-topology.md)** - What runs where: prod1 (9 containers) vs prod2 (5 containers)
- **[Two-Phase Processing](./docs/diagrams/6-two-phase-processing.md)** - How Ketchup meets Slack's 3-second response requirement
- **[Service Data Flows](./docs/diagrams/7-service-data-flows.md)** - Data models, DynamoDB structure, service interactions

**Quick Navigation:**
- **New to Ketchup?** Start with [System Architecture](./docs/diagrams/1-system-architecture.md) → [Slack Event Flow](./docs/diagrams/02-slack-event-flow.md)
- **Adding a feature?** Review [Command Routing](./docs/diagrams/03-slash-command-processing.md) → [Service Data Flows](./docs/diagrams/7-service-data-flows.md)
- **Debugging?** Check [Two-Phase Processing](./docs/diagrams/6-two-phase-processing.md) → [Event Flow](./docs/diagrams/02-slack-event-flow.md)
- **Deploying?** See [Container Topology](./docs/diagrams/5-container-topology.md) → [Feature Flags](./docs/diagrams/8-feature-flags.md)

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

For issues and feature requests:

- **Slack**: [#ketchup_feedback](https://adobe.enterprise.slack.com/archives/C08CQN1JCSC)
- **Email**: [org-omeara-all@adobe.com](mailto:org-omeara-all@adobe.com)
