/**
 * Virtual module resolver for MCP tool wrappers.
 * Generates and caches TypeScript wrappers, enabling import from
 * ./servers/<name>/<tool>.ts paths.
 */

import type { ToolDefinition, ServerManifest } from '@justanothermldude/mcp-exec-oss-core';
import { loadServerManifest } from '@justanothermldude/mcp-exec-oss-core';
import { generateToolWrapper } from './wrapper-generator.js';

/**
 * Sanitize a tool name to create a valid filename
 */
function sanitizeFileName(name: string): string {
  return name.replace(/[^a-zA-Z0-9_-]/g, '_').toLowerCase();
}

/**
 * Virtual module resolver that maintains a cache of generated TypeScript
 * wrappers for MCP tools, enabling import from ./servers/<name>/<tool>.ts paths.
 */
export class VirtualModuleResolver {
  /**
   * Map of virtual module path -> generated TypeScript code
   */
  private modules: Map<string, string> = new Map();

  /**
   * Register a virtual module at the given path
   * @param path - Virtual path (e.g., ./servers/github/create_issue.ts)
   * @param code - Generated TypeScript code
   */
  registerModule(path: string, code: string): void {
    this.modules.set(this.normalizePath(path), code);
  }

  /**
   * Resolve a virtual module path to its generated code
   * @param path - Virtual path to resolve
   * @returns Generated TypeScript code or undefined if not found
   */
  resolve(path: string): string | undefined {
    return this.modules.get(this.normalizePath(path));
  }

  /**
   * Check if a virtual module exists at the given path
   * @param path - Virtual path to check
   * @returns True if module exists
   */
  has(path: string): boolean {
    return this.modules.has(this.normalizePath(path));
  }

  /**
   * Clear all registered modules
   */
  clear(): void {
    this.modules.clear();
  }

  /**
   * Get the number of registered modules
   */
  size(): number {
    return this.modules.size;
  }

  /**
   * Get all registered module paths
   */
  listModules(): string[] {
    return Array.from(this.modules.keys());
  }

  /**
   * Normalize a path for consistent lookup
   */
  private normalizePath(path: string): string {
    // Remove leading ./ if present and ensure consistent format
    return path.replace(/^\.\//, '').replace(/\\/g, '/');
  }

  /**
   * Generate the virtual path for a tool
   * @param serverName - Name of the MCP server
   * @param toolName - Name of the tool
   * @returns Virtual path in format servers/<name>/<tool>.ts
   */
  static getToolPath(serverName: string, toolName: string): string {
    return `servers/${serverName}/${sanitizeFileName(toolName)}.ts`;
  }

  /**
   * Generate the virtual path for a server's index module
   * @param serverName - Name of the MCP server
   * @returns Virtual path in format servers/<name>/index.ts
   */
  static getServerIndexPath(serverName: string): string {
    return `servers/${serverName}/index.ts`;
  }
}

/**
 * Options for generating modules from manifest
 */
export interface GenerateFromManifestOptions {
  /**
   * Tool cache to fetch tool definitions from
   * Maps server name to array of tool definitions
   */
  toolCache: Map<string, ToolDefinition[]>;

  /**
   * Optional custom manifest (uses loadServerManifest() if not provided)
   */
  manifest?: ServerManifest;
}

/**
 * Generate virtual modules from server manifest and tool cache.
 * Creates wrappers for all configured servers and their tools.
 *
 * @param resolver - VirtualModuleResolver to populate
 * @param options - Options including tool cache and optional manifest
 * @returns Promise resolving to number of modules generated
 */
export async function generateFromManifest(
  resolver: VirtualModuleResolver,
  options: GenerateFromManifestOptions
): Promise<number> {
  const { toolCache, manifest = loadServerManifest() } = options;

  let moduleCount = 0;

  // Iterate over each server in the manifest
  for (const serverName of Object.keys(manifest.servers)) {
    const tools = toolCache.get(serverName);

    if (!tools || tools.length === 0) {
      continue;
    }

    // Generate individual tool modules
    for (const tool of tools) {
      const path = VirtualModuleResolver.getToolPath(serverName, tool.name);
      const code = generateToolWrapper(tool, serverName);
      resolver.registerModule(path, code);
      moduleCount++;
    }

    // Generate server index module that re-exports all tools
    const indexPath = VirtualModuleResolver.getServerIndexPath(serverName);
    const indexCode = generateServerIndexModule(serverName, tools);
    resolver.registerModule(indexPath, indexCode);
    moduleCount++;
  }

  return moduleCount;
}

/**
 * Generate an index module that re-exports all tools for a server
 */
function generateServerIndexModule(serverName: string, tools: ToolDefinition[]): string {
  const lines: string[] = [];

  lines.push('/**');
  lines.push(` * Auto-generated index for ${serverName} MCP server tools.`);
  lines.push(' * Re-exports all tool wrappers for convenient imports.');
  lines.push(' */');
  lines.push('');

  for (const tool of tools) {
    const fileName = sanitizeFileName(tool.name);
    lines.push(`export * from './${fileName}.js';`);
  }

  return lines.join('\n');
}

/**
 * Create a VirtualModuleResolver and populate it from manifest
 * Convenience function for one-step initialization
 *
 * @param options - Options including tool cache and optional manifest
 * @returns Promise resolving to populated VirtualModuleResolver
 */
export async function createModuleResolver(options: GenerateFromManifestOptions): Promise<VirtualModuleResolver> {
  const resolver = new VirtualModuleResolver();
  await generateFromManifest(resolver, options);
  return resolver;
}
