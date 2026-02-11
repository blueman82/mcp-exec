# Bravo - Jira Hygiene Nudge System

Bravo monitors Jira tickets across EMEA Campaign Operations teams and nudges engineers via Slack DM when tickets need attention. Hybrid approach: heuristic gates (pass/fail) + LLM scoring (quality dimensions).

## Architecture

```
src/bravo/
  main.py              # FastAPI app + lifespan (creates DI container)
  config.py            # pydantic-settings (nested: database/jira/slack/llm/gates) + load_settings()
  container.py         # create_container() — wires all services via DI
  protocols.py         # @runtime_checkable Protocol per service
  di/                  # Lightweight TypedDI framework
    types.py           #   DependencySpec, ServiceRegistration
    resolver.py        #   Kahn's topological sort + CircularDependencyError
    registry.py        #   ServiceRegistry: register, initialize_all, get, shutdown_all
  services/
    gates.py           # G1-G4 heuristic evaluation (GateEvaluation dataclass)
    llm.py             # LLM ticket scoring (LLMScore dataclass)
    jira.py            # Async Jira MCP client (httpx JSON-RPC 2.0)
    slack.py           # Socket Mode + Web API (slack-sdk)
    nudge.py           # Orchestrates gates -> LLM -> Slack DM
    poller.py          # Periodic Jira polling via JQL
    blocks.py          # Block Kit message builders (pure functions)
    resilience.py      # Async retry with exponential backoff (used by jira.py)
    secrets.py         # AWS Secrets Manager client (aioboto3, 60-min cache)
  db/
    pool.py            # asyncpg connection pool singleton
    queries.py         # Raw SQL with $1/$2 parameterized queries
    init.sql           # Schema DDL
  api/
    deps.py            # FastAPI Depends() helpers (bridges container -> routes)
    health.py          # Health check endpoints
    admin.py           # Stats, config, poll trigger, logs
    polling.py         # Polling state and history
    tickets.py         # Ticket CRUD + gate/LLM evaluation
    nudge.py           # Nudge listing and details
    assignees.py       # Assignee management
  worker/main.py       # Background worker (poll loop + Socket Mode)
  models/schemas.py    # Pydantic response models
```

```
mcp-jira/                    # TypeScript Jira MCP server
  src/
    index.ts                 # Express server, JSON-RPC dispatch
    config.ts                # Config from env vars
    utils.ts                 # jiraRequest(), auth headers
    errors.ts                # JiraError class
    env.ts                   # .env or AWS secrets loader
    env-aws.ts               # AWS Secrets Manager loader
    operations/              # Tool handlers (10 tools)
  tests/                     # Vitest test suite
  Dockerfile                 # Multi-stage Node.js build
```

## Dependency Injection

Services depend on Protocol interfaces, not concrete classes. Import direction:
- `container.py` -> concrete services + `di/`
- `nudge.py`, `poller.py` -> `protocols.py` (not concrete classes)
- `protocols.py` -> data classes only (`GateEvaluation`, `LLMScore`)
- `di/` -> nothing from services or protocols
- `api/deps.py` -> `container` via `request.app.state` (Depends() bridge)

Adding a new service: 1 Protocol in `protocols.py` + 1 class in `services/` + 1 `DependencySpec` in `container.py`.

## Code Standards

- Python 3.13+, use builtins: `list[dict]`, `str | None` (never `typing.List`, `Optional`)
- `collections.abc` for `Callable`, `AsyncIterator` etc. (not `typing`)
- No `TYPE_CHECKING` blocks — fix architecture if circular imports exist
- f-strings only, Google-style docstrings, EAFP pattern
- asyncpg with parameterized SQL (`$1`, `$2`), `get_pool()` pattern
- structlog for all logging

## Heuristic Gates

| Gate | Rule | Threshold |
|------|------|-----------|
| G1 | Assignee has commented (excl. bots) | Boolean |
| G2 | Last comment not stale | 4 hours |
| G3 | Response within deadline | 24 hours |
| G4 | Resolution within deadline | 24 hours |

