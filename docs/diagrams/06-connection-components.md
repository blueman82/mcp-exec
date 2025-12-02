# Connection and Transport Layer Architecture

This document details the connection lifecycle, transport layer selection, error handling, and cleanup sequences in Meta-MCP Server.

## Component Overview

```mermaid
graph TB
    subgraph "Connection Factory"
        CF[createConnection]
        BSC[buildSpawnConfig]
        CF -->|1. Build config| BSC
    end

    subgraph "Transport Layer"
        SCT[StdioClientTransport]
        SP[Process Spawn]
        STDIO[stdio streams]
        SCT -->|spawns| SP
        SP -->|provides| STDIO
    end

    subgraph "MCP Client Layer"
        CLIENT[MCP Client]
        CONN[MCPConnection]
        CLIENT -->|wrapped by| CONN
    end

    subgraph "Configuration"
        SC[ServerConfig]
        DOCKER[Docker Config]
        NODE[Node Config]
        UVX[uvx Config]
        SC -.->|type: docker| DOCKER
        SC -.->|type: node| NODE
        SC -.->|type: uvx| UVX
    end

    SC -->|input| CF
    BSC -->|2. Create| SCT
    SCT -->|3. Initialize| CLIENT
    CLIENT -->|4. Wrap| CONN
    CONN -->|5. Connect| CLIENT
    CLIENT -.->|uses| SCT

    style CF fill:#e1f5ff
    style CONN fill:#d4edda
    style CLIENT fill:#fff3cd
    style SCT fill:#f8d7da
```

## Transport Selection Logic

```mermaid
flowchart TD
    START[buildSpawnConfig] --> CHECK_CMD{command field<br/>present?}
    CHECK_CMD -->|No| ERROR1[throw Error<br/>'Config requires command']

    CHECK_CMD -->|Yes| INFER{Infer spawn type<br/>from command}

    INFER -->|command = 'docker'| DOCKER[Docker Transport]
    INFER -->|command = 'uvx'| UVX[uvx Transport]
    INFER -->|command = 'npx'| NPX[npx Transport]
    INFER -->|other| DIRECT[Direct Execution]

    DOCKER --> D_CONFIG["command: 'docker'<br/>args: [run, -i, --rm, image, ...]<br/>env: merged"]
    UVX --> U_CONFIG["command: 'uvx'<br/>args: [package-name, ...]<br/>env: merged"]
    NPX --> N_CONFIG["command: 'npx'<br/>args: [package-name, ...]<br/>env: merged"]
    DIRECT --> DIR_CONFIG["command: executable path<br/>args: command arguments<br/>env: merged"]

    D_CONFIG --> RETURN[Return SpawnConfig]
    U_CONFIG --> RETURN
    N_CONFIG --> RETURN
    DIR_CONFIG --> RETURN

    style DOCKER fill:#e3f2fd
    style UVX fill:#f3e5f5
    style NPX fill:#fff9c4
    style DIRECT fill:#e8f5e9
    style ERROR1 fill:#ffcdd2
```

### Transport Examples

```typescript
// Docker Transport
{
  command: "docker",
  args: ["run", "-i", "--rm", "mcp/filesystem"],
  env: { ...process.env, ...customEnv }
}

// uvx Transport
{
  command: "uvx",
  args: ["mcp-server-git"],
  env: { ...process.env, ...customEnv }
}

// Node Transport
{
  command: "node",
  args: ["/path/to/jira/dist/index.js"],
  env: { ...process.env, JIRA_API_KEY: "..." }
}

// Python Transport
{
  command: "python",
  args: ["-m", "mcp_server_module"],
  env: { ...process.env, ...customEnv }
}
```

## Connection Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Disconnected: createConnection()

    Disconnected --> Connecting: connect()

    Connecting --> Connected: client.connect() success
    Connecting --> Error: client.connect() failure

    Connected --> Disconnected: disconnect()
    Connected --> Error: UnexpectedExitError

    Error --> Disconnected: disconnect()

    Disconnected --> [*]: closeConnection()

    note right of Connecting
        - StdioClientTransport spawns process
        - MCP client establishes protocol
        - Timeout after connection timeout
    end note

    note right of Connected
        - Process running
        - MCP protocol active
        - Ready for tool calls
    end note

    note right of Error
        - SpawnError: failed to spawn
        - ConnectionError: protocol error
        - TimeoutError: connection timeout
        - UnexpectedExitError: process died
    end note
