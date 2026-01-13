#!/usr/bin/env node
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { createServer } from './server.js';
import {
  ServerPool,
  createConnection,
  ToolCache,
  getServerConfig,
} from '@justanothermldude/meta-mcp-core';
import { parseTransportConfig, TransportMode } from './transport.js';
import { createHttpServer, HttpServerResult } from './http-server.js';

export const APP_NAME = 'meta-mcp-server';
export const VERSION = '0.1.2';

// Handle --version and --help flags
const args = process.argv.slice(2);
if (args.includes('--version') || args.includes('-v')) {
  console.log(VERSION);
  process.exit(0);
}
if (args.includes('--help') || args.includes('-h')) {
  console.log(`${APP_NAME} v${VERSION}

A meta MCP server that wraps multiple backend MCP servers,
exposing only 3 meta-tools to reduce context token consumption.

Usage:
  meta-mcp-server              Start the server (stdio transport by default)
  meta-mcp-server --version    Show version
  meta-mcp-server --help       Show this help

Environment:
  SERVERS_CONFIG        Path to servers.json config file
                        Default: ~/.meta-mcp/servers.json

  META_MCP_TRANSPORT    Transport mode: 'stdio' or 'http'
                        Default: stdio

  META_MCP_HTTP_PORT    HTTP port (only used when transport is 'http')
                        Default: 3000

  META_MCP_HTTP_HOST    HTTP host (only used when transport is 'http')
                        Default: 127.0.0.1
`);
  process.exit(0);
}

async function main() {
  // Parse transport configuration from environment
  const transportConfig = parseTransportConfig();

  // Load config on startup
  const configPath = process.env.SERVERS_CONFIG;
  if (configPath) {
    process.stderr.write(`Loading config from: ${configPath}\n`);
  }

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

  // Initialize pool and cache
  const pool = new ServerPool(connectionFactory);
  const toolCache = new ToolCache();

  // Create server
  const { server, shutdown } = createServer(pool, toolCache);

  // Track HTTP server result for cleanup (only used in HTTP mode)
  let httpServerResult: HttpServerResult | null = null;

  // Graceful shutdown handlers
  let isShuttingDown = false;
  const handleShutdown = async () => {
    if (isShuttingDown) return; // Prevent multiple shutdown attempts
    isShuttingDown = true;
    process.stderr.write('Shutting down...\n');
    await shutdown();
    // Clean up based on transport mode
    if (httpServerResult) {
      await httpServerResult.stop();
    }
    await server.close();
    process.exit(0);
  };

  process.on('SIGINT', handleShutdown);
  process.on('SIGTERM', handleShutdown);

  // Branch on transport mode
  if (transportConfig.mode === TransportMode.HTTP) {
    // HTTP transport mode
    httpServerResult = createHttpServer(server, transportConfig);
    await httpServerResult.start();
    // Note: start() already logs the listening address
  } else {
    // stdio transport mode (default)
    const transport = new StdioServerTransport();
    await server.connect(transport);
    process.stderr.write('Meta MCP Server running on stdio\n');
    
    // Handle stdin close (parent process died without signaling)
    // Register AFTER transport connects to avoid race conditions
    process.stdin.on('end', handleShutdown);
    process.stdin.on('close', handleShutdown);
  }
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});
