import { z } from 'zod';

/**
 * Zod schema for a single server configuration
 * Matches meta-mcp-server/src/registry/loader.ts
 * Supports both stdio (command) and HTTP (url) transports
 */
export const ServerConfigSchema = z.object({
    // Stdio transport
    type: z.string().optional(),
    command: z.string().optional(),
    args: z.array(z.string()).optional(),
    env: z.record(z.string()).optional(),
    // HTTP transport
    url: z.string().optional(),
    headers: z.record(z.string()).optional(),
    // Common
    disabled: z.boolean().optional(),
    description: z.string().optional(),
    tags: z.array(z.string()).optional(),
}).refine(
    (data) => data.command || data.url,
    { message: 'Either command or url is required' }
);

/**
 * Zod schema for servers.json file
 */
export const ServersConfigSchema = z.object({
    mcpServers: z.record(ServerConfigSchema),
});

export type ServerConfig = z.infer<typeof ServerConfigSchema>;
export type ServersConfig = z.infer<typeof ServersConfigSchema>;

/**
 * Check if config uses URL-based transport
 */
export function isUrlConfig(config: ServerConfig): boolean {
    return !!config.url;
}
