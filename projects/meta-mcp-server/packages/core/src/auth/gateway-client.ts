/**
 * Gateway Client
 * 
 * Wraps MCP Gateway connections with automatic authentication:
 * 1. OAuth token from Cursor storage (if available)
 * 2. PAT passthrough via X-Backend-Auth-* headers
 * 
 * This enables seamless Gateway calls without requiring users to
 * manually configure authentication for each backend service.
 */

import type { ServerConfig } from '../types/index.js';
import { extractCursorToken, isTokenExtractionSupported } from './cursor-token-reader.js';
import { formatBackendAuthHeaders } from './pat-matcher.js';
import { resolveBackendAuth, parseEnvFile } from './backend-auth.js';

/**
 * Configuration for Gateway authentication
 */
export interface GatewayAuthConfig {
  /** Try to extract OAuth token from Cursor storage */
  useCursorToken?: boolean;
  /** Manual OAuth token override */
  oauthToken?: string;
  /** Manual backend auth headers */
  manualBackendAuth?: Record<string, string>;
}

/**
 * Result of authentication resolution
 */
export interface GatewayAuthResult {
  /** Headers to inject into Gateway requests */
  headers: Record<string, string>;
  /** Whether OAuth token was found */
  hasOAuthToken: boolean;
  /** Source of OAuth token */
  oauthSource?: 'cursor' | 'manual' | 'config';
  /** Backends that were matched for PAT passthrough */
  matchedBackends: string[];
  /** Warnings about missing env vars */
  warnings: string[];
}

/**
 * Check if a server config looks like a Gateway
 * (has URL and potentially OAuth support)
 */
export function isGatewayServer(config: ServerConfig): boolean {
  return !!config.url && (
    config.url.includes('mcp') ||
    config.url.includes('gateway') ||
    !!config.backendAuth
  );
}

/**
 * Resolve authentication for a Gateway server
 * 
 * @param gatewayName - Name of the gateway server (as configured in Cursor)
 * @param gatewayConfig - Gateway server configuration
 * @param options - Authentication options
 * @returns Headers to inject into Gateway requests
 * 
 * @example
 * ```ts
 * const result = await resolveGatewayAuth(
 *   'adobe-mcp-gateway',
 *   gatewayConfig,
 *   { useCursorToken: true }
 * );
 * 
 * // Use result.headers when creating the connection
 * ```
 */
export async function resolveGatewayAuth(
  gatewayName: string,
  gatewayConfig: ServerConfig,
  options: GatewayAuthConfig = {}
): Promise<GatewayAuthResult> {
  const {
    useCursorToken = true,
    oauthToken,
    manualBackendAuth,
  } = options;
  
  const headers: Record<string, string> = {};
  const warnings: string[] = [];
  let hasOAuthToken = false;
  let oauthSource: 'cursor' | 'manual' | 'config' | undefined;
  let matchedBackends: string[] = [];
  
  // 1. Resolve OAuth token
  if (oauthToken) {
    // Manual override takes highest precedence
    headers['Authorization'] = `Bearer ${oauthToken}`;
    hasOAuthToken = true;
    oauthSource = 'manual';
  } else if (useCursorToken && isTokenExtractionSupported()) {
    // Try to extract from Cursor storage using server name
    const result = extractCursorToken(gatewayName);
    if (result.success && result.token) {
      headers['Authorization'] = `Bearer ${result.token.access_token}`;
      hasOAuthToken = true;
      oauthSource = 'cursor';
    } else if (result.error) {
      warnings.push(`Could not extract Cursor token: ${result.error}`);
    }
  }
  
  // Check for Authorization in existing config headers
  if (!hasOAuthToken && gatewayConfig.headers?.['Authorization']) {
    headers['Authorization'] = gatewayConfig.headers['Authorization'];
    hasOAuthToken = true;
    oauthSource = 'config';
  }
  
  // 2. Resolve backend PATs
  let backendHeaders: Record<string, string> = {};
  
  // Load from backendAuthEnvFile if specified
  // Keys are converted from UPPERCASE_UNDERSCORE to lowercase-hyphen format
  // and used directly as header names (e.g., JIRA_PAT_TOKEN -> x-jira-pat-token)
  if (gatewayConfig.backendAuthEnvFile) {
    const envPats = parseEnvFile(gatewayConfig.backendAuthEnvFile);
    for (const [envKey, value] of Object.entries(envPats)) {
      // Convert JIRA_PAT_TOKEN -> x-jira-pat-token
      const headerName = 'x-' + envKey.toLowerCase().replace(/_/g, '-');
      headers[headerName] = value;
      matchedBackends.push(envKey.toLowerCase().replace(/_/g, '-'));
    }
  }
  
  // Merge explicit backendAuth (uses X-Backend-Auth-* format, takes precedence)
  if (gatewayConfig.backendAuth) {
    for (const [backend, value] of Object.entries(gatewayConfig.backendAuth)) {
      try {
        backendHeaders[backend.toLowerCase()] = resolveBackendAuth(value);
      } catch {
        warnings.push(`Could not resolve backendAuth for ${backend}`);
      }
    }
  }
  
  // Add manual overrides to backendHeaders
  if (manualBackendAuth) {
    for (const [backend, value] of Object.entries(manualBackendAuth)) {
      backendHeaders[backend.toLowerCase()] = value;
      if (!matchedBackends.includes(backend.toLowerCase())) {
        matchedBackends.push(backend.toLowerCase());
      }
    }
  }
  
  // Format backendAuth and manualBackendAuth as X-Backend-Auth-* headers
  if (Object.keys(backendHeaders).length > 0) {
    const formattedBackendHeaders = formatBackendAuthHeaders(backendHeaders);
    Object.assign(headers, formattedBackendHeaders);
    // Add to matchedBackends if not already there
    for (const backend of Object.keys(backendHeaders)) {
      if (!matchedBackends.includes(backend)) {
        matchedBackends.push(backend);
      }
    }
  }
  
  // Include any other existing headers from config
  if (gatewayConfig.headers) {
    for (const [key, value] of Object.entries(gatewayConfig.headers)) {
      if (!headers[key]) {
        headers[key] = value;
      }
    }
  }
  
  // Add X-MCP-Client header to identify mcp-exec as the client
  // This is required for Gateway to return tools (MCPClientGateMiddleware)
  headers['X-MCP-Client'] = 'mcp-exec';
  
  return {
    headers,
    hasOAuthToken,
    oauthSource,
    matchedBackends,
    warnings,
  };
}

/**
 * Create an enhanced server config with resolved Gateway auth
 * 
 * @param serverName - Name of the server (as configured in Cursor)
 * @param config - Original server config
 * @param options - Auth options
 * @returns Enhanced config with auth headers injected
 */
export async function enhanceGatewayConfig(
  serverName: string,
  config: ServerConfig,
  options: GatewayAuthConfig = {}
): Promise<ServerConfig> {
  if (!isGatewayServer(config)) {
    return config;
  }
  
  const authResult = await resolveGatewayAuth(serverName, config, options);
  
  return {
    ...config,
    headers: {
      ...config.headers,
      ...authResult.headers,
    },
  };
}
