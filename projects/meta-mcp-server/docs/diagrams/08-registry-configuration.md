# Registry and Configuration Loading System

This document provides detailed diagrams of the configuration registry system, showing how Meta-MCP Server loads, validates, and manages backend server configurations.

## Overview

The registry system is responsible for:
- Loading configuration files from disk
- Validating configuration structure with Zod schemas
- Generating and caching server manifests
- Providing access to server configurations
- Managing disabled servers

## Configuration Loading Flow

```mermaid
flowchart TD
    Start([Process Startup]) --> EnvCheck{SERVERS_CONFIG<br/>env var set?}

    EnvCheck -->|Yes| CustomPath[Use custom path]
    EnvCheck -->|No| DefaultPath[Use default:<br/>~/.config/mcp/servers.json]

    CustomPath --> FileExists{File exists?}
    DefaultPath --> FileExists

    FileExists -->|No| ErrNotFound[Throw ConfigNotFoundError]
    FileExists -->|Yes| ReadFile[fs.readFileSync<br/>read as UTF-8]

    ReadFile --> ParseJSON{Parse JSON}

    ParseJSON -->|Success| ValidateSchema[Validate with Zod:<br/>BackendsConfigSchema]
    ParseJSON -->|Fail| ErrParse[Throw ConfigParseError]

    ValidateSchema -->|Success| ExtractServers[Extract mcpServers<br/>Record]
    ValidateSchema -->|Fail| ErrValidation[Throw ConfigValidationError]

    ExtractServers --> BuildManifest[Build ServerManifest:<br/>- servers: configs<br/>- metadata]

    BuildManifest --> CacheManifest[Store in cachedManifest<br/>global variable]

    CacheManifest --> Ready([Ready for Queries])

    ErrNotFound --> ErrorEnd([Error State])
    ErrParse --> ErrorEnd
    ErrValidation --> ErrorEnd

    style Start fill:#e1f5e1
    style Ready fill:#e1f5e1
    style ErrNotFound fill:#ffe1e1
    style ErrParse fill:#ffe1e1
    style ErrValidation fill:#ffe1e1
    style ErrorEnd fill:#ffe1e1
```

## Zod Schema Validation Pipeline

```mermaid
flowchart TD
    Input[Raw JSON Object] --> Level1[BackendsConfigSchema<br/>Validation]

    Level1 --> CheckStructure{Has mcpServers<br/>property?}

    CheckStructure -->|No| Fail1[Validation Failed:<br/>Missing mcpServers]
    CheckStructure -->|Yes| IsRecord{mcpServers is<br/>Record type?}

    IsRecord -->|No| Fail2[Validation Failed:<br/>Invalid structure]
    IsRecord -->|Yes| IterateServers[Iterate over each<br/>server entry]

    IterateServers --> ServerValidation[ServerConfigSchema<br/>Validation per entry]

    ServerValidation --> ValidateCommand{command<br/>is string?}
    ValidateCommand -->|No| Fail3[Validation Failed:<br/>Invalid command]
    ValidateCommand -->|Yes| ValidateArgs{args is<br/>string[] or<br/>undefined?}

    ValidateArgs -->|No| Fail4[Validation Failed:<br/>Invalid args]
    ValidateArgs -->|Yes| ValidateEnv{env is<br/>Record string, string<br/>or undefined?}

    ValidateEnv -->|No| Fail5[Validation Failed:<br/>Invalid env]
    ValidateEnv -->|Yes| ValidateDisabled{disabled is<br/>boolean or<br/>undefined?}

    ValidateDisabled -->|No| Fail6[Validation Failed:<br/>Invalid disabled]
    ValidateDisabled -->|Yes| ValidateDesc{description is<br/>string or<br/>undefined?}

    ValidateDesc -->|No| Fail7[Validation Failed:<br/>Invalid description]
    ValidateDesc -->|Yes| ValidateTags{tags is<br/>string[] or<br/>undefined?}

    ValidateTags -->|No| Fail8[Validation Failed:<br/>Invalid tags]
    ValidateTags -->|Yes| ValidateType{type is<br/>string or<br/>undefined?}

    ValidateType -->|No| Fail9[Validation Failed:<br/>Invalid type]
    ValidateType -->|Yes| ServerValid[Server config valid]

    ServerValid --> MoreServers{More servers<br/>to validate?}
    MoreServers -->|Yes| IterateServers
    MoreServers -->|No| AllValid[All servers valid]

    AllValid --> Success[Return validated<br/>config object]

    Fail1 --> FailEnd[Throw ConfigValidationError]
    Fail2 --> FailEnd
    Fail3 --> FailEnd
    Fail4 --> FailEnd
    Fail5 --> FailEnd
    Fail6 --> FailEnd
    Fail7 --> FailEnd
    Fail8 --> FailEnd
    Fail9 --> FailEnd

    style Input fill:#e1e5ff
    style Success fill:#e1f5e1
    style FailEnd fill:#ffe1e1
```

