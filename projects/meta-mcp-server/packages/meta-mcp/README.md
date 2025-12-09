# @meta-mcp/server

Meta MCP server that wraps multiple backend MCP servers, exposing only 3 meta-tools to reduce context token consumption.

## Installation

```bash
npm install -g @meta-mcp/server
```

Or use via npx:

```bash
npx @meta-mcp/server
```

## Overview

When AI tools (Claude, Cursor, etc.) connect to many MCP servers, they load all tool schemas upfront - potentially 100+ tools consuming significant context tokens before any work begins.

Meta-MCP solves this by exposing only 3 tools:

| Tool | Purpose |
|------|---------|
| `list_servers` | List available backend servers (lightweight, no schemas) |
| `get_server_tools` | Fetch tools from a server with two-tier lazy loading |
| `call_tool` | Execute a tool on a backend server |

## Features

- **Lazy Loading**: Servers spawn only when first accessed
- **Two-Tier Tool Discovery**: Fetch summaries first (~100 tokens), then specific schemas on-demand
- **Connection Pool**: LRU eviction (max 20 connections) with idle cleanup (5 min)
- **Tool Caching**: Tool definitions cached per-server for session duration

## Quick Start

### 1. Configure Your AI Tool

Add meta-mcp to your AI tool's config file:

**Claude** (`~/.claude.json`):
```json
{
  "mcpServers": {
    "meta-mcp": {
      "command": "npx",
      "args": ["-y", "@meta-mcp/server"],
      "env": {
        "SERVERS_CONFIG": "~/.meta-mcp/servers.json"
      }
    }
  }
}
```

**Cursor** (`~/.cursor/mcp.json`):
```json
{
  "mcpServers": {
    "meta-mcp": {
      "command": "npx",
      "args": ["-y", "@meta-mcp/server"],
      "env": {
        "SERVERS_CONFIG": "~/.meta-mcp/servers.json"
      }
    }
  }
}
```

### 2. Configure Backend Servers

Create `~/.meta-mcp/servers.json`:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/user"],
      "description": "File system access"
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "your-token"
      },
      "description": "GitHub integration"
    }
  }
}
```

### 3. Restart Your AI Tool

Restart Claude/Cursor to load the new configuration.

## API Reference

### list_servers

List all available backend MCP servers.

```typescript
list_servers(filter?: string): ServerInfo[]
```

**Parameters:**
- `filter` (optional): Filter servers by name pattern

**Returns:**
```typescript
[
  { name: "filesystem", description: "File system access" },
  { name: "github", description: "GitHub integration" }
]
```

### get_server_tools

Fetch tools from a backend server with two-tier lazy loading.

```typescript
get_server_tools(options: {
  server_name: string;
  summary_only?: boolean;  // Only fetch names/descriptions (~100 tokens)
  tools?: string[];        // Fetch specific tool schemas
}): ToolDefinition[]
```

**Examples:**

```typescript
// Get all tool summaries (lightweight)
get_server_tools({ server_name: "filesystem", summary_only: true })
// => [{ name: "read_file", description: "..." }, ...]

// Get specific tool schemas
get_server_tools({ server_name: "filesystem", tools: ["read_file", "write_file"] })
// => [{ name: "read_file", inputSchema: {...} }, ...]

// Get all tools with full schemas (backward compatible)
get_server_tools({ server_name: "filesystem" })
// => [{ name: "read_file", inputSchema: {...} }, ...]
```

### call_tool

Execute a tool on a backend server.

```typescript
call_tool(options: {
  server_name: string;
  tool_name: string;
  arguments?: Record<string, unknown>;
}): CallToolResult
```

**Example:**

```typescript
call_tool({
  server_name: "filesystem",
  tool_name: "read_file",
  arguments: { path: "/tmp/test.txt" }
})
// => { content: [{ type: "text", text: "file contents..." }] }
```

## Programmatic Usage

```typescript
import { createServer } from '@meta-mcp/server';
import { ServerPool, ToolCache, createConnection, getServerConfig } from '@meta-mcp/core';

// Create connection factory
const connectionFactory = async (serverId: string) => {
  const config = getServerConfig(serverId);
  if (!config) throw new Error(`Server not found: ${serverId}`);
  return createConnection(config);
};

// Initialize components
const pool = new ServerPool(connectionFactory);
const toolCache = new ToolCache();

// Create server
const { server, shutdown } = createServer(pool, toolCache);

// Connect to transport
await server.connect(transport);

// Graceful shutdown
await shutdown();
await server.close();
```

## CLI Usage

```bash
# Start the server (stdio transport)
meta-mcp-server

# Show version
meta-mcp-server --version

# Show help
meta-mcp-server --help
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVERS_CONFIG` | `~/.meta-mcp/servers.json` | Path to backend servers configuration |
| `MAX_CONNECTIONS` | `20` | Maximum concurrent server connections |
| `IDLE_TIMEOUT_MS` | `300000` | Idle connection cleanup timeout (5 min) |
| `MCP_DEFAULT_TIMEOUT` | none | Global timeout for MCP tool calls (ms). Per-server `timeout` takes precedence. |

## Token Optimization

Meta-MCP provides 87-91% token savings through two-tier lazy loading:

1. **Discovery Phase**: `list_servers()` returns only server names/descriptions
2. **Summary Phase**: `get_server_tools({ summary_only: true })` returns tool names/descriptions (~100 tokens for 25 tools)
3. **Schema Phase**: `get_server_tools({ tools: ["specific_tool"] })` fetches only needed schemas
4. **Execution Phase**: `call_tool()` executes with full context only when needed

## License

MIT
