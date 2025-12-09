import { createServer, IncomingMessage, ServerResponse, Server } from 'http';
import type { ServerPool, MCPConnection } from '@meta-mcp/core';
import { getServerConfig } from '@meta-mcp/core';

/**
 * Request body for the /call endpoint
 */
export interface CallRequest {
  /** Name of the MCP server to call */
  server: string;
  /** Name of the tool to invoke */
  tool: string;
  /** Arguments to pass to the tool */
  args?: Record<string, unknown>;
}

/**
 * Response from the /call endpoint
 */
export interface CallResponse {
  /** Whether the call was successful */
  success: boolean;
  /** Tool result content (when success is true) */
  content?: unknown[];
  /** Error message (when success is false) */
  error?: string;
  /** Whether the result indicates an error from the tool */
  isError?: boolean;
}

/**
 * Configuration options for MCPBridge
 */
export interface MCPBridgeConfig {
  /** Port to listen on (default: 3000) */
  port?: number;
  /** Host to bind to (default: '127.0.0.1') */
  host?: string;
}

/**
 * Extended MCPConnection with callTool capability
 */
interface MCPConnectionWithClient extends MCPConnection {
  client: {
    callTool: (
      params: { name: string; arguments?: Record<string, unknown> },
      resultSchema?: unknown,
      options?: { timeout?: number }
    ) => Promise<{
      content: unknown[];
      isError?: boolean;
    }>;
  };
}

const DEFAULT_PORT = 3000;
const DEFAULT_HOST = '127.0.0.1';

/**
 * MCP Bridge HTTP server that allows sandboxed code to call
 * MCP tools via HTTP requests to localhost.
 */
export class MCPBridge {
  private readonly pool: ServerPool;
  private readonly port: number;
  private readonly host: string;
  private server: Server | null = null;

  constructor(pool: ServerPool, config: MCPBridgeConfig = {}) {
    this.pool = pool;
    this.port = config.port ?? DEFAULT_PORT;
    this.host = config.host ?? DEFAULT_HOST;
  }

  /**
   * Start the HTTP bridge server
   * @returns Promise that resolves when server is listening
   */
  async start(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.server = createServer((req, res) => {
        this.handleRequest(req, res);
      });

      this.server.on('error', (err) => {
        reject(err);
      });

      this.server.listen(this.port, this.host, () => {
        resolve();
      });
    });
  }

  /**
   * Stop the HTTP bridge server
   * @returns Promise that resolves when server is closed
   */
  async stop(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!this.server) {
        resolve();
        return;
      }

      this.server.close((err) => {
        if (err) {
          reject(err);
        } else {
          this.server = null;
          resolve();
        }
      });
    });
  }

  /**
   * Get the port the server is listening on
   */
  getPort(): number {
    return this.port;
  }

  /**
   * Get the host the server is bound to
   */
  getHost(): string {
    return this.host;
  }

  /**
   * Check if the server is running
   */
  isRunning(): boolean {
    return this.server !== null && this.server.listening;
  }

  /**
   * Handle incoming HTTP requests
   */
  private handleRequest(req: IncomingMessage, res: ServerResponse): void {
    // Set CORS headers for local access
    res.setHeader('Content-Type', 'application/json');
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    // Handle preflight
    if (req.method === 'OPTIONS') {
      res.writeHead(204);
      res.end();
      return;
    }

    // Route requests
    if (req.method === 'POST' && req.url === '/call') {
      this.handleCallRequest(req, res);
    } else if (req.method === 'GET' && req.url === '/health') {
      this.handleHealthRequest(res);
    } else {
      this.sendError(res, 404, 'Not Found');
    }
  }

  /**
   * Handle POST /call endpoint for tool invocation
   */
  private handleCallRequest(req: IncomingMessage, res: ServerResponse): void {
    let body = '';

    req.on('data', (chunk: Buffer) => {
      body += chunk.toString();
    });

    req.on('end', async () => {
      try {
        // Parse request body
        let request: CallRequest;
        try {
          request = JSON.parse(body) as CallRequest;
        } catch {
          this.sendError(res, 400, 'Invalid JSON body');
          return;
        }

        // Validate required fields
        if (!request.server || typeof request.server !== 'string') {
          this.sendError(res, 400, 'Missing or invalid "server" field');
          return;
        }
        if (!request.tool || typeof request.tool !== 'string') {
          this.sendError(res, 400, 'Missing or invalid "tool" field');
          return;
        }

        // Get connection from pool
        let connection: MCPConnectionWithClient;
        try {
          connection = await this.pool.getConnection(request.server) as unknown as MCPConnectionWithClient;
        } catch (err) {
          const errorMsg = err instanceof Error ? err.message : String(err);
          this.sendError(res, 502, `Failed to connect to server "${request.server}": ${errorMsg}`);
          return;
        }

        // Call the tool with server-configured timeout or global default
        try {
          const serverConfig = getServerConfig(request.server);
          const defaultTimeout = process.env.MCP_DEFAULT_TIMEOUT
            ? parseInt(process.env.MCP_DEFAULT_TIMEOUT, 10)
            : undefined;
          const timeout = serverConfig?.timeout ?? defaultTimeout;

          const result = await connection.client.callTool(
            {
              name: request.tool,
              arguments: request.args ?? {},
            },
            undefined, // resultSchema
            timeout ? { timeout } : undefined
          );

          const response: CallResponse = {
            success: true,
            content: result.content,
            isError: result.isError,
          };

          res.writeHead(200);
          res.end(JSON.stringify(response));
        } catch (err) {
          const errorMsg = err instanceof Error ? err.message : String(err);
          this.sendError(res, 500, `Tool execution failed: ${errorMsg}`);
        } finally {
          // Release connection back to pool
          this.pool.releaseConnection(request.server);
        }
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : String(err);
        this.sendError(res, 500, `Internal error: ${errorMsg}`);
      }
    });

    req.on('error', (err) => {
      this.sendError(res, 400, `Request error: ${err.message}`);
    });
  }

  /**
   * Handle GET /health endpoint
   */
  private handleHealthRequest(res: ServerResponse): void {
    const response = {
      status: 'ok',
      timestamp: new Date().toISOString(),
    };
    res.writeHead(200);
    res.end(JSON.stringify(response));
  }

  /**
   * Send an error response
   */
  private sendError(res: ServerResponse, statusCode: number, message: string): void {
    const response: CallResponse = {
      success: false,
      error: message,
    };
    res.writeHead(statusCode);
    res.end(JSON.stringify(response));
  }
}
