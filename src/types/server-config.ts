/**
 * Spawn configuration for MCP server processes
 */
export interface ServerSpawnConfig {
  command: string;
  args?: string[];
  env?: Record<string, string>;
}

/**
 * Configuration for an MCP server
 * Supports multiple spawn types: docker, node, uvx
 * Also supports URL-based HTTP/SSE transport
 */
export interface ServerConfig {
  name: string;
  // Stdio transport (spawn process)
  command?: string;
  args?: string[];
  type?: 'docker' | 'node' | 'uvx';
  docker?: {
    image: string;
    tag?: string;
  };
  env?: Record<string, string>;
  // HTTP transport (URL-based)
  url?: string;
  headers?: Record<string, string>;
}

/**
 * Check if config uses URL-based transport
 */
export function isUrlTransport(config: ServerConfig): boolean {
  return !!config.url;
}