Engineers never see gate codes (G1/G2/G3/G4). Slack messages use human-readable reasons: "No assignee comment found", "Last comment is stale", etc.

## Testing

```bash
uv run python -m pytest tests/ -v     # All tests
```

- `tests/test_blocks.py` — 21 tests for Block Kit message builders
- `tests/test_di.py` — 12 tests for DI framework (resolver, registry, container)
- `tests/test_llm.py` — 8 tests for LLM scoring service
- `tests/test_jira.py` — 18 tests for Jira MCP client (JSON-RPC, search, transitions, lifecycle)
- `tests/test_resilience.py` — tests for retry/backoff logic
- `tests/test_deps.py` — 10 tests for Depends() wiring + admin endpoints
- `tests/test_poller.py` — 5 tests for poller → nudge wiring
- `tests/test_nudge.py` — 10 tests for nudge orchestration + cooldown + snooze
- `tests/test_secrets.py` — 8 tests for AWS Secrets Manager + load_settings() hydration
- `asyncio_mode = "auto"` in pyproject.toml — async tests just work

## Docker (Local Dev)

```bash
docker compose -f infrastructure/docker-compose.local.yml up --build -d
```

Four services: `postgres:16-alpine` (:5432), `mcp-jira` (:8081), `bravo-api` (:8000), `bravo-worker`. Both Python app services require `.env` file (see `.env.example`). The `mcp-jira` service uses AWS Secrets Manager for credentials.

## Git Workflow

- Squash agent auto-commits into clean atomic commits before PR
- Branch naming: `feature/bravo-{feature-name}`

## Jira MCP Integration

Bravo talks to Jira via `corp_jira_mcp` (Ketchup iPaaS fork), not direct REST. `JiraMCPClient` in `services/jira.py` is a thin httpx client sending JSON-RPC 2.0 to the MCP server's `/message` endpoint.

- Config: `BRAVO_JIRA__MCP_URL` (default `http://mcp-jira:8081`)
- Tools used: `search_jira_issues`, `add_jira_comment`, `transition_jira_status`, `get_jira_transitions`, `create_jira_issue`, `update_jira_issue`, `download_attachment`
- Comment schema: `{"comment": {"body": "..."}}` (nested, not top-level)
- MCP server handles iPaaS auth, IMS tokens, and PAT rotation

## Jira MCP Server

TypeScript Express server on port 8081 implementing JSON-RPC 2.0 protocol. Matches the `JiraMCPClient._call_tool()` contract in `services/jira.py`.

- Two auth modes: iPaaS (production, via `USE_IPAAS=true`) and direct PAT (local dev)
- 10 tools: `test_jira_auth`, `search_jira_issues`, `add_jira_comment`, `delete_jira_comment`, `get_jira_transitions`, `transition_jira_status`, `create_jira_issue`, `update_jira_issue`, `get_project_issue_types`, `download_attachment`
- `npm test` to run Vitest suite, `npm run dev` for local dev with hot reload

## AWS Secrets Manager

Production secrets are stored in AWS Secrets Manager (`eu-west-1`). Local dev uses `.env` files — AWS is opt-in via `BRAVO_AWS_SECRETS_ENABLED=true`.

- `load_settings()` in `config.py` hydrates settings from AWS when enabled
- `SecretsManager` in `services/secrets.py` is the async client (aioboto3, 60-min cache)
- Env vars always take precedence over AWS values (via `or` pattern)
- `BRAVO_AWS_PROFILE` for local dev (e.g. `campaign_prod_v7`), empty on EC2 (uses IAM role)
- Three secrets: `bravo/slack`, `bravo/llm`, `bravo/database`
- IAM: `BravoSecretsManagerAccess` policy on `campaign-role` (Javelin EC2), standalone `bravo-iam` role also available

## Jira Project

- Epic: CPGNCX-63253
- Key tickets: 63864 (Slack foundation), 63865 (Jira integration), 63878 (Nudge workflow)
- Projects watched: CPGNCX, AMSE, CPGNREQ, CPGNPROV, CAMP, NEO, PLATIR, CPGNTT
