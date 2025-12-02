# Meta-MCP Server System Architecture

## Overview

This diagram illustrates the complete architecture of Meta-MCP Server, showing how it acts as an intelligent proxy between AI clients and multiple backend MCP servers, using lazy loading and connection pooling to optimize token usage.

## Architecture Diagram

```mermaid
graph TB
    %% Define styles
    classDef clientStyle fill:#e1f5ff,stroke:#01579b,stroke-width:3px,color:#000
    classDef metaStyle fill:#fff3e0,stroke:#e65100,stroke-width:3px,color:#000
    classDef poolStyle fill:#f3e5f5,stroke:#4a148c,stroke-width:2px,color:#000
    classDef backendStyle fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px,color:#000
    classDef cacheStyle fill:#fce4ec,stroke:#880e4f,stroke-width:2px,color:#000
    classDef configStyle fill:#fff9c4,stroke:#f57f17,stroke-width:2px,color:#000

    %% AI Client Layer
    AI[AI Client / Claude Desktop<br/>---<br/>Sends high-level requests<br/>using 3 meta-tools]
    class AI clientStyle

    %% Meta-MCP Server Layer
    subgraph MetaServer["Meta-MCP Server (Center Layer)"]
        direction TB
        Server[MCP Server<br/>src/server.ts<br/>---<br/>Request Router]

        subgraph MetaTools["3 Meta-Tools (Exposed API)"]
            direction LR
            T1[list_servers<br/>---<br/>List available<br/>backends]
            T2[get_server_tools<br/>---<br/>Fetch tool schemas<br/>summary or full]
            T3[call_tool<br/>---<br/>Execute backend<br/>tool]
        end

        Server --> MetaTools
    end
    class Server metaStyle
    class T1,T2,T3 metaStyle

    %% Registry & Cache Layer
    subgraph Support["Support Components"]
        direction TB
        Registry[Server Registry<br/>src/registry/loader.ts<br/>---<br/>Loads & validates<br/>servers.json]
        ToolCache[Tool Cache<br/>src/tools/tool-cache.ts<br/>---<br/>Caches tool definitions<br/>per server]

        Registry -.->|Config| Server
        ToolCache -.->|Cached schemas| Server
    end
    class Registry configStyle
    class ToolCache cacheStyle

    %% Connection Pool Layer
    subgraph Pool["Connection Pool (LRU Strategy)"]
        direction TB
        PoolMgr[ServerPool<br/>src/pool/server-pool.ts<br/>---<br/>Max: 6 connections<br/>Idle timeout: 5min<br/>Cleanup: 1min intervals]

        subgraph Connections["Active Connections (0-6)"]
            direction LR
            C1[Connection 1<br/>src/pool/connection.ts]
            C2[Connection 2]
            C3[Connection N]
            C1 -..- C2 -..- C3
        end

        PoolMgr --> Connections
    end
    class PoolMgr,C1,C2,C3 poolStyle

    %% Backend Servers Layer
    subgraph Backends["Backend MCP Servers (Spawned on Demand)"]
        direction TB
        B1[Node.js Server<br/>---<br/>node script.js]
        B2[Docker Server<br/>---<br/>docker run...]
        B3[Python Server<br/>---<br/>uvx package]
        B4[NPX Server<br/>---<br/>npx package]
        B5[Custom Server<br/>---<br/>Any MCP-compatible<br/>server]
    end
    class B1,B2,B3,B4,B5 backendStyle

    %% Request Flow Connections
    AI -->|1. Request| Server
    Server -->|2. Route to<br/>meta-tool| MetaTools
    MetaTools -->|3. Query pool| PoolMgr

    %% Lazy Loading Connections (dashed)
    PoolMgr -.->|4. Spawn on<br/>first access| Connections
    C1 -.->|5. Start process| B1
    C2 -.->|5. Start process| B2
    C3 -.->|5. Start process| B3

    %% Response Flow
    B1 -->|6. Response| C1
    C1 -->|7. Forward| PoolMgr
    PoolMgr -->|8. Return result| Server
    Server -->|9. Reply| AI

    %% Configuration
    Config[(servers.json<br/>---<br/>Backend server<br/>definitions)]
    Config -.->|Load at startup| Registry
    class Config configStyle
```

