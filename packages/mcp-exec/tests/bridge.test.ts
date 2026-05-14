/**
 * Unit tests for MCPBridge
 * Tests HTTP endpoint POST /call, request/response format, ServerPool usage
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { MCPBridge, type CallRequest, type CallResponse } from '../src/bridge/server.js';
import type { ServerPool } from '@justanothermldude/mcp-exec-oss-core';

// Helper to create mock pool
function createMockPool(overrides: Partial<ServerPool> = {}): ServerPool {
  return {
    getConnection: vi.fn().mockResolvedValue({
      client: {
        callTool: vi.fn().mockResolvedValue({
          content: [{ type: 'text', text: 'Tool result' }],
          isError: false,
        }),
      },
    }),
    releaseConnection: vi.fn(),
    shutdown: vi.fn().mockResolvedValue(undefined),
    getActiveCount: vi.fn().mockReturnValue(0),
    runCleanup: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  } as unknown as ServerPool;
}

// Helper to make HTTP requests using bridge's actual port
async function makeRequest(
  bridge: MCPBridge,
  method: string,
  path: string,
  body?: unknown
): Promise<{ status: number; body: CallResponse }> {
  const port = bridge.getPort();
  const response = await fetch(`http://127.0.0.1:${port}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });

  const responseBody = await response.json() as CallResponse;
  return { status: response.status, body: responseBody };
}

describe('MCPBridge', () => {
  let bridge: MCPBridge;
  let mockPool: ServerPool;
  const testPort = 3100; // Use non-default port for testing

  beforeEach(() => {
    mockPool = createMockPool();
    bridge = new MCPBridge(mockPool, { port: testPort });
  });

  afterEach(async () => {
    if (bridge.isRunning()) {
      await bridge.stop();
    }
  });

  describe('constructor', () => {
    it('should create bridge with default config', () => {
      const defaultBridge = new MCPBridge(mockPool);
      expect(defaultBridge.getPort()).toBe(3000);
      expect(defaultBridge.getHost()).toBe('127.0.0.1');
    });

    it('should create bridge with custom config', () => {
      const customBridge = new MCPBridge(mockPool, { port: 4000, host: '0.0.0.0' });
      expect(customBridge.getPort()).toBe(4000);
      expect(customBridge.getHost()).toBe('0.0.0.0');
    });
  });

  describe('start/stop', () => {
    it('should start and stop server', async () => {
      expect(bridge.isRunning()).toBe(false);

      await bridge.start();
      expect(bridge.isRunning()).toBe(true);

      await bridge.stop();
      expect(bridge.isRunning()).toBe(false);
    });

    it('should handle multiple stop calls', async () => {
      await bridge.start();
      await bridge.stop();
      await bridge.stop(); // Should not throw
      expect(bridge.isRunning()).toBe(false);
    });
  });

  describe('GET /health', () => {
    it('should return health status', async () => {
      await bridge.start();
      const port = bridge.getPort();

      const response = await fetch(`http://127.0.0.1:${port}/health`);
      const body = await response.json() as { status: string; timestamp: string };

      expect(response.status).toBe(200);
      expect(body.status).toBe('ok');
      expect(body.timestamp).toBeDefined();
    });
  });

  describe('POST /call', () => {
    beforeEach(async () => {
      await bridge.start();
    });

    it('should call tool and return result', async () => {
      const request: CallRequest = {
        server: 'test-server',
        tool: 'test-tool',
        args: { key: 'value' },
      };

      const { status, body } = await makeRequest(bridge, 'POST', '/call', request);

      expect(status).toBe(200);
      expect(body.success).toBe(true);
      expect(body.content).toBeDefined();
      expect(mockPool.getConnection).toHaveBeenCalledWith('test-server');
      expect(mockPool.releaseConnection).toHaveBeenCalledWith('test-server');
    });

    it('should return 400 for invalid JSON', async () => {
      const port = bridge.getPort();
      const response = await fetch(`http://127.0.0.1:${port}/call`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: 'invalid json{',
      });

      expect(response.status).toBe(400);
      const body = await response.json() as CallResponse;
      expect(body.success).toBe(false);
      expect(body.error).toContain('Invalid JSON');
    });

    it('should return 400 for missing server field', async () => {
      const request = { tool: 'test-tool' };
      const { status, body } = await makeRequest(bridge, 'POST', '/call', request);

      expect(status).toBe(400);
      expect(body.success).toBe(false);
      expect(body.error).toContain('server');
    });

    it('should return 400 for missing tool field', async () => {
      const request = { server: 'test-server' };
      const { status, body } = await makeRequest(bridge, 'POST', '/call', request);

      expect(status).toBe(400);
      expect(body.success).toBe(false);
      expect(body.error).toContain('tool');
    });

    it('should return 502 when connection fails', async () => {
      mockPool.getConnection = vi.fn().mockRejectedValue(new Error('Connection failed'));

      const request: CallRequest = {
        server: 'failing-server',
        tool: 'test-tool',
      };

      const { status, body } = await makeRequest(bridge, 'POST', '/call', request);

      expect(status).toBe(502);
      expect(body.success).toBe(false);
      expect(body.error).toContain('Failed to connect');
    });

    it('should return 500 when tool execution fails', async () => {
      mockPool.getConnection = vi.fn().mockResolvedValue({
        client: {
          callTool: vi.fn().mockRejectedValue(new Error('Tool execution error')),
        },
      });

      const request: CallRequest = {
        server: 'test-server',
        tool: 'failing-tool',
      };

      const { status, body } = await makeRequest(bridge, 'POST', '/call', request);

      expect(status).toBe(500);
      expect(body.success).toBe(false);
      expect(body.error).toContain('Tool execution failed');
    });

    it('should pass isError from tool result', async () => {
      mockPool.getConnection = vi.fn().mockResolvedValue({
        client: {
          callTool: vi.fn().mockResolvedValue({
            content: [{ type: 'text', text: 'Error from tool' }],
            isError: true,
          }),
        },
      });

      const request: CallRequest = {
        server: 'test-server',
        tool: 'error-tool',
      };

      const { status, body } = await makeRequest(bridge, 'POST', '/call', request);

      expect(status).toBe(200);
      expect(body.success).toBe(true);
      expect(body.isError).toBe(true);
    });

    it('should handle requests without args', async () => {
      const request: CallRequest = {
        server: 'test-server',
        tool: 'no-args-tool',
      };

      const { status, body } = await makeRequest(bridge, 'POST', '/call', request);

      expect(status).toBe(200);
      expect(body.success).toBe(true);
    });
  });

  describe('ServerPool integration', () => {
    beforeEach(async () => {
      await bridge.start();
    });

    it('should call pool.getConnection with correct server name', async () => {
      const request: CallRequest = {
        server: 'my-mcp-server',
        tool: 'some-tool',
      };

      await makeRequest(bridge, 'POST', '/call', request);

      expect(mockPool.getConnection).toHaveBeenCalledWith('my-mcp-server');
    });

    it('should call pool.releaseConnection after tool call completes', async () => {
      const request: CallRequest = {
        server: 'release-test-server',
        tool: 'some-tool',
      };

      await makeRequest(bridge, 'POST', '/call', request);

      expect(mockPool.releaseConnection).toHaveBeenCalledWith('release-test-server');
    });

    it('should release connection even when tool fails', async () => {
      mockPool.getConnection = vi.fn().mockResolvedValue({
        client: {
          callTool: vi.fn().mockRejectedValue(new Error('Tool failed')),
        },
      });

      const request: CallRequest = {
        server: 'error-server',
        tool: 'failing-tool',
      };

      await makeRequest(bridge, 'POST', '/call', request);

      expect(mockPool.releaseConnection).toHaveBeenCalledWith('error-server');
    });
  });

  describe('CORS headers', () => {
    beforeEach(async () => {
      await bridge.start();
    });

    it('should set CORS headers', async () => {
      const port = bridge.getPort();
      const response = await fetch(`http://127.0.0.1:${port}/health`);

      // CORS origin is restricted to localhost (security fix)
      expect(response.headers.get('Access-Control-Allow-Origin')).toBe(`http://127.0.0.1:${port}`);
      expect(response.headers.get('Content-Type')).toBe('application/json');
    });

    it('should handle OPTIONS preflight', async () => {
      const port = bridge.getPort();
      const response = await fetch(`http://127.0.0.1:${port}/call`, {
        method: 'OPTIONS',
      });

      expect(response.status).toBe(204);
      expect(response.headers.get('Access-Control-Allow-Methods')).toContain('POST');
    });
  });

  describe('404 handling', () => {
    beforeEach(async () => {
      await bridge.start();
    });

    it('should return 404 for unknown paths', async () => {
      const port = bridge.getPort();
      const response = await fetch(`http://127.0.0.1:${port}/unknown`);

      expect(response.status).toBe(404);
      const body = await response.json() as CallResponse;
      expect(body.success).toBe(false);
      expect(body.error).toBe('Not Found');
    });

    it('should return 404 for GET /call', async () => {
      const port = bridge.getPort();
      const response = await fetch(`http://127.0.0.1:${port}/call`);

      expect(response.status).toBe(404);
    });
  });
});
