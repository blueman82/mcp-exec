/**
 * list_available_mcp_servers MCP tool handler
 * Lists all available MCP servers with optional filtering
 */
import { listServers, type ServerManifestEntry } from '@meta-mcp/core';

/**
 * Input type for list_available_mcp_servers tool
 */
export interface ListServersInput {
  filter?: string;
}

/**
 * MCP Tool definition for list_available_mcp_servers
 */
export const listAvailableMcpServersTool = {
  name: 'list_available_mcp_servers',
  description:
    'List available MCP servers with their names, descriptions, and tags. Optionally filter by name or tag.',
  inputSchema: {
    type: 'object' as const,
    properties: {
      filter: {
        type: 'string',
        description: 'Optional filter string to match server names, descriptions, or tags',
      },
    },
    required: [] as string[],
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
 * Creates the list_available_mcp_servers handler function
 *
 * @returns Handler function for list_available_mcp_servers tool
 */
export function createListServersHandler() {
  /**
   * List servers handler - gets available servers and applies optional filter
   */
  return async function listServersHandler(
    args: ListServersInput
  ): Promise<CallToolResult> {
    const { filter } = args;

    try {
      // Get all available servers from the registry
      let servers: ServerManifestEntry[] = listServers();

      // Apply filter if provided
      if (filter && typeof filter === 'string') {
        const filterLower = filter.toLowerCase();
        servers = servers.filter((server) => {
          // Match against name
          if (server.name.toLowerCase().includes(filterLower)) {
            return true;
          }
          // Match against description
          if (server.description?.toLowerCase().includes(filterLower)) {
            return true;
          }
          // Match against tags
          if (server.tags?.some((tag) => tag.toLowerCase().includes(filterLower))) {
            return true;
          }
          return false;
        });
      }

      // Format and return result
      return {
        content: [{ type: 'text', text: JSON.stringify(servers, null, 2) }],
        isError: false,
      };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      return {
        content: [{ type: 'text', text: `Error listing servers: ${errorMessage}` }],
        isError: true,
      };
    }
  };
}

/**
 * Type guard for ListServersInput
 */
export function isListServersInput(args: unknown): args is ListServersInput {
  if (typeof args !== 'object' || args === null) {
    return false;
  }
  const input = args as Record<string, unknown>;
  // filter is optional, but if provided must be a string
  if ('filter' in input && typeof input.filter !== 'string') {
    return false;
  }
  return true;
}