## Zod Schema Structure

```mermaid
classDiagram
    class BackendsConfigSchema {
        +Record<string, ServerConfigSchema> mcpServers
    }

    class ServerConfigSchema {
        +string command
        +string? type
        +string[]? args
        +Record<string,string>? env
        +boolean? disabled
        +string? description
        +string[]? tags
    }

    class ValidatedConfig {
        +Record<string, ServerConfig> mcpServers
    }

    class ServerConfig {
        +string name
        +string? command
        +string[]? args
        +string? type
        +docker? object
        +Record<string,string>? env
    }

    class ServerConfigWithMeta {
        +string name
        +string? command
        +string[]? args
        +string? type
        +docker? object
        +Record<string,string>? env
        +string? description
        +string[]? tags
    }

    BackendsConfigSchema --> ServerConfigSchema : validates each entry
    BackendsConfigSchema ..> ValidatedConfig : produces
    ValidatedConfig --> ServerConfig : contains
    ServerConfig <|-- ServerConfigWithMeta : extends

    note for ServerConfigSchema "Zod Schema\n- Optional fields use .optional()\n- Records use z.record()\n- Arrays use z.array()"
    note for ServerConfig "TypeScript Interface\n- Runtime type after validation\n- Used by pool/connections"
```

## Manifest Structure and Caching

```mermaid
flowchart TD
    subgraph Input [Configuration Input]
        ConfigFile[servers.json]
        RawConfig[Raw JSON Config]
    end

    subgraph Validation [Validation Layer]
        Zod[Zod Schema Validation]
        ValidatedData[Validated mcpServers<br/>Record]
    end

    subgraph ManifestGen [Manifest Generation]
        BuildFull[Build ServerManifest]
        ExtractMeta[Extract metadata fields:<br/>- description<br/>- tags]
        CreateEntries[Create ServerManifestEntry[]<br/>for listing]
    end

    subgraph Cache [In-Memory Cache]
        CachedManifest[cachedManifest:<br/>ServerManifest | null]
        FullConfigs[servers:<br/>Record string, ServerConfigWithMeta]
    end

    subgraph API [Public API]
        GetConfig[getServerConfig serverId:<br/>Returns ServerConfig?]
        ListServers[listServers:<br/>Returns ServerManifestEntry[]]
        ClearCache[clearCache:<br/>Invalidates cache]
    end

    ConfigFile --> RawConfig
    RawConfig --> Zod
    Zod --> ValidatedData
    ValidatedData --> BuildFull
    BuildFull --> ExtractMeta
    ExtractMeta --> CreateEntries

    BuildFull --> CachedManifest
    CachedManifest --> FullConfigs

    FullConfigs --> GetConfig
    FullConfigs --> ListServers
    CachedManifest --> ClearCache

    style ConfigFile fill:#f9f9f9
    style CachedManifest fill:#fff4e1
    style GetConfig fill:#e1f5e1
    style ListServers fill:#e1f5e1
    style ClearCache fill:#ffe1e1
```

## ServerManifest Data Model

