# Meta-MCP Server Architecture

## 1. System Overview

### Complete System Diagram

```mermaid
graph TB
    AI[AI Client<br/>Claude/Cursor/VS Code]

    subgraph MetaServer["Meta-MCP Server"]
        Server[MCP Server<br/>src/server.ts]
        MetaTools["3 Meta-Tools<br/>list_servers<br/>get_server_tools<br/>call_tool"]
        Server --> MetaTools
    end

    subgraph Support["Support Systems"]
        Registry[Registry<br/>src/registry/loader.ts<br/>Loads & validates servers.json<br/>Caches manifest]
        Cache[Tool Cache<br/>src/tools/tool-cache.ts<br/>Per-server definitions]
        Registry -.->|Config| Server
        Cache -.->|Schemas| Server
    end

    subgraph Pool["Connection Pool<br/>src/pool/server-pool.ts<br/>Max 20, LRU eviction<br/>5min idle timeout"]
        P["Active Connections<br/>1-6 backends"]
    end

    subgraph Backends["Backend MCP Servers<br/>Spawned on demand"]
        B1[Node.js]
        B2[Docker]
        B3[Python/uvx]
        B4[NPX]
        B5[Custom]
    end

    AI -->|1. Request| Server
    MetaTools -->|2. Query| Pool
    Pool -.->|3. Spawn| P
    P -.->|4. Start| Backends
    Backends -->|5. Response| P
    P -->|6. Return| MetaTools
    MetaTools -->|7. Reply| AI

    Config[(servers.json)]
    Config -.->|Load| Registry

    classDef client fill:#e1f5ff,stroke:#01579b
    classDef core fill:#fff3e0,stroke:#e65100
    classDef support fill:#fff9c4,stroke:#f57f17
    classDef pool fill:#f3e5f5,stroke:#4a148c
    classDef backend fill:#e8f5e9,stroke:#1b5e20

    class AI client
    class Server,MetaTools core
    class Registry,Cache,Config support
    class Pool,P pool
    class B1,B2,B3,B4,B5 backend
```

### Component List (One-Liners)

| Component | Location | Purpose |
|-----------|----------|---------|
| **MCP Server** | `src/server.ts` | Routes requests to 3 meta-tools |
| **ServerPool** | `src/pool/server-pool.ts` | Manages up to 20 backend connections with LRU eviction |
| **Connection** | `src/pool/connection.ts` | Spawns and manages individual backend processes |
| **Registry** | `src/registry/loader.ts` | Loads, validates, caches servers.json manifest |
| **ToolCache** | `src/tools/tool-cache.ts` | Caches tool schemas per-server in memory |
| **Meta-Tools** | `src/tools/*.ts` | Implements list_servers, get_server_tools, call_tool |

---

## 2. Configuration & Registry

### servers.json Format

```json
{
  "mcpServers": {
    "corp-jira": {
      "command": "node",
      "args": ["/path/to/server.js"],
      "env": {"JIRA_URL": "https://...", "JIRA_TOKEN": "..."},
      "description": "JIRA integration",
      "tags": ["work", "tickets"],
      "disabled": false
    },
    "slack": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "slack-mcp:latest"]
    },
    "python-server": {
      "command": "uvx",
      "args": ["package-name"]
    }
  }
}
```

### Zod Validation Schema

```typescript
const ServerConfigSchema = z.object({
  command: z.string(),                          // Required
  args: z.array(z.string()).optional(),         // Command args
  env: z.record(z.string()).optional(),         // Environment vars
  type: z.string().optional(),                  // "stdio", "docker", etc.
  disabled: z.boolean().optional(),             // Skip if true
  description: z.string().optional(),           // Human description
  tags: z.array(z.string()).optional()          // Categorization
});

const BackendsConfigSchema = z.object({
  mcpServers: z.record(ServerConfigSchema)      // Map of configs
});
```

### Manifest Loading Sequence

