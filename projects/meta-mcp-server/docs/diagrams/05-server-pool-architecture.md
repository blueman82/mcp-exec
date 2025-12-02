# ServerPool Architecture

This diagram shows the complete ServerPool class architecture, including all components, relationships, and the LRU eviction algorithm.

## Class Structure

```mermaid
classDiagram
    class ServerPool {
        -Map~string,PoolEntry~ connections
        -ConnectionFactory factory
        -PoolConfig config
        -Timer cleanupInterval
        +constructor(factory, config?)
        +getConnection(serverId) Promise~MCPConnection~
        +releaseConnection(serverId) void
        +runCleanup() Promise~void~
        +getActiveCount() number
        +shutdown() Promise~void~
        -evictLRU() boolean
        -startCleanupTimer() void
    }

    class PoolEntry {
        +MCPConnection connection
        +number lastAccessTime
        +boolean inUse
    }

    class PoolConfig {
        +number maxConnections
        +number idleTimeoutMs
    }

    class ConnectionFactory {
        <<interface>>
        +(serverId: string) Promise~MCPConnection~
    }

    class MCPConnection {
        <<interface>>
        +string serverId
        +ConnectionState state
        +connect() Promise~void~
        +disconnect() Promise~void~
        +isConnected() boolean
        +getTools() Promise~ToolDefinition[]~
    }

    class ConnectionState {
        <<enumeration>>
        Disconnected
        Connecting
        Connected
        Error
    }

    class ConnectionError {
        <<Error>>
        +string message
        +Error cause
    }

    class PoolExhaustedError {
        <<Error>>
        +string message
    }

    ServerPool *-- "0..6" PoolEntry : contains
    ServerPool ..> ConnectionFactory : uses
    ServerPool *-- PoolConfig : has
    ServerPool ..> ConnectionError : throws
    ServerPool ..> PoolExhaustedError : throws
    PoolEntry --> MCPConnection : wraps
    MCPConnection --> ConnectionState : has
```

## Component Details

### ServerPool Configuration

```mermaid
graph TB
    subgraph "Default Configuration"
        MAX[maxConnections: 20]
        IDLE[idleTimeoutMs: 300000ms<br/>5 minutes]
        CLEANUP[cleanupIntervalMs: 60000ms<br/>1 minute]
    end

    subgraph "Runtime State"
        MAP[connections: Map&lt;serverId, PoolEntry&gt;]
        TIMER[cleanupInterval: NodeJS.Timer]
        FACTORY[factory: ConnectionFactory]
    end

    MAX --> MAP
    IDLE --> MAP
    CLEANUP --> TIMER
```

### PoolEntry Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Created: factory(serverId)
    Created --> InUse: getConnection()
    InUse --> Idle: releaseConnection()
    Idle --> InUse: getConnection()
    Idle --> Evicted: evictLRU() or runCleanup()
    InUse --> Shutdown: shutdown()
    Idle --> Shutdown: shutdown()
    Evicted --> [*]: connection.disconnect()
    Shutdown --> [*]: connection.disconnect()

    note right of Created
        lastAccessTime = Date.now()
        inUse = true
    end note

    note right of Idle
        inUse = false
        lastAccessTime updated
    end note

    note right of Evicted
        LRU algorithm:
        - Only idle connections
        - Oldest lastAccessTime
        - Triggers disconnect()
    end note
