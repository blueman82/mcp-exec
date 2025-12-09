#!/usr/bin/env node
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { createServer } from './server.js';
import {
  ServerPool,
  createConnection,
  ToolCache,
  getServerConfig,
} from '@meta-mcp/core';

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
  meta-mcp-server              Start the server (stdio transport)
  meta-mcp-server --version    Show version
  meta-mcp-server --help       Show this help

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

  // Create connection factory
  const connectionFactory = async (serverId: string) => {
    const config = getServerConfig(serverId);
    if (!config) {
      throw new Error(`Server config not found: ${serverId}`);
    }
    return createConnection(config);
  };

  // Initialize pool and cache
  const pool = new ServerPool(connectionFactory);
  const toolCache = new ToolCache();

  // Create server
  const { server, shutdown } = createServer(pool, toolCache);

  // Graceful shutdown handlers
  const handleShutdown = async () => {
    process.stderr.write('Shutting down...\n');
    await shutdown();
    await server.close();
    process.exit(0);
  };

  process.on('SIGINT', handleShutdown);
  process.on('SIGTERM', handleShutdown);

  // Connect via stdio
  const transport = new StdioServerTransport();
  await server.connect(transport);

  process.stderr.write('Meta MCP Server running on stdio\n');
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});
