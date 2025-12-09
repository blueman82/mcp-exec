import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as fs from 'fs';
import { callToolHandler, callToolTool, ToolNotFoundError, ServerNotFoundError } from '../../src/tools/call-tool.js';
import { ToolCache } from '../../src/tools/tool-cache.js';
import { clearCache } from '../../src/registry/index.js';
import type { ToolDefinition } from '../../src/types/index.js';
import { ConnectionState } from '../../src/types/index.js';

vi.mock('fs');

const testBackendsJson = {
  mcpServers: {
    'filesystem': {
      type: 'stdio',
      command: 'node',
      args: ['server.js'],
    },
    'github': {
      type: 'stdio',
      command: 'npx',
      args: ['@modelcontextprotocol/server-github'],
    },
  }
};

const mockTools: ToolDefinition[] = [
  {
    name: 'read_file',
    description: 'Read a file from disk',
    inputSchema: {
      type: 'object',
      properties: {
        path: { type: 'string', description: 'File path' }
      },
      required: ['path']
    },
    serverId: 'filesystem'
  },
  {
    name: 'write_file',
    description: 'Write content to a file',
    inputSchema: {
      type: 'object',
      properties: {
        path: { type: 'string', description: 'File path' },
        content: { type: 'string', description: 'File content' }
      },
      required: ['path', 'content']
    },
    serverId: 'filesystem'
  },
];

interface MockConnection {
  serverId: string;
  state: typeof ConnectionState.Connected;
  connect: ReturnType<typeof vi.fn>;
  disconnect: ReturnType<typeof vi.fn>;
  isConnected: ReturnType<typeof vi.fn>;
  getTools: ReturnType<typeof vi.fn>;
  client: {
    callTool: ReturnType<typeof vi.fn>;
  };
}

function createMockConnection(serverId: string, tools: ToolDefinition[]): MockConnection {
  return {
    serverId,
    state: ConnectionState.Connected,
    connect: vi.fn().mockResolvedValue(undefined),
    disconnect: vi.fn().mockResolvedValue(undefined),
    isConnected: vi.fn().mockReturnValue(true),
    getTools: vi.fn().mockResolvedValue(tools),
    client: {
      callTool: vi.fn().mockResolvedValue({
        content: [{ type: 'text', text: 'file contents here' }]
      }),
    },
  };
}

