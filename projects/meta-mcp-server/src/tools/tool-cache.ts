import type { ToolDefinition } from '../types/index.js';

/**
 * Cache for server tools to avoid re-fetching on repeated calls
 */
export class ToolCache {
  private readonly cache = new Map<string, ToolDefinition[]>();

  /**
   * Get cached tools for a server
   */
  get(serverId: string): ToolDefinition[] | undefined {
    return this.cache.get(serverId);
  }

  /**
   * Check if tools are cached for a server
   */
  has(serverId: string): boolean {
    return this.cache.has(serverId);
  }

  /**
   * Cache tools for a server
   */
  set(serverId: string, tools: ToolDefinition[]): void {
    this.cache.set(serverId, tools);
  }

  /**
   * Remove cached tools for a server
   */
  delete(serverId: string): boolean {
    return this.cache.delete(serverId);
  }

  /**
   * Clear all cached tools
   */
  clear(): void {
    this.cache.clear();
  }

  /**
   * Get number of cached servers
   */
  size(): number {
    return this.cache.size;
  }
}
