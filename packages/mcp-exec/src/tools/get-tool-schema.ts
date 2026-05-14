/**
 * get_mcp_tool_schema MCP tool handler
 * Fetches the schema for a specific MCP tool from a server
 */
import { ServerPool, type ToolDefinition } from '@justanothermldude/mcp-exec-oss-core';

/**
 * Input type for get_mcp_tool_schema tool
 */
export interface GetToolSchemaInput {
  server: string;
  tool?: string;
}

/**
 * MCP Tool definition for get_mcp_tool_schema
 */
export const getMcpToolSchemaTool = {
  name: 'get_mcp_tool_schema',
  description:
    'Get the full schema for a specific MCP tool, or list all tools on a server. Omit tool param to discover available tools.',
  inputSchema: {
    type: 'object' as const,
    properties: {
      server: {
        type: 'string',
        description: 'The name of the MCP server that has the tool',
      },
      tool: {
        type: 'string',
        description: 'The name of the tool to get the schema for. Omit to list all tools.',
      },
    },
    required: ['server'],
  },
};

/**
 * CallToolResult content item
 */
export interface TextContent {
  type: 'text';
  text: string;
}

/**
 * Standard MCP CallToolResult format
 */
export interface CallToolResult {
  content: TextContent[];
  isError?: boolean;
}

/**
 * Creates the get_mcp_tool_schema handler function
 *
 * @param pool - ServerPool instance for managing connections
 * @returns Handler function for get_mcp_tool_schema tool
 */
export function createGetToolSchemaHandler(pool: ServerPool) {
  /**
   * Get tool schema handler - fetches schema for a specific tool, or lists all tools
   */
  return async function getToolSchemaHandler(
    args: GetToolSchemaInput
  ): Promise<CallToolResult> {
    const { server, tool } = args;

    try {
      // Get connection to the specified server
      const connection = await pool.getConnection(server);

      // Fetch all tools from the server
      const tools: ToolDefinition[] = await connection.getTools();

      // Discovery mode: return all tools with name + description only
      if (!tool) {
        const summary = tools.map((t) => ({
          name: t.name,
          description: t.description || '',
        }));
        return {
          content: [{ type: 'text', text: JSON.stringify(summary, null, 2) }],
          isError: false,
        };
      }

      // Specific tool mode: find and return full schema
      const matchedTool = tools.find((t) => t.name === tool);

      if (!matchedTool) {
        // Provide helpful error with available tool names
        const availableTools = tools.map((t) => t.name).sort();
        return {
          content: [
            {
              type: 'text',
              text: `Tool '${tool}' not found on server '${server}'. Available tools: ${availableTools.join(', ')}`,
            },
          ],
          isError: true,
        };
      }

      // Return the full tool schema
      return {
        content: [{ type: 'text', text: JSON.stringify(matchedTool, null, 2) }],
        isError: false,
      };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);

      // Check if it's a connection/server error and provide helpful suggestions
      if (
        errorMessage.includes('not found') ||
        errorMessage.includes('unknown server')
      ) {
        return {
          content: [
            {
              type: 'text',
              text: `Error connecting to server '${server}': ${errorMessage}. Use list_available_mcp_servers to see available servers.`,
            },
          ],
          isError: true,
        };
      }

      return {
        content: [
          {
            type: 'text',
            text: `Error getting tool schema: ${errorMessage}`,
          },
        ],
        isError: true,
      };
    }
  };
}

/**
 * Type guard for GetToolSchemaInput
 */
export function isGetToolSchemaInput(args: unknown): args is GetToolSchemaInput {
  if (typeof args !== 'object' || args === null) {
    return false;
  }
  const input = args as Record<string, unknown>;
  // server is required, tool is optional
  if (typeof input.server !== 'string') {
    return false;
  }
  if (input.tool !== undefined && typeof input.tool !== 'string') {
    return false;
  }
  return true;
}
