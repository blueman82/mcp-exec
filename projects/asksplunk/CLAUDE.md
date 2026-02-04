# CLAUDE.md

Guidance for Claude Code when working with this repository.

## Implementation Status

**Current State**: Foundation components complete, RAG pipeline planned but not implemented.

### Implemented (~950 lines production code, 67 tests)
- **Entry Point** (`src/asksplunk/main.py`): Async main with signal handlers (SIGTERM/SIGINT)
- **Slack Integration** (`src/asksplunk/slack/`): Socket Mode client, event handlers, Block Kit formatters
- **Session Management** (`src/asksplunk/session/`): DynamoDB CRUD with 30-min TTL, verified deletion
- **Secrets Manager** (`src/asksplunk/secrets.py`): AWS Secrets Manager with 60-min caching
- **Thread Handling**: Conversation continuity via Slack thread timestamps
- **Docker**: Multi-stage builds, ChromaDB service configured

### Planned (Not Yet Implemented)
- **Agent Orchestrator** (`src/asksplunk/agent/`): 7-state GPT-5 agent
- **Indexer** (`src/asksplunk/indexer/`): Document embedding, ChromaDB indexing
- **Retriever** (`src/asksplunk/retriever/`): Semantic search over Adobe Campaign docs
- **RAG Pipeline**: Question → retrieval → SPL generation

See `docs/plans/asksplunk-slack-bot.md` for full implementation plan.

## Project Overview

**AskSplunk**: Slack bot translating natural language to Splunk SPL queries using RAG.

**Tech Stack**:
- Python 3.11+, slack-bolt (async), aioboto3, structlog
- AWS: DynamoDB, Secrets Manager, ECR, EC2
- Planned: Azure OpenAI (GPT-5), ChromaDB

## Repository Structure

```
src/asksplunk/
├── main.py              # Entry point with graceful shutdown
├── secrets.py           # AWS Secrets Manager client
├── slack/
│   ├── client.py        # Socket Mode client, app_mention handler
│   └── formatter.py     # Block Kit message builders
├── session/
│   └── manager.py       # DynamoDB CRUD with verified deletion
├── agent/               # Planned: GPT-5 orchestrator
├── indexer/             # Planned: Document embedding
└── retriever/           # Planned: Semantic search

tests/unit/
├── test_main.py
├── test_secrets.py
├── test_session_manager.py
├── test_slack_client.py
├── test_slack_formatter.py
└── test_slack_thread_handling.py

docs/
├── plans/               # Implementation plan (26 tasks)
├── infrastructure/      # EC2, DynamoDB, LDAP setup
└── diagrams/            # 9 Mermaid architecture diagrams
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

## Commit Convention

```
<type>(<scope>): <summary>

Types: feat, fix, docs, test, refactor, chore
Scopes: agent, indexer, retriever, session, slack, secrets, main, docker, ci
```

## References

- **Implementation Plan**: `docs/plans/asksplunk-slack-bot.md`
- **Infrastructure Guides**: `docs/infrastructure/`
- **Architecture Diagrams**: `docs/diagrams/` (9 Mermaid files)
- **Documentation Index**: `docs/INDEX.md`