```mermaid
flowchart TD
    Start([Process Startup]) --> GetPath["Check SERVERS_CONFIG<br/>env var"]

    GetPath -->|Set| UsePath["Use custom path"]
    GetPath -->|Not set| UseDefault["Use ~/.config/mcp/servers.json"]

    UsePath --> ReadFile["fs.readFileSync<br/>read as UTF-8"]
    UseDefault --> ReadFile

    ReadFile -->|Success| ParseJSON["JSON.parse"]
    ReadFile -->|Fail| ErrFile["ConfigNotFoundError"]

    ParseJSON -->|Success| ValidateSchema["BackendsConfigSchema.safeParse"]
    ParseJSON -->|Fail| ErrParse["ConfigParseError"]

    ValidateSchema -->|Success| CacheManifest["cachedManifest ← parsed"]
    ValidateSchema -->|Fail| ErrValidation["ConfigValidationError"]

    CacheManifest --> Ready["✓ Ready"]
    ErrFile --> Err["✗ Fatal exit"]
    ErrParse --> Err
    ErrValidation --> Err

    style Ready fill:#e1f5e1
    style Err fill:#ffe1e1
```

### Configuration Loading Flow

```mermaid
sequenceDiagram
    participant Main as main()
    participant Env as Environment
    participant Registry as Registry.loader
    participant File as Filesystem
    participant Zod as Zod Schema
    participant Cache as cachedManifest

    Main->>Env: Read SERVERS_CONFIG
    Env-->>Main: path or undefined

    Main->>Registry: loadServerManifest()
    Registry->>Registry: getConfigPath()
    Registry->>File: fs.readFileSync(path)
    File-->>Registry: rawData

    Registry->>Registry: JSON.parse(rawData)
    Registry->>Zod: safeParse(config)
    Zod-->>Registry: {success, data} or {error}

    alt Validation success
        Registry->>Cache: Store parsed config
        Registry-->>Main: ServerManifest
    else Validation fails
        Registry-->>Main: throw ConfigValidationError
    end
```

### Error Handling States

```mermaid
stateDiagram-v2
    [*] --> Uninitialized

    Uninitialized --> LoadingConfig: loadServerManifest()

    LoadingConfig --> FileCheck: Read from disk
    FileCheck --> ParseCheck: Parse JSON
    ParseCheck --> ValidateCheck: Validate schema

    FileCheck --> FileNotFound: File missing
    ParseCheck --> ParseError: Invalid JSON
    ValidateCheck --> ValidationError: Schema mismatch

    ValidateCheck --> Cached: ✓ Success

    FileNotFound --> [*]
    ParseError --> [*]
    ValidationError --> [*]

    Cached --> Serving
    Serving --> Serving: getServerConfig()
    Serving --> Serving: listServers()

    note right of Cached
        cachedManifest populated
        Fast lookups (O(1))
    end note
```

### Error Classes

| Error | Thrown By | Cause | Recovery |
|-------|-----------|-------|----------|
| `ConfigNotFoundError` | Registry | File missing, permission denied | Create config file |
| `ConfigParseError` | Registry | Invalid JSON syntax | Fix JSON syntax |
| `ConfigValidationError` | Registry | Schema mismatch, type errors | Check required fields |
| `InvalidServerError` | Pool | Server not in manifest | Use list_servers first |

---

## 3. Lifecycle

### Startup Sequence

```mermaid
sequenceDiagram
    participant Process as Node Process
    participant Main as index.ts
    participant Registry as Registry
    participant Pool as ServerPool
    participant Cache as ToolCache
    participant Server as MCP Server
    participant Signals as Signal Handlers

    Process->>Main: Start execution
    Main->>Main: Parse CLI args

    Main->>Registry: loadServerManifest()
    Registry-->>Main: ServerManifest (or error → exit 1)

    Main->>Pool: new ServerPool(factory, config)
    Pool->>Pool: startCleanupTimer() (60s interval)
    Pool-->>Main: Instance

    Main->>Cache: new ToolCache()
    Cache-->>Main: Instance

    Main->>Server: createServer(pool, cache)
    Server->>Server: Define listToolsHandler
    Server->>Server: Define callToolHandler
    Server-->>Main: {server, shutdown}

    Main->>Signals: Register SIGINT/SIGTERM handlers

    Main->>Server: await server.connect(StdioTransport)
    Server-->>Main: Connected

    Main->>Process: Ready - listening on stdio
```

