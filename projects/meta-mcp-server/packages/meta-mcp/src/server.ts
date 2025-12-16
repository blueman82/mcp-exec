import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  CallToolResult,
  Tool,
} from '@modelcontextprotocol/sdk/types.js';
import {
  ServerPool,
  ToolCache,
  getServerConfig,
  getBackendAuthHeader,
} from '@justanothermldude/meta-mcp-core';
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
          {
            server_name: args.server_name as string,
            summary_only: args.summary_only as boolean | undefined,
            tools: args.tools as string[] | undefined,
          },
          pool,
          toolCache
        );
        return {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
        };
      }

      case 'call_tool': {
        const serverName = args.server_name as string;
        const toolName = args.tool_name as string;
        const toolArguments = (args.arguments as Record<string, unknown>) ?? {};

        // Get server config to check for backendAuth
        const config = getServerConfig(serverName);

        // Build _meta with backendAuth if configured
        let meta: { backendAuth?: string } | undefined;
        if (config?.backendAuth) {
          // Try to extract backend name from tool prefix (e.g., "jira:create_issue" -> "jira")
          const colonIndex = toolName.indexOf(':');
          const backendName = colonIndex > 0 ? toolName.substring(0, colonIndex) : serverName;

          const authHeader = getBackendAuthHeader(config, backendName);
          if (authHeader) {
            meta = { backendAuth: authHeader };
          }
        }

        const result = await callToolHandler(
          {
            server_name: serverName,
            tool_name: toolName,
            arguments: toolArguments,
            _meta: meta,
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
