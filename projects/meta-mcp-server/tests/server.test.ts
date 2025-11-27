import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { createServer } from '../src/server.js';
import type { ServerPool } from '../src/pool/index.js';
import type { ToolCache } from '../src/tools/tool-cache.js';
import {
  listServersTool,
  getServerToolsTool,
  callToolTool,
} from '../src/tools/index.js';

// Mock Server from SDK
vi.mock('@modelcontextprotocol/sdk/server/index.js', () => {
  const MockServer = vi.fn().mockImplementation(() => ({
    setRequestHandler: vi.fn(),
    connect: vi.fn().mockResolvedValue(undefined),
    close: vi.fn().mockResolvedValue(undefined),
  }));
  return { Server: MockServer };
});

// Mock StdioServerTransport
vi.mock('@modelcontextprotocol/sdk/server/stdio.js', () => ({
  StdioServerTransport: vi.fn().mockImplementation(() => ({})),
}));

describe('MCP Server', () => {
  let mockPool: ServerPool;
  let mockToolCache: ToolCache;

  beforeEach(() => {
    vi.clearAllMocks();

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
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('createServer', () => {
    it('should create server instance', () => {
      const { server } = createServer(mockPool, mockToolCache);
      expect(server).toBeDefined();
      expect(Server).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'meta-mcp-server',
          version: expect.any(String),
        }),
        expect.objectContaining({
          capabilities: { tools: {} },
        })
      );
    });

    it('should register all tool handlers', () => {
      const { server } = createServer(mockPool, mockToolCache);
      // setRequestHandler should be called for ListTools and CallTool
      expect(server.setRequestHandler).toHaveBeenCalledTimes(2);
    });
  });

  describe('ListToolsRequest handler', () => {
    it('should return 3 tools registered', async () => {
      const { listToolsHandler } = createServer(mockPool, mockToolCache);
      const result = await listToolsHandler();

      expect(result.tools).toHaveLength(3);
      expect(result.tools.map((t) => t.name)).toEqual([
        'list_servers',
        'get_server_tools',
        'call_tool',
      ]);
    });

    it('should include correct tool definitions', async () => {
      const { listToolsHandler } = createServer(mockPool, mockToolCache);
      const result = await listToolsHandler();

      expect(result.tools[0]).toEqual(listServersTool);
      expect(result.tools[1]).toEqual(getServerToolsTool);
      expect(result.tools[2]).toEqual(callToolTool);
    });
  });

  describe('CallToolRequest handler', () => {
    it('should route list_servers correctly', async () => {
      const { callToolHandler } = createServer(mockPool, mockToolCache);
      const result = await callToolHandler({
        name: 'list_servers',
        arguments: {},
      });

      expect(result.content).toBeDefined();
      expect(result.content[0]).toHaveProperty('type', 'text');
    });

    it('should throw for unknown tool', async () => {
      const { callToolHandler } = createServer(mockPool, mockToolCache);

      await expect(
        callToolHandler({
          name: 'unknown_tool',
          arguments: {},
        })
      ).rejects.toThrow("Tool 'unknown_tool' not found");
    });
  });

  describe('graceful shutdown', () => {
    it('should shutdown pool on close', async () => {
      const { shutdown } = createServer(mockPool, mockToolCache);
      await shutdown();

      expect(mockPool.shutdown).toHaveBeenCalled();
      expect(mockToolCache.clear).toHaveBeenCalled();
    });
  });
});