### Request Flow (Two-Tier Discovery)

```mermaid
sequenceDiagram
    participant AI as AI Client
    participant Meta as Meta-MCP Server
    participant Pool as ServerPool
    participant Cache as ToolCache
    participant Backend as Backend MCP

    Note over AI,Backend: Phase 1: List Servers
    AI->>Meta: list_servers(filter?)
    Meta->>Meta: Query registry (no pool call)
    Meta-->>AI: [Server names] (~100 tokens)

    Note over AI,Backend: Phase 2: Tool Summary (Lazy Spawn)
    AI->>Meta: get_server_tools(server, summary_only=true)
    Meta->>Cache: Check cache
    alt Cache miss
        Meta->>Pool: getConnection(serverId)
        Pool->>Pool: Check existing
        alt Connection exists
            Pool-->>Meta: Return connection
        else No connection
            Pool->>Backend: Spawn process
            Backend-->>Pool: Connected
            Pool-->>Meta: Connection
        end
        Meta->>Backend: listTools()
        Backend-->>Meta: [ToolDefinition]
        Meta->>Cache: Store full definitions
    end
    Meta->>Meta: Filter to names + descriptions only
    Meta-->>AI: [Tool summaries] (~100 tokens)

    Note over AI,Backend: Phase 3: Full Schema (Cache Hit)
    AI->>Meta: get_server_tools(server, tools=["specific"])
    Meta->>Cache: Check cache (HIT)
    Meta->>Meta: Extract selected tools
    Meta-->>AI: [Full schemas] (~640 tokens per tool)

    Note over AI,Backend: Phase 4: Execute
    AI->>Meta: call_tool(server, tool, args)
    Meta->>Pool: getConnection(serverId)
    Pool-->>Meta: Connection (reuse)
    Meta->>Backend: callTool(name, args)
    Backend-->>Meta: Result
    Meta-->>AI: Tool result
```

### Pool Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> Empty: Server starts

    Empty --> Active: First tool call<br/>spawn backend
    Active --> Idle: No requests<br/>for 5 minutes
    Active --> Active: Continuous use<br/>LRU updated
    Idle --> Active: New request<br/>reuse connection
    Idle --> Evicted: Cleanup cycle<br/>1 min interval
    Evicted --> [*]

    note right of Empty
        Pool empty
        Max 20 connections
        LRU eviction policy
    end note

    note right of Active
        Connection in use
        Spawned backend running
        lastAccessTime = now()
    end note

    note right of Idle
        Connection exists
        No active requests
        Waiting for timeout
    end note

    note right of Evicted
        Idle > 5 minutes
        Disconnect gracefully
        Remove from pool
    end note
```

### Graceful Shutdown Sequence

```mermaid
sequenceDiagram
    participant OS as Operating System
    participant Process as Node Process
    participant Signal as Signal Handler
    participant Shutdown as shutdown()
    participant Pool as ServerPool
    participant Cleanup as Cleanup Timer
    participant Cache as ToolCache
    participant Backend as Backends

    OS->>Process: SIGINT or SIGTERM
    Process->>Signal: handleShutdown()

    Signal->>Cleanup: clearInterval(cleanupTimer)
    Cleanup-->>Signal: Timer stopped

    Signal->>Shutdown: await pool.shutdown()

    loop For each connection
        Shutdown->>Backend: await disconnect()
        Backend->>Backend: SIGTERM graceful
        Backend-->>Shutdown: Exited
    end

    Shutdown->>Pool: connections.clear()

    Shutdown->>Cache: clear()
    Cache->>Cache: Map.clear()

    Signal->>Process: await server.close()

    Signal->>Process: process.exit(0)
    Process->>OS: Exit
