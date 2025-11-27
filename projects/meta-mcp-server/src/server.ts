import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  CallToolResult,
  Tool,
} from '@modelcontextprotocol/sdk/types.js';
import { ServerPool } from './pool/index.js';
import { ToolCache } from './tools/tool-cache.js';
import {
  listServersTool,
  listServersHandler,
  getServerToolsTool,
  getServerToolsHandler,
  callToolTool,
  callToolHandler,
  ToolNotFoundError,
} from './tools/index.js';

const VERSION = '0.1.0';

interface CallToolParams {
  name: string;
  arguments?: Record<string, unknown>;
}

export function createServer(pool: ServerPool, toolCache: ToolCache) {
  const server = new Server(
    {
      name: 'meta-mcp-server',
      version: VERSION,
    },
    {
      capabilities: {
        tools: {},
      },
    }
  );

  const tools: Tool[] = [listServersTool, getServerToolsTool, callToolTool];

  const listToolsHandler = async () => ({ tools });

  const callToolRequestHandler = async (
    params: CallToolParams
  ): Promise<CallToolResult> => {
    const { name, arguments: args = {} } = params;

    switch (name) {
      case 'list_servers': {
        const result = await listServersHandler({ filter: args.filter as string | undefined });
        return {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
        };
      }

      case 'get_server_tools': {
        const result = await getServerToolsHandler(
          { server_name: args.server_name as string },
          pool,
          toolCache
        );
        return {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
        };
      }

      case 'call_tool': {
        const result = await callToolHandler(
          {
            server_name: args.server_name as string,
            tool_name: args.tool_name as string,
            arguments: (args.arguments as Record<string, unknown>) ?? {},
          },
          pool,
          toolCache
        );
        return result;
      }

      default:
        throw new ToolNotFoundError('meta-mcp-server', name);
    }
  };

  server.setRequestHandler(ListToolsRequestSchema, listToolsHandler);

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    try {
      return await callToolRequestHandler(request.params);
    } catch (error) {
      if (error instanceof ToolNotFoundError) {
        throw new Error(`Unknown tool: ${request.params.name}`);
      }
      throw error;
    }
  });

  const shutdown = async () => {
    await pool.shutdown();
    toolCache.clear();
  };

  return {
    server,
    listToolsHandler,
    callToolHandler: callToolRequestHandler,
    shutdown,
  };
}
