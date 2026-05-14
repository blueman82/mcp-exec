# @justanothermldude/mcp-exec-oss

MCP execution utilities for sandboxed TypeScript/JavaScript code execution with OS-level isolation.

## Installation

```bash
npm install @justanothermldude/mcp-exec-oss
```

## Overview

This package provides secure code execution capabilities with:

- **Sandbox Isolation**: OS-level sandboxing via `@anthropic-ai/sandbox-runtime` (sandbox-exec on macOS, bubblewrap on Linux)
- **MCP Bridge**: HTTP bridge allowing sandboxed code to call MCP tools
- **Wrapper Generation**: Auto-generate type-safe TypeScript wrappers for MCP tools

## Quick Start

### Basic Code Execution

```typescript
import { executeCode } from '@justanothermldude/mcp-exec-oss';

const result = await executeCode({
  code: 'console.log("Hello from sandbox!")',
  timeout_ms: 5000,
});

console.log(result.output);  // ['Hello from sandbox!']
console.log(result.durationMs);  // execution time in ms
```

### Using as MCP Server

```bash
# Start the mcp-exec server
npx @justanothermldude/mcp-exec-oss

# Or with specific config
SERVERS_CONFIG=~/.meta-mcp/servers.json npx @justanothermldude/mcp-exec-oss
```

## API Reference

### executeCode

Execute code in a sandboxed environment.

```typescript
import { executeCode } from '@justanothermldude/mcp-exec-oss';

const result = await executeCode({
  code: string;       // TypeScript/JavaScript code to execute
  timeout_ms?: number; // Max execution time (default: 30000)
});

// Result type
interface ExecutionResult {
  output: string[];    // stdout lines
  error?: string;      // stderr content
  durationMs: number;  // execution time
}
```

### SandboxExecutor

Create a custom executor with specific configuration:

```typescript
import { SandboxExecutor, createExecutor } from '@justanothermldude/mcp-exec-oss';

// Using factory function
const executor = createExecutor({
  mcpBridgePort: 4000,
  additionalWritePaths: ['/tmp/my-app'],
  enableLogMonitor: true,
});

// Using class directly
const executor = new SandboxExecutor({
  mcpBridgePort: 4000,
  additionalWritePaths: ['/tmp/my-app'],
});

// Execute code
const result = await executor.execute('console.log(1 + 1)', 5000);

// Check status
executor.checkDependencies();   // true if sandbox-runtime available
executor.isSandboxingEnabled(); // true if OS sandboxing active

// Update config
executor.updateConfig({ mcpBridgePort: 5000 });

// Clean up
await executor.reset();
```

### MCPBridge

HTTP bridge for MCP tool access from sandboxed code:

```typescript
import { MCPBridge } from '@justanothermldude/mcp-exec-oss';
import { ServerPool, createConnection, getServerConfig } from '@justanothermldude/mcp-exec-oss-core';

// Create server pool
const connectionFactory = async (serverId: string) => {
  const config = getServerConfig(serverId);
  if (!config) throw new Error(`Server not found: ${serverId}`);
  return createConnection(config);
};
const pool = new ServerPool(connectionFactory);

// Create and start bridge
const bridge = new MCPBridge(pool, {
  port: 3000,
  host: '127.0.0.1',
});

await bridge.start();

// Bridge endpoints:
// GET  /health - Health check
// POST /call   - Execute MCP tool call

// Check status
bridge.isRunning();  // true
bridge.getPort();    // 3000
bridge.getHost();    // '127.0.0.1'

// Stop bridge
await bridge.stop();
```

### Wrapper Generator

Generate type-safe TypeScript wrappers for MCP tools:

```typescript
import { generateToolWrapper, generateServerModule } from '@justanothermldude/mcp-exec-oss';
import type { ToolDefinition } from '@justanothermldude/mcp-exec-oss-core';

// Generate wrapper for single tool
const tool: ToolDefinition = {
  name: 'read_file',
  description: 'Read contents of a file',
  inputSchema: {
    type: 'object',
    properties: {
      path: { type: 'string', description: 'File path to read' },
    },
    required: ['path'],
  },
};

const wrapper = generateToolWrapper(tool, 'filesystem');
// Generates TypeScript function that calls bridge endpoint

// Generate module for all server tools
const tools: ToolDefinition[] = [/* ... */];
const module = generateServerModule(tools, 'filesystem');
// Generates complete TypeScript module with all tool wrappers
```

**Generated wrapper example:**

```typescript
export interface ReadFileInput {
  /** File path to read */
  path: string;
}

/**
 * Read contents of a file
 * @param input.path - File path to read
 * @returns Promise resolving to tool result
 */
export async function read_file(input: ReadFileInput): Promise<unknown> {
  const response = await fetch('http://localhost:3000/call', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      server_name: 'filesystem',
      tool_name: 'read_file',
      arguments: input,
    }),
  });

  if (!response.ok) {
    throw new Error(`Tool call failed: ${response.statusText}`);
  }

  return response.json();
}
```

### MCP Server

Create the mcp-exec MCP server programmatically:

```typescript
import { createMcpExecServer } from '@justanothermldude/mcp-exec-oss';
import { ServerPool, createConnection, getServerConfig } from '@justanothermldude/mcp-exec-oss-core';

// Create pool
const connectionFactory = async (serverId: string) => {
  const config = getServerConfig(serverId);
  if (!config) throw new Error(`Server not found: ${serverId}`);
  return createConnection(config);
};
const pool = new ServerPool(connectionFactory);

// Create server
const { server, listToolsHandler, callToolHandler, shutdown } = createMcpExecServer(pool);

// List available tools
const tools = await listToolsHandler();
// => { tools: [{ name: 'execute_code_with_wrappers', ... }, ...] }

// Call execute_code_with_wrappers tool
const result = await callToolHandler({
  name: 'execute_code_with_wrappers',
  arguments: {
    code: 'console.log("Hello!")',
    wrappers: [],  // optional: MCP server names to generate typed wrappers for
  },
});

// Graceful shutdown
await shutdown();
```

