# mcp-exec

Sandboxed code execution for AI tools, with typed access to all your MCP servers. A single MCP entry point that wraps your existing backend servers for token-efficient tool discovery and isolated code execution.

## Monorepo Structure

This project is organized as a monorepo with the following packages:

```
packages/
├── core/           # @justanothermldude/mcp-exec-oss-core - Shared utilities, types, pool, and registry
└── mcp-exec/       # @justanothermldude/mcp-exec-oss - Sandboxed code execution with typed wrappers

extension/          # VS Code/Cursor extension (VSIX)
```

| Package | Description | Install |
|---------|-------------|---------|
| [`@justanothermldude/mcp-exec-oss-core`](./packages/core/README.md) | Core utilities: types, connection pool, registry, tool cache | `npm i @justanothermldude/mcp-exec-oss-core` |
| [`@justanothermldude/mcp-exec-oss`](./packages/mcp-exec/README.md) | Sandboxed code execution with MCP tool access via typed wrappers | `npm i -g @justanothermldude/mcp-exec-oss` |

## Problem

When an AI client connects to many MCP servers, it loads all tool schemas upfront - potentially 100+ tools consuming significant context tokens before any work begins.

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
- **Multi-Transport**: Supports Node, Docker, and uvx/npx spawn types
- **Tool Caching**: Tool definitions cached per-server for session duration
- **VS Code Extension**: Visual UI for managing servers and configuring AI tools
- **Sandboxed Execution**: Execute code in isolated environments with MCP tool access

## Quick Start

### Option 2: npm

**1. Install mcp-exec:**

```bash
npm install -g @justanothermldude/mcp-exec-oss
```

**2. Create `~/.meta-mcp/servers.json`:**

```bash
mkdir -p ~/.meta-mcp
```

Open your AI tool's current `mcp.json` and copy all your existing `mcpServers` entries into `~/.meta-mcp/servers.json`:

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "your-token"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-filesystem", "/path/to/allowed/dir"]
    }
  }
}
```

**3. Replace your AI tool config with only mcp-exec:**

Remove all existing entries from your AI tool's `mcp.json` and replace with just this:

```json
{
  "mcpServers": {
    "mcp-exec": {
      "command": "npx",
      "args": ["-y", "@justanothermldude/mcp-exec-oss"],
      "env": {
        "SERVERS_CONFIG": "$HOME/.meta-mcp/servers.json"
      }
    }
  }
}
```

**4. Restart your AI tool.**

### Option 2b: Build from Source

```bash
npm install
npm run build
```

## Configuration

### servers.json

All MCP servers are configured in `~/.meta-mcp/servers.json`:

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "your-token"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-filesystem", "/path/to/allowed/dir"]
    }
  }
}
```

> **Note**: The optional `timeout` field sets per-server timeout in milliseconds. This overrides `MCP_DEFAULT_TIMEOUT`.

### AI Tool Configuration

Add mcp-exec to your AI tool's config file:

**Claude** (`~/.claude.json`):
```json
{
  "mcpServers": {
    "mcp-exec": {
      "command": "npx",
      "args": ["-y", "@justanothermldude/mcp-exec-oss"],
      "env": {
        "SERVERS_CONFIG": "$HOME/.meta-mcp/servers.json"
      }
    }
  }
}
```

**Using local build** (instead of npx):
```json
{
  "mcpServers": {
    "mcp-exec": {
      "command": "node",
      "args": ["/path/to/meta-mcp-server/packages/mcp-exec/dist/index.js"],
      "env": {
        "SERVERS_CONFIG": "$HOME/.meta-mcp/servers.json"
      }
    }
  }
}
```

### Restart your AI tool

Restart your AI tool to load the new configuration.

## Usage

Once configured, the AI will see only 3 tools instead of all backend tools:

