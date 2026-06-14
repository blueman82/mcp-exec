# mcp-exec

Sandboxed code execution for AI tools, with typed access to all your MCP servers. A single, local, STDIO MCP entry point that wraps your existing backend MCP servers for token-efficient tool discovery and isolated code execution.

> Private/local-only. This project is not published to any package registry. Build it from source and run it over STDIO from your AI tool's config.

## Monorepo Structure

This project is organized as a monorepo with the following packages:

```
packages/
├── core/           # mcp-exec-core - Shared utilities, types, pool, and registry
└── mcp-exec/       # mcp-exec - Sandboxed code execution with typed wrappers

extension/          # VS Code/Cursor extension (servers.json management UI)
```

| Package | Description |
|---------|-------------|
| [`mcp-exec-core`](./packages/core/README.md) | Core utilities: types, connection pool, registry, tool cache |
| [`mcp-exec`](./packages/mcp-exec/README.md) | Sandboxed code execution with MCP tool access via typed wrappers |

## Problem

When an AI agent connects to many MCP servers, it loads all tool schemas upfront — potentially 100+ tools consuming significant context tokens before any work begins.

## Solution

mcp-exec exposes only 3 tools to the AI:

| Tool | Purpose |
|------|---------|
| `list_available_mcp_servers` | List available backend servers (lightweight, no schemas) |
| `get_mcp_tool_schema` | Fetch schema for a specific tool on-demand |
| `execute_code_with_wrappers` | Run code in a sandbox with typed access to any MCP tool |

Backend servers are spawned lazily on first access and managed via a connection pool.

## Features

- **Lazy Loading**: Servers spawn only when first accessed
- **Two-Tier Tool Discovery**: Fetch summaries first (~100 tokens), then specific schemas on-demand
- **Connection Pool**: LRU eviction (max 20 connections) with idle cleanup (5 min)
- **Multi-Transport**: Supports Node, Docker, and uvx/npx spawn types, plus header-authed HTTP/SSE backends
- **Tool Caching**: Tool definitions cached per-server for session duration
- **VS Code Extension**: Visual UI for managing `servers.json` and configuring AI tools
- **Sandboxed Execution**: Execute code in OS-isolated environments (sandbox-exec on macOS, bubblewrap on Linux) with MCP tool access over an inherited file-descriptor pipe

## Quick Start

### Build from source

```bash
npm install
npm run build
```

This builds `packages/core` then `packages/mcp-exec`. The runnable server lands at `packages/mcp-exec/dist/index.js`.

### Create `~/.mcp-exec/servers.json`

List every backend MCP server you want mcp-exec to manage. Standard MCP config format:

```json
{
  "mcpServers": {
    "everything": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-everything"]
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"]
    }
  }
}
```

### Point your AI tool at the local build

Replace your AI tool's `mcpServers` with a single entry that runs mcp-exec over STDIO:

```json
{
  "mcpServers": {
    "mcp-exec": {
      "command": "node",
      "args": ["/path/to/mcp-exec/packages/mcp-exec/dist/index.js"],
      "env": {
        "SERVERS_CONFIG": "$HOME/.mcp-exec/servers.json"
      }
    }
  }
}
```

Config locations for common tools:

| Tool | Config Location |
|------|-----------------|
| Claude Code | `~/.claude.json` |
| Cursor | `~/.cursor/mcp.json` |
| VS Code | `~/.vscode/mcp.json` |

Restart your AI tool to load the new configuration.

## Configuration

### servers.json

