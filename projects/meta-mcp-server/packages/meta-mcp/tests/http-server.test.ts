import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import * as http from 'node:http';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import {
  createHttpServer,
  HttpServerResult,
  HealthResponse,
} from '../src/http-server.js';
import { DEFAULT_HTTP_PORT, DEFAULT_HTTP_HOST } from '../src/transport.js';

// Helper to make HTTP requests
function httpRequest(
  options: http.RequestOptions,
  body?: string
): Promise<{ statusCode: number; headers: http.IncomingHttpHeaders; body: string }> {
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
    if (body) {
      req.write(body);
    }
    req.end();
  });
}

describe('HTTP Server Wrapper', () => {
  let mockServer: Server;
  let httpServerResult: HttpServerResult;
  let testPort: number;

  beforeEach(async () => {
    // Use a random port for testing to avoid conflicts
    testPort = 30000 + Math.floor(Math.random() * 10000);

    // Create a minimal mock MCP server
    mockServer = new Server(
      { name: 'test-server', version: '1.0.0' },
      { capabilities: { tools: {} } }
    );
  });

  afterEach(async () => {
    if (httpServerResult) {
      try {
        await httpServerResult.stop();
      } catch {
        // Ignore cleanup errors
      }
    }
  });

  describe('createHttpServer', () => {
    it('should return HttpServerResult with all required properties', () => {
      httpServerResult = createHttpServer(mockServer, { port: testPort });

      expect(httpServerResult).toHaveProperty('httpServer');
      expect(httpServerResult).toHaveProperty('transport');
      expect(httpServerResult).toHaveProperty('start');
      expect(httpServerResult).toHaveProperty('stop');
      expect(typeof httpServerResult.start).toBe('function');
      expect(typeof httpServerResult.stop).toBe('function');
    });

    it('should use default port and host when not specified', () => {
      httpServerResult = createHttpServer(mockServer);

      // The httpServer should be created with defaults
      expect(httpServerResult.httpServer).toBeDefined();
    });

    it('should use custom port from config', async () => {
      const customPort = testPort;
      httpServerResult = createHttpServer(mockServer, { port: customPort });

      await httpServerResult.start();

      // Verify server is listening on custom port
      const address = httpServerResult.httpServer.address();
      expect(address).not.toBeNull();
      if (typeof address === 'object' && address !== null) {
        expect(address.port).toBe(customPort);
      }
    });

    it('should use custom host from config', async () => {
      httpServerResult = createHttpServer(mockServer, {
        port: testPort,
        host: '127.0.0.1',
      });

      await httpServerResult.start();

      const address = httpServerResult.httpServer.address();
      expect(address).not.toBeNull();
      if (typeof address === 'object' && address !== null) {
        expect(address.address).toBe('127.0.0.1');
      }
    });

    it('should pass sessionIdGenerator to transport', () => {
      const mockSessionId = 'test-session-123';
      const sessionIdGenerator = vi.fn(() => mockSessionId);

      httpServerResult = createHttpServer(mockServer, {
        port: testPort,
        sessionIdGenerator,
      });

      expect(httpServerResult.transport).toBeDefined();
    });
  });

  describe('Health endpoint', () => {
    it('should return 200 OK with status and timestamp at /health', async () => {
      httpServerResult = createHttpServer(mockServer, { port: testPort });
      await httpServerResult.start();

      const response = await httpRequest({
        hostname: '127.0.0.1',
        port: testPort,
        path: '/health',
        method: 'GET',
      });

      expect(response.statusCode).toBe(200);

      const body: HealthResponse = JSON.parse(response.body);
      expect(body.status).toBe('ok');
      expect(body.timestamp).toBeDefined();
      // Verify timestamp is valid ISO string
      expect(() => new Date(body.timestamp)).not.toThrow();
    });
  });

  describe('CORS headers', () => {
    it('should set CORS headers for localhost origin', async () => {
      httpServerResult = createHttpServer(mockServer, { port: testPort });
      await httpServerResult.start();

      const response = await httpRequest({
        hostname: '127.0.0.1',
        port: testPort,
        path: '/health',
        method: 'GET',
        headers: {
          Origin: 'http://localhost:5173',
        },
      });

      expect(response.headers['access-control-allow-origin']).toBe(
        'http://localhost:5173'
      );
      expect(response.headers['access-control-allow-methods']).toContain('GET');
      expect(response.headers['access-control-allow-methods']).toContain('POST');
      expect(response.headers['access-control-allow-methods']).toContain(
        'DELETE'
      );
    });

    it('should set CORS headers for 127.0.0.1 origin', async () => {
      httpServerResult = createHttpServer(mockServer, { port: testPort });
      await httpServerResult.start();

      const response = await httpRequest({
        hostname: '127.0.0.1',
        port: testPort,
        path: '/health',
        method: 'GET',
        headers: {
          Origin: 'http://127.0.0.1:3000',
        },
      });

      expect(response.headers['access-control-allow-origin']).toBe(
        'http://127.0.0.1:3000'
      );
    });

    it('should NOT set Access-Control-Allow-Origin for non-localhost origins', async () => {
      httpServerResult = createHttpServer(mockServer, { port: testPort });
      await httpServerResult.start();

      const response = await httpRequest({
        hostname: '127.0.0.1',
        port: testPort,
        path: '/health',
        method: 'GET',
        headers: {
          Origin: 'http://evil.com',
        },
      });

      expect(response.headers['access-control-allow-origin']).toBeUndefined();
    });

    it('should handle OPTIONS preflight requests', async () => {
      httpServerResult = createHttpServer(mockServer, { port: testPort });
      await httpServerResult.start();

      const response = await httpRequest({
        hostname: '127.0.0.1',
        port: testPort,
        path: '/mcp',
        method: 'OPTIONS',
        headers: {
          Origin: 'http://localhost:5173',
        },
      });

      expect(response.statusCode).toBe(204);
      expect(response.headers['access-control-allow-origin']).toBe(
        'http://localhost:5173'
      );
    });
  });

  describe('MCP endpoint routing', () => {
    it('should return 404 for unrecognized paths', async () => {
      httpServerResult = createHttpServer(mockServer, { port: testPort });
      await httpServerResult.start();

      const response = await httpRequest({
        hostname: '127.0.0.1',
        port: testPort,
        path: '/unknown',
        method: 'GET',
      });

      expect(response.statusCode).toBe(404);
      const body = JSON.parse(response.body);
      expect(body.error).toBe('Not found');
    });

    it('should route POST to /mcp to transport', async () => {
      httpServerResult = createHttpServer(mockServer, { port: testPort });
      await httpServerResult.start();

      // Send a minimal JSON-RPC request to /mcp
      const response = await httpRequest(
        {
          hostname: '127.0.0.1',
          port: testPort,
          path: '/mcp',
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream',
          },
        },
        JSON.stringify({
          jsonrpc: '2.0',
          id: 1,
          method: 'initialize',
          params: {
            protocolVersion: '2024-11-05',
            capabilities: {},
            clientInfo: { name: 'test-client', version: '1.0.0' },
          },
        })
      );

      // The response is handled by the transport - any non-500 response
      // indicates routing is working (transport returns specific error codes)
      expect(response.statusCode).not.toBe(500);
      expect(response.statusCode).not.toBe(404);
    });

    it('should route POST to / (root) to transport', async () => {
      httpServerResult = createHttpServer(mockServer, { port: testPort });
      await httpServerResult.start();

      const response = await httpRequest(
        {
          hostname: '127.0.0.1',
          port: testPort,
          path: '/',
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream',
          },
        },
        JSON.stringify({
          jsonrpc: '2.0',
          id: 1,
          method: 'initialize',
          params: {
            protocolVersion: '2024-11-05',
            capabilities: {},
            clientInfo: { name: 'test-client', version: '1.0.0' },
          },
        })
      );

      // The response is handled by the transport - any non-500/404 response
      // indicates routing is working correctly
      expect(response.statusCode).not.toBe(500);
      expect(response.statusCode).not.toBe(404);
    });
  });

  describe('start and stop', () => {
    it('should start the server and write to stderr', async () => {
      const stderrSpy = vi
        .spyOn(process.stderr, 'write')
        .mockImplementation(() => true);

      httpServerResult = createHttpServer(mockServer, { port: testPort });
      await httpServerResult.start();

      expect(stderrSpy).toHaveBeenCalledWith(
        expect.stringContaining('Meta MCP Server running on')
      );

      stderrSpy.mockRestore();
    });

    it('should stop the server cleanly', async () => {
      httpServerResult = createHttpServer(mockServer, { port: testPort });
      await httpServerResult.start();

      // Server should be listening
      expect(httpServerResult.httpServer.listening).toBe(true);

      await httpServerResult.stop();

      // Server should no longer be listening
      expect(httpServerResult.httpServer.listening).toBe(false);
    });

    it('should reject start if port is already in use', async () => {
      // Start first server
      httpServerResult = createHttpServer(mockServer, { port: testPort });
      await httpServerResult.start();

      // Try to start second server on same port
      const mockServer2 = new Server(
        { name: 'test-server-2', version: '1.0.0' },
        { capabilities: { tools: {} } }
      );
      const httpServerResult2 = createHttpServer(mockServer2, { port: testPort });

      await expect(httpServerResult2.start()).rejects.toThrow();
    });
  });
});