```

### Cleanup and Eviction Order

```mermaid
graph TD
    Start([SIGINT/SIGTERM]) --> Phase1["Phase 1: Stop Pool<br/>clearInterval(cleanupTimer)<br/>cleanupInterval = null"]

    Phase1 --> Phase2["Phase 2: Disconnect All<br/>for each connection<br/>await client.close()"]

    Phase2 --> Phase3["Phase 3: Clear Cache<br/>toolCache.clear()<br/>connections.clear()"]

    Phase3 --> Phase4["Phase 4: Close Server<br/>Stop accepting requests<br/>Close stdio transport"]

    Phase4 --> Phase5["Phase 5: Exit<br/>process.exit(0)"]

    Phase5 --> End(["✓ Graceful Shutdown"])

    style Phase1 fill:#e1f0ff
    style Phase2 fill:#e1f0ff
    style Phase3 fill:#e1f0ff
    style Phase4 fill:#e1f0ff
    style Phase5 fill:#e1f0ff
    style End fill:#e1f5e1
```

### Complete System State Machine

```mermaid
stateDiagram-v2
    [*] --> Starting

    Starting --> LoadingArgs
    LoadingArgs --> ExitVersion: --version/-v
    LoadingArgs --> ExitHelp: --help/-h
    LoadingArgs --> LoadingConfig: normal

    LoadingConfig --> ValidatingConfig
    ValidatingConfig --> ConfigError: Validation fails
    ValidatingConfig --> CreatingComponents: Success

    ConfigError --> [*]: exit(1)
    ExitVersion --> [*]: exit(0)
    ExitHelp --> [*]: exit(0)

    CreatingComponents --> InitPool
    InitPool --> InitCache
    InitCache --> CreatingServer
    CreatingServer --> RegisterHandlers
    RegisterHandlers --> RegisterSignals
    RegisterSignals --> ConnectTransport
    ConnectTransport --> Ready

    Ready --> Processing

    state Processing {
        [*] --> Idle
        Idle --> Request: Request arrives
        Request --> Route: Parse type
        Route --> Execute: Dispatch to meta-tool
        Execute --> Response: Return result
        Response --> Idle
    }

    Processing --> ShuttingDown: SIGINT/SIGTERM

    state ShuttingDown {
        [*] --> StopTimer
        StopTimer --> DisconnectAll
        DisconnectAll --> ClearCaches
        ClearCaches --> CloseServer
        CloseServer --> Exit
        Exit --> [*]
    }

    ShuttingDown --> [*]: exit(0)
```

### Background Processes

```mermaid
gantt
    title Timeline: Pool Cleanup & Connections
    dateFormat X
    axisFormat %Ss

    section Pool
    Startup         :milestone, 0, 0s
    Ready           :active, 2, 60
    Shutdown        :crit, 60, 62

    section Cleanup
    Timer started   :milestone, 1, 1s
    Waiting         :60s, 1, 60
    Cleanup 1       :milestone, 60, 60s
    Cleanup 2       :milestone, 120, 120s

    section Conn1
    Created         :milestone, 5, 5s
    Active          :active, 5, 15
    Idle            :15, 310
    Evicted         :crit, 310, 311

    section Conn2
    Created         :milestone, 10, 10s
    Active          :active, 10, 20
    Idle            :20, 320
```

---

## 4. Key Metrics

### Token Consumption

```
Traditional MCP:           16,000 tokens (all 25 tools upfront)
Meta-MCP Two-Tier:          1,480 tokens (typical 2-tool workflow)
Token Reduction:            90.8%

Breakdown:
  Phase 1 (list_servers):     100 tokens
  Phase 2 (summary_only):     100 tokens
  Phase 3 (full schema):      640 tokens × N tools (on-demand)
  Phase 4 (execution):        Variable (result size)
```

### Response Times

```
list_servers:              1ms      (cached manifest)
get_server_tools (spawn):  100-500ms (backend spawn)
get_server_tools (cached): 1ms      (cache hit)
call_tool (first):         50-200ms (spawn + execute)
call_tool (reuse):         10-50ms  (execute only)

