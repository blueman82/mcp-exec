/**
 * Transport-agnostic MCP tool dispatch handler.
 * Extracted from MCPBridge so it can be reused by the fd transport
 * without coupling to HTTP concerns (status codes, CORS, headers).
 */
import type { ServerPool, MCPConnection } from 'mcp-exec-core';
import { getServerConfig, listServers } from 'mcp-exec-core';

/**
 * Request to call an MCP tool.
 */
export interface DispatchRequest {
  server: string;
  tool: string;
  args?: Record<string, unknown>;
}

/**
 * Response from dispatching an MCP tool call.
 * Mirrors the HTTP bridge CallResponse but is transport-independent.
 */
export interface DispatchResponse {
  success: boolean;
  content?: unknown[];
  error?: string;
  isError?: boolean;
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
  getTools: () => Promise<Array<{ name: string }>>;
}

/**
 * Calculate simple string similarity using common prefix/suffix length.
 * Returns a score between 0 and 1.
 */
function stringSimilarity(a: string, b: string): number {
  const aLower = a.toLowerCase();
  const bLower = b.toLowerCase();

  if (aLower === bLower) return 1;
  if (aLower.includes(bLower) || bLower.includes(aLower)) return 0.8;

  let prefixLen = 0;
  const minLen = Math.min(aLower.length, bLower.length);
  for (let i = 0; i < minLen; i++) {
    if (aLower[i] === bLower[i]) prefixLen++;
    else break;
  }

  let suffixLen = 0;
  for (let i = 0; i < minLen; i++) {
    if (aLower[aLower.length - 1 - i] === bLower[bLower.length - 1 - i]) suffixLen++;
    else break;
  }

  const maxLen = Math.max(aLower.length, bLower.length);
  return (prefixLen + suffixLen) / (2 * maxLen);
}

function findClosestMatch(target: string, candidates: string[]): string | null {
  if (candidates.length === 0) return null;
  let bestMatch: string | null = null;
  let bestScore = 0;
  const threshold = 0.3;
  for (const candidate of candidates) {
    const score = stringSimilarity(target, candidate);
    if (score > bestScore && score >= threshold) {
      bestScore = score;
      bestMatch = candidate;
    }
  }
  return bestMatch;
}

function buildServerNotFoundError(requestedServer: string): string {
  const servers = listServers();
  const serverNames = servers.map(s => s.name);

  let msg = `Server '${requestedServer}' not found.`;
  if (serverNames.length === 0) {
    return msg + ' No servers are configured. Check that servers.json is properly set up.';
  }

  const display = serverNames.slice(0, 5);
  const hasMore = serverNames.length > 5;
  msg += ` Available: ${display.join(', ')}${hasMore ? ` (+${serverNames.length - 5} more)` : ''}.`;
  const closest = findClosestMatch(requestedServer, serverNames);
  if (closest) msg += ` Did you mean '${closest}'?`;
  return msg;
}

function buildToolNotFoundError(
  serverName: string,
  requestedTool: string,
  availableTools: string[]
): string {
  let msg = `Tool '${requestedTool}' not found on server '${serverName}'.`;
  if (availableTools.length === 0) return msg + ' No tools available on this server.';

  const display = availableTools.slice(0, 5);
  const hasMore = availableTools.length > 5;
  msg += ` Available tools: ${display.join(', ')}${hasMore ? ` (+${availableTools.length - 5} more)` : ''}.`;
  const closest = findClosestMatch(requestedTool, availableTools);
  if (closest) msg += ` Did you mean '${closest}'?`;
  return msg;
}

function buildConnectionError(serverName: string, originalError: string): string {
  let msg = `Failed to connect to server '${serverName}': ${originalError}`;
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
  hints.push('Is the server configured in servers.json?');
  if (hints.length > 0) msg += ` Troubleshooting: ${hints.join('; ')}.`;
  return msg;
}

/**
 * Dispatch a single MCP tool call using the given ServerPool.
 * All error details are embedded in the returned DispatchResponse.error string.
 * Never throws — errors are always surface as { success: false, error }.
 */
export async function dispatchToolCall(
  pool: ServerPool,
  request: DispatchRequest
): Promise<DispatchResponse> {
  let connection: MCPConnectionWithClient | undefined;

  try {
    connection = await pool.getConnection(request.server) as unknown as MCPConnectionWithClient;
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    let errorMsg: string;
    if (
      msg.includes('not found') ||
      msg.includes('No server configured') ||
      msg.includes('Unknown server')
    ) {
      errorMsg = buildServerNotFoundError(request.server);
    } else if (
      msg.includes('403') ||
      msg.includes('Forbidden') ||
      msg.includes('PermissionError') ||
      msg.includes('Unauthorized')
    ) {
      errorMsg = `Authentication failed for server '${request.server}'. Check the server's auth headers in servers.json.`;
    } else if (msg.includes('503') || msg.includes('Service Unavailable')) {
      errorMsg = `Server '${request.server}' is unavailable. It may be starting up — retry in a few seconds.`;
    } else {
      errorMsg = buildConnectionError(request.server, msg);
    }
    return { success: false, error: errorMsg };
  }

  try {
    const serverConfig = getServerConfig(request.server);
    const defaultTimeout = process.env.MCP_DEFAULT_TIMEOUT
      ? parseInt(process.env.MCP_DEFAULT_TIMEOUT, 10)
      : undefined;
    const timeout = serverConfig?.timeout ?? defaultTimeout;

    const result = await connection.client.callTool(
      { name: request.tool, arguments: request.args ?? {} },
      undefined,
      timeout ? { timeout } : undefined
    );

    pool.releaseConnection(request.server);
    return { success: true, content: result.content, isError: result.isError };
  } catch (err) {
    pool.releaseConnection(request.server);
    const msg = err instanceof Error ? err.message : String(err);

    let errorMsg: string;
    if (
      msg.includes('not found') ||
      msg.includes('Unknown tool') ||
      msg.includes('no such tool')
    ) {
      // Try to get available tools for better error message
      try {
        const tools = await connection.getTools();
        const toolNames = tools.map(t => t.name);
        errorMsg = buildToolNotFoundError(request.server, request.tool, toolNames);
      } catch {
        errorMsg = `Tool '${request.tool}' not found on server '${request.server}'. Unable to fetch available tools.`;
      }
    } else if (
      msg.includes('403') ||
      msg.includes('Forbidden') ||
      msg.includes('PermissionError') ||
      msg.includes('Unauthorized')
    ) {
      errorMsg = `Authorization failed calling '${request.tool}' on '${request.server}': ${msg}. Check the server's auth headers in servers.json.`;
    } else if (
      msg.includes('503') ||
      msg.includes('504') ||
      msg.includes('Gateway')
    ) {
      errorMsg = `Server '${request.server}' temporarily unavailable during tool '${request.tool}'. Retry after a short delay.`;
    } else {
      errorMsg = `[${request.server}.${request.tool}] Tool execution failed: ${msg}`;
    }

    return { success: false, error: errorMsg };
  }
}
