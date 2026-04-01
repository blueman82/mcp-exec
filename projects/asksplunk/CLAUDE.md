# CLAUDE.md

AskSplunk: Slack bot translating natural language to Splunk SPL queries using RAG.

**Tech Stack**: Python 3.13+, slack-bolt (async), aioboto3, structlog, Azure OpenAI (GPT-5), ChromaDB, AWS (DynamoDB, Secrets Manager, ECR, EC2)

**Status**: Fully operational. Bot deployed and handling queries.

## Repository Structure

```
src/asksplunk/
├── main.py              # Entry point with graceful shutdown (SIGTERM/SIGINT)
├── secrets.py           # AWS Secrets Manager client (60-min cache)
├── agent/               # Multi-turn GPT-5 agent (7 states) + OWASP content filter
├── auth/                # Whitelist-based access control
├── indexer/             # Schema -> ChromaDB embeddings (130 chunks)
├── retriever/           # Semantic search over indexed docs
├── session/             # DynamoDB CRUD with 30-min TTL, conversation history
├── usage/               # Privacy-first usage tracking (timestamp only)
└── slack/               # Socket Mode client, Block Kit formatters
```

## Development Commands

```bash
uv venv && source .venv/bin/activate
uv pip install -r requirements-dev.txt
python -m asksplunk.main                              # Run bot
pytest tests/unit/ -v                                  # Unit tests
pytest tests/unit/ --cov=src/asksplunk --cov-report=html  # Coverage
black src/ tests/ && ruff check src/ tests/ && mypy src/  # Quality
docker-compose up -d chromadb                          # ChromaDB
docker build --platform linux/amd64 -t asksplunk:prod .   # Docker
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

## Signal Handling (main.py)

```python
signal.signal(signal.SIGTERM, create_signal_handler(client, loop))
signal.signal(signal.SIGINT, create_signal_handler(client, loop))
```

## Commit Convention

```
<type>(<scope>): <summary>
Types: feat, fix, docs, test, refactor, chore
Scopes: agent, indexer, retriever, session, slack, secrets, main, docker, ci
```

## References

- **Implementation Plan**: `docs/plans/asksplunk-slack-bot.md`
- **Infrastructure Scripts**: `infrastructure/` (validate.sh, deploy-build-push.sh, create-usage-gsi.sh, run-indexer.py)
- **Architecture Diagrams**: `docs/diagrams/`
- **Security Audit**: `docs/security/security-audit-report.md`
- **Coding Rules**: `.claude/rules/` (path-scoped Python style, privacy, testing, Slack, agent, AWS patterns)
