import { z } from 'zod';
import { Tool } from '@modelcontextprotocol/sdk/types.js';
import type { ToolDefinition } from '../types/index.js';
import {
  loadServerManifest,
  getServerConfig,
  ConfigNotFoundError,
  ConfigParseError,
  ConfigValidationError,
} from '../registry/index.js';
import { ServerPool, ConnectionError } from '../pool/index.js';
import { ToolCache } from './tool-cache.js';

export class ServerNotFoundError extends Error {
  constructor(serverName: string) {
    super(`Server not found: ${serverName}`);
    this.name = 'ServerNotFoundError';
  }
}

const GetServerToolsInputSchema = z.object({
  server_name: z.string(),
});

type GetServerToolsInput = z.infer<typeof GetServerToolsInputSchema>;

interface GetServerToolsResult {
  tools: ToolDefinition[];
  server_name: string;
  cached: boolean;
}

export const getServerToolsTool: Tool = {
  name: 'get_server_tools',
  description: 'Get available tools from a specific MCP server. Lazily connects to the server if not already connected.',
  inputSchema: {
    type: 'object',
    properties: {
      server_name: {
        type: 'string',
        description: 'Name of the server to get tools from',
      },
    },
    required: ['server_name'],
  },
};

export async function getServerToolsHandler(
  input: GetServerToolsInput,
  pool: ServerPool,
  toolCache: ToolCache
): Promise<GetServerToolsResult> {
  const { server_name } = input;

  // Check cache first
  if (toolCache.has(server_name)) {
    return {
      tools: toolCache.get(server_name)!,
      server_name,
      cached: true,
    };
  }

  // Load manifest if needed
  try {
    loadServerManifest();
  } catch (err) {
    if (
      err instanceof ConfigNotFoundError ||
      err instanceof ConfigParseError ||
      err instanceof ConfigValidationError
    ) {
      throw new ServerNotFoundError(server_name);
    }
    throw err;
  }

  // Get server config
  const config = getServerConfig(server_name);
  if (!config) {
    throw new ServerNotFoundError(server_name);
  }

  // Get or create connection via pool
  let connection;
  try {
    connection = await pool.getConnection(server_name);
  } catch (err) {
    if (err instanceof ConnectionError) {
      throw err;
    }
    throw new ConnectionError(
      `Failed to connect to server ${server_name}`,
      err instanceof Error ? err : undefined
    );
  }

  // Get tools from connection
  const tools = await connection.getTools();

  // Cache tools
  toolCache.set(server_name, tools);

  // Release connection back to pool
  pool.releaseConnection(server_name);

  return {
    tools,
    server_name,
    cached: false,
  };
}
