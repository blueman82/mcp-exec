# Token Economics

## Traditional vs Meta-MCP

```mermaid
flowchart TB
  subgraph Traditional["Traditional: 16k+"]
    T1[Start] --> T2[Load ALL]
    T2 --> T3["57,600 tokens"]
  end

  subgraph Meta["Meta-MCP: 80% less"]
    M1[Start] --> M2["1.9k startup"]
    M2 --> M3["+640/tool"]
    M3 --> M4["~3.2k typical"]
  end

  style T3 fill:#ff6b6b
  style M4 fill:#51cf66
```

## Savings

Traditional loads ALL schemas upfront (~57k for 3 servers). Meta-MCP scales with usage.

| Tools Used | Meta-MCP | Savings |
|------------|----------|---------|
| 1 | 2,500 | **96%** |
| 2 | 3,200 | **94%** |
| 5 | 5,100 | **91%** |

Formula: `1,900 + (tools × 640)`

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
