/**
 * MCP Server for mcp-exec
 * Exposes code execution tools via MCP protocol
 */
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  CallToolResult,
  Tool,
} from '@modelcontextprotocol/sdk/types.js';
import type { ServerPool } from '@justanothermldude/meta-mcp-core';
import {
  listAvailableMcpServersTool,
  createListServersHandler,
  isListServersInput,
  getMcpToolSchemaTool,
  createGetToolSchemaHandler,
  isGetToolSchemaInput,
  createExecuteCodeWithWrappersToolDefinition,
  createExecuteWithWrappersHandler,
  isExecuteWithWrappersInput,
  type ExecuteWithWrappersHandlerConfig,
} from './tools/index.js';

const VERSION = '0.1.0';

interface CallToolParams {
  name: string;
  arguments?: Record<string, unknown>;
}

export interface McpExecServerConfig {
  /** Configuration for the execute_code_with_wrappers handler */
  handlerConfig?: ExecuteWithWrappersHandlerConfig;
}

/**
 * Creates the mcp-exec MCP server
 *
 * @param pool - Server pool for MCP connections
 * @param config - Optional server configuration
 * @returns Server instance and shutdown function
 */
export function createMcpExecServer(pool: ServerPool, config: McpExecServerConfig = {}) {
  const server = new Server(
    {
      name: 'mcp-exec',
      version: VERSION,
    },
    {
      capabilities: {
        tools: {},
      },
    }
  );

  // Create the list_available_mcp_servers handler
  const listServersHandler = createListServersHandler();

  // Create the get_mcp_tool_schema handler with the pool
  const getToolSchemaHandler = createGetToolSchemaHandler(pool);

  // Create the execute_code_with_wrappers handler with the pool
  const { handler: executeWithWrappersHandler, stopActiveBridge } = createExecuteWithWrappersHandler(pool, config.handlerConfig);

  // Static tools (never change)
  const staticTools: Tool[] = [
    listAvailableMcpServersTool as Tool,
    getMcpToolSchemaTool as Tool,
  ];

  // Rebuild execute_code_with_wrappers definition on each request
  // so it includes the latest disk-cached tool catalog
  const listToolsHandler = async () => ({
    tools: [...staticTools, createExecuteCodeWithWrappersToolDefinition() as Tool],
  });

  const callToolRequestHandler = async (
    params: CallToolParams
  ): Promise<CallToolResult> => {
    const { name, arguments: args = {} } = params;

    switch (name) {
      case 'list_available_mcp_servers': {
        if (!isListServersInput(args)) {
          return {
            content: [{ type: 'text', text: 'Error: Invalid arguments for list_available_mcp_servers' }],
            isError: true,
          };
        }
        const result = await listServersHandler(args);
        return {
          content: result.content,
          isError: result.isError,
        };
      }

      case 'get_mcp_tool_schema': {
        if (!isGetToolSchemaInput(args)) {
          return {
            content: [{ type: 'text', text: 'Error: Invalid arguments for get_mcp_tool_schema. Required: server (string), tool (string)' }],
            isError: true,
          };
        }
        const result = await getToolSchemaHandler(args);
        return {
          content: result.content,
          isError: result.isError,
        };
      }

      case 'execute_code_with_wrappers': {
        if (!isExecuteWithWrappersInput(args)) {
          return {
            content: [{ type: 'text', text: 'Error: Invalid arguments for execute_code_with_wrappers. Required: code (string), wrappers (string[])' }],
            isError: true,
          };
        }
        const result = await executeWithWrappersHandler(args);
        return {
          content: result.content,
          isError: result.isError,
        };
      }

      default:
        return {
          content: [{ type: 'text', text: `Unknown tool: ${name}` }],
          isError: true,
        };
    }
  };

  server.setRequestHandler(ListToolsRequestSchema, listToolsHandler);

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    return callToolRequestHandler(request.params);
  });

  const shutdown = async () => {
    // Stop any in-flight bridge so it doesn't keep the event loop alive
    await stopActiveBridge();
  };

  return {
    server,
    listToolsHandler,
    callToolHandler: callToolRequestHandler,
    shutdown,
  };
}
