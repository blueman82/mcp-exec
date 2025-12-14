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
  type: z.string().optional(), // "stdio"
  command: z.string(),
  args: z.array(z.string()).optional(),
  env: z.record(z.string()).optional(),
  disabled: z.boolean().optional(),
  description: z.string().optional(),
  tags: z.array(z.string()).optional(),
  timeout: z.number().optional(), // Tool call timeout in milliseconds (default: 60000)
});

const BackendsConfigSchema = z.object({
  mcpServers: z.record(ServerConfigSchema),
});

let cachedManifest: ServerManifest | null = null;

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

  cachedManifest = {
    servers: result.data.mcpServers as Record<string, ServerConfigWithMeta>,
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
