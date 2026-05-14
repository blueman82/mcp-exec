import { createServer, IncomingMessage, ServerResponse, Server } from 'http';
import getPort from 'get-port';
import type { ServerPool, MCPConnection } from '@justanothermldude/mcp-exec-oss-core';
import { getServerConfig, listServers } from '@justanothermldude/mcp-exec-oss-core';
import { cleanupStaleProcess } from './port-cleanup.js';

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
const MAX_REQUEST_BODY_SIZE = 10 * 1024 * 1024; // 10MB limit

/**
 * Calculate simple string similarity using common prefix/suffix length
 * Returns a score between 0 and 1
 */
function stringSimilarity(a: string, b: string): number {
  const aLower = a.toLowerCase();
  const bLower = b.toLowerCase();

  // Exact match
  if (aLower === bLower) return 1;

  // Check if one contains the other
  if (aLower.includes(bLower) || bLower.includes(aLower)) {
    return 0.8;
  }

  // Calculate common prefix length
  let prefixLen = 0;
  const minLen = Math.min(aLower.length, bLower.length);
  for (let i = 0; i < minLen; i++) {
    if (aLower[i] === bLower[i]) prefixLen++;
    else break;
  }

  // Calculate common suffix length
  let suffixLen = 0;
  for (let i = 0; i < minLen; i++) {
    if (aLower[aLower.length - 1 - i] === bLower[bLower.length - 1 - i]) suffixLen++;
    else break;
  }

  // Normalize by max length
  const maxLen = Math.max(aLower.length, bLower.length);
  return (prefixLen + suffixLen) / (2 * maxLen);
}

/**
 * Find the most similar string from a list
 */
function findClosestMatch(target: string, candidates: string[]): string | null {
  if (candidates.length === 0) return null;

  let bestMatch: string | null = null;
  let bestScore = 0;
  const threshold = 0.3; // Minimum similarity to suggest

  for (const candidate of candidates) {
    const score = stringSimilarity(target, candidate);
    if (score > bestScore && score >= threshold) {
      bestScore = score;
      bestMatch = candidate;
    }
  }

  return bestMatch;
}

/**
 * Build enhanced error message for server not found
 */
function buildServerNotFoundError(requestedServer: string): string {
  const servers = listServers();
  const serverNames = servers.map(s => s.name);

  let errorMsg = `Server '${requestedServer}' not found.`;

  if (serverNames.length === 0) {
    errorMsg += ' No servers are configured. Check that servers.json is properly set up.';
    return errorMsg;
  }

  // Show available servers (limit to 5)
  const displayServers = serverNames.slice(0, 5);
  const hasMore = serverNames.length > 5;
  errorMsg += ` Available: ${displayServers.join(', ')}${hasMore ? ` (+${serverNames.length - 5} more)` : ''}.`;

  // Suggest closest match
  const closest = findClosestMatch(requestedServer, serverNames);
  if (closest) {
    errorMsg += ` Did you mean '${closest}'?`;
  }

  return errorMsg;
}

/**
 * Build enhanced error message for tool not found
 */
function buildToolNotFoundError(
  serverName: string,
  requestedTool: string,
  availableTools: string[]
): string {
  let errorMsg = `Tool '${requestedTool}' not found on server '${serverName}'.`;

  if (availableTools.length === 0) {
    errorMsg += ' No tools available on this server.';
    return errorMsg;
  }

  // Show available tools (limit to 5)
  const displayTools = availableTools.slice(0, 5);
  const hasMore = availableTools.length > 5;
  errorMsg += ` Available tools: ${displayTools.join(', ')}${hasMore ? ` (+${availableTools.length - 5} more)` : ''}.`;

  // Suggest closest match
  const closest = findClosestMatch(requestedTool, availableTools);
  if (closest) {
    errorMsg += ` Did you mean '${closest}'?`;
  }

  return errorMsg;
}

/**
 * Build enhanced error message for connection failures
 */
function buildConnectionError(serverName: string, originalError: string): string {
  let errorMsg = `Failed to connect to server '${serverName}': ${originalError}`;

  // Add troubleshooting hints based on error content
  const hints: string[] = [];

  if (originalError.includes('ENOENT') || originalError.includes('not found')) {
    hints.push('Check that the server command/binary exists and is in PATH');
  }
  if (originalError.includes('ECONNREFUSED')) {
    hints.push('Check that the server process is running');
  }
  if (originalError.includes('timeout') || originalError.includes('Timeout')) {
    hints.push('Server may be slow to start - try increasing timeout in servers.json');
  }
  if (originalError.includes('spawn')) {
    hints.push('Verify the server configuration in servers.json');
  }

  // Always add general hints
  hints.push('Is the server configured in servers.json?');

  if (hints.length > 0) {
    errorMsg += ` Troubleshooting: ${hints.join('; ')}.`;
  }

  return errorMsg;
}

/**
 * MCP Bridge HTTP server that allows sandboxed code to call
 * MCP tools via HTTP requests to localhost.
 */
export class MCPBridge {
  private readonly pool: ServerPool;
  private readonly preferredPort: number;
  private port: number;
  private readonly host: string;
  private server: Server | null = null;

  constructor(pool: ServerPool, config: MCPBridgeConfig = {}) {
    this.pool = pool;
    this.preferredPort = config.port ?? DEFAULT_PORT;
    this.port = this.preferredPort;
    this.host = config.host ?? DEFAULT_HOST;
  }