```

## LRU Eviction Algorithm

```mermaid
flowchart TD
    START([getConnection called]) --> CHECK_EXIST{Connection<br/>exists?}
    CHECK_EXIST -->|Yes| UPDATE[Update lastAccessTime<br/>Set inUse = true]
    UPDATE --> RETURN1[Return existing connection]

    CHECK_EXIST -->|No| CHECK_SIZE{Pool size >=<br/>maxConnections?}
    CHECK_SIZE -->|No| CREATE[Create new connection]

    CHECK_SIZE -->|Yes| EVICT_START[Start LRU eviction]
    EVICT_START --> FIND_OLDEST[Find oldest idle connection]

    FIND_OLDEST --> ITERATE[Iterate connections Map]
    ITERATE --> FILTER{inUse =<br/>false?}
    FILTER -->|No| SKIP[Skip this entry]
    SKIP --> MORE{More<br/>entries?}

    FILTER -->|Yes| COMPARE{lastAccessTime <<br/>current oldest?}
    COMPARE -->|Yes| SET_OLDEST[Update oldest reference]
    COMPARE -->|No| MORE
    SET_OLDEST --> MORE

    MORE -->|Yes| ITERATE
    MORE -->|No| CHECK_FOUND{Oldest<br/>found?}

    CHECK_FOUND -->|Yes| DISCONNECT[Call disconnect()]
    DISCONNECT --> DELETE[Delete from Map]
    DELETE --> CREATE

    CHECK_FOUND -->|No| ERROR[Throw PoolExhaustedError]

    CREATE --> FACTORY[Call factory(serverId)]
    FACTORY --> CONNECT[Call connection.connect()]
    CONNECT --> ADD_ENTRY[Add to Map with:<br/>lastAccessTime = now<br/>inUse = true]
    ADD_ENTRY --> RETURN2[Return new connection]

    ERROR --> END1([Error thrown])
    RETURN1 --> END2([Connection returned])
    RETURN2 --> END2

    style EVICT_START fill:#ffe6e6
    style FIND_OLDEST fill:#ffe6e6
    style DISCONNECT fill:#ffcccc
    style DELETE fill:#ffcccc
    style ERROR fill:#ff9999
```

## Connection Pool Operations

### getConnection() Flow

```mermaid
sequenceDiagram
    participant Client
    participant Pool as ServerPool
    participant Map as connections Map
    participant Factory as ConnectionFactory
    participant Conn as MCPConnection

    Client->>Pool: getConnection(serverId)
    Pool->>Map: get(serverId)

    alt Connection exists
        Map-->>Pool: PoolEntry found
        Pool->>Pool: entry.lastAccessTime = now
        Pool->>Pool: entry.inUse = true
        Pool-->>Client: Return existing connection
    else Connection not found
        Map-->>Pool: undefined
        Pool->>Pool: Check size >= maxConnections

        alt Pool is full
            Pool->>Pool: evictLRU()
            Pool->>Map: Find oldest idle connection
            Map-->>Pool: Oldest entry
            Pool->>Conn: disconnect()
            Pool->>Map: delete(oldestServerId)
        end

        Pool->>Factory: factory(serverId)
        Factory-->>Pool: new MCPConnection
        Pool->>Conn: connect()
        Conn-->>Pool: Connected
        Pool->>Map: set(serverId, new PoolEntry)
        Pool-->>Client: Return new connection
    end
```

### releaseConnection() Flow

```mermaid
sequenceDiagram
    participant Client
    participant Pool as ServerPool
    participant Map as connections Map
    participant Entry as PoolEntry

    Client->>Pool: releaseConnection(serverId)
    Pool->>Map: get(serverId)
    Map-->>Pool: PoolEntry or undefined

    alt Entry exists
        Pool->>Entry: Set inUse = false
        Pool->>Entry: Update lastAccessTime = now
    else Entry not found
        Note over Pool: No-op (silent)
    end
```

### Cleanup Timer Flow

```mermaid
sequenceDiagram
    participant Timer
    participant Pool as ServerPool
    participant Map as connections Map
    participant Conn as MCPConnection

    Timer->>Pool: runCleanup() [every 60s]
    Pool->>Pool: now = Date.now()
    Pool->>Map: Iterate entries

    loop For each entry
        Map-->>Pool: [serverId, entry]
        Pool->>Pool: Check !inUse && <br/>(now - lastAccessTime) > idleTimeoutMs

        alt Should remove
            Pool->>Pool: Add to toRemove[]
        end
    end

    loop For each serverId in toRemove
        Pool->>Map: get(serverId)
        Map-->>Pool: PoolEntry
        Pool->>Conn: disconnect()
        Pool->>Map: delete(serverId)
    end
```

### Shutdown Flow

```mermaid
sequenceDiagram
    participant Signal as SIGINT/SIGTERM
    participant Main as main()
    participant Pool as ServerPool
    participant Timer
    participant Map as connections Map
    participant Conn as MCPConnection

    Signal->>Main: Shutdown signal
    Main->>Pool: shutdown()

    Pool->>Timer: clearInterval()
    Timer-->>Pool: Cleared

    Pool->>Map: Iterate all entries
    loop For each connection
        Map-->>Pool: PoolEntry
        Pool->>Conn: disconnect()
        Note over Conn: Graceful disconnect
    end

    Pool->>Map: clear()
    Pool-->>Main: Shutdown complete