## Types

```typescript
import type {
  ExecuteCodeInput,
  ExecutionResult,
  SandboxExecutorConfig,
  MCPBridgeConfig,
  CallRequest,
  CallResponse,
} from '@justanothermldude/mcp-exec-oss';

interface ExecuteCodeInput {
  code: string;
  timeout_ms?: number;
}

interface ExecutionResult {
  output: string[];
  error?: string;
  durationMs: number;
}

interface SandboxExecutorConfig {
  mcpBridgePort?: number;
  additionalWritePaths?: string[];
  enableLogMonitor?: boolean;
}

interface MCPBridgeConfig {
  port?: number;
  host?: string;
}

interface CallRequest {
  server: string;
  tool: string;
  args?: Record<string, unknown>;
}

interface CallResponse {
  success: boolean;
  content?: unknown[];
  isError?: boolean;
  error?: string;
}
```

## CLI Usage

```bash
# Start the MCP server
mcp-exec

# Show version
mcp-exec --version

# Show help
mcp-exec --help
```

## Using Wrappers in Sandboxed Code

When code runs in the sandbox, it can call MCP tools via the HTTP bridge:

```typescript
// Code running inside sandbox
const result = await fetch('http://localhost:3000/call', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    server: 'filesystem',
    tool: 'read_file',
    args: { path: '/tmp/test.txt' },
  }),
});

const data = await result.json();
console.log(data.content[0].text);
```

Or use generated wrappers:

```typescript
// Import generated wrappers
import { read_file, write_file } from './filesystem-wrappers';

// Type-safe tool calls
const content = await read_file({ path: '/tmp/test.txt' });
await write_file({ path: '/tmp/output.txt', content: 'Hello!' });
```

## Tool Catalog

mcp-exec maintains a disk-cached tool catalog at `~/.meta-mcp/tool-catalog.json` that stores tool names and parameter signatures for every server the agent has used.

### How it works

1. **First session (cold start):** No catalog exists. The agent discovers tools via `get_mcp_tool_schema` or trial and error. The first `execute_code_with_wrappers` call fetches the live tool list from the server and writes it to the catalog file.

2. **Every session after:** On startup, mcp-exec reads the catalog and embeds the full API reference in the `execute_code_with_wrappers` tool description. The agent sees all tool names and parameter signatures before writing code:
   ```
   Tool API Reference:
     github: list_issues({owner, repo, ...}), create_issue({owner, repo, title, ...}), ...
   ```

3. **Self-maintaining:**
   - Refreshed on every tool call (picks up new/changed tools from the live server)
   - Pruned on startup against `servers.json` (removed servers are cleaned from the catalog)
   - No TTL, no timers, no manual maintenance

### Error guardrails

Wrong tool or parameter names produce immediate, actionable errors:

```typescript
// Wrong tool name
server.searchMemory({ query: "test" });
// TypeError: Property "searchMemory" not found on "recall".
//   Available: memory_store_tool, memory_recall_tool, ...
//   API: memory_store_tool({content, memory_type?, ...}), ...

// Wrong parameter name
server.memory_recall_tool({ search_text: "test" });
// Error: Missing required parameter "query". Got: search_text.
//   Expected: {query, n_results?, namespace?, ...}
```

## Case-Agnostic Access

Server and tool names support flexible, case-agnostic access via Proxy-based fuzzy resolution. This means you don't need to remember exact naming conventions—camelCase, snake_case, and kebab-case all work interchangeably.

### Server Name Resolution

All of these access patterns resolve to the same server:

```typescript
// Original server name: "brave-search"
mcp['brave-search']    // Bracket notation with original name
mcp.braveSearch        // camelCase
mcp.brave_search       // snake_case
mcp.bravesearch        // Lowercase without separators
```

### Tool Name Resolution

Similarly, tool names within a server support fuzzy matching:

```typescript
// Original tool name: "search_results"
const server = mcp['brave-search'];

server.search_results     // Original snake_case
server.searchResults       // camelCase
server.searchresults       // Lowercase
server['search-jira-issues']  // kebab-case via bracket notation
```

### How It Works

The resolution uses a two-step approach:

1. **Fast-path**: If the exact property name exists, it's returned immediately
2. **Fuzzy match**: The requested name is normalized (lowercased, hyphens/underscores removed) and compared against normalized versions of all available names

### Helpful Error Messages

When a property doesn't match any available option, a `TypeError` is thrown with helpful suggestions:

```typescript
const server = mcp['brave-search'];
server.nonExistentTool;
// TypeError: Property "nonExistentTool" not found on brave-search.
//            Available: search_results, create_issue, get_issue, ...
```

```typescript
mcp.unknownServer;
// TypeError: Property "unknownServer" not found on mcp.
//            Available: brave-search, github, filesystem, ...
```

This makes it easy to discover available tools and servers when debugging or exploring the API.

## Security

- **Network Isolation**: Sandbox only allows connections to the local bridge (e.g., `localhost:3000`)
- **Filesystem Isolation**: Write access restricted to configured paths
- **Timeout Enforcement**: Code execution automatically terminated after timeout
- **OS-Level Sandboxing**: Uses `sandbox-exec` (macOS) or `bubblewrap` (Linux)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVERS_CONFIG` | `~/.meta-mcp/servers.json` | Path to servers configuration |
| `MCP_DEFAULT_TIMEOUT` | none | Global timeout for MCP tool calls (ms) |

## License

MIT
