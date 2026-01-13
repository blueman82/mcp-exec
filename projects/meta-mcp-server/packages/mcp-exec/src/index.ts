#!/usr/bin/env node
/**
 * @meta-mcp/exec - MCP execution utilities for sandboxed code execution
 *
 * Entry point for both the MCP server and programmatic API usage.
 */
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { createMcpExecServer } from './server.js';
import { ServerPool, createConnection, getServerConfig, loadServerManifest } from '@justanothermldude/meta-mcp-core';

// Export types
export * from './types/index.js';

// Export sandbox module
export * from './sandbox/index.js';

// Export codegen module
export * from './codegen/index.js';

// Export bridge module
export * from './bridge/index.js';

// Export tools module
export * from './tools/index.js';

// Export server module
export { createMcpExecServer, type McpExecServerConfig } from './server.js';

// Export type interfaces explicitly for convenience
export type { ExecuteCodeInput, ExecutionResult } from './types/execution.js';

import type { ExecuteCodeInput, ExecutionResult } from './types/execution.js';
import { SandboxExecutor, type SandboxExecutorConfig } from './sandbox/index.js';
import { DEFAULT_TIMEOUT_MS } from './types/execution.js';
export const APP_NAME = 'mcp-exec';
export const VERSION = '__MCP_EXEC_VERSION__';

// Default executor instance (lazily initialized)
let defaultExecutor: SandboxExecutor | null = null;

/**
 * Get or create the default SandboxExecutor instance
 */
function getDefaultExecutor(): SandboxExecutor {
  if (!defaultExecutor) {
    defaultExecutor = new SandboxExecutor();
  }
  return defaultExecutor;
}

/**
 * Execute code in a sandboxed environment using @anthropic-ai/sandbox-runtime.
 * Provides OS-level isolation (sandbox-exec on macOS, bubblewrap on Linux).
 *
 * @param input - The code execution input parameters
 * @returns Promise resolving to execution result
 */
export async function executeCode(input: ExecuteCodeInput): Promise<ExecutionResult> {
  const { code, timeout_ms = DEFAULT_TIMEOUT_MS } = input;
  const executor = getDefaultExecutor();
  return executor.execute(code, timeout_ms);
}

/**
 * Create a new SandboxExecutor with custom configuration
 * @param config - Configuration options for the sandbox
 * @returns New SandboxExecutor instance
 */
export function createExecutor(config?: SandboxExecutorConfig): SandboxExecutor {
  return new SandboxExecutor(config);
}

// Handle --version and --help flags
const args = process.argv.slice(2);
if (args.includes('--version') || args.includes('-v')) {
  console.log(VERSION);
  process.exit(0);
}
if (args.includes('--help') || args.includes('-h')) {
  console.log(`${APP_NAME} v${VERSION}

An MCP server for executing TypeScript/JavaScript code in sandboxed environments
with access to MCP tools via HTTP bridge.

Usage:
  mcp-exec              Start the server (stdio transport)
  mcp-exec --version    Show version
  mcp-exec --help       Show this help

Environment:
  SERVERS_CONFIG    Path to servers.json config file
                    Default: ~/.meta-mcp/servers.json
`);
  process.exit(0);
}

async function main() {
  // Load config on startup
  const configPath = process.env.SERVERS_CONFIG;
  if (configPath) {
    process.stderr.write(`Loading config from: ${configPath}\n`);
  }

  // Load server manifest (required before getServerConfig works)
  loadServerManifest();

  // Create connection factory with Gateway auth support
  const connectionFactory = async (serverId: string) => {
    const config = getServerConfig(serverId);
    if (!config) {
      throw new Error(`Server config not found: ${serverId}`);
    }
    return createConnection({ ...config, name: serverId }, { 
      gatewayAuth: { useCursorToken: true }
    });
  };

  // Initialize pool
  const pool = new ServerPool(connectionFactory);

  // Create server
  const { server, shutdown } = createMcpExecServer(pool);

  // Graceful shutdown handlers
  let isShuttingDown = false;
  const handleShutdown = async () => {
    if (isShuttingDown) return; // Prevent multiple shutdown attempts
    isShuttingDown = true;
    process.stderr.write('Shutting down...\n');
    await shutdown();
    await pool.shutdown();
    await server.close();
    process.exit(0);
  };

  process.on('SIGINT', handleShutdown);
  process.on('SIGTERM', handleShutdown);

  // Connect via stdio
  const transport = new StdioServerTransport();
  await server.connect(transport);

  process.stderr.write('mcp-exec server running on stdio\n');
}

// Only run main if this is the entry point (not when imported as a module)
const isMainModule = process.argv[1]?.endsWith('index.js') || process.argv[1]?.endsWith('mcp-exec');
if (isMainModule && !args.includes('--no-server')) {
  main().catch((error) => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}