## Request Flow Sequence

```mermaid
sequenceDiagram
    participant AI as AI Client
    participant Meta as Meta-MCP Server
    participant Pool as Connection Pool
    participant Cache as Tool Cache
    participant Backend as Backend Server

    Note over AI,Backend: Phase 1: Discovery (Minimal Tokens)
    AI->>Meta: list_servers(filter?)
    Meta->>Meta: Load from registry
    Meta-->>AI: Server names & descriptions (~100 tokens)

    Note over AI,Backend: Phase 2: Tool Discovery (Summary Only)
    AI->>Meta: get_server_tools(server_name, summary_only=true)
    Meta->>Cache: Check cache
    alt Cache miss
        Meta->>Pool: Get/create connection
        Pool-->>Backend: Lazy spawn if needed
        Pool->>Backend: list_tools()
        Backend-->>Pool: Tool list
        Pool-->>Meta: Tool names & descriptions
        Meta->>Cache: Store summary
    else Cache hit
        Cache-->>Meta: Cached summary
    end
    Meta-->>AI: Tool names only (~100 tokens)

    Note over AI,Backend: Phase 3: Full Schema (Specific Tools)
    AI->>Meta: get_server_tools(server_name, tools=["tool1"])
    Meta->>Cache: Check full schema cache
    alt Cache miss
        Meta->>Pool: Get connection (reuse existing)
        Pool->>Backend: get_tool_schema("tool1")
        Backend-->>Pool: Full JSON schema
        Pool-->>Meta: Tool schema
        Meta->>Cache: Store schema
    else Cache hit
        Cache-->>Meta: Cached schema
    end
    Meta-->>AI: Full schema for tool1 (~500 tokens)

    Note over AI,Backend: Phase 4: Execution
    AI->>Meta: call_tool(server_name, tool_name, args)
    Meta->>Pool: Get connection (reuse existing)
    Pool->>Backend: Execute tool(args)
    Backend-->>Pool: Result
    Pool-->>Meta: Result
    Meta-->>AI: Tool result

    Note over Pool,Backend: Background: Connection Lifecycle
    loop Every 1 minute
        Pool->>Pool: Cleanup idle connections (>5min)
        Pool->>Backend: Disconnect if idle
    end
```

## Token Optimization Strategy

```mermaid
graph LR
    subgraph Traditional["Traditional MCP (16k tokens)"]
        direction TB
        T1[Load all 100+ tools<br/>at startup]
        T2[Full schemas in context<br/>~16,000 tokens]
        T3[High memory usage]
        T1 --> T2 --> T3
    end

    subgraph MetaMCP["Meta-MCP (2k tokens)"]
        direction TB
        M1[Load 3 meta-tools<br/>at startup]
        M2[Summary only initially<br/>~100 tokens]
        M3[Full schemas on demand<br/>~500 tokens per tool]
        M4[87% token reduction]
        M1 --> M2 --> M3 --> M4
    end

    Traditional -.->|Optimize with| MetaMCP

    classDef oldStyle fill:#ffcdd2,stroke:#c62828,stroke-width:2px
    classDef newStyle fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px

    class T1,T2,T3 oldStyle
    class M1,M2,M3,M4 newStyle
```

## Connection Pool Behavior

```mermaid
stateDiagram-v2
    [*] --> Empty: Server starts

    state "Pool Empty" as Empty
    state "Connection Active" as Active
    state "Connection Idle" as Idle
    state "Connection Evicted" as Evicted

    Empty --> Active: First tool call<br/>(spawn backend)
    Active --> Idle: No requests<br/>for 5 minutes
    Active --> Active: Continuous use<br/>(LRU updated)
    Idle --> Active: New request<br/>(reuse connection)
    Idle --> Evicted: Cleanup cycle<br/>(1 min interval)
    Evicted --> [*]: Disconnect

    state Active {
        [*] --> Spawning
        Spawning --> Connected: Process ready
        Connected --> Executing: Tool call
        Executing --> Connected: Result returned
    }

    note right of Empty
        Max 6 connections
        LRU eviction policy
    end note

    note right of Idle
        Idle timeout: 5 minutes
        Cleanup interval: 1 minute
    end note
```