```
# AI lists available servers
list_available_mcp_servers()
→ [{name: "corp-jira", description: "JIRA integration"}, ...]

# AI fetches a specific tool schema on-demand
get_mcp_tool_schema({server_name: "corp-jira", tool_name: "search_issues"})
→ {name: "search_issues", inputSchema: {...}}

# AI executes code with typed MCP wrappers
execute_code_with_wrappers({
  code: 'const issues = await mcp.corpJira.searchIssues({ jql: "..." }); console.log(issues)',
  wrappers: ["corp-jira"]
})
→ {output: [...]}
```

### Two-Tier Lazy Loading

See [Token Economics](docs/diagrams/token-economics.md) for detailed analysis of 87-91% token savings across different workflow patterns.

## Development

### Monorepo Commands

```bash
# Install all dependencies
npm install

# Build all packages
npm run build --workspaces

# Build specific package
npm run build -w @justanothermldude/mcp-exec-oss-core

# Run all tests
npm test --workspaces

# Run tests for specific package
npm test -w @justanothermldude/mcp-exec-oss

# Type check all packages
npx tsc --noEmit --workspaces

# Clean all build artifacts
npm run clean --workspaces
```

### Package-Specific Development

```bash
# Core package
cd packages/core
npm run build
npm run dev  # watch mode

# MCP-Exec package
cd packages/mcp-exec
npm run build
npm test
npm run test:integration  # Full integration tests
```

### Testing

```bash
# Run all tests
npm test --workspaces

# Run with vitest (full suite)
npx vitest run

# Run real MCP integration tests
RUN_REAL_MCP_TESTS=true npm test -w @meta-mcp/exec
```

## Architecture

For detailed architecture documentation with diagrams, see:
- **[Architecture Guide](docs/ARCHITECTURE.md)** - Complete narrative guide with all concepts explained
- **[Diagram Index](docs/diagrams/README.md)** - Visual diagrams organized by topic
  - [Token Economics](docs/diagrams/token-economics.md) - 87-91% savings, ROI analysis

### Monorepo Package Structure

```
packages/
├── core/                    # @justanothermldude/mcp-exec-oss-core - Shared utilities
│   └── src/
│       ├── types/           # TypeScript interfaces (connection, server-config, tool-definition)
│       ├── registry/        # Server manifest loading (loader.ts, manifest.ts)
│       ├── pool/            # Connection pool with LRU eviction
│       │   ├── server-pool.ts
│       │   ├── connection.ts
│       │   └── stdio-transport.ts
│       ├── auth/            # Backend authentication
│       │   ├── backend-auth.ts
│       │   ├── cursor-token-reader.ts
│       │   ├── gateway-client.ts
│       │   ├── pat-matcher.ts
│       │   └── index.ts
│       ├── process/         # Process lifecycle
│       │   └── cleanup.ts
│       └── tools/           # Tool caching utilities (tool-cache.ts)
│
└── mcp-exec/                # @justanothermldude/mcp-exec-oss - Code execution
    └── src/
        ├── index.ts         # Entry point and public API
        ├── server.ts        # MCP server for execute_code tools
        ├── sandbox/         # Sandbox executor with OS-level isolation
        ├── bridge/          # HTTP bridge for MCP access
        ├── codegen/         # Typed wrapper generator (wrapper-generator.ts, module-resolver.ts)
        ├── types/           # TypeScript interfaces
        └── tools/           # Tool implementations
            ├── list-servers.ts
            ├── get-tool-schema.ts
            └── execute-with-wrappers.ts
```

## Configuration Options

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `SERVERS_CONFIG` | `~/.meta-mcp/servers.json` | Path to backends configuration |
| `MAX_CONNECTIONS` | `20` | Maximum concurrent server connections |
| `IDLE_TIMEOUT_MS` | `300000` | Idle connection cleanup timeout (5 min) |
| `MCP_DEFAULT_TIMEOUT` | none | Global timeout for MCP tool calls (ms). Per-server `timeout` takes precedence. |

## Test Results

- **341 tests passing** (unit + integration across all packages)
- 48 integration tests skipped by default (require `RUN_REAL_MCP_TESTS=true`)
- Tested with Node, Docker, and uvx/npx spawn types
