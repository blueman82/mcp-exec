#!/usr/bin/env node
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { createServer } from './server.js';
import { ServerPool, createConnection } from './pool/index.js';
import { ToolCache } from './tools/tool-cache.js';
import { getServerConfig } from './registry/index.js';

export const APP_NAME = 'meta-mcp-server';

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