```

## Detailed Connection Sequence

```mermaid
sequenceDiagram
    participant Pool as ServerPool
    participant Factory as createConnection
    participant Builder as buildSpawnConfig
    participant Transport as StdioClientTransport
    participant Process as Child Process
    participant Client as MCP Client
    participant Conn as MCPConnection

    Pool->>Factory: createConnection(config)

    rect rgb(240, 248, 255)
        Note over Factory,Builder: Phase 1: Configuration
        Factory->>Builder: buildSpawnConfig(config)
        Builder->>Builder: Validate command exists
        Builder->>Builder: Infer transport type
        Builder->>Builder: Build spawn config
        alt Config validation fails
            Builder-->>Factory: throw SpawnError
            Factory-->>Pool: throw SpawnError
        end
        Builder-->>Factory: SpawnConfig
    end

    rect rgb(255, 250, 240)
        Note over Factory,Transport: Phase 2: Transport Setup
        Factory->>Transport: new StdioClientTransport(spawnConfig)
        alt Transport creation fails
            Transport-->>Factory: throw error
            Factory-->>Pool: throw SpawnError
        end
        Transport->>Transport: Store spawn config
        Transport-->>Factory: transport instance
    end

    rect rgb(240, 255, 240)
        Note over Factory,Client: Phase 3: Client Initialization
        Factory->>Client: new Client(clientInfo, capabilities)
        Client-->>Factory: client instance
        Factory->>Conn: Create MCPConnection wrapper
        Conn-->>Factory: connection object
    end

    rect rgb(255, 240, 240)
        Note over Factory,Process: Phase 4: Connection Establishment
        Factory->>Conn: connection.connect()
        Conn->>Conn: Set state: Connecting
        Conn->>Client: client.connect(transport)
        Client->>Transport: Start transport
        Transport->>Process: spawn(command, args, {env})

        alt Process spawn fails
            Process-->>Transport: spawn error
            Transport-->>Client: error
            Client-->>Conn: error
            Conn->>Conn: Set state: Error
            Conn-->>Factory: throw SpawnError
            Factory-->>Pool: throw SpawnError
        end

        Process-->>Transport: stdio streams
        Transport->>Transport: Setup stdio handlers
        Transport->>Client: Transport ready
        Client->>Client: MCP handshake

        alt MCP handshake fails
            Client-->>Conn: error
            Conn->>Conn: Set state: Error
            Conn-->>Factory: throw SpawnError
            Factory-->>Pool: throw SpawnError
        end

        Client-->>Conn: Connected
        Conn->>Conn: Set state: Connected
        Conn-->>Factory: success
    end

    Factory-->>Pool: MCPConnection (connected)
```

## Error Handling Architecture

```mermaid
graph TB
    subgraph "Error Types"
        SE[SpawnError]
        CE[ConnectionError]
        TE[TimeoutError]
        UE[UnexpectedExitError]
        TRE[TransportError]
    end

    subgraph "Error Sources"
        CONFIG[Config Validation]
        SPAWN[Process Spawn]
        HANDSHAKE[MCP Handshake]
        RUNTIME[Runtime Errors]
        STDIO[stdio Streams]
    end

    subgraph "Error Handlers"
        CATCH[Try-Catch Blocks]
        STATE[State Updates]
        CLEANUP[Resource Cleanup]
        RETHROW[Error Propagation]
    end

    CONFIG -->|Invalid config| SE
    SPAWN -->|Spawn failure| SE
    HANDSHAKE -->|Protocol error| CE
    RUNTIME -->|Connection timeout| TE
    RUNTIME -->|Process died| UE
    STDIO -->|Stream error| TRE

    SE --> CATCH
    CE --> CATCH
    TE --> CATCH
    UE --> CATCH
    TRE --> CATCH

    CATCH --> STATE
    STATE --> CLEANUP
    CLEANUP --> RETHROW

    style SE fill:#ffebee
    style CE fill:#fff3e0
    style TE fill:#e8eaf6
    style UE fill:#fce4ec
    style TRE fill:#f3e5f5
```

### Error Details

```mermaid
classDiagram
    class SpawnError {
        +string message
        +string command
        +string[] args
        +Error? cause
        +constructor(message, command, args, cause?)
    }

    class TimeoutError {
        +string message
        +number timeoutMs
        +constructor(message, timeoutMs)
    }

    class UnexpectedExitError {
        +string message
        +number? exitCode
        +string? signal
        +constructor(message, exitCode, signal)
    }

    class ConnectionError {
        +string message
        +string serverId
        +constructor(message, serverId)
    }

    class TransportError {
        +string message
        +string transportType
        +constructor(message, transportType)
    }

    Error <|-- SpawnError
    Error <|-- TimeoutError
    Error <|-- UnexpectedExitError
    Error <|-- ConnectionError
    Error <|-- TransportError

    note for SpawnError "Thrown when:\n- Config validation fails\n- Process spawn fails\n- MCP connection fails"
    note for TimeoutError "Thrown when:\n- Connection timeout\n- Operation timeout"
    note for UnexpectedExitError "Thrown when:\n- Process exits unexpectedly\n- Process killed by signal"
