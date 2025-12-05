# Token Economics

## Traditional vs Meta-MCP

```mermaid
flowchart TB
  subgraph Traditional["Traditional"]
    T1[Start] --> T2[Load ALL tools]
    T2 --> T3["16k-48k+ tokens"]
  end

  subgraph Meta["Meta-MCP"]
    M1[Start] --> M2["1.9k startup"]
    M2 --> M3["only load what you use"]
    M3 --> M4["~3k typical"]
  end

  style T3 fill:#ff6b6b
  style M4 fill:#51cf66
```

## Savings

Traditional loads ALL available tools at startup. Meta-MCP only loads what you use.

| Servers | Tools Available | Traditional | You Use | Meta-MCP | Savings |
|---------|-----------------|-------------|---------|----------|---------|
| 1 | 25 | 16,000 | 2 | 3,200 | **80%** |
| 3 | 75 | 48,000 | 2 | 3,200 | **93%** |
| 3 | 75 | 48,000 | 5 | 5,100 | **89%** |

Formula: `1,900 + (tools used × 640)`

## Request Flow

```mermaid
sequenceDiagram
  participant AI
  participant Meta
  participant Backend

  rect rgb(230,245,255)
    Note over AI: Startup: 1.9k tokens
  end

  AI->>Meta: list_servers()
  Meta-->>AI: ["jira", "slack"]

  AI->>Meta: get_server_tools(jira, summary_only)
  Meta-->>AI: [summaries]

  rect rgb(232,245,233)
    Note over AI: +640 per tool
  end

  AI->>Meta: call_tool(jira, search, {})
  Meta->>Backend: execute
  Backend-->>AI: results
```
