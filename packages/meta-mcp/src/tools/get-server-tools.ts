import { z } from 'zod';
import { Tool } from '@modelcontextprotocol/sdk/types.js';
import {
  loadServerManifest,
  getServerConfig,
  ConfigNotFoundError,
  ConfigParseError,
  ConfigValidationError,
  ServerPool,
  ConnectionError,
  ToolCache,
  type ToolDefinition,
} from '@justanothermldude/meta-mcp-core';

export class ServerNotFoundError extends Error {
  constructor(serverName: string) {
    super(`Server not found: ${serverName}`);
    this.name = 'ServerNotFoundError';
  }
}

const GetServerToolsInputSchema = z.object({
  server_name: z.string(),
  summary_only: z.boolean().optional(),
  tools: z.array(z.string()).optional(),
});

type GetServerToolsInput = z.infer<typeof GetServerToolsInputSchema>;

interface ToolSummary {
  name: string;
  description?: string;
}

interface GetServerToolsResult {
  tools: ToolDefinition[] | ToolSummary[];
  server_name: string;
  cached: boolean;
}

export const getServerToolsTool: Tool = {
  name: 'get_server_tools',
  description: 'Get available tools from a specific MCP server. Lazily connects to the server if not already connected. Use summary_only=true for lightweight discovery (~100 tokens), then fetch specific tools by name for full schemas.',
  inputSchema: {
    type: 'object',
    properties: {
      server_name: {
        type: 'string',
        description: 'Name of the server to get tools from',
      },
      summary_only: {
        type: 'boolean',
        description: 'If true, returns only tool names and descriptions (no inputSchema). Use for discovery to reduce token usage.',
      },
      tools: {
        type: 'array',
        items: { type: 'string' },
        description: 'Optional list of specific tool names to fetch. Returns full schemas only for these tools.',
      },
    },
    required: ['server_name'],
  },
};

function filterTools(
  tools: ToolDefinition[],
  summaryOnly?: boolean,
  toolNames?: string[]
): ToolDefinition[] | ToolSummary[] {
  let filtered = tools;

  // Filter by tool names if specified
  if (toolNames && toolNames.length > 0) {
    filtered = tools.filter((t) => toolNames.includes(t.name));
  }

  // Return summaries only if requested
  if (summaryOnly) {
    return filtered.map((t) => ({ name: t.name, description: t.description }));
  }

  return filtered;
}

export async function getServerToolsHandler(
  input: GetServerToolsInput,
  pool: ServerPool,
  toolCache: ToolCache
): Promise<GetServerToolsResult> {
  const { server_name, summary_only, tools: toolNames } = input;

  // Check cache first
  if (toolCache.has(server_name)) {
    const cachedTools = toolCache.get(server_name)!;
    return {
      tools: filterTools(cachedTools, summary_only, toolNames),
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
  const allTools = await connection.getTools();

  // Cache full tools (always cache complete set)
  toolCache.set(server_name, allTools);

  // Release connection back to pool
  pool.releaseConnection(server_name);

  return {
    tools: filterTools(allTools, summary_only, toolNames),
    server_name,
    cached: false,
  };
}
