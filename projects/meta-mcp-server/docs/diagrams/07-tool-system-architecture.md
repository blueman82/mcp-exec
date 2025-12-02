# Tool System Architecture

This diagram shows the complete tool discovery, caching, and execution flow in the Meta-MCP Server.

## Complete Tool System Flow

```mermaid
graph TB
    subgraph "AI Client"
        AI[AI Assistant]
    end

    subgraph "Meta-MCP Server"
        subgraph "Request Handlers"
            LSH[listServersHandler]
            GSTH[getServerToolsHandler]
            CTH[callToolHandler]
        end

        subgraph "Core Components"
            REG[Registry Loader]
            CACHE[ToolCache<br/>Map&lt;serverId, ToolDefinition[]&gt;]
            POOL[ServerPool<br/>LRU Connection Pool]
        end

        subgraph "Validation"
            VAL[Input Validation<br/>Zod Schemas]
        end
    end

    subgraph "Backend Servers"
        BS1[Backend Server 1<br/>filesystem]
        BS2[Backend Server 2<br/>sqlite]
        BS3[Backend Server N<br/>...]
    end

    %% Flow 1: List Servers
    AI -->|1. list_servers| LSH
    LSH -->|Load manifest| REG
    REG -->|Return configs| LSH
    LSH -->|Filter disabled| LSH
    LSH -->|Server metadata[]| AI

    %% Flow 2: Get Server Tools
    AI -->|2. get_server_tools<br/>server_name, summary_only?, tools?| GSTH
    GSTH -->|Validate params| VAL
    VAL -->|Valid| GSTH
    GSTH -->|Check cache| CACHE

    CACHE -->|Cache HIT<br/>Matches request| GSTH
    CACHE -->|Cache MISS or<br/>Different params| GSTH

    GSTH -->|Cache MISS| POOL
    POOL -->|getConnection| BS1
    BS1 -->|client.listTools| POOL
    POOL -->|ToolDefinition[]| GSTH

    GSTH -->|Apply filters<br/>summary_only or tools[]| GSTH
    GSTH -->|Store filtered result| CACHE
    GSTH -->|Filtered tools| AI

    %% Flow 3: Call Tool
    AI -->|3. call_tool<br/>server_name, tool_name, arguments| CTH
    CTH -->|Validate params| VAL
    VAL -->|Valid| CTH
    CTH -->|getConnection| POOL
    POOL -->|Get/Create connection| BS2
    CTH -->|client.callTool<br/>tool_name, arguments| BS2
    BS2 -->|Result or Error| CTH
    CTH -->|Return result| AI

    %% Pool eviction triggers cache cleanup
    POOL -.->|On eviction| CACHE
    CACHE -.->|delete(serverId)| CACHE

    style LSH fill:#e1f5ff
    style GSTH fill:#ffe1e1
    style CTH fill:#e1ffe1
    style CACHE fill:#fff4e1
    style POOL fill:#f0e1ff
    style REG fill:#e1ffe8
```

## Flow 1: listServersHandler() - Server Discovery

```mermaid
sequenceDiagram
    participant AI as AI Client
    participant Handler as listServersHandler
    participant Registry as Registry Loader
    participant Cache as Manifest Cache

    AI->>Handler: list_servers(filter?)
    Handler->>Registry: loadManifest()

    alt Manifest cached
        Registry->>Cache: Get cached manifest
        Cache-->>Registry: Return manifest
    else First load
        Registry->>Registry: Read servers.json
        Registry->>Registry: Validate with Zod
        Registry->>Cache: Store manifest
    end

    Registry-->>Handler: ServerManifest[]
    Handler->>Handler: Filter disabled servers

    opt Filter parameter provided
        Handler->>Handler: Apply name/desc filter
    end

    Handler-->>AI: ServerMetadata[]<br/>{name, description, type}

    Note over AI,Handler: ~100-500 tokens<br/>No tool schemas loaded
```

## Flow 2: getServerToolsHandler() - Tool Discovery & Caching

