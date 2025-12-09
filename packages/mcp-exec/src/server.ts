/**
 * MCP Server for mcp-exec
 * Exposes the execute_code tool via MCP protocol
 */
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  CallToolResult,
  Tool,
} from '@modelcontextprotocol/sdk/types.js';
import type { ServerPool } from '@meta-mcp/core';
import {
  executeCodeTool,
  createExecuteCodeHandler,
  isExecuteCodeInput,
  type ExecuteCodeHandlerConfig,
  listAvailableMcpServersTool,
  createListServersHandler,
  isListServersInput,
  getMcpToolSchemaTool,
  createGetToolSchemaHandler,
  isGetToolSchemaInput,
  executeCodeWithWrappersTool,
  createExecuteWithWrappersHandler,
  isExecuteWithWrappersInput,
  executeBatchTool,
  createExecuteBatchHandler,
  isExecuteBatchInput,
  executeWithContextTool,
  createExecuteWithContextHandler,
  isExecuteWithContextInput,
} from './tools/index.js';

const VERSION = '0.1.0';

interface CallToolParams {
  name: string;
  arguments?: Record<string, unknown>;
}

export interface McpExecServerConfig {
  /** Configuration for the execute_code handler */
  handlerConfig?: ExecuteCodeHandlerConfig;
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

  // Create the execute_code handler with the pool
  const executeCodeHandler = createExecuteCodeHandler(pool, config.handlerConfig);

  // Create the list_available_mcp_servers handler
  const listServersHandler = createListServersHandler();

  // Create the get_mcp_tool_schema handler with the pool
  const getToolSchemaHandler = createGetToolSchemaHandler(pool);

  // Create the execute_code_with_wrappers handler with the pool
  const executeWithWrappersHandler = createExecuteWithWrappersHandler(pool);

  // Create the execute_batch handler with the pool
  const executeBatchHandler = createExecuteBatchHandler(pool);

  // Create the execute_with_context handler with the pool
  const executeWithContextHandler = createExecuteWithContextHandler(pool);

  // Register all tools
  const tools: Tool[] = [
    executeCodeTool as Tool,
    listAvailableMcpServersTool as Tool,
    getMcpToolSchemaTool as Tool,
    executeCodeWithWrappersTool as Tool,
    executeBatchTool as Tool,
    executeWithContextTool as Tool,
  ];

  const listToolsHandler = async () => ({ tools });

  const callToolRequestHandler = async (
    params: CallToolParams
  ): Promise<CallToolResult> => {
    const { name, arguments: args = {} } = params;

    switch (name) {
      case 'execute_code': {
        if (!isExecuteCodeInput(args)) {
          return {
            content: [{ type: 'text', text: 'Error: Invalid arguments for execute_code. Required: code (string)' }],
            isError: true,
          };
        }
        const result = await executeCodeHandler(args);
        return {
          content: result.content,
          isError: result.isError,
        };
      }

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
            content: [{ type: 'text', text: 'Error: Invalid arguments for get_mcp_tool_schema. Required: server_name (string), tool_name (string)' }],
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

      case 'execute_batch': {
        if (!isExecuteBatchInput(args)) {
          return {
            content: [{ type: 'text', text: 'Error: Invalid arguments for execute_batch. Required: snippets (array of {id, code, depends_on?})' }],
            isError: true,
          };
        }
        const result = await executeBatchHandler(args);
        return {
          content: result.content,
          isError: result.isError,
        };
      }

      case 'execute_with_context': {
        if (!isExecuteWithContextInput(args)) {
          return {
            content: [{ type: 'text', text: 'Error: Invalid arguments for execute_with_context. Required: code (string), optional: context (object)' }],
            isError: true,
          };
        }
        const result = await executeWithContextHandler(args);
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
    // No pool shutdown needed - pool is managed externally
    // Server cleanup handled by server.close()
  };

  return {
    server,
    listToolsHandler,
    callToolHandler: callToolRequestHandler,
    shutdown,
  };
}
