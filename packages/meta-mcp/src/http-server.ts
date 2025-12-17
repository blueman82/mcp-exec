/**
 * HTTP server wrapper for meta-mcp using StreamableHTTPServerTransport.
 * Integrates the SDK transport with Node.js http module.
 */

import * as http from 'node:http';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import {
  TransportConfig,
  DEFAULT_HTTP_PORT,
  DEFAULT_HTTP_HOST,
} from './transport.js';

/**
 * Result of createHttpServer function
 */
export interface HttpServerResult {
  /** The underlying Node.js HTTP server */
  httpServer: http.Server;
  /** The MCP StreamableHTTPServerTransport instance */
  transport: StreamableHTTPServerTransport;
  /** Start the HTTP server and connect the MCP server to the transport */
  start: () => Promise<void>;
  /** Stop the HTTP server and close the transport */
  stop: () => Promise<void>;
}

/**
 * Health check response format
 */
export interface HealthResponse {
  status: 'ok';
  timestamp: string;
}

/**
 * CORS headers for localhost requests
 */
const CORS_HEADERS: Record<string, string> = {
  'Access-Control-Allow-Methods': 'GET, POST, DELETE, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, mcp-session-id',
  'Access-Control-Expose-Headers': 'mcp-session-id',
  'Access-Control-Max-Age': '86400',
};

/**
 * Check if origin is a localhost origin
 */
function isLocalhostOrigin(origin: string | undefined): boolean {
  if (!origin) return false;
  try {
    const url = new URL(origin);
    return (
      url.hostname === 'localhost' ||
      url.hostname === '127.0.0.1' ||
      url.hostname === '::1'
    );
  } catch {
    return false;
  }
}

/**
 * Set CORS headers for localhost origins
 */
function setCorsHeaders(
  req: http.IncomingMessage,
  res: http.ServerResponse
): void {
  const origin = req.headers.origin;
  if (isLocalhostOrigin(origin)) {
    res.setHeader('Access-Control-Allow-Origin', origin!);
  }
  for (const [key, value] of Object.entries(CORS_HEADERS)) {
    res.setHeader(key, value);
  }
}

/**
 * Handle health check endpoint
 */
function handleHealthCheck(res: http.ServerResponse): void {
  const response: HealthResponse = {
    status: 'ok',
    timestamp: new Date().toISOString(),
  };
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(response));
}

/**
 * Create an HTTP server wrapper that integrates StreamableHTTPServerTransport
 * with a Node.js http server.
 *
 * @param mcpServer - The MCP Server instance from createServer()
 * @param config - Transport configuration
 * @returns HttpServerResult with server, transport, start(), and stop()
 */
export function createHttpServer(
  mcpServer: Server,
  config: Partial<TransportConfig> = {}
): HttpServerResult {
  const port = config.port ?? DEFAULT_HTTP_PORT;
  const host = config.host ?? DEFAULT_HTTP_HOST;
  const sessionIdGenerator = config.sessionIdGenerator;

  // Create the StreamableHTTPServerTransport
  const transport = new StreamableHTTPServerTransport({
    sessionIdGenerator,
  });

  // Create HTTP server
  const httpServer = http.createServer(
    async (req: http.IncomingMessage, res: http.ServerResponse) => {
      const url = new URL(req.url ?? '/', `http://${req.headers.host}`);
      const pathname = url.pathname;

      // Set CORS headers for all responses
      setCorsHeaders(req, res);

      // Handle CORS preflight
      if (req.method === 'OPTIONS') {
        res.writeHead(204);
        res.end();
        return;
      }

      // Health check endpoint
      if (pathname === '/health' && req.method === 'GET') {
        handleHealthCheck(res);
        return;
      }

      // Route MCP requests (POST/GET/DELETE) to transport
      // The SDK transport handles all MCP protocol details
      if (
        pathname === '/mcp' ||
        pathname === '/' ||
        pathname === ''
      ) {
        if (
          req.method === 'POST' ||
          req.method === 'GET' ||
          req.method === 'DELETE'
        ) {
          try {
            await transport.handleRequest(req, res);
          } catch (error) {
            // Log error but don't crash
            process.stderr.write(
              `Error handling MCP request: ${error instanceof Error ? error.message : String(error)}\n`
            );
            if (!res.headersSent) {
              res.writeHead(500, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ error: 'Internal server error' }));
            }
          }
          return;
        }
      }

      // 404 for unrecognized paths
      res.writeHead(404, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Not found' }));
    }
  );

  // Start function: connect MCP server to transport, then start HTTP server
  const start = async (): Promise<void> => {
    // Connect MCP server to the transport
    await mcpServer.connect(transport);

    // Start listening
    return new Promise<void>((resolve, reject) => {
      httpServer.on('error', reject);
      httpServer.listen(port, host, () => {
        process.stderr.write(
          `Meta MCP Server running on http://${host}:${port}\n`
        );
        resolve();
      });
    });
  };

  // Stop function: close HTTP server and transport
  const stop = async (): Promise<void> => {
    return new Promise<void>((resolve, reject) => {
      httpServer.close(async (err) => {
        if (err) {
          reject(err);
          return;
        }
        try {
          await transport.close();
          resolve();
        } catch (closeErr) {
          reject(closeErr);
        }
      });
    });
  };

  return {
    httpServer,
    transport,
    start,
    stop,
  };
}