```mermaid
sequenceDiagram
    participant AI as AI Client
    participant Handler as getServerToolsHandler
    participant Validator as Input Validator
    participant ToolCache as ToolCache
    participant Pool as ServerPool
    participant Backend as Backend Server

    AI->>Handler: get_server_tools({<br/>  server_name: "filesystem",<br/>  summary_only?: true,<br/>  tools?: ["read_file"]<br/>})

    Handler->>Validator: Validate params
    Validator-->>Handler: Valid

    Handler->>ToolCache: get(serverId)

    alt Cache HIT + Matches Request
        ToolCache-->>Handler: Cached ToolDefinition[]
        Handler->>Handler: Apply filters
        Handler-->>AI: Filtered tools
        Note over AI,Handler: Instant response<br/>No backend call
    else Cache MISS or Different Params
        ToolCache-->>Handler: null or stale

        Handler->>Pool: getConnection(server_name)

        alt Connection exists
            Pool-->>Handler: Existing connection
        else New connection needed
            Pool->>Pool: Check capacity
            Pool->>Pool: Create connection
            Pool->>Backend: Spawn process
            Backend-->>Pool: Connected
            Pool-->>Handler: New connection
        end

        Handler->>Backend: client.listTools()
        Backend-->>Handler: ToolDefinition[]<br/>(Full schemas)

        Handler->>Handler: Apply filters
        Note over Handler: summary_only: names/desc only<br/>tools: specific schemas only

        Handler->>ToolCache: set(serverId, filtered)
        Handler-->>AI: Filtered tools

        Note over AI,Handler: summary_only: ~100 tokens<br/>tools: ~1-2k tokens<br/>all tools: ~16k tokens
    end
```

## Flow 3: callToolHandler() - Tool Execution

```mermaid
sequenceDiagram
    participant AI as AI Client
    participant Handler as callToolHandler
    participant Validator as Input Validator
    participant Pool as ServerPool
    participant Backend as Backend Server

    AI->>Handler: call_tool({<br/>  server_name: "filesystem",<br/>  tool_name: "read_file",<br/>  arguments: {path: "/foo"}<br/>})

    Handler->>Validator: Validate params
    Validator-->>Handler: Valid

    Handler->>Pool: getConnection(server_name)

    alt Connection exists
        Pool-->>Handler: Return existing
        Note over Pool,Handler: LRU cache hit<br/>Instant connection
    else Connection needed
        Pool->>Pool: Check capacity

        alt Pool full
            Pool->>Pool: Evict LRU connection
            Pool->>Pool: Cleanup old process
        end

        Pool->>Backend: Spawn/Connect
        Backend-->>Pool: Ready
        Pool-->>Handler: New connection
    end

    Handler->>Backend: client.callTool(<br/>  tool_name,<br/>  arguments<br/>)

    alt Success
        Backend-->>Handler: {content: [...]}
        Handler-->>AI: Success result
    else Error
        Backend-->>Handler: Error details
        Handler-->>AI: Propagate error
    end

    Note over Pool: Connection stays warm<br/>for next request
```

## ToolCache Structure & Lifecycle

```mermaid
classDiagram
    class ToolCache {
        -Map~string, ToolDefinition[]~ cache
        +get(serverId: string) ToolDefinition[] | undefined
        +has(serverId: string) boolean
        +set(serverId: string, tools: ToolDefinition[]) void
        +delete(serverId: string) boolean
        +clear() void
        +size() number
    }

    class ToolDefinition {
        +name: string
        +description?: string
        +inputSchema: object
    }

    class ServerPool {
        -Map~string, Connection~ connections
        -Map~string, number~ lastUsed
        +getConnection(serverId: string) Connection
        +evictLRU() void
    }

    ToolCache "1" -- "*" ToolDefinition : stores
    ServerPool "1" ..> "1" ToolCache : eviction triggers delete

    note for ToolCache "Per-server cache\nNo TTL\nCleared on eviction"
    note for ServerPool "Eviction calls\ntoolCache.delete(serverId)"
```

## Cache Interaction State Diagram

