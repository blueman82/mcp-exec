/**
 * PAT Matcher
 * 
 * Scans servers.json for PAT (Personal Access Token) patterns and matches
 * them to Gateway backend services. This enables automatic PAT passthrough
 * without requiring explicit backendAuth configuration.
 * 
 * Pattern matching:
 * - JIRA_*TOKEN*  -> jira backend
 * - GITHUB_*TOKEN* -> github backend
 * - CONFLUENCE_*TOKEN* -> confluence backend
 * - Server names are also checked: "corp-jira" -> jira backend
 * 
 * Security:
 * - Header values are sanitized to prevent CRLF injection
 * - Backend names are validated against allowlist
 */

import type { ServerConfig } from '../types/index.js';
import { resolveBackendAuth, EnvVarNotFoundError } from './backend-auth.js';

/**
 * Known backend names - explicit allowlist
 * Security: Unknown backends must pass character validation
 */
const KNOWN_BACKENDS = new Set(['jira', 'github', 'glean', 'confluence', 'bitbucket', 'slack']);

/**
 * Allowed characters for backend names
 */
const ALLOWED_BACKEND_CHARS = new Set(
  'abcdefghijklmnopqrstuvwxyz0123456789-_'.split('')
);

/**
 * Validate a backend name
 * Security: Uses allowlist + character validation instead of regex
 * 
 * @throws Error if backend name is invalid
 */
function validateBackendName(backend: string): void {
  const normalized = backend.toLowerCase();
  
  // Known backends are always valid
  if (KNOWN_BACKENDS.has(normalized)) {
    return;
  }
  
  // Unknown backends must pass validation
  if (backend.length === 0 || backend.length > 64) {
    throw new Error('Backend name must be 1-64 characters');
  }
  
  // First character must be letter
  const firstChar = normalized[0];
  if (!firstChar || !('abcdefghijklmnopqrstuvwxyz'.includes(firstChar))) {
    throw new Error('Backend name must start with a letter');
  }
  
  for (const char of normalized) {
    if (!ALLOWED_BACKEND_CHARS.has(char)) {
      // Security: Don't reveal which character is invalid
      throw new Error('Backend name contains invalid characters');
    }
  }
}

/**
 * Sanitize a header value to prevent CRLF injection
 * 
 * Security: HTTP headers are delimited by CRLF (\r\n). A malicious value
 * containing these characters could inject arbitrary headers.
 * 
 * @param value - Header value to sanitize
 * @throws Error if value contains CR, LF, or NULL characters
 */
export function sanitizeHeaderValue(value: string): string {
  // Check for CRLF injection and null bytes
  if (/[\r\n\0]/.test(value)) {
    throw new Error('Header value contains invalid characters (CR, LF, or NULL)');
  }
  return value;
}

/**
 * Known backend patterns and their corresponding header names
 */
const BACKEND_PATTERNS: Array<{
  /** Pattern to match env var names */
  envPattern: RegExp;
  /** Pattern to match server names */
  serverPattern: RegExp;
  /** Backend identifier for X-Backend-Auth-{name} header */
  backend: string;
}> = [
  {
    envPattern: /jira.*token|jira.*pat|jira.*api.*key/i,
    serverPattern: /jira/i,
    backend: 'jira',
  },
  {
    envPattern: /github.*token|github.*pat|gh.*token/i,
    serverPattern: /github|git.*corp/i,
    backend: 'github',
  },
  {
    envPattern: /confluence.*token|confluence.*pat|confluence.*api.*key/i,
    serverPattern: /confluence/i,
    backend: 'confluence',
  },
  {
    envPattern: /glean.*token|glean.*api.*key/i,
    serverPattern: /glean/i,
    backend: 'glean',
  },
  {
    envPattern: /slack.*token|slack.*bot/i,
    serverPattern: /slack/i,
    backend: 'slack',
  },
];

/**
 * Maps backend name to X-Backend-Auth header value
 */
export type BackendAuthHeaders = Record<string, string>;

/**
 * Result from PAT matching
 */
export interface PatMatchResult {
  /** Successfully matched backends with their auth values */
  headers: BackendAuthHeaders;
  /** Env vars that were referenced but not found */
  missingEnvVars: string[];
  /** Backends that were matched */
  matchedBackends: string[];
}

/**
 * Extract potential PAT env var names from a server config's env section
 */
function extractEnvVarPatterns(config: ServerConfig): Map<string, string> {
  const patterns = new Map<string, string>();
  
  if (!config.env) {
    return patterns;
  }
  
  for (const [varName, value] of Object.entries(config.env)) {
    // Check if this looks like a token/PAT env var
    for (const pattern of BACKEND_PATTERNS) {
      if (pattern.envPattern.test(varName)) {
        patterns.set(pattern.backend, value);
        break;
      }
    }
  }
  
  return patterns;
}