```mermaid
classDiagram
    class ServerManifest {
        +Record<string, ServerConfigWithMeta> servers
    }

    class ServerConfigWithMeta {
        +string name
        +string command
        +string[]? args
        +string? type
        +Record<string,string>? env
        +boolean? disabled
        +string? description
        +string[]? tags
    }

    class ServerManifestEntry {
        +string name
        +string? description
        +string[]? tags
    }

    class GenerateManifestFunction {
        +generateManifest(configs) ServerManifestEntry[]
    }

    ServerManifest --> ServerConfigWithMeta : contains configs
    GenerateManifestFunction ..> ServerConfigWithMeta : reads from
    GenerateManifestFunction ..> ServerManifestEntry : produces

    note for ServerManifest "Full manifest\nCached in memory\nContains all server configs"

    note for ServerManifestEntry "Lightweight listing\nOnly name + metadata\nNo execution details"
```

## Configuration Retrieval Flow

```mermaid
sequenceDiagram
    participant Client as Client Code
    participant API as Registry API
    participant Cache as cachedManifest
    participant Gen as generateManifest

    rect rgb(230, 245, 230)
        Note over Client,Gen: Scenario 1: Get Specific Server Config
        Client->>API: getServerConfig("filesystem")
        API->>Cache: Check cachedManifest
        alt Cache empty
            Cache-->>API: null
            API-->>Client: undefined
        else Cache exists
            Cache-->>API: servers["filesystem"]
            API-->>Client: ServerConfig object
        end
    end

    rect rgb(230, 240, 255)
        Note over Client,Gen: Scenario 2: List All Servers
        Client->>API: listServers()
        API->>Cache: Check cachedManifest
        alt Cache empty
            Cache-->>API: null
            API-->>Client: [] empty array
        else Cache exists
            Cache-->>API: servers Record
            API->>Gen: generateManifest(servers)
            Gen->>Gen: Extract name, description, tags
            Gen->>Gen: Filter disabled if needed
            Gen-->>API: ServerManifestEntry[]
            API-->>Client: Array of entries
        end
    end

    rect rgb(255, 240, 230)
        Note over Client,Gen: Scenario 3: Clear Cache
        Client->>API: clearCache()
        API->>Cache: Set to null
        Cache-->>API: Cleared
        API-->>Client: void
    end
```

## Error Handling System

```mermaid
flowchart TD
    Start([Configuration Load]) --> TryLoad{Try load<br/>config file}

    TryLoad -->|File not found| ErrFileNotFound
    TryLoad -->|Permission denied| ErrFileNotFound
    TryLoad -->|Success| TryParse{Try parse<br/>JSON}

    TryParse -->|Syntax error| ErrParse
    TryParse -->|Invalid encoding| ErrParse
    TryParse -->|Success| TryValidate{Zod schema<br/>validation}

    TryValidate -->|Schema mismatch| ErrValidation
    TryValidate -->|Type error| ErrValidation
    TryValidate -->|Missing required| ErrValidation
    TryValidate -->|Success| CheckServers{Iterate<br/>servers}

    CheckServers --> ServerLookup{Server lookup<br/>in manifest}

    ServerLookup -->|Not found| ErrServerNotFound
    ServerLookup -->|Found| Success

    subgraph ErrorTypes [Error Classes]
        ErrFileNotFound[ConfigNotFoundError<br/>---<br/>message: Config file not found: path<br/>name: ConfigNotFoundError]

        ErrParse[ConfigParseError<br/>---<br/>message: Failed to parse config: details<br/>name: ConfigParseError]

        ErrValidation[ConfigValidationError<br/>---<br/>message: Config validation failed: details<br/>name: ConfigValidationError]

        ErrServerNotFound[InvalidServerError<br/>---<br/>message: Server not found: serverId<br/>name: InvalidServerError]
    end

    Success([Configuration Ready])

    style Start fill:#e1f5e1
    style Success fill:#e1f5e1
    style ErrFileNotFound fill:#ffe1e1
    style ErrParse fill:#ffe1e1
    style ErrValidation fill:#ffe1e1
    style ErrServerNotFound fill:#ffe1e1
```

## Complete Error Hierarchy

