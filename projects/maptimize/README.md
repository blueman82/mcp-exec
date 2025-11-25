# Maptimize

A Slack-integrated bot that optimizes task mapping, process management, and team collaboration through intelligent message formatting and Jira integration.

## Overview

Maptimize is a production-ready Slack bot designed to streamline team communication and task management workflows. It integrates seamlessly with Jira, providing real-time task optimization, process recommendations, and intelligent message formatting for teams managing complex infrastructure and operations.

The bot uses Socket Mode for secure, outbound-only WebSocket connections to Slack, eliminating the need for public HTTP endpoints while maintaining full event handling capabilities.

**Current Version**: 0.1.0 (Alpha)

## Features

- **Intelligent Task Mapping**: Processes Slack mentions and slash commands to extract and optimize task information
- **Jira Integration**: Direct integration with Jira for task creation, querying, and status updates
- **Message Formatting**: Advanced Block Kit message formatting for rich, interactive Slack experiences
- **Process Optimization**: Analyzes and recommends process improvements based on task patterns
- **AWS Integration**: Secure credential management through AWS Secrets Manager
- **Structured Logging**: Comprehensive logging with structured output for monitoring and debugging
- **Error Handling**: Robust error recovery and graceful degradation for external service failures
- **Async-First Architecture**: Built with Python asyncio for high-performance concurrent operations
- **Docker Support**: Production-ready Docker configuration with multi-stage builds and security hardening
- **Health Checks**: Built-in health monitoring for container orchestration platforms
- **Comprehensive Testing**: 80%+ code coverage with 200+ unit, integration, and E2E tests

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                          Slack Workspace                         │
│  (Messages, Slash Commands, App Mentions via Socket Mode)       │
└────────────────────────────────────────┬────────────────────────┘
                                         │
                            ┌────────────▼────────────┐
                            │  Socket Mode Connection │
                            │  (Persistent WebSocket) │
                            └────────────┬────────────┘
                                         │
         ┌───────────────────────────────┼───────────────────────────────┐
         │                               │                               │
    ┌────▼──────┐               ┌───────▼────────┐           ┌──────────▼────┐
    │   Bot     │               │   Config       │           │   Handlers    │
    │ (Slack    │               │   Manager      │           │ (Events &     │
    │  Bolt)    │               │ (AWS Secrets)  │           │  Commands)    │
    └────┬──────┘               └────────────────┘           └──────┬────────┘
         │                                                           │
         │               ┌─────────────────┬──────────┐             │
         │               │                 │          │             │
    ┌────▼──────┐   ┌────▼──────┐    ┌────▼──┐   ┌──▼──┐      ┌────▼─────┐
    │ Message   │   │  Formatter │    │ Utils │   │ AWS │      │   Jira   │
    │ Handlers  │   │  (Block    │    │       │   │ API │      │ Client   │
    │           │   │   Kit)     │    │       │   │     │      │          │
    └───────────┘   └────────────┘    └───────┘   └─────┘      └──────────┘
         │
    ┌────▼──────────────────────────────────────────────────────────┐
    │                   Slack API (REST)                             │
    │              (Message Send, Response Handling)                │
    └──────────────────────────────────────────────────────────────┘
