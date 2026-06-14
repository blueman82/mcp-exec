import type { ServerConfig } from '../types/index.js';

/**
 * Lightweight manifest entry for listing servers
 */
export interface ServerManifestEntry {
  name: string;
  description?: string;
  tags?: string[];
}

/**
 * Full server manifest with configs
 */
export interface ServerManifest {
  servers: Record<string, ServerConfigWithMeta>;
}

/**
 * ServerConfig extended with metadata for manifest
 */
export interface ServerConfigWithMeta extends ServerConfig {
  description?: string;
  tags?: string[];
}

/**
 * Generate lightweight manifest entries from full configs
 */
export function generateManifest(configs: Record<string, ServerConfigWithMeta>): ServerManifestEntry[] {
  return Object.entries(configs).map(([name, config]) => ({
    name,
    description: config.description,
    tags: config.tags,
  }));
}
