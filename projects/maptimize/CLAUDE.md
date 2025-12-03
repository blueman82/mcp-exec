# Maptimize - Claude Code Memory File

## Project Overview

Maptimize is a production-ready Slack bot that optimizes task mapping, process management, and team collaboration through intelligent message formatting and Jira integration. Current version: 0.1.0 (Alpha).

## Architecture

### Communication Pattern
- **Slack Socket Mode**: Persistent WebSocket connection for secure, outbound-only communication
- **No public HTTP endpoints required**: All events handled via Socket Mode
- **Async-first design**: Built with Python asyncio for high-performance concurrent operations

### Core Components
```
Bot (bot.py)           → Main Slack Bolt application entry point
Config (config.py)     → AWS Secrets Manager integration for credentials
Handlers (handlers.py) → Slack event handlers (mentions, slash commands)
Formatter (formatter.py) → Block Kit message formatting utilities
Utils (utils.py)       → General utility functions
```

### External Integrations
- **Slack**: Socket Mode + REST API for messaging
- **Jira**: Task creation, querying, status updates
- **AWS Secrets Manager**: Secure token storage
- **AWS EC2**: Production deployment environment

## Tech Stack

### Core Dependencies
- Python 3.11+ (async/await, modern type hints)
- slack-bolt (async Slack app framework)
- aioboto3 (async AWS SDK)
- structlog (structured logging)
- pydantic (data validation)
- httpx (async HTTP client)

### Development Tools
- pytest (testing with async support)
- mypy (static type checking)
- black (code formatting)
- ruff (fast Python linter)
- Docker (containerization)

## Project Structure

```
src/maptimize/              # Source code
├── __init__.py            # Package initialization
├── __main__.py            # CLI entry point
├── bot.py                 # Slack bot initialization
├── config.py              # Configuration & AWS Secrets
├── handlers.py            # Event handlers
├── formatter.py           # Message formatting
└── utils.py               # Utilities

tests/                      # 200+ tests, 80%+ coverage
├── test_bot.py
├── test_config.py
├── test_handlers.py
├── test_formatter.py
├── test_integration.py
├── test_e2e_bot.py
└── ... (more test files)

infrastructure/             # Deployment & CI/CD
├── Dockerfile             # Multi-stage Docker build
├── docker-compose.yml     # Local development
├── docker-compose.production.yml
├── validate.sh            # Local CI validation (pytest, mypy, ruff, black)
├── deploy.sh              # Full deployment with validation gate
├── deploy-ec2.sh          # EC2 runtime deployment (systemd hook)
├── launch-ec2.sh          # EC2 launcher
├── user-data.sh           # EC2 initialization
├── maptimize.service      # Systemd service
└── iam/                   # IAM policy definitions

config/
└── processes.json         # Process definitions

docs/                       # Documentation
├── DEPLOYMENT.md          # Deployment guide
├── TROUBLESHOOTING.md     # Troubleshooting guide
└── plans/                 # Implementation plans (YAML)
    └── maptimize-slack-bot/
```

## Development Workflow

### Running Locally
```bash
# Docker Compose (recommended)
docker-compose up --build

# Python directly
python -m maptimize.bot
```

### Testing
```bash
# All tests with coverage
pytest --cov=src/maptimize --cov-report=html

# Specific test file
pytest tests/test_bot.py -v

# By marker
pytest -m unit
pytest -m integration
```

### Code Quality
```bash
mypy src/              # Type checking
black src/ tests/      # Formatting
ruff check src/ tests/ # Linting
```

## Configuration

### Environment Variables
Required in `.env`:
```
SLACK_TOKENS_SECRET_ID=maptimize/slack-tokens
AWS_REGION=eu-west-1
ENVIRONMENT=development
LOG_LEVEL=INFO
```

### AWS Secrets Manager
Slack tokens stored as JSON:
```json
{
  "app_token": "xapp-...",
  "bot_token": "xoxb-..."
}
```

### Process Configuration
`config/processes.json` defines process mappings and optimization rules.

## Deployment

### AWS Infrastructure
- **EC2**: Compute instances running Docker containers
- **Secrets Manager**: Secure credential storage
- **IAM**: Least privilege policies for service access
- **ECR**: Docker image registry (483013340174.dkr.ecr.eu-west-1.amazonaws.com/maptimize)
- **AWS Profile**: campaign_prod_v7

### Local CI/CD Pipeline
GitHub Actions is disabled at the organization level, so all deployments use a local CI/CD pipeline with validation gate.

**Workflow:**
1. Code validation (pytest, mypy, ruff, black) - MUST pass before build
2. Version auto-increment from ECR tags (semantic versioning)
3. Docker image build
4. Image tagging (version + latest)
5. ECR push

