# @justanothermldude/mcp-exec-oss-core

Core utilities and shared types for mcp-exec-oss packages.

## Installation

```bash
npm install @justanothermldude/mcp-exec-oss-core
```

## Overview

This package provides the foundational components shared across the meta-mcp ecosystem:

- **Types**: TypeScript interfaces for server configuration, tool definitions, and connections
- **Registry**: Server manifest loading and configuration management
- **Pool**: Connection pooling with LRU eviction for MCP server connections
- **Tools**: Tool caching utilities

## API Reference

### Types

```typescript
import type {
  ServerSpawnConfig,
  ServerConfig,
  ToolSchema,
  ToolDefinition,
  MCPConnection,
} from '@justanothermldude/mcp-exec-oss-core';

// Check transport type
import { isUrlTransport, ConnectionState } from '@justanothermldude/mcp-exec-oss-core';
```

#### ServerConfig

Configuration for an MCP server:

```typescript
interface ServerConfig {
  command: string;        // Command to spawn (e.g., 'npx', 'node')
  args?: string[];        // Command arguments
  env?: Record<string, string>;  // Environment variables
  timeout?: number;       // Per-server timeout in milliseconds (overrides MCP_DEFAULT_TIMEOUT)
}
```

#### ToolDefinition

MCP tool definition with schema:

```typescript
interface ToolDefinition {
  name: string;
  description?: string;
  inputSchema?: {
    type: 'object';
    properties?: Record<string, unknown>;
    required?: string[];
  };
}
```

#### MCPConnection

Connection interface for MCP clients:

```typescript
interface MCPConnection {
  serverId: string;
  state: ConnectionState;
  connect(): Promise<void>;
  disconnect(): Promise<void>;
  isConnected(): boolean;
  getTools(): Promise<ToolDefinition[]>;
  client: {
    callTool(name: string, args: unknown): Promise<CallToolResult>;
  };
}
```

### Registry

Load and manage server configurations from `servers.json`:

```typescript
import {
  loadServerManifest,
  getServerConfig,
  listServers,
  clearCache,
  generateManifest,
} from '@justanothermldude/mcp-exec-oss-core';

// Load manifest from SERVERS_CONFIG env var or default path
const manifest = loadServerManifest();

// Get config for a specific server
const config = getServerConfig('filesystem');

// List all available servers
const servers = listServers();
// => [{ name: 'filesystem', description: '...' }, ...]

// Clear cached manifest
clearCache();
```

#### Error Classes

```typescript
import {
  ConfigNotFoundError,
  ConfigParseError,
  ConfigValidationError,
} from '@justanothermldude/mcp-exec-oss-core';

try {
  const manifest = loadServerManifest();
} catch (error) {
  if (error instanceof ConfigNotFoundError) {
    console.log('Config file not found');
  } else if (error instanceof ConfigParseError) {
    console.log('Invalid JSON in config');
  } else if (error instanceof ConfigValidationError) {
    console.log('Schema validation failed');
  }
}
```

### Pool

Manage MCP server connections with automatic pooling:

```typescript
import {
  ServerPool,
  createConnection,
  closeConnection,
  buildSpawnConfig,
} from '@justanothermldude/mcp-exec-oss-core';

import type {
  ConnectionFactory,
  PoolConfig,
  SpawnConfig,
} from '@justanothermldude/mcp-exec-oss-core';

// Create a connection factory
const connectionFactory: ConnectionFactory = async (serverId: string) => {
  const config = getServerConfig(serverId);
  if (!config) throw new Error(`Server not found: ${serverId}`);
  return createConnection(config);
};

// Create pool with optional config
const pool = new ServerPool(connectionFactory, {
  maxConnections: 20,       // Default: 20
  idleTimeoutMs: 300000,    // Default: 5 minutes
  cleanupIntervalMs: 60000, // Default: 1 minute
});

// Get a connection (creates or reuses)
const connection = await pool.getConnection('filesystem');

// Use the connection
const tools = await connection.getTools();
const result = await connection.client.callTool('read_file', { path: '/tmp/test.txt' });

// Release connection back to pool
pool.releaseConnection('filesystem');

// Shutdown pool and all connections
await pool.shutdown();
```

#### Pool Error Classes

```typescript
import {
  ConnectionError,
  PoolExhaustedError,
  SpawnError,
  TimeoutError,
  UnexpectedExitError,
} from '@justanothermldude/mcp-exec-oss-core';
```

### Tools

Cache tool definitions per server:

```typescript
import { ToolCache } from '@justanothermldude/mcp-exec-oss-core';

const cache = new ToolCache();

// Cache tools for a server
cache.set('filesystem', [
  { name: 'read_file', description: 'Read file contents' },
  { name: 'write_file', description: 'Write file contents' },
]);

// Retrieve cached tools
const tools = cache.get('filesystem');

// Check if server has cached tools
const hasCached = cache.has('filesystem');

// Clear cache for a server
cache.delete('filesystem');

// Clear all cached tools
cache.clear();
```

## Subpath Exports

Import specific modules directly:

```typescript
// Types only
import type { ServerConfig, ToolDefinition } from '@justanothermldude/mcp-exec-oss-core/types';

// Registry only
import { loadServerManifest, getServerConfig } from '@justanothermldude/mcp-exec-oss-core/registry';

// Pool only
import { ServerPool, createConnection } from '@justanothermldude/mcp-exec-oss-core/pool';

// Tools only
import { ToolCache } from '@justanothermldude/mcp-exec-oss-core/tools';
```

## Configuration

The registry loads server configurations from:

1. Path specified in `SERVERS_CONFIG` environment variable
2. Default: `~/.meta-mcp/servers.json`

### servers.json Format

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
      "description": "Filesystem access server"
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "your-token"
      }
    }
  }
}
```

## License

MIT
