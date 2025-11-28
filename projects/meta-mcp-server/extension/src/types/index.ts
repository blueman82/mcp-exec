import { z } from 'zod';

/**
 * Zod schema for a single server configuration
 * Matches meta-mcp-server/src/registry/loader.ts
 */
export const ServerConfigSchema = z.object({
    type: z.string().optional(),
    command: z.string(),
    args: z.array(z.string()).optional(),
    env: z.record(z.string()).optional(),
    disabled: z.boolean().optional(),
    description: z.string().optional(),
    tags: z.array(z.string()).optional(),
});

/**
 * Zod schema for servers.json file
 */
export const ServersConfigSchema = z.object({
    mcpServers: z.record(ServerConfigSchema),
});

export type ServerConfig = z.infer<typeof ServerConfigSchema>;
export type ServersConfig = z.infer<typeof ServersConfigSchema>;
