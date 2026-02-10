# CLAUDE.md

Guidance for Claude Code when working with this repository.

## Implementation Status

**Current State**: Fully operational. Bot deployed and handling queries.

### Implemented
- **Entry Point** (`src/asksplunk/main.py`): Async main with signal handlers (SIGTERM/SIGINT)
- **Slack Integration** (`src/asksplunk/slack/`): Socket Mode client with connection resilience, event handlers, Block Kit formatters
- **Session Management** (`src/asksplunk/session/`): DynamoDB CRUD with 30-min TTL, verified deletion
- **Secrets Manager** (`src/asksplunk/secrets.py`): AWS Secrets Manager with 60-min caching, authorized user list
- **Access Control** (`src/asksplunk/auth/`): Whitelist-based authorization via Secrets Manager
- **Usage Tracking** (`src/asksplunk/usage/`): Privacy-first DM event tracking (timestamp only, no user IDs)
- **Agent Orchestrator** (`src/asksplunk/agent/`): 7-state GPT-5 agent with confidence evaluation
- **Indexer** (`src/asksplunk/indexer/`): Document embedding, ChromaDB indexing (130 chunks)
- **Retriever** (`src/asksplunk/retriever/`): Semantic search over Adobe Campaign schema docs
- **Content Filter** (`src/asksplunk/agent/content_filter.py`): OWASP prompt injection prevention
- **Docker**: Multi-stage builds, ChromaDB service configured

### Scripts
- `scripts/send_welcome_messages.py`: Invite users to #asksplunk + send welcome DMs
- `scripts/pin_welcome_message.py`: Pin welcome message to #asksplunk channel

## Project Overview

**AskSplunk**: Slack bot translating natural language to Splunk SPL queries using RAG.

**Tech Stack**:
- Python 3.11+, slack-bolt (async), aioboto3, structlog
- AWS: DynamoDB, Secrets Manager, ECR, EC2
- Azure OpenAI (GPT-5), ChromaDB

## Repository Structure

```
src/asksplunk/
├── main.py              # Entry point with graceful shutdown
├── secrets.py           # AWS Secrets Manager client
├── agent/
│   ├── orchestrator.py  # 7-state GPT-5 agent
│   └── content_filter.py # OWASP prompt injection prevention
├── auth/
│   └── validator.py     # Whitelist-based access control
├── cli/
│   └── test_retrieval.py # Manual retrieval testing
├── indexer/
│   └── indexer.py       # Schema → ChromaDB embeddings
├── retriever/
│   └── retriever.py     # Semantic search over indexed docs
├── session/
│   └── manager.py       # DynamoDB CRUD with verified deletion
├── usage/
│   └── tracker.py       # Privacy-first usage tracking (timestamp only)
└── slack/
    ├── client.py        # Socket Mode client, event handlers, auth retry, resilient shutdown
    └── formatter.py     # Block Kit message builders

tests/
├── unit/
│   ├── test_main.py
│   ├── test_secrets.py
│   ├── test_session_manager.py
│   ├── test_slack_client.py
│   ├── test_slack_formatter.py
│   ├── test_slack_thread_handling.py
│   ├── test_slack_session_integration.py
│   ├── test_auth_validator.py
│   ├── test_agent.py
│   ├── test_content_filter.py
│   ├── test_indexer.py
│   ├── test_retriever.py
│   ├── test_schema_validation.py
│   └── test_usage_tracker.py
└── integration/
    ├── test_azure_openai_integration.py
    ├── test_secrets_integration.py
    └── test_usage_tracking.py

scripts/
├── send_welcome_messages.py  # Invite users + send welcome DMs
└── pin_welcome_message.py    # Pin welcome message to channel

docs/
├── plans/               # Implementation plan
├── schema/              # Adobe Campaign field definitions
├── security/            # Security audit report
└── diagrams/            # 6 Mermaid architecture diagrams
```

## Development Commands

```bash
# Setup
uv venv && source .venv/bin/activate
uv pip install -r requirements-dev.txt

# Run bot
python -m asksplunk.main

# Tests
pytest tests/unit/ -v
pytest tests/unit/ --cov=src/asksplunk --cov-report=html

# Code quality
black src/ tests/
ruff check src/ tests/
mypy src/

# Docker
docker-compose up -d chromadb
docker build --platform linux/amd64 -t asksplunk:prod .
```

## AWS Configuration

| Resource | Value |
|----------|-------|
| Region | eu-west-1 |
| Account | 483013340174 |
| ECR | `483013340174.dkr.ecr.eu-west-1.amazonaws.com/asksplunk` |
| DynamoDB | `splunk-bot-sessions` (TTL: 30 min) |
| Secrets | `splunk-bot/slack-tokens`, `splunk-bot/azure-openai` |
| IAM Role | `asksplunk-iam` |
| EC2 | t3.xlarge, Debian 12, LDAP auth via Balabit |

## Privacy Rules (Critical)

```python
# NEVER log message content - metadata only
logger.info("event", user=user_id, channel=channel_id, thread_ts=ts)
# NEVER: logger.info("event", message=text, question=content)
```

Verification:
```bash
rg "log.*user.*message|logger.*question" src/  # Should return nothing
rg "xoxb-|xapp-|sk-" src/                       # Should return nothing
```

## Key Patterns

### Async Context Managers
All AWS clients use async context managers for proper cleanup:
```python
async with SecretsManager() as manager:
    tokens = await manager.get_slack_tokens()

async with SessionManager() as manager:
    await manager.delete_session(thread_id)  # Verified deletion
```

### Signal Handling (main.py)
```python
signal.signal(signal.SIGTERM, create_signal_handler(client, loop))
signal.signal(signal.SIGINT, create_signal_handler(client, loop))
```

### TDD Approach
1. Write test FIRST
2. Write minimal code to pass
3. Refactor while green

### Connection Resilience (client.py)
- **Auth retry**: `_auth_test_with_retry()` with exponential backoff (3 attempts, 10s timeout)
- **Error classification**: `_is_fatal_slack_error()` separates fatal (invalid_auth, token_revoked) from transient errors
- **Resilient shutdown**: Each cleanup step in try/except/finally — one failure doesn't skip the rest
- **Structured logging**: `socket_mode_handler_starting`, `socket_mode_transient_error`, `socket_mode_fatal_error`

### Usage Tracking
- **Privacy**: Records timestamp only - NO user IDs stored
- **Storage**: DynamoDB GSI `usage-by-timestamp` on splunk-bot-sessions table
- **Admin Access**: Dynamic list from `admin_user_ids` in `splunk-bot/slack-tokens` secret
- **Retrieval**: Natural language queries like "show usage for last 7 days"
- **Supported timeframes**: hours, days, weeks, minutes, yesterday, today

## Commit Convention

```
<type>(<scope>): <summary>

Types: feat, fix, docs, test, refactor, chore
Scopes: agent, indexer, retriever, session, slack, secrets, main, docker, ci
```

## References

- **Implementation Plan**: `docs/plans/asksplunk-slack-bot.md`
- **Infrastructure Scripts**: `infrastructure/` (validate.sh, deploy-build-push.sh)
- **Architecture Diagrams**: `docs/diagrams/`
- **Security Audit**: `docs/security/security-audit-report.md`
