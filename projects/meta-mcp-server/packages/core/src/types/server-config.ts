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
  /**
   * Maps backend server names to auth header values for PAT passthrough.
   * Used when connecting through a gateway server to route authentication
   * to specific backend services.
   *
   * @example
   * ```json
   * {
   *   "jira": "Bearer ${JIRA_PAT}",
   *   "confluence": "Bearer ${CONFLUENCE_PAT}"
   * }
   * ```
   */
  backendAuth?: Record<string, string>;
  // Tool call timeout in milliseconds (default: 60000 from MCP SDK)
  timeout?: number;
}

/**
 * Check if config uses URL-based transport
 */
export function isUrlTransport(config: ServerConfig): boolean {
  return !!config.url;
}
