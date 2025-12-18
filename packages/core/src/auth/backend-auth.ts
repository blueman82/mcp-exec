import { readFileSync, existsSync, lstatSync, realpathSync, statSync } from 'node:fs';
import { resolve, relative } from 'node:path';
import { homedir } from 'node:os';
import type { ServerConfig } from '../types/index.js';

/**
 * Maximum file size for .env files (64KB)
 * Legitimate .env files with PATs are typically <1KB
 */
const MAX_ENV_FILE_SIZE = 64 * 1024;

/**
 * Error thrown when an environment variable required for auth resolution is not defined.
 */
export class EnvVarNotFoundError extends Error {
  constructor(varName: string) {
    super(`Environment variable not found: ${varName}`);
    this.name = 'EnvVarNotFoundError';
  }
}

/**
 * Resolves environment variables in a string using ${VAR_NAME} syntax.
 * Throws if any referenced environment variable is undefined.
 *
 * @param value - String potentially containing ${VAR_NAME} patterns
 * @returns Resolved string with env vars replaced
 * @throws EnvVarNotFoundError if any referenced env var is not set
 *
 * @example
 * ```ts
 * // With JIRA_PAT="abc123" in process.env
 * resolveBackendAuth("Bearer ${JIRA_PAT}") // => "Bearer abc123"
 *
 * // Throws if MISSING_VAR is not set
 * resolveBackendAuth("Bearer ${MISSING_VAR}") // throws EnvVarNotFoundError
 * ```
 */
export function resolveBackendAuth(value: string): string {
  return value.replace(/\$\{([^}]+)\}/g, (_match, varName: string) => {
    const envValue = process.env[varName];
    if (envValue === undefined) {
      throw new EnvVarNotFoundError(varName);
    }
    return envValue;
  });
}

/**
 * Looks up and resolves the auth header value for a specific backend server.
 *
 * @param config - Server configuration containing backendAuth mapping
 * @param serverName - Name of the backend server to get auth for
 * @returns Resolved auth header value, or undefined if no mapping exists
 * @throws EnvVarNotFoundError if auth value references undefined env var
 *
 * @example
 * ```ts
 * const config: ServerConfig = {
 *   name: 'gateway',
 *   backendAuth: {
 *     jira: 'Bearer ${JIRA_PAT}',
 *     confluence: 'Bearer ${CONFLUENCE_PAT}'
 *   }
 * };
 *
 * // Returns resolved header value
 * getBackendAuthHeader(config, 'jira') // => "Bearer actual-token"
 *
 * // Returns undefined for unknown server
 * getBackendAuthHeader(config, 'unknown') // => undefined
 * ```
 */
export function getBackendAuthHeader(
  config: ServerConfig,
  serverName: string
): string | undefined {
  if (!config.backendAuth) {
    return undefined;
  }

  const authValue = config.backendAuth[serverName];
  if (authValue === undefined) {
    return undefined;
  }

  return resolveBackendAuth(authValue);
}

/**
 * Validate that a file path is within allowed directories.
 * 
 * Security:
 * - Prevents path traversal attacks (e.g., ../../etc/passwd)
 * - Rejects symbolic links to prevent symlink-based escapes
 * - Only allows files within home directory or current working directory
 * 
 * @param filePath - Path to validate
 * @throws Error if path is outside allowed directories or is a symlink
 */
function validateEnvFilePath(filePath: string): string {
  // Expand ~ to home directory
  const expandedPath = filePath.startsWith('~') 
    ? filePath.replace(/^~/, homedir()) 
    : filePath;
  const resolved = resolve(expandedPath);
  
  if (!existsSync(resolved)) {
    // File doesn't exist - return resolved path, caller will handle
    return resolved;
  }
  
  // Security: Reject symbolic links - they can point outside allowed directories
  const stats = lstatSync(resolved);
  if (stats.isSymbolicLink()) {
    throw new Error('Symbolic links are not allowed for security files');
  }
  
  // Resolve any relative path components (.., .)
  const realPath = realpathSync(resolved);
  
  // Allowed base directories
  const home = homedir();
  const cwd = process.cwd();
  
  // Check if path is within home directory
  const relativeToHome = relative(home, realPath);
  const isWithinHome = !relativeToHome.startsWith('..') && !relativeToHome.startsWith('/');
  
  // Check if path is within current working directory
  const relativeToCwd = relative(cwd, realPath);
  const isWithinCwd = !relativeToCwd.startsWith('..') && !relativeToCwd.startsWith('/');
  
  if (!isWithinHome && !isWithinCwd) {
    throw new Error('ENV file must be within home directory or project directory');
  }
  
  return realPath;
}

/**
 * Parse a .env file and return key-value pairs.
 * Supports basic .env format: KEY=value (one per line).
 * Ignores comments (#) and empty lines.
 * 
 * Security:
 * - Path traversal protection (files must be in home or cwd)
 * - Symlink rejection
 * - File size limit (64KB max)
 * 
 * @param filePath - Path to the .env file
 * @returns Record of key-value pairs, or empty object if file doesn't exist
 * @throws Error if path is outside allowed directories, is a symlink, or file is too large
 */
export function parseEnvFile(filePath: string): Record<string, string> {
  // Security: Validate path is within allowed directories and not a symlink
  const validatedPath = validateEnvFilePath(filePath);
  
  if (!existsSync(validatedPath)) {
    return {};
  }
  
  // Security: Check file size to prevent DoS via large files
  const stats = statSync(validatedPath);
  if (stats.size > MAX_ENV_FILE_SIZE) {
    throw new Error(`ENV file too large (max ${MAX_ENV_FILE_SIZE} bytes)`);
  }
  
  const content = readFileSync(validatedPath, 'utf-8');
  const result: Record<string, string> = {};
  
  for (const line of content.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) {
      continue;
    }
    
    const eqIndex = trimmed.indexOf('=');
    if (eqIndex === -1) {
      continue;
    }
    
    const key = trimmed.slice(0, eqIndex).trim();
    let value = trimmed.slice(eqIndex + 1).trim();
    
    // Remove surrounding quotes if present
    if ((value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    
    if (key) {
      result[key] = value;
    }
  }
  
  return result;
}
