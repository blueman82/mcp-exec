# AskSplunk

<img src="ask_splunk.png" width="120" alt="AskSplunk Logo" />

Slack bot that translates natural language questions about Adobe Campaign logs into Splunk SPL queries using RAG (Retrieval-Augmented Generation) and GPT.

## Status: Working

The bot is deployed and operational:

- Slack Socket Mode client (DMs + channel mentions)
- 7-state agent orchestrator with confidence evaluation
- ChromaDB vector store with 234 indexed chunks from schema
- Azure OpenAI (GPT-5) for query generation
- DynamoDB session management (30-min TTL)
- Real-time status callbacks during processing
- 128 unit tests passing

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- AWS credentials (v7 account)
- uv (Python package manager)

### Setup

```bash
# Clone and setup
git clone git@github.com:harrison_adobe/asksplunk.git
cd asksplunk
uv venv && source .venv/bin/activate
uv pip install -r requirements-dev.txt

# Configure AWS profile
cp .env.test.example .env.test
# Edit .env.test and set AWS_PROFILE=your-profile

# Run validation (lint + tests)
./infrastructure/validate.sh

# Fix lint issues automatically
./infrastructure/validate.sh --fix
```

### Deploy

```bash
# Dry run (shows what would happen)
./infrastructure/deploy-build-push.sh --dry-run

# Full deploy (build, push to ECR, deploy to EC2)
./infrastructure/deploy-build-push.sh

# Force reindex ChromaDB
./infrastructure/deploy-build-push.sh --reindex
```

## Architecture

```
User Question
     ↓
┌─────────────────┐
│  Slack Client   │  Socket Mode (DM + mentions)
└────────┬────────┘
         ↓
┌─────────────────┐
│     Agent       │  7-state orchestrator
│  ┌───────────┐  │
│  │ INITIALIZE│→ RAG retrieval
│  │ EVALUATE  │→ Confidence assessment (GPT)
│  │ CLARIFY   │→ Ask clarifying question
│  │ WAIT      │→ Wait for user response
│  │ REFINE    │→ Re-retrieve with context
│  │ GENERATE  │→ SPL query generation (GPT)
│  │ COMPLETE  │→ Delete session
│  └───────────┘  │
└────────┬────────┘
         ↓
┌─────────────────┐
│   ChromaDB      │  234 indexed chunks from schema
└─────────────────┘
```

## Project Structure

```
src/asksplunk/
├── main.py              # Entry point, wires everything together
├── secrets.py           # AWS Secrets Manager (60-min cache)
├── agent/
│   └── orchestrator.py  # 7-state agent with GPT calls
├── indexer/
│   └── indexer.py       # Schema → ChromaDB embeddings
├── retriever/
│   └── retriever.py     # Semantic search over indexed docs
├── session/
│   └── manager.py       # DynamoDB CRUD with TTL
└── slack/
    ├── client.py        # Socket Mode, event handlers
    └── formatter.py     # Block Kit message builders

infrastructure/
├── validate.sh          # Lint (black, ruff) + tests
├── deploy-build-push.sh # Build → ECR → EC2 deploy
└── run-indexer.py       # Standalone indexer for deployment

docs/
├── schema/              # Adobe Campaign field definitions
├── infrastructure/      # AWS/EC2/LDAP setup guides
└── diagrams/            # Mermaid architecture diagrams
```

## Configuration

### AWS Resources (eu-west-1)

| Resource | Name |
|----------|------|
| DynamoDB | `splunk-bot-sessions` |
| Secrets | `splunk-bot/slack-tokens`, `splunk-bot/azure-openai` |
| ECR | `483013340174.dkr.ecr.eu-west-1.amazonaws.com/asksplunk` |
| EC2 | t3.xlarge, Debian 12 |

### Environment Variables

Set in `.env.test` for local dev, or in AWS for production:

```bash
AWS_PROFILE=your-profile          # Local dev only
CHROMA_HOST=localhost             # ChromaDB host
CHROMA_PORT=8000                  # ChromaDB port
```

### Secrets Manager

**splunk-bot/slack-tokens:**
```json
{"bot_token": "xoxb-...", "app_token": "xapp-..."}
```

**splunk-bot/azure-openai:**
```json
{
  "endpoint": "https://....openai.azure.com/",
  "api_key": "...",
  "api_version": "2023-05-15",
  "chat_deployment": "gpt-5",
  "embedding_deployment": "text-embedding-ada-002"
}
```

## Development

### Running Tests

```bash
# All tests
uv run pytest tests/unit/ -v

# With coverage
uv run pytest tests/unit/ --cov=src/asksplunk --cov-report=html

# Specific file
uv run pytest tests/unit/test_agent.py -v
```

### Code Quality

```bash
# Format
uv run black src/ tests/

# Lint
uv run ruff check src/ tests/

# Auto-fix
uv run ruff check src/ tests/ --fix
```

### Local Development

```bash
# Start ChromaDB
docker-compose up -d chromadb

# Run bot locally (requires AWS credentials)
uv run python -m asksplunk.main
```

## How It Works

1. **User asks question** in Slack (DM or @mention)
2. **Agent retrieves** relevant docs from ChromaDB (semantic search)
3. **GPT evaluates confidence** based on retrieved context
4. **If confident (≥50%)**: Generate SPL query with explanations
5. **If uncertain (30-49%)**: Ask clarifying question with numbered options
6. **User replies** with number (1, 2, etc.) or free text
7. **Agent refines** context and re-evaluates
8. **Final query** sent to Slack with plain + technical explanations
9. **Session deleted** immediately (privacy)

### Example Interaction

```
User: Show me hard bounces for virginatlantic* in the last hour

Bot: 🔍 Searching documentation...
Bot: 🤔 Evaluating your question...
Bot: ✨ Generating SPL query...

Bot: This shows hard bounce events for Virgin Atlantic hosts in the past hour.

index=campaign_prod sourcetype=eventlog_momentum 
host=virginatlantic* msys.message_event.type="inband" 
earliest=-1h | stats count

[Technical: Searches eventlog_momentum for inband (hard bounce) 
events filtered by host pattern and 1-hour time range]
```

## Privacy

- Never log user message content
- Only log metadata (thread_id, state, timestamps)
- Sessions deleted immediately on completion
- DynamoDB TTL as backup (30 min)
- No hardcoded credentials

## Troubleshooting

**Bot not responding?**
- Check EC2 logs: `ssh asksplunk-prod 'sudo docker logs asksplunk-bot-prod --tail 50'`

**ChromaDB collection missing?**
- Force reindex: `./infrastructure/deploy-build-push.sh --reindex`

**Tests failing?**
- Run `./infrastructure/validate.sh --fix` to auto-fix lint issues

## License

Internal Adobe project. Not for public distribution.
