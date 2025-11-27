import { z } from 'zod';
import { Tool, CallToolResult } from '@modelcontextprotocol/sdk/types.js';
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

export class ToolNotFoundError extends Error {
  constructor(serverName: string, toolName: string) {
    super(`Tool '${toolName}' not found on server '${serverName}'`);
    this.name = 'ToolNotFoundError';
  }
}

const CallToolInputSchema = z.object({
  server_name: z.string(),
  tool_name: z.string(),
  arguments: z.record(z.unknown()).optional().default({}),
});

type CallToolInput = z.infer<typeof CallToolInputSchema>;

export const callToolTool: Tool = {
  name: 'call_tool',
  description: 'Call a tool on a specific MCP server. The tool must exist on the server.',
  inputSchema: {
    type: 'object',
    properties: {
      server_name: {
        type: 'string',
        description: 'Name of the server to call the tool on',
      },
      tool_name: {
        type: 'string',
        description: 'Name of the tool to call',
      },
      arguments: {
        type: 'object',
        description: 'Arguments to pass to the tool',
        additionalProperties: true,
      },
    },
    required: ['server_name', 'tool_name'],
  },
};

interface ConnectionWithClient {
  serverId: string;
  client: {
    callTool: (params: { name: string; arguments?: Record<string, unknown> }) => Promise<CallToolResult>;
  };
}

export async function callToolHandler(
  input: CallToolInput,
  pool: ServerPool,
  toolCache: ToolCache
): Promise<CallToolResult> {
  const { server_name, tool_name, arguments: args } = input;

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

  // Validate tool exists in cache
  const cachedTools = toolCache.get(server_name);
  if (cachedTools) {
    const toolExists = cachedTools.some(t => t.name === tool_name);
    if (!toolExists) {
      throw new ToolNotFoundError(server_name, tool_name);
    }
  }

  // Get connection from pool
  let connection: ConnectionWithClient;
  try {
    connection = (await pool.getConnection(server_name)) as unknown as ConnectionWithClient;
  } catch (err) {
    if (err instanceof ConnectionError) {
      throw err;
    }
    throw new ConnectionError(
      `Failed to connect to server ${server_name}`,
      err instanceof Error ? err : undefined
    );
  }

  // Call the tool
  try {
    const result = await connection.client.callTool({
      name: tool_name,
      arguments: args,
    });
    return result;
  } finally {
    pool.releaseConnection(server_name);
  }
}
