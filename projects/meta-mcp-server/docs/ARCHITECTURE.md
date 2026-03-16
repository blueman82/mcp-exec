# Meta-MCP Architecture

> **TL;DR**: Proxy layer exposing 3 meta-tools instead of 100+. Reduces tokens by **79%+**.

---

## How It Works

```mermaid
flowchart LR
  subgraph AI["AI Client"]
    C[Claude/Cursor]
  end

  subgraph Meta["Meta-MCP"]
    M1[list_servers]
    M2[get_server_tools]
    M3[call_tool]
  end

  subgraph Pool["Connection Pool"]
    P["Max 20 | LRU | 5min timeout"]
  end

  subgraph Backends["Backend Servers"]
    B1[Jira]
    B2[Slack]
    B3[GitHub]
    B4[...]
  end

  C --> M1 & M2 & M3
  M2 & M3 --> P
  P -.->|lazy spawn| B1 & B2 & B3 & B4

  style AI fill:#e3f2fd
  style Meta fill:#fff3e0
  style Pool fill:#f3e5f5
  style Backends fill:#e8f5e9
```

---

## Token Cost

**Startup**: ~1.9k tokens (3 meta-tool schemas loaded once)

**mcp-exec catalog**: ~800-1000 tokens (tool names + param signatures, loaded once per session from `~/.meta-mcp/tool-catalog.json`)

| Tool | Per-call cost |
|------|---------------|
| `list_servers` | minimal |
| `get_server_tools` | ~640/tool |
| `call_tool` | variable |

---

## Request Flow

```mermaid
sequenceDiagram
  participant AI
  participant Meta as Meta-MCP
  participant Pool
  participant Backend

  Note over AI,Backend: Startup: 1.9k tokens (3 meta-tools)

  AI->>Meta: list_servers()
  Meta-->>AI: ["jira", "slack", "github"]

  AI->>Meta: get_server_tools(jira, summary_only=true)
  Meta->>Pool: getConnection()
  Pool->>Backend: spawn (if needed)
  Meta-->>AI: [25 tool summaries]

  Note over AI,Backend: Per tool: ~640 tokens
  AI->>Meta: get_server_tools(jira, tools=["search_issues"])
  Meta-->>AI: [full schema]

  AI->>Meta: call_tool(jira, search_issues, {...})
  Meta->>Backend: execute
  Backend-->>AI: results
```

---

## Token Savings

```
Traditional:  16,000+ tokens (all tool schemas upfront)
Meta-MCP:      3,200 tokens (startup + 2 backend tools used)
─────────────────────────────────────────────────
Savings:       80%
```

| Tools | Traditional | Meta-MCP | Savings |
|-------|-------------|----------|---------|
| 1 | 16,000 | 2,500 | **84%** |
| 2 | 16,000 | 3,200 | **80%** |
| 5 | 16,000 | 5,100 | **68%** |
| 10 | 16,000 | 8,300 | **48%** |

Formula: `1,900 + (tools × 640)`

---

## Configuration

**servers.json**:
```json
{
  "mcpServers": {
    "jira": {
      "command": "node",
      "args": ["/path/to/jira-mcp/dist/index.js"],
      "env": { "JIRA_TOKEN": "..." }
    }
  }
}
```

```bash
SERVERS_CONFIG=~/.meta-mcp/servers.json
```

---

## Pool Behavior

```mermaid
stateDiagram-v2
  [*] --> Empty: startup
  Empty --> Active: first request
  Active --> Idle: no requests
  Idle --> Active: new request
  Idle --> Evicted: idle > 5min
```

| Setting | Value |
|---------|-------|
| Max connections | 20 |
| Idle timeout | 5 min |
| Cleanup interval | 1 min |
| Eviction | LRU |

---

## Quick Reference

```bash
npm run build        # Build
npx vitest run       # Test
node dist/index.js   # Run
```

| File | Purpose |
|------|---------|
| `src/server.ts` | MCP server + handlers |
| `src/pool/server-pool.ts` | Connection manager |
| `src/registry/loader.ts` | Config loading |
| `src/tools/tool-cache.ts` | Schema cache |

---

See [`diagrams/`](diagrams/README.md) for pool mechanics and token economics.