```mermaid
classDiagram
    class Error {
        <<JavaScript>>
        +string message
        +string name
        +string? stack
    }

    class ConfigNotFoundError {
        +constructor(path: string)
        +string message
        +string name = "ConfigNotFoundError"
    }

    class ConfigParseError {
        +constructor(message: string)
        +string message
        +string name = "ConfigParseError"
    }

    class ConfigValidationError {
        +constructor(message: string)
        +string message
        +string name = "ConfigValidationError"
    }

    class InvalidServerError {
        +constructor(serverId: string)
        +string message
        +string name = "InvalidServerError"
    }

    Error <|-- ConfigNotFoundError
    Error <|-- ConfigParseError
    Error <|-- ConfigValidationError
    Error <|-- InvalidServerError

    note for ConfigNotFoundError "Thrown when:\n- File doesn't exist\n- File is inaccessible\n- Permission denied"

    note for ConfigParseError "Thrown when:\n- Invalid JSON syntax\n- Encoding errors\n- Malformed data"

    note for ConfigValidationError "Thrown when:\n- Schema mismatch\n- Type errors\n- Missing required fields\n- Invalid field values"

    note for InvalidServerError "Thrown when:\n- Server ID not in manifest\n- Server lookup fails\n- Note: Not in loader.ts,\n  used by pool/connections"
```

## Configuration File Format

```mermaid
graph TD
    subgraph JSONStructure [servers.json Structure]
        Root[Root Object]
        MCPServers[mcpServers: object]

        Server1["'filesystem': object"]
        Server2["'github': object"]
        Server3["'docker-example': object"]

        FS_Command[command: 'npx']
        FS_Args["args: ['-y', '@modelcontextprotocol/server-filesystem']"]
        FS_Env[env: object]
        FS_Desc["description: 'File system access'"]
        FS_Tags["tags: ['filesystem', 'local']"]

        GH_Command[command: 'npx']
        GH_Args["args: ['-y', '@modelcontextprotocol/server-github']"]
        GH_Env["env: {GITHUB_TOKEN: '...'}"]
        GH_Disabled[disabled: true]

        Docker_Command[command: 'docker']
        Docker_Type[type: 'stdio']
        Docker_Args["args: ['run', '-i', 'image:tag']"]
    end

    Root --> MCPServers
    MCPServers --> Server1
    MCPServers --> Server2
    MCPServers --> Server3

    Server1 --> FS_Command
    Server1 --> FS_Args
    Server1 --> FS_Env
    Server1 --> FS_Desc
    Server1 --> FS_Tags

    Server2 --> GH_Command
    Server2 --> GH_Args
    Server2 --> GH_Env
    Server2 --> GH_Disabled

    Server3 --> Docker_Command
    Server3 --> Docker_Type
    Server3 --> Docker_Args

    style Root fill:#f9f9f9
    style MCPServers fill:#e1e5ff
    style Server1 fill:#e1f5e1
    style Server2 fill:#fff4e1
    style Server3 fill:#ffe1e1
```

## Registry Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Uninitialized: Process starts

    Uninitialized --> Loading: loadServerManifest() called

    Loading --> ValidatingFile: Read file
    ValidatingFile --> ParsingJSON: File read OK
    ValidatingFile --> Error: File not found

    ParsingJSON --> ValidatingSchema: JSON parsed
    ParsingJSON --> Error: Parse error

    ValidatingSchema --> BuildingManifest: Schema valid
    ValidatingSchema --> Error: Validation failed

    BuildingManifest --> Cached: Manifest built

    Cached --> Serving: Ready for queries

    Serving --> Serving: getServerConfig()
    Serving --> Serving: listServers()
    Serving --> Uninitialized: clearCache()

    Error --> [*]: Throw exception

    note right of Uninitialized
        cachedManifest = null
        No config loaded
    end note

    note right of Cached
        cachedManifest populated
        In-memory cache active
    end note

    note right of Serving
        Fast lookups
        No I/O on queries
    end note

    note right of Error
        ConfigNotFoundError
        ConfigParseError
        ConfigValidationError
    end note