```

### Project Structure

```
maptimize/
├── src/maptimize/              # Source code
│   ├── __init__.py             # Package initialization
│   ├── bot.py                  # Slack bot entry point
│   ├── config.py               # Configuration and AWS Secrets Manager
│   ├── handlers.py             # Slack event handlers
│   ├── formatter.py            # Message formatting utilities
│   └── utils.py                # General utility functions
├── tests/                       # Test suite (200+ tests)
│   ├── test_bot.py
│   ├── test_config.py
│   ├── test_handlers.py
│   ├── test_formatter.py
│   ├── test_utils.py
│   ├── test_integration.py
│   ├── test_e2e_bot.py
│   ├── test_documentation.py
│   └── ... (more test files)
├── config/                      # Configuration files
│   └── processes.yml           # Process definitions
├── infrastructure/              # Deployment and infrastructure
│   ├── Dockerfile              # Multi-stage Docker build
│   ├── docker-compose.yml      # Local development
│   ├── docker-compose.production.yml
│   ├── deploy.sh               # Deployment script
│   ├── launch-ec2.sh           # EC2 instance launcher
│   ├── user-data.sh            # EC2 initialization
│   ├── maptimize.service       # Systemd service file
│   └── iam/                    # IAM policy definitions
├── docs/                        # Documentation
│   ├── AWS_SETUP.md            # AWS configuration guide
│   ├── DEPLOYMENT.md           # Deployment instructions
│   ├── TROUBLESHOOTING.md      # Troubleshooting guide
│   └── SLACK_APP_SETUP.md      # Slack app configuration
├── pyproject.toml              # Project metadata and dependencies
├── pytest.ini                  # Pytest configuration
└── README.md                   # This file

```

## Tech Stack

### Core Dependencies
- **Python 3.11+**: Async-first Python with modern type hints
- **slack-bolt**: Slack app framework with async support
- **aioboto3**: Async AWS SDK for Python
- **structlog**: Structured, composable logging
- **pydantic**: Data validation with Python type hints
- **httpx**: Async HTTP client
- **python-dotenv**: Environment configuration

### Development Tools
- **pytest**: Testing framework with async support
- **pytest-cov**: Code coverage reporting
- **mypy**: Static type checking
- **black**: Code formatting
- **ruff**: Fast Python linter
- **isort**: Import sorting

### Infrastructure
- **Docker**: Container runtime with multi-stage builds
- **Docker Compose**: Local development orchestration
- **AWS EC2**: Cloud compute instances
- **AWS Secrets Manager**: Secure credential storage
- **AWS IAM**: Identity and access management

## Quick Start

### Prerequisites

- Python 3.11 or higher
- Docker and Docker Compose (for containerized deployment)
- AWS account with Secrets Manager access (for production)
- Slack workspace with bot app created
- Git for version control

### Installation

1. **Clone the repository**

```bash
git clone https://github.com/camp-ops-emea/projects/maptimize.git
cd maptimize
```

2. **Create Python virtual environment**

```bash
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -e ".[dev]"
```

4. **Configure environment variables**

```bash
cp .env.example .env
# Edit .env with your Slack app token
```

### Running Locally

**Using Docker Compose (Recommended)**

```bash
docker-compose up --build
```

**Using Python directly**

```bash
python -m maptimize.bot
```

### Running Tests

```bash
# Run all tests with coverage
pytest --cov=src/maptimize --cov-report=html

# Run specific test file
pytest tests/test_bot.py -v

# Run with markers
pytest -m unit
pytest -m integration
```

### Development Workflow

1. Make code changes in `src/maptimize/`
2. Run tests: `pytest`
3. Check types: `mypy src/`
4. Format code: `black src/ tests/`
5. Lint: `ruff check src/ tests/`
6. Commit with conventional commits

## Configuration

### Environment Variables

Required environment variables (in `.env`):

```bash
SLACK_TOKENS_SECRET_ID=maptimize/slack-tokens
AWS_REGION=eu-west-1
ENVIRONMENT=development
LOG_LEVEL=INFO
```

### AWS Secrets Manager

Store Slack tokens in AWS Secrets Manager:

```bash
aws secretsmanager create-secret \
  --name maptimize/slack-tokens \
  --secret-string '{"app_token":"xapp-...", "bot_token":"xoxb-..."}'
```

### Process Configuration

Edit `config/processes.yml` to define process mappings and optimization rules:

```yaml
processes:
  deployment:
    name: "Deployment Process"
    steps:
      - validate
      - build
      - test
      - deploy
    estimated_time: "2h"
