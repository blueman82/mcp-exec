# AskSplunk

Slack bot that translates natural language questions about Adobe Campaign logs into Splunk SPL queries using GPT-5 + RAG.

## Core Commands

```bash
# Validation (lint + tests)
./infrastructure/validate.sh
./infrastructure/validate.sh --fix    # auto-fix formatting

# Deployment
./infrastructure/deploy-build-push.sh --dry-run   # test
./infrastructure/deploy-build-push.sh             # deploy
./infrastructure/deploy-build-push.sh --reindex   # force reindex

# Local dev
uv venv && source .venv/bin/activate && uv pip install -r requirements-dev.txt
docker-compose up -d chromadb
uv run python -m asksplunk.main
```

## Project Layout

```
src/asksplunk/
├── main.py          # Entry point, wires components
├── secrets.py       # AWS Secrets Manager (60-min cache)
├── agent/
│   └── orchestrator.py  # 7-state agent with GPT
├── indexer/
│   └── indexer.py       # Schema → ChromaDB (103 chunks)
├── retriever/
│   └── retriever.py     # Semantic search
├── session/
│   └── manager.py       # DynamoDB CRUD (30-min TTL)
└── slack/
    ├── client.py        # Socket Mode + handlers
    └── formatter.py     # Block Kit messages
```

## Agent State Machine

```
INITIALIZE → EVALUATE → GENERATE → COMPLETE
                ↓
            CLARIFY → WAIT → REFINE → EVALUATE
                ↓
            UNCERTAIN
```

**Thresholds**:
- ≥70%: Generate query
- 50-69%: Ask clarification (numbered options)
- <50%: Admit uncertainty

**Loop breaker**: After 2 clarifications, force generation.

**Status callbacks**: 🔍 Searching → 🤔 Evaluating → ✨ Generating

## Critical Rules

### Privacy
- ❌ NEVER log message content
- ✅ ONLY log metadata: thread_id, state, timestamp
- ✅ Delete session immediately in COMPLETE state

### Async Pattern
- OpenAI, DynamoDB, Slack: native async
- ChromaDB: `await asyncio.to_thread(collection.query, ...)`

## External Services

| Service | Resource |
|---------|----------|
| DynamoDB | `splunk-bot-sessions` |
| Secrets | `splunk-bot/slack-tokens`, `splunk-bot/azure-openai` |
| ECR | `483013340174.dkr.ecr.eu-west-1.amazonaws.com/asksplunk` |
| Region | eu-west-1 |

## Tests

127 unit tests, run with: `uv run pytest tests/unit/ -v`

## Commit Convention

```
<type>(<scope>): <summary>
```
Types: feat, fix, docs, test, refactor, chore
Scopes: agent, indexer, retriever, session, slack, secrets, docker
