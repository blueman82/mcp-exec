# mcp-exec

MCP execution utilities for sandboxed TypeScript/JavaScript code execution with OS-level isolation.

> Private/local-only. Not published to any registry. Build it from source: `npm install && npm run build` at the repo root. The runnable server lands at `packages/mcp-exec/dist/index.js`.

## Overview

This package provides secure code execution capabilities with:

- **Sandbox Isolation**: OS-level sandboxing via `@anthropic-ai/sandbox-runtime` (sandbox-exec on macOS, bubblewrap on Linux)
- **MCP Bridge**: HTTP bridge allowing sandboxed code to call MCP tools
- **Wrapper Generation**: Auto-generate type-safe TypeScript wrappers for MCP tools

## Quick Start

### Basic Code Execution

```typescript
import { executeCode } from 'mcp-exec';

const result = await executeCode({
  code: 'console.log("Hello from sandbox!")',
  timeout_ms: 5000,
});

console.log(result.output);  // ['Hello from sandbox!']
console.log(result.durationMs);  // execution time in ms
```

### Using as MCP Server

```bash
# Start the mcp-exec server (from the built output)
node packages/mcp-exec/dist/index.js

# Or with specific config
SERVERS_CONFIG=~/.mcp-exec/servers.json node packages/mcp-exec/dist/index.js
```

## API Reference

### executeCode

Execute code in a sandboxed environment.

```typescript
import { executeCode } from 'mcp-exec';

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
import { SandboxExecutor, createExecutor } from 'mcp-exec';

// Using factory function
const executor = createExecutor({
  additionalWritePaths: ['/tmp/my-app'],
  enableLogMonitor: true,
});

// Using class directly
const executor = new SandboxExecutor({
  additionalWritePaths: ['/tmp/my-app'],
});

// Execute code
const result = await executor.execute('console.log(1 + 1)', 5000);

// Check status
executor.checkDependencies();   // true if sandbox-runtime available
executor.isSandboxingEnabled(); // true if OS sandboxing active

// Clean up
await executor.reset();
```

### Wrapper Generator

Generate type-safe TypeScript wrappers for MCP tools:

```typescript
import { generateToolWrapper, generateServerModule } from 'mcp-exec';
import type { ToolDefinition } from 'mcp-exec-core';

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
import { createMcpExecServer } from 'mcp-exec';
import { ServerPool, createConnection, getServerConfig } from 'mcp-exec-core';

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
} from 'mcp-exec';

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
  additionalWritePaths?: string[];
  enableLogMonitor?: boolean;
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

When code runs in the sandbox, MCP tools are accessible via inherited file descriptors
(fd 3 + fd 4) — no HTTP bridge, no TCP socket. The fd transport works across the
bubblewrap network namespace boundary on Linux where loopback TCP is unavailable.

Use the generated typed wrappers (recommended):

```typescript
// execute_code_with_wrappers injects these automatically based on the 'wrappers' param.
// Inside sandbox code, call via the typed namespace:
const result = await filesystem.read_file({ path: '/tmp/test.txt' });
console.log(result.content[0].text);

// Or via the fuzzy-proxy mcp dictionary:
const data = await mcp['issue-tracker'].searchIssues({ query: 'project = DEMO' });
```

The underlying fd RPC primitive (`__mcpFdCall`) is injected by the preamble —
user code never calls it directly.

## Tool Catalog

mcp-exec maintains a disk-cached tool catalog at `~/.mcp-exec/tool-catalog.json` that stores tool names and parameter signatures for every server the agent has used.

### How it works

1. **First session (cold start):** No catalog exists. The agent discovers tools via `get_mcp_tool_schema` or trial and error. The first `execute_code_with_wrappers` call fetches the live tool list from the server and writes it to the catalog file.

2. **Every session after:** On startup, mcp-exec reads the catalog and embeds the full API reference in the `execute_code_with_wrappers` tool description. The agent sees all tool names and parameter signatures before writing code:
   ```
   Tool API Reference:
     example-server: tool_one({args, config?}), tool_two({args, config?}), ...
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
// Original server name: "issue-tracker"
mcp['issue-tracker']  // Bracket notation with original name
mcp.issueTracker      // camelCase
mcp.issue_tracker     // snake_case
mcp.issuetracker      // Lowercase without separators
```

### Tool Name Resolution

Similarly, tool names within a server support fuzzy matching:

```typescript
// Original tool name: "search_issues"
const server = mcp['issue-tracker'];

server.search_issues     // Original snake_case
server.searchIssues      // camelCase
server.searchissues      // Lowercase
server['search-issues']  // kebab-case via bracket notation
```

### How It Works

The resolution uses a two-step approach:

1. **Fast-path**: If the exact property name exists, it's returned immediately
2. **Fuzzy match**: The requested name is normalized (lowercased, hyphens/underscores removed) and compared against normalized versions of all available names

### Helpful Error Messages

When a property doesn't match any available option, a `TypeError` is thrown with helpful suggestions:

```typescript
const server = mcp['issue-tracker'];
server.nonExistentTool;
// TypeError: Property "nonExistentTool" not found on issue-tracker.
//            Available: search_issues, create_issue, get_issue, ...
```

```typescript
mcp.unknownServer;
// TypeError: Property "unknownServer" not found on mcp.
//            Available: issue-tracker, github, filesystem, ...
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
| `SERVERS_CONFIG` | `~/.mcp-exec/servers.json` | Path to servers configuration |
| `MCP_DEFAULT_TIMEOUT` | none | Global timeout for MCP tool calls (ms) |

## License

MIT
