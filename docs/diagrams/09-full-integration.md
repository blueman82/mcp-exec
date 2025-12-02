# 09 - Full System Integration: Startup to Shutdown

This diagram documents the complete lifecycle of Meta-MCP Server from process start to graceful termination.

---

## Table of Contents

1. [Startup Sequence Diagram](#startup-sequence-diagram)
2. [Initialization Dependency Graph](#initialization-dependency-graph)
3. [Configuration Loading Flow](#configuration-loading-flow)
4. [Error Boundaries and Recovery](#error-boundaries-and-recovery)
5. [Runtime Request Flow](#runtime-request-flow)
6. [Graceful Shutdown Sequence](#graceful-shutdown-sequence)
7. [Cleanup Sequence Order](#cleanup-sequence-order)
8. [Signal Handling Flow](#signal-handling-flow)

---

## Startup Sequence Diagram

```mermaid
sequenceDiagram
    participant Process as Node Process
    participant Main as index.ts main()
    participant Args as CLI Args Parser
    participant Env as Environment
    participant Registry as Registry.load()
    participant Factory as ConnectionFactory
    participant Pool as ServerPool
    participant Cache as ToolCache
    participant Server as MCP Server
    participant Handlers as Request Handlers
    participant Transport as StdioTransport
    participant Signals as Signal Handlers

    Process->>Main: Start execution
    Main->>Args: Parse process.argv

    alt --version or -v
        Args->>Process: Print VERSION & exit(0)
    else --help or -h
        Args->>Process: Print help text & exit(0)
    else normal startup
        Args->>Main: Continue
    end

    Note over Main: Load Configuration
    Main->>Env: Get SERVERS_CONFIG env var
    Env-->>Main: configPath or undefined

    alt configPath provided
        Main->>Process: stderr.write("Loading config from: ...")
    end

    Main->>Registry: loadServerManifest()
    Registry->>Env: getConfigPath()
    Env-->>Registry: path or default (~/.config/mcp/servers.json)

    Note over Registry: Validate & Cache Config
    Registry->>Registry: fs.existsSync(configPath)
    alt file not found
        Registry->>Main: throw ConfigNotFoundError
        Main->>Process: Fatal error & exit(1)
    end

    Registry->>Registry: fs.readFileSync(configPath)
    alt read error
        Registry->>Main: throw ConfigNotFoundError
        Main->>Process: Fatal error & exit(1)
    end

    Registry->>Registry: JSON.parse(rawData)
    alt parse error
        Registry->>Main: throw ConfigParseError
        Main->>Process: Fatal error & exit(1)
    end

    Registry->>Registry: BackendsConfigSchema.safeParse()
    alt validation error
        Registry->>Main: throw ConfigValidationError
        Main->>Process: Fatal error & exit(1)
    end

    Registry->>Registry: Cache manifest in memory
    Registry-->>Main: ServerManifest loaded

    Note over Main: Create Connection Factory Closure
    Main->>Factory: Create async (serverId) => {...}
    Factory->>Factory: Captures getServerConfig() reference
    Factory-->>Main: connectionFactory function

    Note over Main: Initialize Core Components
    Main->>Pool: new ServerPool(connectionFactory, config)
    Pool->>Pool: Store factory reference
    Pool->>Pool: Set DEFAULT_CONFIG
    Note over Pool: maxConnections: 20<br/>idleTimeoutMs: 300000 (5min)
    Pool->>Pool: startCleanupTimer()
    Pool->>Pool: setInterval(runCleanup, 60000)
    Pool-->>Main: ServerPool instance

    Main->>Cache: new ToolCache()
    Cache->>Cache: Initialize empty Map<string, ToolDefinition[]>
    Cache-->>Main: ToolCache instance

    Note over Main: Create MCP Server
    Main->>Server: createServer(pool, toolCache)
    Server->>Server: new Server({name, version}, {capabilities})

    Server->>Handlers: Define 3 meta-tools
    Note over Handlers: listServersTool<br/>getServerToolsTool<br/>callToolTool

    Server->>Handlers: Create listToolsHandler
    Note over Handlers: Returns static list of 3 tools

    Server->>Handlers: Create callToolRequestHandler
    Note over Handlers: Routes to list_servers,<br/>get_server_tools, or call_tool

    Server->>Server: setRequestHandler(ListToolsRequestSchema)
    Server->>Server: setRequestHandler(CallToolRequestSchema)

    Server->>Server: Create shutdown() closure
    Note over Server: Captures pool & toolCache references

    Server-->>Main: {server, shutdown}

    Note over Main: Setup Graceful Shutdown
    Main->>Signals: Create handleShutdown() closure
    Note over Signals: Captures server & shutdown references

    Main->>Process: process.on('SIGINT', handleShutdown)
    Main->>Process: process.on('SIGTERM', handleShutdown)
    Process-->>Main: Signal handlers registered

    Note over Main: Connect Transport
    Main->>Transport: new StdioServerTransport()
    Transport->>Transport: Setup stdin/stdout streams
    Transport-->>Main: transport instance

    Main->>Server: await server.connect(transport)
    Server->>Transport: Bind to stdio
    Server->>Server: Start listening for requests
    Server-->>Main: Connected

    Main->>Process: stderr.write("Meta MCP Server running on stdio")

    Note over Process,Signals: System Ready - Listening for MCP requests
```

---

## Initialization Dependency Graph

```mermaid
graph TB
    Start([Node Process Start]) --> ArgParse[CLI Args Parser]

    ArgParse -->|--version/-v| ExitVersion[Print VERSION<br/>exit 0]
    ArgParse -->|--help/-h| ExitHelp[Print Help<br/>exit 0]
    ArgParse -->|normal| EnvCheck[Check SERVERS_CONFIG]

    EnvCheck --> LoadRegistry[Registry.loadServerManifest]

    LoadRegistry --> ValidateConfig{Config Valid?}
    ValidateConfig -->|ConfigNotFoundError| FatalExit[Fatal Error<br/>exit 1]
    ValidateConfig -->|ConfigParseError| FatalExit
    ValidateConfig -->|ConfigValidationError| FatalExit
    ValidateConfig -->|Success| CacheManifest[Cache Manifest in Memory]

    CacheManifest --> CreateFactory[Create ConnectionFactory]
    CreateFactory --> CreatePool[Create ServerPool]
    CreateFactory --> CreateCache[Create ToolCache]

    CreatePool --> StartCleanup[Start Cleanup Timer<br/>60s interval]
    CreateCache --> InitServer[Create MCP Server]
    CreatePool --> InitServer

    InitServer --> DefineTools[Define 3 Meta-Tools]
    DefineTools --> RegisterHandlers[Register Request Handlers]

    RegisterHandlers --> ListToolsHandler[ListToolsRequestSchema Handler]
    RegisterHandlers --> CallToolHandler[CallToolRequestSchema Handler]

    ListToolsHandler --> CreateShutdown[Create shutdown Closure]
    CallToolHandler --> CreateShutdown

    CreateShutdown --> RegisterSignals[Register Signal Handlers]
    RegisterSignals --> SigInt[SIGINT Handler]
    RegisterSignals --> SigTerm[SIGTERM Handler]

    SigInt --> CreateTransport[Create StdioServerTransport]
    SigTerm --> CreateTransport

    CreateTransport --> ConnectServer[server.connect transport]
    ConnectServer --> Ready([System Ready<br/>Listening on stdio])

    StartCleanup -.periodic.-> RunCleanup[Pool Cleanup Every 60s]

    style Start fill:#e1f5e1
    style Ready fill:#e1f5e1
    style FatalExit fill:#ffe1e1
    style ExitVersion fill:#e1e5ff
    style ExitHelp fill:#e1e5ff
```

---

## Configuration Loading Flow

```mermaid
flowchart TD
    Start([main Execution]) --> GetEnv{SERVERS_CONFIG<br/>env var set?}

    GetEnv -->|Yes| LogPath[stderr: Loading config from path]
    GetEnv -->|No| UseDefault[Use default path:<br/>~/.config/mcp/servers.json]

    LogPath --> LoadCall[Registry.loadServerManifest]
    UseDefault --> LoadCall

    LoadCall --> GetPath[getConfigPath]
    GetPath --> CheckExists{File exists?}

    CheckExists -->|No| ThrowNotFound[throw ConfigNotFoundError]
    CheckExists -->|Yes| ReadFile[fs.readFileSync]

    ReadFile --> ReadSuccess{Read success?}
    ReadSuccess -->|No| ThrowNotFound
    ReadSuccess -->|Yes| ParseJSON[JSON.parse rawData]

    ParseJSON --> ParseSuccess{Parse success?}
    ParseSuccess -->|No| ThrowParse[throw ConfigParseError]
    ParseSuccess -->|Yes| ValidateSchema[BackendsConfigSchema.safeParse]

    ValidateSchema --> SchemaValid{Valid?}
    SchemaValid -->|No| ThrowValidation[throw ConfigValidationError]
    SchemaValid -->|Yes| CacheManifest[cachedManifest = parsed data]

    CacheManifest --> ReturnManifest[Return ServerManifest]

    ThrowNotFound --> CatchMain[Caught in main]
    ThrowParse --> CatchMain
    ThrowValidation --> CatchMain

    CatchMain --> FatalError[console.error Fatal error]
    FatalError --> Exit[process.exit 1]

    ReturnManifest --> Success([Manifest cached & available])

    style Start fill:#e1f5e1
    style Success fill:#e1f5e1
    style Exit fill:#ffe1e1
    style ThrowNotFound fill:#ffe1e1
    style ThrowParse fill:#ffe1e1
    style ThrowValidation fill:#ffe1e1
```

### Configuration Schema

```mermaid
graph LR
    Config[servers.json] --> Root{mcpServers}

    Root --> Server1[server_name_1]
    Root --> Server2[server_name_2]
    Root --> ServerN[server_name_N]

    Server1 --> Type1[type: 'stdio' optional]
    Server1 --> Cmd1[command: string]
    Server1 --> Args1[args: string[] optional]
    Server1 --> Env1[env: Record string optional]
    Server1 --> Disabled1[disabled: boolean optional]
    Server1 --> Desc1[description: string optional]
    Server1 --> Tags1[tags: string[] optional]

    style Config fill:#ffe1b3
    style Root fill:#b3d9ff
```

---

## Error Boundaries and Recovery

```mermaid
flowchart TD
    subgraph "Error Boundaries"
        MainBoundary[main try-catch]
        FactoryBoundary[ConnectionFactory try-catch]
        PoolBoundary[Pool getConnection try-catch]
        ConnectionBoundary[Connection connect try-catch]
        HandlerBoundary[Handler try-catch]
    end

    subgraph "Startup Errors - Fatal"
        ConfigNotFound[ConfigNotFoundError]
        ConfigParse[ConfigParseError]
        ConfigValidation[ConfigValidationError]
    end

    subgraph "Runtime Errors - Recoverable"
        PoolExhausted[PoolExhaustedError]
        ConnectionError[ConnectionError]
        SpawnError[SpawnError]
        TimeoutError[TimeoutError]
        UnexpectedExit[UnexpectedExitError]
        ToolNotFound[ToolNotFoundError]
    end

    subgraph "Recovery Strategies"
        FatalExit[Log & exit 1]
        ReturnError[Return error to client]
        EvictLRU[Evict LRU connection]
        Retry[Retry connection optional]
    end

    ConfigNotFound --> MainBoundary
    ConfigParse --> MainBoundary
    ConfigValidation --> MainBoundary
    MainBoundary --> FatalExit

    PoolExhausted --> PoolBoundary
    PoolBoundary --> EvictLRU
    EvictLRU -->|Success| Retry
    EvictLRU -->|Fail| ReturnError

    ConnectionError --> PoolBoundary
    SpawnError --> ConnectionBoundary
    TimeoutError --> ConnectionBoundary
    UnexpectedExit --> ConnectionBoundary
    ConnectionBoundary --> ReturnError

    ToolNotFound --> HandlerBoundary
    HandlerBoundary --> ReturnError

    style ConfigNotFound fill:#ffe1e1
    style ConfigParse fill:#ffe1e1
    style ConfigValidation fill:#ffe1e1
    style PoolExhausted fill:#fff4e1
    style ConnectionError fill:#fff4e1
    style SpawnError fill:#fff4e1
    style FatalExit fill:#ffe1e1
    style EvictLRU fill:#e1ffe1
```

### Error Flow Details

```mermaid
sequenceDiagram
    participant Client as AI Client
    participant Server as MCP Server
    participant Handler as callToolHandler
    participant Pool as ServerPool
    participant Factory as ConnectionFactory
    participant Connection as MCPConnection

    Client->>Server: call_tool request
    Server->>Handler: Route to handler

    Handler->>Pool: getConnection(serverId)

    alt Connection exists
        Pool-->>Handler: Return cached connection
    else Pool full
        Pool->>Pool: evictLRU()
        alt Eviction success
            Pool->>Factory: Create new connection
            Factory->>Connection: createConnection(config)
            Connection->>Connection: buildSpawnConfig()
            alt Spawn config error
                Connection->>Factory: throw SpawnError
                Factory->>Pool: Propagate error
                Pool->>Handler: throw ConnectionError
                Handler->>Server: Error response
                Server->>Client: Error result
            else Spawn success
                Connection->>Connection: client.connect(transport)
                alt Connect error
                    Connection->>Factory: throw SpawnError
                    Factory->>Pool: Propagate error
                    Pool->>Handler: throw ConnectionError
                    Handler->>Server: Error response
                    Server->>Client: Error result
                else Connect success
                    Connection-->>Factory: Connected
                    Factory-->>Pool: Connection
                    Pool-->>Handler: Connection
                end
            end
        else Eviction fails (all in use)
            Pool->>Handler: throw PoolExhaustedError
            Handler->>Server: Error response
            Server->>Client: Error result
        end
    end

    Handler->>Connection: callTool(toolName, args)
    Connection-->>Handler: Result
    Handler->>Server: Success response
    Server->>Client: Tool result
```

---

## Runtime Request Flow

```mermaid
sequenceDiagram
    participant Client as AI Client
    participant Transport as StdioTransport
    participant Server as MCP Server
    participant Handler as Request Handler
    participant MetaTool as Meta-Tool Handler
    participant Pool as ServerPool
    participant Backend as Backend MCP Server
    participant Cache as ToolCache

    Note over Client,Cache: Example: get_server_tools → call_tool flow

    Client->>Transport: list_tools request
    Transport->>Server: ListToolsRequestSchema
    Server->>Handler: listToolsHandler()
    Handler-->>Server: [list_servers, get_server_tools, call_tool]
    Server->>Transport: Response
    Transport->>Client: 3 meta-tools

    Client->>Transport: call_tool(get_server_tools, {server_name, summary_only: true})
    Transport->>Server: CallToolRequestSchema
    Server->>Handler: callToolRequestHandler()
    Handler->>MetaTool: getServerToolsHandler()

    MetaTool->>Cache: has(serverId)?
    alt Tools cached
        Cache-->>MetaTool: Cached tools
    else Not cached
        MetaTool->>Pool: getConnection(serverId)
        Pool->>Backend: Get/create connection
        Backend-->>Pool: Connection
        Pool-->>MetaTool: Connection
        MetaTool->>Backend: client.listTools()
        Backend-->>MetaTool: Tool definitions
        MetaTool->>Cache: set(serverId, tools)
    end

    MetaTool->>MetaTool: Filter to summary (name + description only)
    MetaTool-->>Handler: Tool summaries (~100 tokens)
    Handler->>Server: JSON response
    Server->>Transport: Response
    Transport->>Client: Tool list

    Client->>Transport: call_tool(call_tool, {server_name, tool_name, arguments})
    Transport->>Server: CallToolRequestSchema
    Server->>Handler: callToolRequestHandler()
    Handler->>MetaTool: callToolHandler()

    MetaTool->>Pool: getConnection(serverId)
    Pool-->>MetaTool: Connection (cached or new)

    MetaTool->>Backend: client.callTool(toolName, args)
    Backend->>Backend: Execute actual tool
    Backend-->>MetaTool: Tool result

    MetaTool->>Pool: releaseConnection(serverId)
    Pool->>Pool: Mark not in use, update lastAccessTime

    MetaTool-->>Handler: Result
    Handler->>Server: JSON response
    Server->>Transport: Response
    Transport->>Client: Tool result
```

---

## Graceful Shutdown Sequence

```mermaid
sequenceDiagram
    participant OS as Operating System
    participant Process as Node Process
    participant Signal as Signal Handler
    participant Shutdown as shutdown()
    participant Pool as ServerPool
    participant Connections as Pool Connections
    participant Cache as ToolCache
    participant Server as MCP Server
    participant Cleanup as Cleanup Timer

    OS->>Process: SIGINT or SIGTERM
    Process->>Signal: Trigger handleShutdown()
    Signal->>Process: stderr.write("Shutting down...")

    Note over Signal,Cache: Phase 1: Stop Pool Operations
    Signal->>Shutdown: await shutdown()
    Shutdown->>Pool: await pool.shutdown()

    Pool->>Cleanup: clearInterval(cleanupInterval)
    Cleanup-->>Pool: Timer stopped
    Pool->>Pool: cleanupInterval = null

    Note over Pool,Connections: Phase 2: Close All Connections
    Pool->>Connections: Iterate connections.entries()

    loop For each connection
        Pool->>Connections: await connection.disconnect()
        Connections->>Connections: await client.close()
        Connections->>Connections: state = Disconnected
        Connections-->>Pool: Disconnected
    end

    Pool->>Pool: connections.clear()
    Pool-->>Shutdown: Pool shutdown complete

    Note over Shutdown,Cache: Phase 3: Clear Caches
    Shutdown->>Cache: toolCache.clear()
    Cache->>Cache: cache.clear() (Map cleared)
    Cache-->>Shutdown: Cache cleared

    Shutdown-->>Signal: Cleanup complete

    Note over Signal,Server: Phase 4: Close Server
    Signal->>Server: await server.close()
    Server->>Server: Stop accepting requests
    Server->>Server: Close transport
    Server-->>Signal: Server closed

    Note over Signal,Process: Phase 5: Exit Process
    Signal->>Process: process.exit(0)
    Process->>OS: Exit with code 0

    Note over OS: Clean shutdown complete
```

---

## Cleanup Sequence Order

```mermaid
flowchart TD
    Start([SIGINT/SIGTERM Received]) --> Log[stderr.write: Shutting down...]

    Log --> Phase1[Phase 1: Stop Pool Operations]
    Phase1 --> StopTimer[Clear cleanup timer interval]
    StopTimer --> SetNull[cleanupInterval = null]

    SetNull --> Phase2[Phase 2: Close All Connections]
    Phase2 --> IterateConns[Iterate connections Map]

    IterateConns --> HasMore{More connections?}
    HasMore -->|Yes| DisconnectOne[await connection.disconnect]
    DisconnectOne --> ClientClose[await client.close]
    ClientClose --> SetState[state = Disconnected]
    SetState --> HasMore

    HasMore -->|No| ClearMap[connections.clear]

    ClearMap --> Phase3[Phase 3: Clear Caches]
    Phase3 --> ClearToolCache[toolCache.clear]
    ClearToolCache --> ClearRegistryCache[Registry cache cleared implicitly]

    ClearRegistryCache --> Phase4[Phase 4: Close MCP Server]
    Phase4 --> StopRequests[Stop accepting new requests]
    StopRequests --> CloseTransport[Close stdio transport]
    CloseTransport --> CleanupHandlers[Cleanup request handlers]

    CleanupHandlers --> Phase5[Phase 5: Exit Process]
    Phase5 --> Exit[process.exit 0]

    Exit --> End([Graceful Shutdown Complete])

    style Start fill:#ffe1e1
    style Phase1 fill:#e1f0ff
    style Phase2 fill:#e1f0ff
    style Phase3 fill:#e1f0ff
    style Phase4 fill:#e1f0ff
    style Phase5 fill:#e1f0ff
    style End fill:#e1f5e1
```

### Critical Cleanup Ordering

```mermaid
graph TD
    subgraph "Must Execute First"
        A1[Stop cleanup timer]
        A2[Prevent new connections]
    end

    subgraph "Must Execute Second"
        B1[Disconnect all connections]
        B2[Close all backend clients]
        B3[Clear connection pool]
    end

    subgraph "Must Execute Third"
        C1[Clear tool cache]
        C2[Clear registry cache optional]
    end

    subgraph "Must Execute Fourth"
        D1[Close MCP server]
        D2[Close stdio transport]
    end

    subgraph "Must Execute Last"
        E1[process.exit 0]
    end

    A1 --> A2
    A2 --> B1
    B1 --> B2
    B2 --> B3
    B3 --> C1
    C1 --> C2
    C2 --> D1
    D1 --> D2
    D2 --> E1

    style A1 fill:#ffe1e1
    style A2 fill:#ffe1e1
    style E1 fill:#e1f5e1
```

---

## Signal Handling Flow

```mermaid
flowchart TD
    Start([Process Running]) --> Listening[Listening for signals]

    Listening --> SigInt{SIGINT<br/>Ctrl+C}
    Listening --> SigTerm{SIGTERM<br/>kill}
    Listening --> SigOther{Other signals}

    SigInt --> HandleShutdown[Call handleShutdown]
    SigTerm --> HandleShutdown
    SigOther --> DefaultHandler[Default handler]

    HandleShutdown --> LogMsg[stderr: Shutting down...]
    LogMsg --> CallShutdown[await shutdown]

    CallShutdown --> ShutdownPool[pool.shutdown]
    ShutdownPool --> ClearCache[toolCache.clear]

    ClearCache --> CloseServer[server.close]
    CloseServer --> Exit0[process.exit 0]

    Exit0 --> End([Process Terminated])

    DefaultHandler --> DefaultEnd([Default behavior])

    style Start fill:#e1f5e1
    style SigInt fill:#fff4e1
    style SigTerm fill:#fff4e1
    style End fill:#e1e1e1
```

### Signal Handler Registration

```mermaid
sequenceDiagram
    participant Main as main()
    participant Process as Node Process
    participant SigInt as SIGINT Handler
    participant SigTerm as SIGTERM Handler
    participant Shutdown as handleShutdown closure

    Main->>Shutdown: Create handleShutdown()
    Note over Shutdown: Captures: server, shutdown()

    Main->>Process: process.on('SIGINT', handleShutdown)
    Process->>SigInt: Register handler

    Main->>Process: process.on('SIGTERM', handleShutdown)
    Process->>SigTerm: Register handler

    Note over Process,SigTerm: Handlers remain active during runtime

    Note over Process: User presses Ctrl+C
    SigInt->>Shutdown: Invoke handleShutdown()

    Note over Shutdown: OR: kill -TERM <pid>
    SigTerm->>Shutdown: Invoke handleShutdown()

    Shutdown->>Shutdown: stderr: Shutting down...
    Shutdown->>Shutdown: await shutdown()
    Shutdown->>Shutdown: await server.close()
    Shutdown->>Process: process.exit(0)
```

---

## Configuration Sources

```mermaid
graph TD
    subgraph "Environment Variables"
        Env1[SERVERS_CONFIG]
        Env2[NODE_ENV optional]
        Env3[Backend-specific env vars]
    end

    subgraph "Default Paths"
        Default1[~/.config/mcp/servers.json]
        Default2[~/.meta-mcp/servers.json]
    end

    subgraph "Configuration File"
        ConfigFile[servers.json]
    end

    subgraph "Hardcoded Defaults"
        HC1[maxConnections: 20]
        HC2[idleTimeoutMs: 300000]
        HC3[cleanupIntervalMs: 60000]
    end

    subgraph "Runtime Configuration"
        Runtime[ServerManifest cached in memory]
    end

    Env1 -->|If set| ConfigFile
    Env1 -->|Not set| Default1

    ConfigFile --> Validate{Validation}
    Validate -->|Success| Runtime
    Validate -->|Failure| Error[Fatal Exit]

    Default1 --> ConfigFile

    HC1 --> PoolConfig[ServerPool Config]
    HC2 --> PoolConfig
    HC3 --> PoolConfig

    Env3 --> BackendEnv[Passed to backend servers via spawn]

    style ConfigFile fill:#ffe1b3
    style Runtime fill:#e1f5e1
    style Error fill:#ffe1e1
```

### Configuration Priority

```mermaid
flowchart LR
    Check1{SERVERS_CONFIG<br/>env var?} -->|Set| UseEnv[Use specified path]
    Check1 -->|Not set| UseDefault[Use ~/.config/mcp/servers.json]

    UseEnv --> LoadConfig[Load & parse JSON]
    UseDefault --> LoadConfig

    LoadConfig --> Merge{Merge with<br/>defaults?}

    Merge -->|Pool config| MergePool[Merge with DEFAULT_CONFIG]
    Merge -->|Server configs| UseAsIs[Use as-is from file]

    MergePool --> FinalPool[Final Pool Config]
    UseAsIs --> FinalServers[Final Server Configs]

    style Check1 fill:#e1f0ff
    style FinalPool fill:#e1f5e1
    style FinalServers fill:#e1f5e1
```

---

## Complete System State Machine

```mermaid
stateDiagram-v2
    [*] --> Starting: Process Start

    Starting --> LoadingArgs: Parse CLI args
    LoadingArgs --> ExitVersion: --version/-v
    LoadingArgs --> ExitHelp: --help/-h
    LoadingArgs --> LoadingConfig: Normal startup

    LoadingConfig --> ValidatingConfig: Read servers.json
    ValidatingConfig --> ConfigError: Validation fails
    ValidatingConfig --> CreatingComponents: Validation success

    ConfigError --> [*]: exit(1)

    CreatingComponents --> InitializingPool: Create ServerPool
    InitializingPool --> InitializingCache: Create ToolCache
    InitializingCache --> CreatingServer: Create MCP Server
    CreatingServer --> RegisteringHandlers: Register 3 meta-tools
    RegisteringHandlers --> RegisteringSignals: Register SIGINT/SIGTERM
    RegisteringSignals --> ConnectingTransport: Create stdio transport
    ConnectingTransport --> Ready: server.connect()

    Ready --> Processing: Handle requests

    state Processing {
        [*] --> Idle
        Idle --> ReceivingRequest: Request arrives
        ReceivingRequest --> RoutingRequest: Parse request type

        RoutingRequest --> ListTools: list_tools
        RoutingRequest --> CallTool: call_tool

        ListTools --> ReturningMeta: Return 3 meta-tools
        CallTool --> DispatchingMetaTool: Route to meta-tool

        DispatchingMetaTool --> ListServers: list_servers
        DispatchingMetaTool --> GetServerTools: get_server_tools
        DispatchingMetaTool --> CallServerTool: call_tool

        ListServers --> ReturningResult: Query registry
        GetServerTools --> CheckingCache: Check tool cache
        CallServerTool --> AcquiringConnection: Get pool connection

        CheckingCache --> FetchingTools: Cache miss
        CheckingCache --> ReturningResult: Cache hit

        FetchingTools --> CachingTools: Store in cache
        CachingTools --> ReturningResult

        AcquiringConnection --> ExecutingTool: Forward to backend
        ExecutingTool --> ReleasingConnection: Release pool entry
        ReleasingConnection --> ReturningResult

        ReturningMeta --> Idle
        ReturningResult --> Idle
    }

    Processing --> ShuttingDown: SIGINT/SIGTERM

    state ShuttingDown {
        [*] --> StoppingPool
        StoppingPool --> DisconnectingAll: Clear timer
        DisconnectingAll --> ClearingCaches: Close connections
        ClearingCaches --> ClosingServer: Clear maps
        ClosingServer --> Exiting: Close transport
        Exiting --> [*]
    }

    ShuttingDown --> [*]: exit(0)

    ExitVersion --> [*]: exit(0)
    ExitHelp --> [*]: exit(0)
```

---

## Background Processes

```mermaid
gantt
    title Background Operations Timeline
    dateFormat X
    axisFormat %S

    section Main Process
    Process Start           :milestone, 0, 0s
    Initialize Components   :active, 0, 2
    Ready & Listening       :active, 2, 60
    Shutdown                :crit, 60, 62
    Process Exit            :milestone, 62, 62s

    section Pool Cleanup
    Start Cleanup Timer     :milestone, 1, 1s
    Idle                    :60s, 1, 60
    First Cleanup           :milestone, 60, 60s
    Second Cleanup          :milestone, 120, 120s

    section Connections
    Connection 1 Created    :milestone, 5, 5s
    Conn 1 Active           :active, 5, 15
    Conn 1 Idle             :15, 310

    Connection 2 Created    :milestone, 10, 10s
    Conn 2 Active           :active, 10, 20
    Conn 2 Idle             :20, 320

    section Cleanup Events
    Check Idle Timeouts     :60, 61
    Check Idle Timeouts     :120, 121
    Evict Expired           :crit, 310, 311
```

---

## Summary

This document provides a complete view of Meta-MCP Server's lifecycle:

1. **Startup**: CLI parsing → Config loading → Component initialization → Signal registration → Transport connection
2. **Runtime**: Request routing → Pool management → Background cleanup → Tool caching
3. **Shutdown**: Signal handling → Pool cleanup → Cache clearing → Server closure → Graceful exit

### Key Characteristics

- **Lazy Loading**: Servers only spawn when first requested
- **Resource Management**: LRU eviction with 5-minute idle timeout, periodic 60s cleanup
- **Error Isolation**: Startup errors are fatal; runtime errors return to client
- **Graceful Shutdown**: Ordered cleanup ensures no resource leaks
- **Zero Config**: Works with defaults, customizable via environment variables

### Token Optimization

- Startup cost: ~100 tokens (3 meta-tools)
- Summary query: ~100 tokens per server (names only)
- Full schema: ~2k tokens per tool (on-demand)
- Traditional approach: ~16k tokens (all tools upfront)

**Reduction: 87% fewer tokens**