/**
 * Match a server name to a backend
 */
function matchServerName(serverName: string): string | null {
  for (const pattern of BACKEND_PATTERNS) {
    if (pattern.serverPattern.test(serverName)) {
      return pattern.backend;
    }
  }
  return null;
}

/**
 * Scan servers.json configs and match PATs to backends
 * 
 * @param servers - Map of server name to config
 * @param gatewayName - Name of the gateway server (to exclude from scanning)
 * @returns PatMatchResult with headers to inject
 * 
 * @example
 * ```ts
 * const servers = {
 *   gateway: { url: 'https://mcp-gateway.example.com/' },
 *   'corp-jira': { env: { JIRA_PAT: 'token123' } }
 * };
 * 
 * const result = matchPatsFromServers(servers, 'gateway');
 * // result.headers = { jira: 'token123' }
 * // result.matchedBackends = ['jira']
 * ```
 */
export function matchPatsFromServers(
  servers: Record<string, ServerConfig>,
  gatewayName: string
): PatMatchResult {
  const headers: BackendAuthHeaders = {};
  const missingEnvVars: string[] = [];
  const matchedBackends: string[] = [];
  
  for (const [serverName, config] of Object.entries(servers)) {
    // Skip the gateway itself
    if (serverName === gatewayName) {
      continue;
    }
    
    // Check env vars for PAT patterns
    const envPatterns = extractEnvVarPatterns(config);
    for (const [backend, value] of envPatterns) {
      if (!headers[backend]) {
        try {
          // Resolve any ${VAR_NAME} references
          headers[backend] = resolveBackendAuth(value);
          matchedBackends.push(backend);
        } catch (err) {
          if (err instanceof EnvVarNotFoundError) {
            missingEnvVars.push(err.message.replace('Environment variable not found: ', ''));
          }
        }
      }
    }
    
    // Also check server name for backend matching
    // If server has env vars but we haven't matched yet, try server name
    const serverBackend = matchServerName(serverName);
    if (serverBackend && !headers[serverBackend] && config.env) {
      // Look for any TOKEN or PAT env var
      for (const [varName, value] of Object.entries(config.env)) {
        if (/token|pat|api.?key|secret/i.test(varName)) {
          try {
            headers[serverBackend] = resolveBackendAuth(value);
            if (!matchedBackends.includes(serverBackend)) {
              matchedBackends.push(serverBackend);
            }
            break;
          } catch (err) {
            if (err instanceof EnvVarNotFoundError) {
              missingEnvVars.push(err.message.replace('Environment variable not found: ', ''));
            }
          }
        }
      }
    }
  }
  
  return {
    headers,
    missingEnvVars,
    matchedBackends,
  };
}

/**
 * Convert backend auth headers to X-Backend-Auth-{name} format
 * 
 * Security:
 * - Validates backend names against allowlist
 * - Sanitizes header values to prevent CRLF injection
 * 
 * @param headers - Backend name to auth value mapping
 * @returns Headers with X-Backend-Auth- prefix
 * @throws Error if backend name is invalid or header value contains CRLF
 * 
 * @example
 * ```ts
 * const headers = { jira: 'token123', github: 'ghp_xxx' };
 * const result = formatBackendAuthHeaders(headers);
 * // { 'X-Backend-Auth-Jira': 'token123', 'X-Backend-Auth-Github': 'ghp_xxx' }
 * ```
 */
export function formatBackendAuthHeaders(
  headers: BackendAuthHeaders
): Record<string, string> {
  const formatted: Record<string, string> = {};
  
  for (const [backend, value] of Object.entries(headers)) {
    // Security: Validate backend name
    validateBackendName(backend);
    
    // Security: Sanitize header value to prevent CRLF injection
    const sanitizedValue = sanitizeHeaderValue(value);
    
    // Capitalize first letter: jira -> Jira
    const capitalizedBackend = backend.charAt(0).toUpperCase() + backend.slice(1);
    formatted[`X-Backend-Auth-${capitalizedBackend}`] = sanitizedValue;
  }
  
  return formatted;
}

/**
 * Merge existing backendAuth config with auto-matched PATs
 * Explicit backendAuth takes precedence over auto-matched
 * 
 * @param explicitAuth - Explicit backendAuth from gateway config
 * @param autoMatched - Auto-matched PATs from other servers
 * @returns Merged headers
 */
export function mergeBackendAuth(
  explicitAuth: Record<string, string> | undefined,
  autoMatched: BackendAuthHeaders
): Record<string, string> {
  const merged = { ...autoMatched };
  
  // Explicit auth takes precedence
  if (explicitAuth) {
    for (const [backend, value] of Object.entries(explicitAuth)) {
      merged[backend.toLowerCase()] = value;
    }
  }
  
  return merged;
}