```

## Graceful Shutdown Sequence

```mermaid
sequenceDiagram
    participant Pool as ServerPool
    participant Conn as MCPConnection
    participant Client as MCP Client
    participant Transport as StdioClientTransport
    participant Process as Child Process

    Pool->>Conn: disconnect()

    rect rgb(255, 250, 240)
        Note over Conn: Phase 1: Check State
        Conn->>Conn: Check if already disconnected
        alt Already disconnected
            Conn-->>Pool: return (no-op)
        end
    end

    rect rgb(240, 248, 255)
        Note over Conn,Client: Phase 2: Protocol Shutdown
        Conn->>Client: client.close()
        Client->>Transport: Send close notification
        Transport->>Process: Write to stdin
        Process->>Process: Handle close gracefully
        Process-->>Transport: Flush stdout/stderr
        Transport-->>Client: Close acknowledged
        Client-->>Conn: Close complete
    end

    rect rgb(255, 240, 240)
        Note over Conn,Process: Phase 3: Process Cleanup
        alt Process still running
            Transport->>Process: process.kill()
            Process-->>Transport: Exit
        end
    end

    rect rgb(240, 255, 240)
        Note over Conn: Phase 4: State Update
        Conn->>Conn: Set state: Disconnected
        Conn-->>Pool: Disconnection complete
    end

    Note over Pool,Process: Resources cleaned up:<br/>- stdio streams closed<br/>- process terminated<br/>- memory released
```

## Connection State Management

```mermaid
graph LR
    subgraph "State Transitions"
        DISC[Disconnected]
        CONN_ING[Connecting]
        CONN_ED[Connected]
        ERR[Error]
    end

    subgraph "State Checks"
        IS_CONN{isConnected?}
        CAN_GET{Can getTools?}
        CAN_CALL{Can call_tool?}
    end

    subgraph "Actions"
        CONNECT[connect]
        DISCONNECT[disconnect]
        GET_TOOLS[getTools]
    end

    DISC -->|connect| CONN_ING
    CONN_ING -->|success| CONN_ED
    CONN_ING -->|failure| ERR
    CONN_ED -->|disconnect| DISC
    CONN_ED -->|error| ERR
    ERR -->|disconnect| DISC

    CONN_ED --> IS_CONN
    IS_CONN -->|true| CAN_GET
    IS_CONN -->|true| CAN_CALL
    CAN_GET -->|state check| GET_TOOLS

    style DISC fill:#e3f2fd
    style CONN_ING fill:#fff9c4
    style CONN_ED fill:#c8e6c9
    style ERR fill:#ffcdd2
```

## Component Interactions

```mermaid
graph TB
    subgraph "High-Level Components"
        SP[ServerPool]
        TC[ToolCache]
    end

    subgraph "Connection Layer"
        CF[createConnection]
        CC[closeConnection]
        CONN[MCPConnection]
    end

    subgraph "Transport Layer"
        BSC[buildSpawnConfig]
        SCT[StdioClientTransport]
    end

    subgraph "MCP SDK"
        CLIENT[Client]
        PROTO[MCP Protocol]
    end

    subgraph "Process Layer"
        SPAWN[child_process.spawn]
        PROC[Child Process]
        STDIO[stdio streams]
    end

    SP -->|create| CF
    SP -->|close| CC
    CF -->|build| BSC
    CF -->|create| SCT
    CF -->|initialize| CLIENT
    CF -->|wrap| CONN

    CONN -->|uses| CLIENT
    CLIENT -->|uses| SCT
    SCT -->|spawns| SPAWN
    SPAWN -->|creates| PROC
    PROC -->|provides| STDIO
    SCT -->|reads/writes| STDIO

    CLIENT -->|implements| PROTO
    PROTO -.->|messages| STDIO

    CC -->|cleanup| CONN
    CONN -->|close| CLIENT
    CLIENT -->|close| SCT
    SCT -->|kill| PROC

    TC -.->|cache tools| CONN

    style SP fill:#e1f5ff
    style CONN fill:#d4edda
    style CLIENT fill:#fff3cd
    style SCT fill:#f8d7da
    style PROC fill:#e0e0e0
```

## Resource Lifecycle

```mermaid
gantt
    title Connection Resource Lifecycle
    dateFormat X
    axisFormat %s

    section Configuration
    Build SpawnConfig       :a1, 0, 1s
    Validate Config        :a2, after a1, 1s

    section Transport
    Create Transport       :b1, after a2, 1s
    Setup stdio           :b2, after b1, 1s

    section Process
    Spawn Process         :c1, after b2, 1s
    Process Running       :c2, after c1, 10s

    section Protocol
    MCP Handshake        :d1, after c1, 2s
    Ready for Tools      :d2, after d1, 8s

    section Cleanup
    Send Close           :e1, after d2, 1s
    Process Exit         :e2, after e1, 1s
    Resource Free        :e3, after e2, 1s
