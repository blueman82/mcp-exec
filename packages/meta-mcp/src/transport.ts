/**
 * Transport configuration types for meta-mcp server.
 * Enables switching between stdio (default) and HTTP transport modes.
 */

/**
 * Transport mode enum - determines how the server communicates
 */
export enum TransportMode {
  STDIO = 'stdio',
  HTTP = 'http',
}

/**
 * Default HTTP port for the server
 */
export const DEFAULT_HTTP_PORT = 3000;

/**
 * Default HTTP host for the server
 */
export const DEFAULT_HTTP_HOST = '127.0.0.1';

/**
 * Transport configuration interface
 */
export interface TransportConfig {
  /** Transport mode: stdio or http */
  mode: TransportMode;
  /** HTTP port (only used when mode is http) */
  port: number;
  /** HTTP host (only used when mode is http) */
  host: string;
  /** Optional session ID generator for HTTP mode */
  sessionIdGenerator?: () => string;
}

/**
 * Parse transport configuration from environment variables.
 *
 * Environment variables:
 * - META_MCP_TRANSPORT: 'stdio' | 'http' (default: stdio)
 * - META_MCP_HTTP_PORT: number (default: 3000)
 * - META_MCP_HTTP_HOST: string (default: '127.0.0.1')
 *
 * @returns TransportConfig parsed from environment
 */
export function parseTransportConfig(): TransportConfig {
  const transportEnv = process.env.META_MCP_TRANSPORT?.toLowerCase();
  const portEnv = process.env.META_MCP_HTTP_PORT;
  const hostEnv = process.env.META_MCP_HTTP_HOST;

  // Parse transport mode
  let mode: TransportMode = TransportMode.STDIO;
  if (transportEnv === 'http') {
    mode = TransportMode.HTTP;
  } else if (transportEnv && transportEnv !== 'stdio') {
    // Log warning for invalid transport mode, fall back to stdio
    process.stderr.write(
      `Warning: Invalid META_MCP_TRANSPORT value '${transportEnv}', falling back to 'stdio'\n`
    );
  }

  // Parse port
  let port = DEFAULT_HTTP_PORT;
  if (portEnv) {
    const parsedPort = parseInt(portEnv, 10);
    if (!isNaN(parsedPort) && parsedPort > 0 && parsedPort <= 65535) {
      port = parsedPort;
    } else {
      process.stderr.write(
        `Warning: Invalid META_MCP_HTTP_PORT value '${portEnv}', using default ${DEFAULT_HTTP_PORT}\n`
      );
    }
  }

  // Parse host
  const host = hostEnv || DEFAULT_HTTP_HOST;

  return {
    mode,
    port,
    host,
  };
}