```

## Integration Points

```mermaid
graph TB
    subgraph "External Components"
        INDEX[index.ts<br/>Main Entry Point]
        FACTORY[connectionFactory closure]
        CACHE[ToolCache]
        SERVER[MCP Server]
    end

    subgraph "ServerPool"
        POOL[ServerPool Instance]
        CONFIG[PoolConfig<br/>max: 6, idle: 5min]
        ENTRIES[Map&lt;serverId, PoolEntry&gt;]
        TIMER[Cleanup Timer<br/>every 60s]
    end

    subgraph "Backend Connections"
        CONN1[MCPConnection 1]
        CONN2[MCPConnection 2]
        CONN3[MCPConnection N]
    end

    INDEX -->|Creates| FACTORY
    INDEX -->|Creates| POOL
    FACTORY -->|Injected into| POOL
    CONFIG -->|Configured in| POOL

    POOL -->|Manages| ENTRIES
    POOL -->|Runs| TIMER

    ENTRIES -->|Contains| CONN1
    ENTRIES -->|Contains| CONN2
    ENTRIES -->|Contains| CONN3

    SERVER -->|Requests connection| POOL
    POOL -->|Returns| CONN1

    TIMER -->|Triggers cleanup| POOL
    POOL -->|Disconnects idle| CONN2

    POOL -.->|On eviction| CACHE
    CACHE -.->|Cache invalidation| SERVER

    style POOL fill:#e6f3ff
    style TIMER fill:#fff4e6
    style FACTORY fill:#e6ffe6
```

## Error Handling

```mermaid
flowchart TD
    START([Operation Start]) --> TRY{Try operation}

    TRY -->|getConnection| CONN_EXIST{Connection<br/>exists?}
    CONN_EXIST -->|No| POOL_FULL{Pool full?}
    POOL_FULL -->|Yes| EVICT{Can evict<br/>idle conn?}
    EVICT -->|No| ERR1[Throw PoolExhaustedError]
    EVICT -->|Yes| CREATE_NEW[Create new connection]
    POOL_FULL -->|No| CREATE_NEW

    CREATE_NEW --> FACTORY_CALL{Factory<br/>succeeds?}
    FACTORY_CALL -->|No| ERR2[Throw ConnectionError<br/>with cause]
    FACTORY_CALL -->|Yes| CONNECT{Connect<br/>succeeds?}
    CONNECT -->|No| ERR2
    CONNECT -->|Yes| SUCCESS[Add to pool]

    CONN_EXIST -->|Yes| SUCCESS

    TRY -->|releaseConnection| SAFE[Safe operation<br/>no errors]
    TRY -->|runCleanup| SAFE
    TRY -->|shutdown| GRACEFUL[Graceful cleanup<br/>catch all errors]

    SUCCESS --> END([Success])
    SAFE --> END
    GRACEFUL --> END
    ERR1 --> CATCH([Error caught by caller])
    ERR2 --> CATCH

    style ERR1 fill:#ff9999
    style ERR2 fill:#ff9999
    style SUCCESS fill:#99ff99
    style SAFE fill:#99ff99
    style GRACEFUL fill:#99ff99
```

## Memory Management

```mermaid
graph TB
    subgraph "Memory Lifecycle"
        ALLOC[Connection Allocated]
        IN_MAP[Stored in Map]
        IN_USE[In Use: inUse=true]
        IDLE[Idle: inUse=false]
        REMOVED[Removed from Map]
        GC[Garbage Collected]
    end

    subgraph "Eviction Triggers"
        LRU[LRU Eviction<br/>Pool full]
        TIMEOUT[Idle Timeout<br/>cleanup timer]
        SHUTDOWN[Explicit Shutdown<br/>graceful exit]
    end

    ALLOC --> IN_MAP
    IN_MAP --> IN_USE
    IN_USE --> IDLE
    IDLE --> IN_USE

    IN_USE --> SHUTDOWN
    IDLE --> LRU
    IDLE --> TIMEOUT
    IDLE --> SHUTDOWN

    LRU --> REMOVED
    TIMEOUT --> REMOVED
    SHUTDOWN --> REMOVED
    REMOVED --> GC

    style REMOVED fill:#ffcccc
    style GC fill:#ff9999