## Component Interaction Matrix

```mermaid
graph TD
    subgraph Legend["Component Interaction Legend"]
        direction LR
        L1[Synchronous Call] -->|Solid line| L2[ ]
        L3[Lazy Loading] -.->|Dashed line| L4[ ]
        L5[Configuration] -.->|Dotted line| L6[ ]

        style L1 fill:#e1f5ff,stroke:#01579b
        style L2 fill:#e1f5ff,stroke:#01579b
        style L3 fill:#f3e5f5,stroke:#4a148c
        style L4 fill:#f3e5f5,stroke:#4a148c
        style L5 fill:#fff9c4,stroke:#f57f17
        style L6 fill:#fff9c4,stroke:#f57f17
    end
```

## Key Architectural Principles

### 1. Lazy Loading (Zero Upfront Cost)
- Backend servers are **NOT** started at Meta-MCP initialization
- Connections spawn only when first accessed via `get_server_tools` or `call_tool`
- Reduces startup time and memory footprint

### 2. Two-Tier Schema Loading
- **Tier 1**: `summary_only=true` returns tool names/descriptions only (~100 tokens)
- **Tier 2**: `tools=["specific"]` returns full JSON schemas on demand (~500 tokens each)
- AI can browse 100+ tools without loading full schemas

### 3. Connection Pooling (Resource Management)
- **Max 6 connections**: Prevents resource exhaustion
- **LRU eviction**: Least recently used connections removed when pool is full
- **5-minute idle timeout**: Automatic cleanup of unused connections
- **1-minute cleanup cycle**: Background maintenance task

### 4. Tool Caching (Performance)
- First request to backend: cache tool schemas
- Subsequent requests: serve from cache (no backend call)
- Cache invalidation: manual or on connection restart

### 5. Configuration-Driven (Flexibility)
- `servers.json` format matches Claude Desktop's `mcp.json`
- Environment variable: `SERVERS_CONFIG` points to config file
- Zod schema validation ensures config correctness

## File Structure Reference

```
src/
├── index.ts                    # Entry point (creates ServerPool + ToolCache)
├── server.ts                   # MCP server with 3 meta-tool handlers
├── pool/
│   ├── server-pool.ts         # LRU connection pool manager
│   └── connection.ts          # MCP client wrapper (spawn/connect)
├── registry/
│   └── loader.ts              # Loads/validates servers.json
└── tools/
    └── tool-cache.ts          # Per-server tool definition cache

tests/
├── integration/               # Real backend tests (Docker, Node, uvx)
└── *.test.ts                  # Unit tests (mocked pool/connections)
```

## Performance Characteristics

| Metric | Traditional MCP | Meta-MCP Server |
|--------|----------------|-----------------|
| **Initial Token Load** | ~16,000 tokens | ~100 tokens |
| **Startup Time** | Start all backends | Zero (lazy loading) |
| **Memory Usage** | All backends running | Only active backends |
| **Tool Discovery** | Full schemas loaded | Summary first, schema on demand |
| **Token Reduction** | Baseline | **87% reduction** |
| **Max Concurrent Backends** | Unlimited | 6 (configurable) |

## Legend

### Line Types
- **Solid lines** (→): Synchronous function calls or data flow
- **Dashed lines** (-.->): Lazy loading or asynchronous spawning
- **Dotted lines** (...): Configuration or cache relationships

### Color Coding
- **Blue** (`#e1f5ff`): AI Client layer
- **Orange** (`#fff3e0`): Meta-MCP Server core
- **Purple** (`#f3e5f5`): Connection pool components
- **Green** (`#e8f5e9`): Backend MCP servers
- **Pink** (`#fce4ec`): Caching layer
- **Yellow** (`#fff9c4`): Configuration/registry

---

**Generated for**: Meta-MCP Server
**Version**: 1.0
**Last Updated**: 2025-12-02
