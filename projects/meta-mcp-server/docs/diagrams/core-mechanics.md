# Core Mechanics

## Handlers

```mermaid
flowchart LR
  subgraph Meta-Tools
    H1[list_servers]
    H2[get_server_tools]
    H3[call_tool]
  end

  subgraph Core
    R[Registry]
    C[Cache]
    P[Pool]
  end

  H1 --> R
  H2 --> C & P
  H3 --> P

  style H1 fill:#e3f2fd
  style H2 fill:#fff3e0
  style H3 fill:#f3e5f5
```

## Pool (LRU)

```mermaid
flowchart TD
  A[getConnection] --> B{Exists?}
  B -->|Yes| C[Return]
  B -->|No| D{Full?}
  D -->|No| E[Create]
  D -->|Yes| F[Evict oldest]
  F --> E
  E --> C

  style C fill:#e8f5e9
```

| Setting | Value |
|---------|-------|
| maxConnections | 6 |
| idleTimeout | 5 min |
| cleanup | 1 min |

## Cache

```mermaid
flowchart TD
  A[Request] --> B{Cached?}
  B -->|Yes| C[Return]
  B -->|No| D[Fetch → Cache]
  D --> C

  style C fill:#e8f5e9
```

Cleared when connection evicted.