**Deploy Script:**
```bash
# Full deployment (with validation)
bash infrastructure/deploy.sh

# Preview without pushing
bash infrastructure/deploy.sh --dry-run

# Skip validation (dangerous, not recommended)
bash infrastructure/deploy.sh --skip-validation

# Build without Docker cache
bash infrastructure/deploy.sh --no-cache
```

**Validate Script (runs independently):**
```bash
# Validate code before deployment
bash infrastructure/validate.sh

# Auto-fix style issues
bash infrastructure/validate.sh --fix

# Quick check (ruff only, skip slow tests)
bash infrastructure/validate.sh --quick

# Verbose output
bash infrastructure/validate.sh -v
```

**Using Make (recommended for developers):**
```bash
# Validate code
make validate

# Deploy to ECR
make deploy

# Preview deployment
make deploy-dry

# Run tests
make test

# Auto-fix code style
make fix

# See all available commands
make help
```

### Deployment Flow Details
- **Validation Gate**: All checks (pytest, mypy, ruff, black) must pass before Docker build
- **Version Management**: Auto-detects patch/minor/major from commit messages
- **Dry-Run Support**: Preview deployments without pushing to ECR
- **Error Handling**: Comprehensive error checking with detailed messages

### Health Monitoring
```bash
# Container health
docker inspect --format='{{.State.Health.Status}}' maptimize-bot-dev

# View logs
docker logs -f maptimize-bot-dev

# View logs from deployment
tail -f /opt/maptimize/logs/deploy.log
```

## Security

### Best Practices
- All Slack tokens in AWS Secrets Manager (never in code)
- Non-root Docker user
- Comprehensive input validation with pydantic
- TLS for all external connections
- IAM policies following least privilege
- Type hints for safer code

## Key Features

1. **Intelligent Task Mapping**: Parse and optimize task information from Slack
2. **Jira Integration**: Create, query, and update tasks
3. **Message Formatting**: Rich Block Kit formatting
4. **Process Optimization**: Analyze patterns and recommend improvements
5. **AWS Integration**: Secure credential management
6. **Structured Logging**: Comprehensive monitoring and debugging
7. **Error Handling**: Robust recovery and graceful degradation
8. **Health Checks**: Built-in monitoring for orchestration

## Code Standards

- Write type hints for all functions
- Follow PEP 8 (enforced by black/ruff)
- Write tests for all new features
- Maintain 80%+ code coverage
- Use conventional commit messages

### Commit Format
```
type: brief description

Longer explanation of changes and rationale.

Fixes #123
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

## Common Commands

### Bot Operations
```bash
# Run bot locally
python -m maptimize.bot

# Run with Docker Compose
docker-compose up --build
```

### Deployment (Use Makefile)
```bash
# Validate code (pytest, mypy, ruff, black)
make validate

# Deploy to ECR with validation gate
make deploy

# Preview deployment without pushing
make deploy-dry

# Deploy without validation (not recommended)
make deploy-skip-validation
```

### Testing
```bash
# Full test suite with coverage
make test

# Unit tests only
make test-unit

# Integration tests only
make test-integration

# Generate coverage report
make coverage
```

### Code Quality
```bash
# Type check
make type-check

# Validate formatting (without fixing)
make format-check

# Lint
make lint

# Auto-fix code style issues
make fix
```

### Development Setup
```bash
# Install dependencies
make install

# Install with dev dependencies
make install-dev

# Check required tools
make check-tools

# Show configuration
make show-config
```

## Troubleshooting

### Common Issues
1. **Check logs**: `docker logs maptimize-bot-dev`
2. **Verify config**: Check `.env` and AWS Secrets Manager
3. **Test Slack connection**: Run integration tests
4. **Check AWS credentials**: `aws sts get-caller-identity`

### Documentation References
- Deployment: `docs/DEPLOYMENT.md`
- Troubleshooting: `docs/TROUBLESHOOTING.md`
- Slack setup: `infrastructure/SLACK_APP_SETUP.md`

## Team Context

**Camp Ops EMEA Team**
- Repository: `camp-ops-emea/projects/maptimize`
- Primary focus: Task optimization and process improvement
- Deployment: AWS (eu-west-1)

## Recent Changes

Current branch: `main`

Recent commits:
- f81a2b6: Merge pull request #24 (Jira PAT migration)
- db8bf5d: Remove PII from usage-stats logging
- fab87fc: Enable PAT authentication, update to v2.360.351
- 5cf40f7: Remove temporary test files and documentation
- c0adb63: Add PAT operation debugging scripts

## Notes for Claude

- Always read files before editing them
- Run tests after significant changes
- Use type hints for all new code
- Follow the async-first pattern consistently
- Never commit secrets or credentials
- Maintain test coverage above 80%
- Use structured logging (structlog) for all log statements
- Prefer editing existing files over creating new ones
- Docker Compose for local development, Docker for production
- AWS Secrets Manager for all sensitive configuration
