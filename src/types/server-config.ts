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
 */
export interface ServerConfig {
  name: string;
  command?: string;
  args?: string[];
  type?: 'docker' | 'node' | 'uvx';
  docker?: {
    image: string;
    tag?: string;
  };
  env?: Record<string, string>;
}