  /**
   * Start the HTTP bridge server with dynamic port allocation
   * Prefers the configured port but falls back to any available port
   * @returns Promise that resolves when server is listening
   */
  async start(): Promise<void> {
    // Find an available port, preferring the configured one
    this.port = await getPort({ port: this.preferredPort });

    return new Promise((resolve, reject) => {
      this.server = createServer((req, res) => {
        this.handleRequest(req, res);
      });

      this.server.on('error', async (err: NodeJS.ErrnoException) => {
        if (err.code === 'EADDRINUSE') {
          // Try to clean up stale process and retry once
          const cleaned = await cleanupStaleProcess(this.port);
          if (cleaned) {
            // Wait a bit for port to be released
            await new Promise((r) => setTimeout(r, 200));
            // Try to get the port again
            this.port = await getPort({ port: this.preferredPort });
            try {
              this.server?.listen(this.port, this.host, () => {
                resolve();
              });
              return;
            } catch {
              // Fall through to reject
            }
          }
        }
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
    // Set CORS headers - restricted to localhost since bridge only serves sandbox code
    res.setHeader('Content-Type', 'application/json');
    res.setHeader('Access-Control-Allow-Origin', `http://${this.host}:${this.port}`);
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
    let bodySize = 0;
    let responseSent = false;

    req.on('data', (chunk: Buffer) => {
      bodySize += chunk.length;
      if (bodySize > MAX_REQUEST_BODY_SIZE) {
        req.destroy();
        if (!responseSent) {
          responseSent = true;
          this.sendError(res, 413, `Request body too large. Maximum size is ${MAX_REQUEST_BODY_SIZE / 1024 / 1024}MB`);
        }
        return;
      }
      body += chunk.toString();
    });

    req.on('end', async () => {
      if (responseSent) return;
      try {
        // Parse request body
        let request: CallRequest;
        try {
          request = JSON.parse(body) as CallRequest;
        } catch {
          if (!responseSent) {
            responseSent = true;
            this.sendError(res, 400, 'Invalid JSON body');
          }
          return;
        }

        // Validate required fields
        if (!request.server || typeof request.server !== 'string') {
          if (!responseSent) {
            responseSent = true;
            this.sendError(res, 400, 'Missing or invalid "server" field');
          }
          return;
        }
        if (!request.tool || typeof request.tool !== 'string') {
          if (!responseSent) {
            responseSent = true;
            this.sendError(res, 400, 'Missing or invalid "tool" field');
          }
          return;
        }
        // Validate args is an object if provided
        if (request.args !== undefined && (typeof request.args !== 'object' || request.args === null || Array.isArray(request.args))) {
          if (!responseSent) {
            responseSent = true;
            this.sendError(res, 400, '"args" must be an object');
          }
          return;
        }

        // Get connection from pool
        let connection: MCPConnectionWithClient;
        try {
          connection = await this.pool.getConnection(request.server) as unknown as MCPConnectionWithClient;
        } catch (err) {
          if (!responseSent) {
            responseSent = true;
            const errorMsg = err instanceof Error ? err.message : String(err);
            // Check if this is a "server not found" type error
            if (errorMsg.includes('not found') || errorMsg.includes('No server configured') || errorMsg.includes('Unknown server')) {
              this.sendError(res, 404, buildServerNotFoundError(request.server));
            } else if (errorMsg.includes('403') || errorMsg.includes('Forbidden') || errorMsg.includes('PermissionError') || errorMsg.includes('Unauthorized')) {
              // HTTP 403 or permission error
              this.sendError(res, 403, `Authentication failed for server '${request.server}'. Check X-MCP-Client header and backend auth config.`);
            } else if (errorMsg.includes('503') || errorMsg.includes('Service Unavailable')) {
              // HTTP 503 or service unavailable
              this.sendError(res, 503, `Server '${request.server}' is unavailable. It may be starting up — retry in a few seconds.`);
            } else {
              this.sendError(res, 502, buildConnectionError(request.server, errorMsg));
            }
          }
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

          if (!responseSent) {
            responseSent = true;
            const response: CallResponse = {
              success: true,
              content: result.content,
              isError: result.isError,
            };

            res.writeHead(200);
            res.end(JSON.stringify(response));
          }
        } catch (err) {
          if (!responseSent) {
            responseSent = true;
            const errorMsg = err instanceof Error ? err.message : String(err);
            // Check if this is a "tool not found" type error
            if (errorMsg.includes('not found') || errorMsg.includes('Unknown tool') || errorMsg.includes('no such tool')) {
              // Try to get available tools for better error message
              try {
                const tools = await connection.getTools();
                const toolNames = tools.map(t => t.name);
                this.sendError(res, 404, buildToolNotFoundError(request.server, request.tool, toolNames));
              } catch {
                // If we can't get tools, fall back to basic error
                this.sendError(res, 500, `Tool '${request.tool}' not found on server '${request.server}'. Unable to fetch available tools.`);
              }
            } else if (errorMsg.includes('403') || errorMsg.includes('Forbidden') || errorMsg.includes('PermissionError') || errorMsg.includes('Unauthorized')) {
              this.sendError(res, 403, `Authorization failed calling '${request.tool}' on '${request.server}': ${errorMsg}. Ensure X-MCP-Client header is being sent.`);
            } else if (errorMsg.includes('503') || errorMsg.includes('504')) {
              this.sendError(res, 503, `Server '${request.server}' temporarily unavailable during tool '${request.tool}'. Retry after a short delay.`);
            } else {
              this.sendError(res, 500, `[${request.server}.${request.tool}] Tool execution failed: ${errorMsg}`);
            }
          }
        } finally {
          // Release connection back to pool
          this.pool.releaseConnection(request.server);
        }
      } catch (err) {
        if (!responseSent) {
          responseSent = true;
          const errorMsg = err instanceof Error ? err.message : String(err);
          this.sendError(res, 500, `Internal error: ${errorMsg}`);
        }
      }
    });

    req.on('error', (err) => {
      if (!responseSent) {
        responseSent = true;
        this.sendError(res, 400, `Request error: ${err.message}`);
      }
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
