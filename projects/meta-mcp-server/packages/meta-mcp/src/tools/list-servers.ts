import { z } from 'zod';
import { Tool } from '@modelcontextprotocol/sdk/types.js';
import {
  loadServerManifest,
  listServers,
  ConfigNotFoundError,
  ConfigParseError,
  ConfigValidationError,
  type ServerManifestEntry,
} from '@justanothermldude/meta-mcp-core';

const ListServersInputSchema = z.object({
  filter: z.string().optional(),
});

type ListServersInput = z.infer<typeof ListServersInputSchema>;

interface ListServersResult {
  servers: ServerManifestEntry[];
  warning?: string;
}

export const listServersTool: Tool = {
  name: 'list_servers',
  description: 'List available MCP servers with their names, descriptions, and tags. Optionally filter by name or tag.',
  inputSchema: {
    type: 'object',
    properties: {
      filter: {
        type: 'string',
        description: 'Optional filter string to match server names, descriptions, or tags',
      },
    },
  },
};

export async function listServersHandler(
  input: ListServersInput
): Promise<ListServersResult> {
  try {
    loadServerManifest();
  } catch (err) {
    if (
      err instanceof ConfigNotFoundError ||
      err instanceof ConfigParseError ||
      err instanceof ConfigValidationError
    ) {
      return {
        servers: [],
        warning: `Config not loaded: ${err.message}`,
      };
    }
    throw err;
  }

  const allServers = listServers();
  const filter = input.filter?.toLowerCase().trim();

  if (!filter) {
    return { servers: allServers };
  }

  const filtered = allServers.filter((server) => {
    const nameMatch = server.name.toLowerCase().includes(filter);
    const descMatch = server.description?.toLowerCase().includes(filter);
    const tagMatch = server.tags?.some((tag) =>
      tag.toLowerCase().includes(filter)
    );
    return nameMatch || descMatch || tagMatch;
  });

  return { servers: filtered };
}
