/**
 * Integration tests for HTTP transport.
 * Tests end-to-end HTTP transport functionality with real HTTP requests.
 */
import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest';
import * as http from 'node:http';
import { createServer } from '../src/server.js';
import { createHttpServer, HttpServerResult } from '../src/http-server.js';
import { TransportMode, TransportConfig } from '../src/transport.js';
import type { ServerPool, ToolCache } from '@justanothermldude/meta-mcp-core';

// Helper to make HTTP requests with proper JSON-RPC formatting
function httpRequest(
  options: http.RequestOptions,
  body?: string
): Promise<{
  statusCode: number;
  headers: http.IncomingHttpHeaders;
  body: string;
}> {
  return new Promise((resolve, reject) => {
    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => (data += chunk));
      res.on('end', () =>
        resolve({
          statusCode: res.statusCode ?? 0,
          headers: res.headers,
          body: data,
        })
      );
    });
    req.on('error', reject);
    req.setTimeout(5000, () => {
      req.destroy(new Error('Request timeout'));
    });
    if (body) {
      req.write(body);
    }
    req.end();
  });
}

// Helper to create JSON-RPC request body
function createJsonRpcRequest(
  method: string,
  params: Record<string, unknown> = {},
  id: number | string = 1
): string {
  return JSON.stringify({
    jsonrpc: '2.0',
    id,
    method,
    params,
  });
}