```

## Connection Pool Integration

```mermaid
sequenceDiagram
    participant Client as AI Client
    participant Server as MCP Server
    participant Pool as ServerPool
    participant Conn as MCPConnection
    participant Backend as Backend MCP

    Client->>Server: call_tool(jira, get_issue, {...})
    Server->>Pool: getConnection('jira')

    alt Connection exists in pool
        Pool->>Pool: Check if connected
        alt Connected
            Pool-->>Server: Return existing connection
        else Not connected
            Pool->>Conn: connect()
            Conn->>Backend: Establish connection
            Backend-->>Conn: Connected
            Conn-->>Pool: Connection ready
            Pool-->>Server: Return connection
        end
    else Connection doesn't exist
        Pool->>Conn: createConnection(jiraConfig)
        Conn->>Backend: Spawn + Connect
        Backend-->>Conn: Connected
        Conn-->>Pool: New connection
        Pool->>Pool: Add to pool
        Pool-->>Server: Return connection
    end

    Server->>Conn: client.callTool(...)
    Conn->>Backend: MCP tool call
    Backend->>Backend: Execute tool
    Backend-->>Conn: Tool result
    Conn-->>Server: Result
    Server-->>Client: Tool result

    Note over Pool,Conn: Connection kept alive<br/>in pool for reuse
```

## Error Recovery Strategies

```mermaid
flowchart TD
    START[Error Detected] --> TYPE{Error Type?}

    TYPE -->|SpawnError| SPAWN_HANDLE[Spawn Error Handler]
    TYPE -->|ConnectionError| CONN_HANDLE[Connection Error Handler]
    TYPE -->|TimeoutError| TIME_HANDLE[Timeout Error Handler]
    TYPE -->|UnexpectedExitError| EXIT_HANDLE[Exit Error Handler]

    SPAWN_HANDLE --> SPAWN_CHECK{Retryable?}
    SPAWN_CHECK -->|Yes| RETRY[Retry spawn with backoff]
    SPAWN_CHECK -->|No| FAIL1[Fail fast, log error]

    CONN_HANDLE --> CONN_ACTION[Disconnect + cleanup]
    CONN_ACTION --> REMOVE1[Remove from pool]

    TIME_HANDLE --> TIME_ACTION[Kill process]
    TIME_ACTION --> REMOVE2[Remove from pool]

    EXIT_HANDLE --> EXIT_ACTION[Cleanup resources]
    EXIT_ACTION --> REMOVE3[Remove from pool]

    RETRY --> SUCCESS{Success?}
    SUCCESS -->|Yes| CONNECTED[Connection ready]
    SUCCESS -->|No| FAIL2[Fail, propagate error]

    FAIL1 --> PROPAGATE[Propagate to caller]
    REMOVE1 --> PROPAGATE
    REMOVE2 --> PROPAGATE
    REMOVE3 --> PROPAGATE
    FAIL2 --> PROPAGATE

    CONNECTED --> END[Error recovered]
    PROPAGATE --> END

    style SPAWN_HANDLE fill:#ffebee
    style CONN_HANDLE fill:#fff3e0
    style TIME_HANDLE fill:#e8eaf6
    style EXIT_HANDLE fill:#fce4ec
    style CONNECTED fill:#c8e6c9
    style PROPAGATE fill:#ffcdd2
```

## Best Practices

### Connection Management
1. **Always check state before operations**: Verify connection is in `Connected` state before calling tools
2. **Handle all error types**: Catch and handle specific error types appropriately
3. **Cleanup on errors**: Always set state to `Disconnected` in finally blocks
4. **Graceful shutdown**: Call `client.close()` before killing process

### Transport Selection
1. **Docker**: Use for isolated, containerized MCP servers
2. **uvx/npx**: Use for package-based Python/Node MCP servers
3. **Direct execution**: Use for custom executable paths

### Error Handling
1. **SpawnError**: Retry with exponential backoff for transient failures
2. **ConnectionError**: Remove from pool, log for debugging
3. **TimeoutError**: Kill process immediately, don't retry
4. **UnexpectedExitError**: Log exit code/signal, remove from pool

### Resource Cleanup
1. **stdio streams**: Automatically closed by transport
2. **Child process**: Killed if still running after close
3. **Memory**: Released when connection removed from pool
4. **Event listeners**: Cleaned up by MCP SDK

## Related Diagrams
- [System Architecture](01-system-architecture.md) - Overall system design
- [Request Flow](02-request-flow.md) - End-to-end request handling
- [Pool Lifecycle](03-pool-lifecycle.md) - Connection pool management
- [Caching Strategy](04-caching-strategy.md) - Tool definition caching
