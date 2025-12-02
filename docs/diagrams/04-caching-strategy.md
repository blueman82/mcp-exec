# Tool Caching Strategy

This diagram illustrates Meta-MCP's tool caching mechanism, which minimizes backend server calls by maintaining a per-server cache of tool definitions.

## Performance Benefits

- **Cache Hit**: ~1-5ms (in-memory lookup)
- **Cache Miss**: ~50-200ms (backend MCP call + cache storage)
- **Token Savings**: Cached tools avoid repeated schema fetches
- **Connection Efficiency**: Reduces load on backend servers

## Caching Strategy Flow

```mermaid
flowchart TD
    Start([Request Tools for 'corp-jira']) --> CheckCache{Is 'corp-jira' in ToolCache?}

    %% Cache Hit Path (Fast)
    CheckCache -->|YES - Cache Hit| ReturnCached[Return Cached ToolDefinition Array]
    ReturnCached --> End([Response to Caller])

    %% Cache Miss Path (Backend Call)
    CheckCache -->|NO - Cache Miss| GetConnection[Get Connection to 'corp-jira' Server]
    GetConnection --> CallBackend[Call MCP client.listTools]
    CallBackend --> ReceiveTools[Receive ToolDefinition Array from Backend]
    ReceiveTools --> StoreCache[Store in Cache ToolCache['corp-jira']]
    StoreCache --> ReturnNew[Return Tools to Caller]
    ReturnNew --> End

    %% Cache Invalidation Triggers
    EvictionTrigger([Server Pool Eviction Event]) --> CheckServerId{Server ID matches cached entry?}
    CheckServerId -->|YES| EvictCache[Remove from ToolCache delete ToolCache[serverId]]
    CheckServerId -->|NO| IgnoreEviction[No Action]
    EvictCache --> EvictionComplete([Cache Entry Removed])

    ShutdownTrigger([Graceful Shutdown]) --> ClearAll[Clear All Caches ToolCache.clear]
    ClearAll --> ShutdownComplete([All Caches Cleared])

    %% Styling
    classDef cacheHit fill:#d4edda,stroke:#28a745,stroke-width:2px
    classDef cacheMiss fill:#fff3cd,stroke:#ffc107,stroke-width:2px
    classDef invalidation fill:#f8d7da,stroke:#dc3545,stroke-width:2px
    classDef decision fill:#d1ecf1,stroke:#17a2b8,stroke-width:2px

    class ReturnCached,End cacheHit
    class GetConnection,CallBackend,ReceiveTools,StoreCache,ReturnNew cacheMiss
    class EvictCache,ClearAll invalidation
    class CheckCache,CheckServerId decision
```

## Cache Structure

```typescript
// Per-Server Cache Storage
interface ToolCache {
  [serverId: string]: ToolDefinition[]
}

// Example:
{
  "corp-jira": [
    { name: "create_issue", description: "...", inputSchema: {...} },
    { name: "search_issues", description: "...", inputSchema: {...} }
  ],
  "filesystem": [
    { name: "read_file", description: "...", inputSchema: {...} },
    { name: "write_file", description: "...", inputSchema: {...} }
  ]
}
```

## Cache Lifecycle Events

### 1. Cache Population (Cache Miss)
```
Request → Cache Miss → Backend Call → Store Result → Return
         ↓
    ~50-200ms (one-time cost)
```

### 2. Cache Hit (Subsequent Requests)
```
Request → Cache Hit → Return Cached
         ↓
    ~1-5ms (in-memory)
```

### 3. Cache Invalidation (Server Eviction)
```
Pool Eviction Event → Match Server ID → Remove from Cache
                      ↓
                  Ensures cache consistency
```

### 4. Cache Clearing (Shutdown)
```
Shutdown Signal → Clear All Caches → Cleanup Complete
                  ↓
              Memory released
```

## Key Design Principles

1. **Lazy Loading**: Tools are only fetched when first requested
2. **Per-Server Isolation**: Each backend server has independent cache entries
3. **Automatic Invalidation**: Cache eviction mirrors pool eviction (LRU)
4. **Memory Efficiency**: Caches cleared on shutdown to prevent leaks
5. **Consistency**: Cache never holds stale data from disconnected servers

## Integration with Server Pool

The ToolCache subscribes to ServerPool eviction events:

```typescript
// When a server is evicted from the pool (LRU or idle timeout)
pool.on('eviction', (serverId: string) => {
  toolCache.evict(serverId); // Remove cached tools
});
```

This ensures:
- Cache size stays bounded by pool size (max 20 servers)
- Stale tool definitions never served after server restart
- Memory usage proportional to active server count

## Token Optimization

Combined with the two-tier loading strategy:

1. **First Request**: `get_server_tools({summary_only: true})`
   - Cache miss → Backend call → Cache tool names
   - ~100 tokens returned (names + descriptions only)

2. **Second Request**: `get_server_tools({tools: ["specific_tool"]})`
   - Cache hit → Return full schema from cache
   - ~50-500 tokens per tool (no backend call)

3. **Subsequent Requests**: All cache hits
   - Zero backend calls
   - Sub-millisecond response times

**Result**: 87% token reduction + near-instant tool lookups after first fetch