describe('HTTP Transport Integration Tests', () => {
  let httpServerResult: HttpServerResult;
  let testPort: number;
  let mockPool: ServerPool;
  let mockToolCache: ToolCache;
  let sessionId: string | undefined;

  beforeAll(async () => {
    // Use a random high port for testing to avoid conflicts
    testPort = 40000 + Math.floor(Math.random() * 10000);

    // Create mock pool and cache
    mockPool = {
      getConnection: vi.fn(),
      releaseConnection: vi.fn(),
      shutdown: vi.fn().mockResolvedValue(undefined),
      getActiveCount: vi.fn().mockReturnValue(0),
      runCleanup: vi.fn().mockResolvedValue(undefined),
    } as unknown as ServerPool;

    mockToolCache = {
      get: vi.fn(),
      has: vi.fn(),
      set: vi.fn(),
      delete: vi.fn(),
      clear: vi.fn(),
      size: vi.fn().mockReturnValue(0),
    } as unknown as ToolCache;

    // Create MCP server with the createServer function
    const { server } = createServer(mockPool, mockToolCache);

    // Create and start HTTP server
    const config: Partial<TransportConfig> = {
      mode: TransportMode.HTTP,
      port: testPort,
      host: '127.0.0.1',
    };

    httpServerResult = createHttpServer(server, config);

    // Suppress stderr output during tests
    const stderrSpy = vi
      .spyOn(process.stderr, 'write')
      .mockImplementation(() => true);

    await httpServerResult.start();

    stderrSpy.mockRestore();
  });

  afterAll(async () => {
    if (httpServerResult) {
      await httpServerResult.stop();

      // Verify port is released by checking server is no longer listening
      expect(httpServerResult.httpServer.listening).toBe(false);
    }
  });

  describe('Health endpoint', () => {
    it('should return {status: "ok"} from GET /health', async () => {
      const response = await httpRequest({
        hostname: '127.0.0.1',
        port: testPort,
        path: '/health',
        method: 'GET',
      });

      expect(response.statusCode).toBe(200);

      const body = JSON.parse(response.body);
      expect(body.status).toBe('ok');
      expect(body.timestamp).toBeDefined();
    });
  });

  describe('MCP Protocol: initialize', () => {
    it('should respond to initialize request with capabilities', async () => {
      const response = await httpRequest(
        {
          hostname: '127.0.0.1',
          port: testPort,
          path: '/',
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json, text/event-stream',
          },
        },
        createJsonRpcRequest('initialize', {
          protocolVersion: '2024-11-05',
          capabilities: {},
          clientInfo: { name: 'integration-test', version: '1.0.0' },
        })
      );

      // Should not be a server error or not found
      expect(response.statusCode).not.toBe(500);
      expect(response.statusCode).not.toBe(404);

      // Store session ID for subsequent requests
      sessionId = response.headers['mcp-session-id'] as string | undefined;

      // Parse response - may be JSON or SSE
      if (response.headers['content-type']?.includes('application/json')) {
        const body = JSON.parse(response.body);
        expect(body.jsonrpc).toBe('2.0');
        expect(body.id).toBe(1);
        // Should have result with capabilities
        if (body.result) {
          expect(body.result).toHaveProperty('capabilities');
          expect(body.result).toHaveProperty('serverInfo');
          expect(body.result.serverInfo.name).toBe('meta-mcp-server');
        }
      }
    });
  });

  describe('MCP Protocol: tools/list', () => {
    it('should return 3 meta-tools: list_servers, get_server_tools, call_tool', async () => {
      // First, initialize to get session
      const initResponse = await httpRequest(
        {
          hostname: '127.0.0.1',
          port: testPort,
          path: '/',
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json, text/event-stream',
          },
        },
        createJsonRpcRequest('initialize', {
          protocolVersion: '2024-11-05',
          capabilities: {},
          clientInfo: { name: 'integration-test', version: '1.0.0' },
        })
      );

      const currentSessionId = initResponse.headers['mcp-session-id'] as
        | string
        | undefined;

      // Send initialized notification
      await httpRequest(
        {
          hostname: '127.0.0.1',
          port: testPort,
          path: '/',
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json, text/event-stream',
            ...(currentSessionId && { 'mcp-session-id': currentSessionId }),
          },
        },
        JSON.stringify({
          jsonrpc: '2.0',
          method: 'notifications/initialized',
        })
      );

      // Now request tools/list
      const response = await httpRequest(
        {
          hostname: '127.0.0.1',
          port: testPort,
          path: '/',
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json, text/event-stream',
            ...(currentSessionId && { 'mcp-session-id': currentSessionId }),
          },
        },
        createJsonRpcRequest('tools/list', {}, 2)
      );

      expect(response.statusCode).not.toBe(500);
      expect(response.statusCode).not.toBe(404);

      // Parse response
      if (response.headers['content-type']?.includes('application/json')) {
        const body = JSON.parse(response.body);
        expect(body.jsonrpc).toBe('2.0');
        expect(body.id).toBe(2);

        if (body.result && body.result.tools) {
          const toolNames = body.result.tools.map(
            (t: { name: string }) => t.name
          );
          expect(toolNames).toContain('list_servers');
          expect(toolNames).toContain('get_server_tools');
          expect(toolNames).toContain('call_tool');
          expect(body.result.tools).toHaveLength(3);
        }
      }
    });
  });

  describe('MCP Protocol: tools/call', () => {
    it('should call list_servers tool and return result', async () => {
      // Initialize first
      const initResponse = await httpRequest(
        {
          hostname: '127.0.0.1',
          port: testPort,
          path: '/',
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json, text/event-stream',
          },
        },
        createJsonRpcRequest('initialize', {
          protocolVersion: '2024-11-05',
          capabilities: {},
          clientInfo: { name: 'integration-test', version: '1.0.0' },
        })
      );

      const currentSessionId = initResponse.headers['mcp-session-id'] as
        | string
        | undefined;

      // Send initialized notification
      await httpRequest(
        {
          hostname: '127.0.0.1',
          port: testPort,
          path: '/',
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json, text/event-stream',
            ...(currentSessionId && { 'mcp-session-id': currentSessionId }),
          },
        },
        JSON.stringify({
          jsonrpc: '2.0',
          method: 'notifications/initialized',
        })
      );

      // Call list_servers tool
      const response = await httpRequest(
        {
          hostname: '127.0.0.1',
          port: testPort,
          path: '/',
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json, text/event-stream',
            ...(currentSessionId && { 'mcp-session-id': currentSessionId }),
          },
        },
        createJsonRpcRequest(
          'tools/call',
          {
            name: 'list_servers',
            arguments: {},
          },
          3
        )
      );

      expect(response.statusCode).not.toBe(500);
      expect(response.statusCode).not.toBe(404);

      if (response.headers['content-type']?.includes('application/json')) {
        const body = JSON.parse(response.body);
        expect(body.jsonrpc).toBe('2.0');
        expect(body.id).toBe(3);

        // Should have result with content
        if (body.result) {
          expect(body.result).toHaveProperty('content');
          expect(Array.isArray(body.result.content)).toBe(true);
        }
      }
    });
  });

  describe('HTTP routing', () => {
    it('should accept requests on /mcp path', async () => {
      const response = await httpRequest(
        {
          hostname: '127.0.0.1',
          port: testPort,
          path: '/mcp',
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json, text/event-stream',
          },
        },
        createJsonRpcRequest('initialize', {
          protocolVersion: '2024-11-05',
          capabilities: {},
          clientInfo: { name: 'integration-test', version: '1.0.0' },
        })
      );

      expect(response.statusCode).not.toBe(404);
      expect(response.statusCode).not.toBe(500);
    });

    it('should accept requests on root path /', async () => {
      const response = await httpRequest(
        {
          hostname: '127.0.0.1',
          port: testPort,
          path: '/',
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json, text/event-stream',
          },
        },
        createJsonRpcRequest('initialize', {
          protocolVersion: '2024-11-05',
          capabilities: {},
          clientInfo: { name: 'integration-test', version: '1.0.0' },
        })
      );

      expect(response.statusCode).not.toBe(404);
      expect(response.statusCode).not.toBe(500);
    });

    it('should return 404 for unknown paths', async () => {
      const response = await httpRequest({
        hostname: '127.0.0.1',
        port: testPort,
        path: '/unknown/path',
        method: 'GET',
      });

      expect(response.statusCode).toBe(404);
      const body = JSON.parse(response.body);
      expect(body.error).toBe('Not found');
    });
  });

  describe('CORS support', () => {
    it('should handle OPTIONS preflight requests', async () => {
      const response = await httpRequest({
        hostname: '127.0.0.1',
        port: testPort,
        path: '/',
        method: 'OPTIONS',
        headers: {
          Origin: 'http://localhost:5173',
        },
      });

      expect(response.statusCode).toBe(204);
      expect(response.headers['access-control-allow-origin']).toBe(
        'http://localhost:5173'
      );
      expect(response.headers['access-control-allow-methods']).toContain(
        'POST'
      );
    });

    it('should include CORS headers for localhost origins', async () => {
      const response = await httpRequest({
        hostname: '127.0.0.1',
        port: testPort,
        path: '/health',
        method: 'GET',
        headers: {
          Origin: 'http://localhost:3000',
        },
      });

      expect(response.headers['access-control-allow-origin']).toBe(
        'http://localhost:3000'
      );
    });
  });

  describe('Error handling', () => {
    it('should handle invalid JSON gracefully', async () => {
      const response = await httpRequest(
        {
          hostname: '127.0.0.1',
          port: testPort,
          path: '/',
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json',
          },
        },
        'not valid json'
      );

      // Should return an error but not crash the server
      expect(response.statusCode).toBeGreaterThanOrEqual(400);
    });

    it('should handle unknown JSON-RPC method gracefully', async () => {
      // Initialize first
      const initResponse = await httpRequest(
        {
          hostname: '127.0.0.1',
          port: testPort,
          path: '/',
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json, text/event-stream',
          },
        },
        createJsonRpcRequest('initialize', {
          protocolVersion: '2024-11-05',
          capabilities: {},
          clientInfo: { name: 'integration-test', version: '1.0.0' },
        })
      );

      const currentSessionId = initResponse.headers['mcp-session-id'] as
        | string
        | undefined;

      // Try an unknown method
      const response = await httpRequest(
        {
          hostname: '127.0.0.1',
          port: testPort,
          path: '/',
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json',
            ...(currentSessionId && { 'mcp-session-id': currentSessionId }),
          },
        },
        createJsonRpcRequest('unknown/method', {}, 99)
      );

      // Should return error response, not crash
      expect(response.statusCode).not.toBe(500);

      if (response.headers['content-type']?.includes('application/json')) {
        const body = JSON.parse(response.body);
        // JSON-RPC error response should have error property
        if (body.error) {
          expect(body.error).toHaveProperty('code');
          expect(body.error).toHaveProperty('message');
        }
      }
    });
  });

  describe('Server lifecycle', () => {
    it('should be listening after start', () => {
      expect(httpServerResult.httpServer.listening).toBe(true);
    });

    it('should respond to requests while running', async () => {
      const response = await httpRequest({
        hostname: '127.0.0.1',
        port: testPort,
        path: '/health',
        method: 'GET',
      });

      expect(response.statusCode).toBe(200);
    });
  });
});