Total typical workflow:    ~250ms (vs 2-6 seconds traditional)
```

### Resource Usage (6 Backends)

```
Backend Process:    30-100 MB × 6 = 180-600 MB
Tool Cache:         50 KB × 6 = 300 KB
Connection Pool:    10 KB × 6 = 60 KB
Meta-MCP Core:      20 MB
───────────────────────────────────────────
Total:              200-620 MB (vs 600 MB traditional)
```

---

## 5. Runtime Configuration

### Environment Variables

```bash
SERVERS_CONFIG       # Path to servers.json (default: ~/.config/mcp/servers.json)
MAX_CONNECTIONS      # Max backends (default: 6, hardcoded per CLAUDE.md)
IDLE_TIMEOUT_MS      # Idle timeout (default: 300000, hardcoded per CLAUDE.md)
```

### Pool Configuration (Hardcoded)

```typescript
DEFAULT_CONFIG = {
  maxConnections: 6,           // From CLAUDE.md spec
  idleTimeoutMs: 300000,       // 5 minutes
  cleanupIntervalMs: 60000     // 1 minute
}
```

### Command Examples

```bash
# Build
npm run build

# Run tests
npx vitest run

# Run server
node dist/index.js

# Debug with logs
export DEBUG=meta-mcp:*
DEBUG=meta-mcp:* node dist/index.js
```

---

## 6. File Structure Reference

```
src/
├── index.ts                 # Entry point (startup, signal handling)
├── server.ts                # MCP server, 3 meta-tool handlers
├── pool/
│   ├── server-pool.ts       # LRU pool manager (max 20, 5min timeout)
│   └── connection.ts        # Backend spawn/connect lifecycle
├── registry/
│   ├── loader.ts            # Loads/validates servers.json via Zod
│   └── manifest.ts          # ServerManifest types
└── tools/
    ├── tool-cache.ts        # Per-server cache Map<serverId, ToolDefinition[]>
    ├── list-servers.ts      # Queries registry, filters by tag
    ├── get-server-tools.ts  # Fetches + caches schemas, summary_only filtering
    └── call-tool.ts         # Pool lookup, backend execution

tests/
├── integration/             # Real backends (Docker, Node, uvx)
├── unit/                    # Mocked pool/connections
└── *.test.ts               # Test files
```

---

## Legend

### Diagram Notation

- **Solid lines** (→): Synchronous calls or direct data flow
- **Dashed lines** (-.->): Lazy loading, async operations
- **Dotted lines** (...): Configuration relationships

### Colors

- **Blue** (#e1f5ff): AI Client layer
- **Orange** (#fff3e0): Meta-MCP Server core
- **Purple** (#f3e5f5): Connection pool
- **Green** (#e8f5e9): Backend MCP servers
- **Pink** (#fce4ec): Caching layer
- **Yellow** (#fff9c4): Configuration/registry

---

## Quick Reference

### Three Meta-Tools

```typescript
list_servers({filter?: string})
→ Returns: [{name, description, tags}]

get_server_tools({server_name, summary_only?: boolean, tools?: string[]})
→ Returns: [ToolDefinition] (full or summary)

call_tool({server_name, tool_name, arguments?: object})
→ Returns: CallToolResult
```

### Pool Defaults (From CLAUDE.md)

```
Max connections:    6
Idle timeout:       5 minutes (300000ms)
Cleanup interval:   1 minute (60000ms)
Eviction policy:    LRU (Least Recently Used)
```

### Error Recovery

```
Startup errors → Fatal (exit 1)
Runtime errors → Return to client (no crash)
Pool exhausted → Evict LRU idle connection
Backend crash → Evict from pool, next request spawns fresh
Stale cache → Manual clear or connection eviction
```

---

**Version**: 1.0
**Updated**: 2025-12-02
**Focus**: Developer-oriented, architecture-first, minimal prose
