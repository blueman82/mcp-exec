/**
 * list_available_mcp_servers MCP tool handler
 * Lists all available MCP servers with optional filtering
 */
import { listServers, type ServerManifestEntry } from '@justanothermldude/meta-mcp-core';

/**
 * Escapes pipe characters in text for safe inclusion in a markdown table cell.
 */
function escapeMarkdownCell(text: string): string {
  return text.replace(/\|/g, '\\|');
}

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

      // Format as markdown table for better LLM parsing
      if (servers.length === 0) {
        // Empty result after filter
        const noMatchMsg = filter
          ? `No servers matched filter: '${filter}'. Try list_available_mcp_servers without a filter.`
          : 'No servers are configured. Check that servers.json is properly set up.';
        return {
          content: [{ type: 'text', text: noMatchMsg }],
          isError: false,
        };
      }

      // Build markdown table
      const rows = servers.map((server) => {
        // Truncate description at 80 chars if needed, respecting UTF-16 surrogate pairs
        const desc = (() => {
          if (!server.description) return '';
          if (server.description.length <= 80) return server.description;
          // Truncate then strip any trailing lone high surrogate (broken emoji)
          let truncated = server.description.substring(0, 77);
          truncated = truncated.replace(/[\uD800-\uDBFF]$/, '');
          return truncated + '...';
        })();

        // Format tags: max 5 shown, append "+N more" if additional
        let tagsStr = '';
        if (server.tags && server.tags.length > 0) {
          const displayTags = server.tags.slice(0, 5);
          const hasMore = server.tags.length > 5;
          tagsStr = displayTags.join(', ') + (hasMore ? ` +${server.tags.length - 5} more` : '');
        }

        const escapedName = escapeMarkdownCell(server.name);
        const escapedDesc = escapeMarkdownCell(desc);
        const escapedTags = escapeMarkdownCell(tagsStr);
        return `| \`${escapedName}\` | ${escapedDesc} | ${escapedTags} |`;
      });

      const table =
        '## Available MCP Servers\n\n' +
        '| Name | Description | Tags |\n' +
        '|------|-------------|------|\n' +
        rows.join('\n') +
        '\n\n' +
        'To use a server, pass its exact name in the `wrappers` array of `execute_code_with_wrappers`.\n' +
        'Example: `wrappers: ["adobe-mcp-gateway"]`\n\n' +
        'To see tools on a server: `get_mcp_tool_schema({ server: "adobe-mcp-gateway" })`';

      return {
        content: [{ type: 'text', text: table }],
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