All MCP servers are configured in `~/.mcp-exec/servers.json` (path overridable via `SERVERS_CONFIG`). STDIO backends use `command`/`args`/`env`; HTTP/SSE backends use a `url`.

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"]
    },
    "remote-http": {
      "url": "https://mcp.example.com/mcp",
      "headers": {
        "Authorization": "Bearer ${MY_API_TOKEN}"
      },
      "timeout": 120000
    }
  }
}
```

> **Note**: The optional `timeout` field sets a per-server timeout in milliseconds. It applies to both tool execution calls (overriding `MCP_DEFAULT_TIMEOUT`) and wrapper-generation tools-fetch. Default is 15s for tools-fetch when unset; raise it for slow backends with many tools.

### Env-var → HTTP header injection (backend auth)

For HTTP/SSE backends, any `${VAR_NAME}` reference inside a `headers` value is resolved from the process environment at connection time. This keeps tokens out of the committed config — set the named variable in your environment (or in a `.env` file referenced from your launcher) and reference it with `${...}`:

```json
{
  "mcpServers": {
    "remote-http": {
      "url": "https://mcp.example.com/mcp",
      "headers": { "Authorization": "Bearer ${MY_API_TOKEN}" }
    }
  }
}
```

If a referenced variable is undefined, connection fails fast with a clear error naming the missing variable.

## Usage

Once configured, the AI sees only 3 tools instead of all backend tools:

```
# AI lists available servers
list_available_mcp_servers()
→ [{name: "filesystem", description: "Filesystem access"}, ...]

# AI fetches a specific tool schema on-demand
get_mcp_tool_schema({server_name: "filesystem", tool_name: "read_file"})
→ {name: "read_file", inputSchema: {...}}

# AI executes code with typed MCP wrappers
execute_code_with_wrappers({
  code: 'const out = await mcp.filesystem.readFile({ path: "/tmp/x" }); console.log(out)',
  wrappers: ["filesystem"]
})
→ {output: [...]}
```

### Two-Tier Lazy Loading

See [Token Economics](docs/diagrams/token-economics.md) for analysis of the token savings across different workflow patterns.

## Development

### Monorepo Commands

```bash
# Install all dependencies (run from repo root — workspaces hoist to root node_modules)
npm install

# Build all packages
npm run build

# Run all tests
npx vitest run

# Type check a package
npx tsc --noEmit -p packages/core/tsconfig.json
npx tsc --noEmit -p packages/mcp-exec/tsconfig.json

# Clean all build artifacts
npm run clean --workspaces
```

### Package-Specific Development

```bash
# Core package
cd packages/core
npm run build
npm run dev  # watch mode

# mcp-exec package
cd packages/mcp-exec
npm run build
npm test
npm run test:integration  # full integration tests
```

### Testing

```bash
# Run the full suite
npx vitest run

# Run real MCP integration tests (spawn real backends)
RUN_REAL_MCP_TESTS=true npx vitest run
```

## Architecture

For detailed architecture documentation with diagrams, see:
- **[Architecture Guide](docs/ARCHITECTURE.md)** — narrative guide with all concepts explained
- **[Diagram Index](docs/diagrams/README.md)** — visual diagrams organized by topic

### Monorepo Package Structure

```
packages/
├── core/                    # mcp-exec-core - Shared utilities
│   └── src/
│       ├── types/           # TypeScript interfaces (connection, server-config, tool-definition)
│       ├── registry/        # Server manifest loading (loader.ts, manifest.ts)
│       ├── pool/            # Connection pool with LRU eviction
│       │   ├── server-pool.ts
│       │   ├── connection.ts
│       │   └── stdio-transport.ts
│       ├── auth/            # Generic env-var → HTTP-header resolution (backend-auth.ts)
│       └── tools/           # Tool caching utilities (tool-cache.ts)
│
└── mcp-exec/                # mcp-exec - Code execution
    └── src/
        ├── index.ts         # Entry point and public API
        ├── server.ts        # MCP server for execute_code tools
        ├── sandbox/         # Sandbox executor with OS-level isolation
        ├── bridge/          # fd-pipe bridge for MCP access from the sandbox
        ├── codegen/         # Typed wrapper generator
        ├── types/           # TypeScript interfaces
        └── tools/           # Tool implementations
            ├── list-servers.ts
            ├── get-tool-schema.ts
            └── execute-with-wrappers.ts
```

## Configuration Options

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `SERVERS_CONFIG` | `~/.mcp-exec/servers.json` | Path to backends configuration |
| `MAX_CONNECTIONS` | `20` | Maximum concurrent server connections |
| `IDLE_TIMEOUT_MS` | `300000` | Idle connection cleanup timeout (5 min) |
| `MCP_DEFAULT_TIMEOUT` | none | Global timeout for MCP tool calls (ms). Per-server `timeout` takes precedence. |