describe('call_tool tool', () => {
  let mockPool: { getConnection: ReturnType<typeof vi.fn>; releaseConnection: ReturnType<typeof vi.fn> };
  let toolCache: ToolCache;

  beforeEach(() => {
    vi.resetAllMocks();
    clearCache();
    process.env.SERVERS_CONFIG = '/path/to/servers.json';
    vi.mocked(fs.readFileSync).mockReturnValue(JSON.stringify(testBackendsJson));
    vi.mocked(fs.existsSync).mockReturnValue(true);

    mockPool = {
      getConnection: vi.fn(),
      releaseConnection: vi.fn(),
    };
    toolCache = new ToolCache();
  });

  afterEach(() => {
    delete process.env.SERVERS_CONFIG;
    clearCache();
  });

  it('routes to correct server', async () => {
    const mockConnection = createMockConnection('filesystem', mockTools);
    mockPool.getConnection.mockResolvedValue(mockConnection);
    toolCache.set('filesystem', mockTools);

    await callToolHandler(
      { server_name: 'filesystem', tool_name: 'read_file', arguments: { path: '/test.txt' } },
      mockPool as any,
      toolCache
    );

    expect(mockPool.getConnection).toHaveBeenCalledWith('filesystem');
  });

  it('passes arguments correctly', async () => {
    const mockConnection = createMockConnection('filesystem', mockTools);
    mockPool.getConnection.mockResolvedValue(mockConnection);
    toolCache.set('filesystem', mockTools);

    const args = { path: '/test.txt' };
    await callToolHandler(
      { server_name: 'filesystem', tool_name: 'read_file', arguments: args },
      mockPool as any,
      toolCache
    );

    expect(mockConnection.client.callTool).toHaveBeenCalledWith(
      {
        name: 'read_file',
        arguments: args,
      },
      undefined, // resultSchema
      undefined  // requestOptions (no timeout in mock config)
    );
  });

  it('returns server response', async () => {
    const mockConnection = createMockConnection('filesystem', mockTools);
    mockConnection.client.callTool.mockResolvedValue({
      content: [{ type: 'text', text: 'test file content' }]
    });
    mockPool.getConnection.mockResolvedValue(mockConnection);
    toolCache.set('filesystem', mockTools);

    const result = await callToolHandler(
      { server_name: 'filesystem', tool_name: 'read_file', arguments: { path: '/test.txt' } },
      mockPool as any,
      toolCache
    );

    expect(result.content).toEqual([{ type: 'text', text: 'test file content' }]);
  });

  it('handles server errors', async () => {
    const mockConnection = createMockConnection('filesystem', mockTools);
    const serverError = new Error('Server processing failed');
    mockConnection.client.callTool.mockRejectedValue(serverError);
    mockPool.getConnection.mockResolvedValue(mockConnection);
    toolCache.set('filesystem', mockTools);

    await expect(
      callToolHandler(
        { server_name: 'filesystem', tool_name: 'read_file', arguments: { path: '/test.txt' } },
        mockPool as any,
        toolCache
      )
    ).rejects.toThrow('Server processing failed');
  });

  it('validates tool exists', async () => {
    const mockConnection = createMockConnection('filesystem', mockTools);
    mockPool.getConnection.mockResolvedValue(mockConnection);
    toolCache.set('filesystem', mockTools);

    await expect(
      callToolHandler(
        { server_name: 'filesystem', tool_name: 'unknown_tool', arguments: {} },
        mockPool as any,
        toolCache
      )
    ).rejects.toThrow(ToolNotFoundError);
  });

  it('throws ServerNotFoundError for unknown server', async () => {
    await expect(
      callToolHandler(
        { server_name: 'unknown-server', tool_name: 'some_tool', arguments: {} },
        mockPool as any,
        toolCache
      )
    ).rejects.toThrow(ServerNotFoundError);
  });

  it('releases connection after successful call', async () => {
    const mockConnection = createMockConnection('filesystem', mockTools);
    mockPool.getConnection.mockResolvedValue(mockConnection);
    toolCache.set('filesystem', mockTools);

    await callToolHandler(
      { server_name: 'filesystem', tool_name: 'read_file', arguments: { path: '/test.txt' } },
      mockPool as any,
      toolCache
    );

    expect(mockPool.releaseConnection).toHaveBeenCalledWith('filesystem');
  });

  it('releases connection after failed call', async () => {
    const mockConnection = createMockConnection('filesystem', mockTools);
    mockConnection.client.callTool.mockRejectedValue(new Error('fail'));
    mockPool.getConnection.mockResolvedValue(mockConnection);
    toolCache.set('filesystem', mockTools);

    await expect(
      callToolHandler(
        { server_name: 'filesystem', tool_name: 'read_file', arguments: { path: '/test.txt' } },
        mockPool as any,
        toolCache
      )
    ).rejects.toThrow();

    expect(mockPool.releaseConnection).toHaveBeenCalledWith('filesystem');
  });

  it('tool definition has correct structure', () => {
    expect(callToolTool.name).toBe('call_tool');
    expect(callToolTool.description).toBeDefined();
    expect(callToolTool.inputSchema).toBeDefined();
    expect(callToolTool.inputSchema.type).toBe('object');
    expect(callToolTool.inputSchema.properties).toHaveProperty('server_name');
    expect(callToolTool.inputSchema.properties).toHaveProperty('tool_name');
    expect(callToolTool.inputSchema.properties).toHaveProperty('arguments');
    expect(callToolTool.inputSchema.required).toContain('server_name');
    expect(callToolTool.inputSchema.required).toContain('tool_name');
  });

  it('passes timeout from server config to callTool', async () => {
    // Create config with timeout
    const configWithTimeout = {
      mcpServers: {
        'slow-server': {
          type: 'stdio',
          command: 'node',
          args: ['slow-server.js'],
          timeout: 600000, // 10 minutes
        },
      }
    };
    vi.mocked(fs.existsSync).mockReturnValue(true);
    vi.mocked(fs.readFileSync).mockReturnValue(JSON.stringify(configWithTimeout));
    clearCache();

    const slowServerTools: ToolDefinition[] = [
      {
        name: 'slow_operation',
        description: 'A slow operation',
        inputSchema: { type: 'object', properties: {} },
        serverId: 'slow-server'
      }
    ];

    const mockConnection = createMockConnection('slow-server', slowServerTools);
    mockPool.getConnection.mockResolvedValue(mockConnection);
    toolCache.set('slow-server', slowServerTools);

    await callToolHandler(
      { server_name: 'slow-server', tool_name: 'slow_operation', arguments: {} },
      mockPool as any,
      toolCache
    );

    // Verify timeout was passed in requestOptions
    expect(mockConnection.client.callTool).toHaveBeenCalledWith(
      { name: 'slow_operation', arguments: {} },
      undefined,
      { timeout: 600000 }
    );
  });
});