```

## Performance Characteristics

### Time Complexity

| Operation | Best Case | Average Case | Worst Case | Notes |
|-----------|-----------|--------------|------------|-------|
| `getConnection()` (hit) | O(1) | O(1) | O(1) | Map lookup |
| `getConnection()` (miss, space) | O(1) | O(1) | O(1) | Create + Map insert |
| `getConnection()` (miss, full) | O(n) | O(n) | O(n) | Must iterate to find LRU |
| `releaseConnection()` | O(1) | O(1) | O(1) | Map lookup |
| `runCleanup()` | O(n) | O(n) | O(n) | Iterate all entries |
| `shutdown()` | O(n) | O(n) | O(n) | Disconnect all |

### Space Complexity

- **Map storage**: O(n) where n = number of active connections
- **Maximum**: 6 connections (configurable via `maxConnections`)
- **Per-entry overhead**: ~96 bytes (PoolEntry + Map overhead)
- **Total max pool overhead**: ~576 bytes + connection objects

### Timing Characteristics

```mermaid
gantt
    title Connection Pool Timing
    dateFormat X
    axisFormat %S.%L

    section Connection Lifecycle
    Create connection: 0, 100
    Connect via stdio: 100, 300
    Active use: 300, 5300
    Idle period: 5300, 305300
    Cleanup scan: 305300, 305350
    Disconnect: 305350, 305450

    section Pool Operations
    getConnection (hit): 0, 1
    getConnection (miss): 0, 400
    releaseConnection: 5300, 5301
    runCleanup: 305300, 305350
    evictLRU: crit, 0, 10
```

## Configuration Examples

### Default Configuration

```typescript
const pool = new ServerPool(connectionFactory);
// Equivalent to:
const pool = new ServerPool(connectionFactory, {
  maxConnections: 20,
  idleTimeoutMs: 300000  // 5 minutes
});
```

### Custom Configuration

```typescript
// High-throughput: more connections, shorter timeout
const highThroughput = new ServerPool(connectionFactory, {
  maxConnections: 12,
  idleTimeoutMs: 60000  // 1 minute
});

// Resource-constrained: fewer connections, longer timeout
const resourceConstrained = new ServerPool(connectionFactory, {
  maxConnections: 3,
  idleTimeoutMs: 600000  // 10 minutes
});
```

## Usage Patterns

### Basic Usage

```typescript
// 1. Create factory
const factory: ConnectionFactory = async (serverId: string) => {
  const config = getServerConfig(serverId);
  return createConnection(config);
};

// 2. Initialize pool
const pool = new ServerPool(factory);

// 3. Get connection
const conn = await pool.getConnection('filesystem');

// 4. Use connection
const tools = await conn.getTools();

// 5. Release when done
pool.releaseConnection('filesystem');

// 6. Shutdown on exit
await pool.shutdown();
```

### Error Handling Pattern

```typescript
try {
  const conn = await pool.getConnection('server-id');
  try {
    // Use connection
    const result = await conn.getTools();
    return result;
  } finally {
    // Always release
    pool.releaseConnection('server-id');
  }
} catch (error) {
  if (error instanceof PoolExhaustedError) {
    // All connections in use, wait and retry
  } else if (error instanceof ConnectionError) {
    // Backend spawn/connect failed
  }
  throw error;
}
```

## Key Design Decisions

1. **LRU Eviction**: Oldest idle connection removed when pool is full
   - Only considers idle connections (`inUse = false`)
   - Protects active connections from eviction
   - Simple timestamp-based algorithm

2. **Graceful Release**: `releaseConnection()` marks as idle but keeps alive
   - Connection stays in pool for reuse
   - Cleaned up later by timer or eviction
   - Optimizes for repeated access patterns

3. **Background Cleanup**: Timer runs every 60 seconds
   - Removes connections idle > 5 minutes
   - Prevents resource leaks
   - Independent of request patterns

4. **No Cache Coupling**: Pool doesn't directly manage ToolCache
   - Separation of concerns
   - Cache invalidation handled by server layer
   - Pool focused on connection lifecycle

5. **Synchronous Release**: No async operations needed
   - Just updates `inUse` flag and timestamp
   - Actual cleanup happens asynchronously
   - Simplifies caller code

6. **Error Transparency**: Factory errors propagate with context
   - Wraps errors as `ConnectionError`
   - Preserves original cause
   - Rich error information for debugging