```mermaid
stateDiagram-v2
    [*] --> Empty: Server starts

    Empty --> CacheMiss: get_server_tools<br/>(first request)
    CacheMiss --> FetchingTools: No cached tools
    FetchingTools --> CallingBackend: Get connection
    CallingBackend --> FilteringTools: client.listTools()
    FilteringTools --> CachePopulated: Apply filters<br/>+ set(serverId, tools)
    CachePopulated --> CacheHit: Next request

    CacheHit --> CacheHit: Same request params<br/>Return cached
    CacheHit --> CacheMiss: Different params<br/>(summary_only changed)

    CachePopulated --> Empty: Pool evicts connection
    CacheHit --> Empty: Pool evicts connection

    note right of Empty
        ToolCache starts empty
        No preloading
    end note

    note right of CacheHit
        Instant response
        No backend call
        Matches request params
    end note

    note right of CacheMiss
        Must fetch from backend
        Different filters require
        new backend call
    end note
```

## Token Optimization Flow

```mermaid
graph LR
    subgraph "First Discovery"
        A1[AI: list_servers] -->|~200 tokens| A2[Server names only]
        A2 --> A3[AI: get_server_tools<br/>summary_only=true]
        A3 -->|~100 tokens| A4[Tool names + descriptions]
    end

    subgraph "Selective Loading"
        A4 --> B1[AI analyzes capabilities]
        B1 --> B2[AI: get_server_tools<br/>tools=['read_file', 'write_file']]
        B2 -->|~1-2k tokens| B3[Only requested schemas]
    end

    subgraph "Execution"
        B3 --> C1[AI: call_tool<br/>read_file, args]
        C1 -->|Result only| C2[File contents]
    end

    subgraph "Cached Requests"
        C2 --> D1[AI: get_server_tools<br/>same params]
        D1 -->|Instant, ~1k tokens| D2[Cached schemas]
    end

    style A1 fill:#e1f5ff
    style A3 fill:#ffe1e1
    style B2 fill:#e1ffe1
    style C1 fill:#fff4e1
    style D1 fill:#f0e1ff

    note1[Total: ~1.5k tokens<br/>vs 16k+ traditional]
    B3 -.-> note1
```

## Integration: Pool Eviction Triggers Cache Cleanup

```mermaid
sequenceDiagram
    participant Timer as Cleanup Timer
    participant Pool as ServerPool
    participant Conn as Connection
    participant Cache as ToolCache

    Timer->>Pool: Check idle connections<br/>(every 60s)

    loop For each connection
        Pool->>Pool: Check lastUsed

        alt Idle > 5 minutes
            Pool->>Pool: Mark for eviction
            Note over Pool: LRU eviction policy
        end
    end

    Pool->>Conn: Close connection
    Conn->>Conn: Kill process
    Conn-->>Pool: Closed

    Pool->>Cache: delete(serverId)
    Cache->>Cache: Remove tools from cache
    Cache-->>Pool: Deleted

    Pool->>Pool: Remove from connections map

    Note over Pool,Cache: Cache and connection<br/>lifecycles are synchronized
```

## Complete Request Lifecycle Example