```

## Full System Integration

```mermaid
flowchart TB
    subgraph External [External Sources]
        EnvVar[SERVERS_CONFIG<br/>environment variable]
        ConfigFile[servers.json<br/>on filesystem]
    end

    subgraph Loader [Registry Loader]
        GetPath[getConfigPath]
        ReadFile[fs.readFileSync]
        ParseJSON[JSON.parse]
        ValidateZod[Zod validation]
        BuildManifest[Build manifest]
        StoreCache[Store in cachedManifest]
    end

    subgraph Cache [In-Memory Cache]
        GlobalCache[cachedManifest:<br/>ServerManifest | null]
    end

    subgraph API [Public API Functions]
        LoadManifest[loadServerManifest]
        GetConfig[getServerConfig]
        ListServers[listServers]
        ClearCache[clearCache]
    end

    subgraph Consumers [System Consumers]
        ServerPool[ServerPool]
        MetaTools[Meta-tools<br/>list_servers, call_tool]
        TestSuite[Test Suite]
    end

    EnvVar -.->|provides path| GetPath
    ConfigFile -.->|read by| ReadFile

    GetPath --> ReadFile
    ReadFile --> ParseJSON
    ParseJSON --> ValidateZod
    ValidateZod --> BuildManifest
    BuildManifest --> StoreCache

    StoreCache --> GlobalCache

    GlobalCache <--> LoadManifest
    GlobalCache <--> GetConfig
    GlobalCache <--> ListServers
    GlobalCache <--> ClearCache

    LoadManifest --> ServerPool
    GetConfig --> ServerPool
    ListServers --> MetaTools
    ClearCache --> TestSuite

    style EnvVar fill:#f9f9f9
    style ConfigFile fill:#f9f9f9
    style GlobalCache fill:#fff4e1
    style ServerPool fill:#e1f5e1
    style MetaTools fill:#e1f5e1
```

## Key Implementation Details

### Validation Schema Definition

```typescript
// ServerConfigSchema - validates individual server entries
const ServerConfigSchema = z.object({
  type: z.string().optional(),           // "stdio", "docker", etc.
  command: z.string(),                    // Required: executable command
  args: z.array(z.string()).optional(),  // Command arguments
  env: z.record(z.string()).optional(),  // Environment variables
  disabled: z.boolean().optional(),      // Skip this server
  description: z.string().optional(),    // Human-readable description
  tags: z.array(z.string()).optional(),  // Categorization tags
});

// BackendsConfigSchema - validates complete config file
const BackendsConfigSchema = z.object({
  mcpServers: z.record(ServerConfigSchema), // Map of server ID to config
});
```

### Cache Management

- **Single global cache**: `cachedManifest` variable stores the manifest
- **Lazy loading**: Cache only populated when `loadServerManifest()` is called
- **No TTL**: Cache persists for process lifetime unless explicitly cleared
- **Synchronous access**: No async needed after initial load

### Error Recovery

1. **ConfigNotFoundError**: Unrecoverable - requires valid config file
2. **ConfigParseError**: Unrecoverable - requires valid JSON syntax
3. **ConfigValidationError**: Unrecoverable - requires schema-compliant data
4. No automatic retry or fallback mechanisms

### Performance Characteristics

- **Initial load**: O(n) where n = number of servers (file I/O + validation)
- **getServerConfig**: O(1) hash lookup in cached Record
- **listServers**: O(n) iteration over servers to extract metadata
- **Memory usage**: Entire config kept in memory (typically < 100KB)

## Example Configuration

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
      "description": "Local filesystem access",
      "tags": ["filesystem", "local", "read-write"]
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "ghp_xxxxxxxxxxxx"
      },
      "description": "GitHub repository access",
      "tags": ["github", "vcs", "remote"]
    },
    "experimental-server": {
      "command": "uvx",
      "args": ["my-experimental-mcp-server"],
      "disabled": true,
      "description": "Disabled experimental server",
      "tags": ["experimental", "disabled"]
    }
  }
}
```

## Summary

The registry and configuration system provides:

1. **Declarative configuration** via JSON files
2. **Strong typing** through Zod schema validation
3. **In-memory caching** for fast lookups
4. **Clear error handling** with specific error types
5. **Metadata support** for server discovery and filtering
6. **Disabled server handling** to skip servers without removing from config

This design ensures configuration is validated once at startup, then served quickly from memory with type safety guarantees.
