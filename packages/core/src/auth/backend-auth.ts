import type { ServerConfig } from '../types/index.js';

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