```mermaid
sequenceDiagram
    participant AI as AI Client
    participant Server as Meta-MCP Server
    participant Cache as ToolCache
    participant Pool as ServerPool
    participant Backend as filesystem-server

    Note over AI,Backend: Initial Discovery Phase

    AI->>Server: list_servers()
    Server-->>AI: ["filesystem", "sqlite", ...]
    Note right of AI: 200 tokens

    AI->>Server: get_server_tools({<br/>  server_name: "filesystem",<br/>  summary_only: true<br/>})
    Server->>Cache: get("filesystem")
    Cache-->>Server: Cache MISS
    Server->>Pool: getConnection("filesystem")
    Pool->>Backend: Spawn process
    Backend-->>Pool: Connected
    Pool-->>Server: Connection
    Server->>Backend: client.listTools()
    Backend-->>Server: [read_file, write_file, ...]<br/>with full schemas
    Server->>Server: Filter to names/desc only
    Server->>Cache: set("filesystem", filtered)
    Server-->>AI: Tool summaries
    Note right of AI: 100 tokens

    Note over AI,Backend: Selective Schema Loading

    AI->>Server: get_server_tools({<br/>  server_name: "filesystem",<br/>  tools: ["read_file"]<br/>})
    Server->>Cache: get("filesystem")
    Cache-->>Server: Cache HIT (but different params)
    Server->>Backend: client.listTools()
    Backend-->>Server: Full schemas
    Server->>Server: Filter to read_file only
    Server->>Cache: set("filesystem", updated)
    Server-->>AI: read_file schema only
    Note right of AI: 500 tokens

    Note over AI,Backend: Tool Execution

    AI->>Server: call_tool({<br/>  server_name: "filesystem",<br/>  tool_name: "read_file",<br/>  arguments: {path: "/data.txt"}<br/>})
    Server->>Pool: getConnection("filesystem")
    Pool-->>Server: Return existing (warm)
    Server->>Backend: client.callTool("read_file", ...)
    Backend-->>Server: File contents
    Server-->>AI: Result
    Note right of AI: Content only

    Note over AI,Backend: Cached Request (Fast Path)

    AI->>Server: get_server_tools({<br/>  server_name: "filesystem",<br/>  tools: ["read_file"]<br/>})
    Server->>Cache: get("filesystem")
    Cache-->>Server: Cache HIT (same params)
    Server-->>AI: Cached schema
    Note right of AI: Instant, 500 tokens<br/>No backend call

    Note over AI,Backend: Idle Timeout & Cleanup

    Note over Pool,Backend: 5 minutes pass...
    Pool->>Pool: Cleanup timer fires
    Pool->>Backend: Close connection
    Backend-->>Pool: Terminated
    Pool->>Cache: delete("filesystem")
    Cache->>Cache: Clear cached tools
```

## Key Architecture Principles

### 1. Lazy Loading
- No tools loaded at startup
- Backend connections created on demand
- Tool schemas fetched only when requested

### 2. Two-Tier Discovery
- **Tier 1**: `summary_only=true` - Names and descriptions only (~100 tokens)
- **Tier 2**: `tools=["specific"]` - Full schemas for selected tools (~1-2k tokens)

### 3. Intelligent Caching
- Per-server cache (not global)
- Cache persists while connection is alive
- Eviction synchronized with connection cleanup
- No TTL - cache cleared only on eviction

### 4. Connection Pooling
- LRU eviction policy (max 6 connections)
- 5-minute idle timeout
- 1-minute cleanup interval
- Warm connections for repeated requests

### 5. Token Optimization
- Traditional MCP: Load all tools upfront (~16k tokens)
- Meta-MCP: Progressive loading (~1.5k tokens total)
- 87% token reduction on discovery
- 100% reduction on cached requests

## Error Handling Flow

```mermaid
graph TD
    A[Request Received] --> B{Input Valid?}
    B -->|No| C[Return Validation Error]
    B -->|Yes| D{Server Exists?}
    D -->|No| E[Return Server Not Found]
    D -->|Yes| F{Can Get Connection?}
    F -->|No| G[Return Connection Error]
    F -->|Yes| H{Backend Available?}
    H -->|No| I[Return Backend Error]
    H -->|Yes| J{Tool Exists?}
    J -->|No| K[Return Tool Not Found]
    J -->|Yes| L{Execution Success?}
    L -->|No| M[Propagate Backend Error]
    L -->|Yes| N[Return Result]

    style C fill:#ffcccc
    style E fill:#ffcccc
    style G fill:#ffcccc
    style I fill:#ffcccc
    style K fill:#ffcccc
    style M fill:#ffcccc
    style N fill:#ccffcc
```

---

## Summary

The tool system architecture provides:

1. **Efficient Discovery**: Three-phase approach (servers → summaries → specific schemas)
2. **Smart Caching**: Per-server cache synchronized with connection lifecycle
3. **Connection Pooling**: LRU pool maintains warm connections for performance
4. **Token Optimization**: 87% reduction through progressive loading
5. **Error Handling**: Comprehensive validation and error propagation
6. **Lifecycle Management**: Automatic cleanup of idle connections and stale cache

This architecture enables Meta-MCP to wrap dozens of backend servers while maintaining minimal token overhead and fast response times.
