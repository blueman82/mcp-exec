import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { z } from 'zod';
import type { ServerConfig } from '../types/index.js';
import { generateManifest, ServerManifest, ServerManifestEntry, ServerConfigWithMeta } from './manifest.js';

export class ConfigNotFoundError extends Error {
  constructor(path: string) {
    super(`Config file not found: ${path}`);
    this.name = 'ConfigNotFoundError';
  }
}

export class ConfigParseError extends Error {
  constructor(message: string) {
    super(`Failed to parse config: ${message}`);
    this.name = 'ConfigParseError';
  }
}

export class ConfigValidationError extends Error {
  constructor(message: string) {
    super(`Config validation failed: ${message}`);
    this.name = 'ConfigValidationError';
  }
}

const ServerConfigSchema = z.object({
  type: z.string().optional(), // "stdio" or "streamable-http"
  command: z.string().optional(), // Required for stdio, not for URL-based
  args: z.array(z.string()).optional(),
  env: z.record(z.string()).optional(),
  // HTTP transport (URL-based)
  url: z.string().optional(),
  headers: z.record(z.string()).optional(),
  disabled: z.boolean().optional(),
  description: z.string().optional(),
  tags: z.array(z.string()).optional(),
  timeout: z.number().optional(), // Tool call timeout in milliseconds (default: 60000)
  backendAuth: z.record(z.string()).optional(), // Maps backend server names to auth header values
});

const BackendsConfigSchema = z.object({
  mcpServers: z.record(ServerConfigSchema),
});

let cachedManifest: ServerManifest | null = null;

/**
 * Resolves environment variables in a string using ${VAR_NAME} syntax.
 * Returns the original string if no env vars found or if var is not set.
 */
function resolveEnvVars(value: string): string {
  return value.replace(/\$\{([^}]+)\}/g, (match, varName) => {
    const envValue = process.env[varName];
    return envValue !== undefined ? envValue : match;
  });
}

/**
 * Resolves environment variables in a string record (backendAuth, headers, etc).
 */
function resolveRecordEnvVars(record: Record<string, string> | undefined): Record<string, string> | undefined {
  if (!record) {
    return undefined;
  }
  const resolved: Record<string, string> = {};
  for (const [key, value] of Object.entries(record)) {
    resolved[key] = resolveEnvVars(value);
  }
  return resolved;
}

function getConfigPath(): string {
  if (process.env.SERVERS_CONFIG) {
    // Expand ~ in env var if present
    return process.env.SERVERS_CONFIG.replace(/^~/, os.homedir());
  }
  return path.join(os.homedir(), '.meta-mcp', 'servers.json');
}

export function loadServerManifest(): ServerManifest {
  const configPath = getConfigPath();

  if (!fs.existsSync(configPath)) {
    throw new ConfigNotFoundError(configPath);
  }

  let rawData: string;
  try {
    rawData = fs.readFileSync(configPath, 'utf-8');
  } catch (err) {
    throw new ConfigNotFoundError(configPath);
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(rawData);
  } catch (err) {
    throw new ConfigParseError((err as Error).message);
  }

  const result = BackendsConfigSchema.safeParse(parsed);
  if (!result.success) {
    throw new ConfigValidationError(result.error.message);
  }

  // Process servers and resolve environment variables in backendAuth and headers
  const processedServers: Record<string, ServerConfigWithMeta> = {};
  for (const [name, config] of Object.entries(result.data.mcpServers)) {
    processedServers[name] = {
      ...config,
      backendAuth: resolveRecordEnvVars(config.backendAuth),
      headers: resolveRecordEnvVars(config.headers),
    } as ServerConfigWithMeta;
  }

  cachedManifest = {
    servers: processedServers,
  };

  return cachedManifest;
}

export function getServerConfig(serverId: string): ServerConfig | undefined {
  if (!cachedManifest) {
    return undefined;
  }
  return cachedManifest.servers[serverId];
}

export function listServers(): ServerManifestEntry[] {
  if (!cachedManifest) {
    return [];
  }
  return generateManifest(cachedManifest.servers);
}

export function clearCache(): void {
  cachedManifest = null;
}