```

## Deployment

### Quick Deployment

For detailed deployment instructions, see [DEPLOYMENT.md](docs/DEPLOYMENT.md).

**Basic steps:**

1. Set up AWS credentials and Secrets Manager
2. Configure Slack app tokens
3. Build and push Docker image to ECR
4. Launch EC2 instance with user data script
5. Monitor logs and health checks

**Deploy to AWS:**

```bash
bash infrastructure/deploy.sh
```

**Stop running instance:**

```bash
bash infrastructure/deploy.sh stop
```

## Monitoring and Maintenance

### Health Checks

The bot includes built-in health checks:

```bash
# Check container health
docker inspect --format='{{.State.Health.Status}}' maptimize-bot-dev

# Check bot logs
docker logs maptimize-bot-dev
```

### Logging

Structured logs are written to stdout:

```bash
# View logs from running container
docker logs -f maptimize-bot-dev

# View logs from EC2 instance
ssh -i path/to/key.pem ubuntu@instance-ip
tail -f /var/log/maptimize/bot.log
```

### Metrics

Monitor these key metrics:

- Message processing latency
- Jira API response times
- AWS Secrets Manager cache hits
- Error rates by type
- Handler execution times

### Updates

To update the running instance:

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose down
docker-compose up --build -d
```

## Troubleshooting

For common issues and solutions, see [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

Quick troubleshooting steps:

1. Check logs: `docker logs maptimize-bot-dev`
2. Verify configuration: Check `.env` and AWS Secrets Manager
3. Test Slack connection: Run integration tests
4. Check AWS credentials: `aws sts get-caller-identity`

## Code Quality

### Testing Strategy

- **Unit Tests**: Test individual components in isolation (60% of tests)
- **Integration Tests**: Test component interactions (25% of tests)
- **E2E Tests**: Test complete workflows (15% of tests)

Current coverage: **80%+** across all modules

### Type Checking

Full type hints required for all code:

```bash
mypy src/
```

### Formatting and Linting

```bash
# Format code
black src/ tests/

# Check linting
ruff check src/ tests/
```

## Contributing

### Development Setup

See Quick Start section above.

### Code Standards

- Write type hints for all functions
- Follow PEP 8 style guide (enforced by black/ruff)
- Write tests for all new features
- Maintain 80%+ code coverage
- Use conventional commit messages

### Commit Message Format

```
type: brief description

Longer explanation of changes and rationale.

Fixes #123
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

### Pull Request Process

1. Create feature branch: `git checkout -b feature/my-feature`
2. Make changes and write tests
3. Ensure all tests pass: `pytest`
4. Format code: `black src/ tests/`
5. Push and create pull request
6. Address review feedback
7. Merge after approval

## API Reference

### Bot Handlers

The bot responds to:

- **App Mentions** (`@maptimize`): Parse task information and provide optimization suggestions
- **Slash Commands** (`/maptimize`): Execute specific actions like creating tasks or querying status

### Message Formatting

Messages use Slack Block Kit for rich formatting:

```python
from maptimize.formatter import format_response

response = format_response(
    title="Task Summary",
    content="Your task information",
    url="https://jira.example.com/browse/TASK-123"
)
```

### Config Management

```python
from maptimize.config import Config

config = Config()
token = config.get_token("app_token")
processes = config.load_processes()
```

## Security

### Best Practices

- All Slack tokens stored in AWS Secrets Manager (never in code)
- Non-root Docker user for container security
- Type hints for safer code
- Comprehensive input validation with pydantic
- TLS for all external connections
- IAM policies following least privilege principle

### Reporting Security Issues

Please report security vulnerabilities to the team privately rather than using public issues.

## License

MIT License - See LICENSE file for details

## Support and Documentation

- **Architecture**: See docs/ARCHITECTURE.md
- **AWS Setup**: See docs/AWS_SETUP.md
- **Slack Configuration**: See docs/SLACK_APP_SETUP.md
- **Deployment Guide**: See docs/DEPLOYMENT.md
- **Troubleshooting**: See docs/TROUBLESHOOTING.md

## Team

Camp Ops EMEA Team
Email: team@campops.com

## Version History

- **0.1.0** (November 2024): Initial release with Slack integration, Jira support, and comprehensive testing
