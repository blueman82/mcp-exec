import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as fs from 'fs';
import { getServerToolsHandler, getServerToolsTool, ServerNotFoundError } from '../../src/tools/get-server-tools.js';
import { ToolCache } from '../../src/tools/tool-cache.js';
import { clearCache } from '../../src/registry/index.js';
import type { MCPConnection, ToolDefinition } from '../../src/types/index.js';
import { ConnectionState } from '../../src/types/index.js';

vi.mock('fs');

const testBackendsJson = {
  mcpServers: {
    'filesystem': {
      type: 'stdio',
      command: 'node',
      args: ['server.js'],
      description: 'File system operations',
      tags: ['filesystem', 'files', 'storage']
    },
    'github': {
      type: 'stdio',
      command: 'npx',
      args: ['@modelcontextprotocol/server-github'],
      description: 'GitHub API access',
      tags: ['github', 'api', 'vcs']
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

function createMockConnection(serverId: string, tools: ToolDefinition[]): MCPConnection {
  return {
    serverId,
    state: ConnectionState.Connected,
    connect: vi.fn().mockResolvedValue(undefined),
    disconnect: vi.fn().mockResolvedValue(undefined),
    isConnected: vi.fn().mockReturnValue(true),
    getTools: vi.fn().mockResolvedValue(tools),
  };
}

describe('get_server_tools tool', () => {
  let mockPool: { getConnection: ReturnType<typeof vi.fn>; releaseConnection: ReturnType<typeof vi.fn> };
  let toolCache: ToolCache;

  beforeEach(() => {
    vi.resetAllMocks();
    clearCache();
    process.env.SERVERS_CONFIG = '/path/to/backends.json';
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

  it('connects to server on first call', async () => {
    const mockConnection = createMockConnection('filesystem', mockTools);
    mockPool.getConnection.mockResolvedValue(mockConnection);

    const result = await getServerToolsHandler(
      { server_name: 'filesystem' },
      mockPool as any,
      toolCache
    );

    expect(mockPool.getConnection).toHaveBeenCalledWith('filesystem');
    expect(mockConnection.getTools).toHaveBeenCalled();
    expect(result.tools).toHaveLength(2);
    expect(result.tools[0].name).toBe('read_file');
  });

  it('returns cached tools on subsequent calls', async () => {
    const mockConnection = createMockConnection('filesystem', mockTools);
    mockPool.getConnection.mockResolvedValue(mockConnection);

    // First call
    await getServerToolsHandler(
      { server_name: 'filesystem' },
      mockPool as any,
      toolCache
    );

    // Second call
    const result = await getServerToolsHandler(
      { server_name: 'filesystem' },
      mockPool as any,
      toolCache
    );

    // Connection created only once
    expect(mockPool.getConnection).toHaveBeenCalledTimes(1);
    expect(result.tools).toHaveLength(2);
  });

  it('returns tool schemas', async () => {
    const mockConnection = createMockConnection('filesystem', mockTools);
    mockPool.getConnection.mockResolvedValue(mockConnection);

    const result = await getServerToolsHandler(
      { server_name: 'filesystem' },
      mockPool as any,
      toolCache
    );

    expect(result.tools).toHaveLength(2);
    const readFileTool = result.tools.find(t => t.name === 'read_file');
    expect(readFileTool).toBeDefined();
    expect(readFileTool!.inputSchema).toBeDefined();
    expect(readFileTool!.inputSchema.type).toBe('object');
    expect(readFileTool!.inputSchema.properties).toHaveProperty('path');
    expect(readFileTool!.inputSchema.required).toContain('path');
  });

  it('handles unknown server', async () => {
    await expect(
      getServerToolsHandler(
        { server_name: 'unknown-server' },
        mockPool as any,
        toolCache
      )
    ).rejects.toThrow(ServerNotFoundError);
  });

  it('tool definition has correct structure', () => {
    expect(getServerToolsTool.name).toBe('get_server_tools');
    expect(getServerToolsTool.description).toBeDefined();
    expect(getServerToolsTool.inputSchema).toBeDefined();
    expect(getServerToolsTool.inputSchema.type).toBe('object');
    expect(getServerToolsTool.inputSchema.properties).toHaveProperty('server_name');
    expect(getServerToolsTool.inputSchema.required).toContain('server_name');
  });
});

describe('ToolCache', () => {
  it('stores and retrieves tools', () => {
    const cache = new ToolCache();
    cache.set('filesystem', mockTools);

    expect(cache.has('filesystem')).toBe(true);
    expect(cache.get('filesystem')).toEqual(mockTools);
  });

  it('returns undefined for uncached servers', () => {
    const cache = new ToolCache();
    expect(cache.has('unknown')).toBe(false);
    expect(cache.get('unknown')).toBeUndefined();
  });

  it('clears cache', () => {
    const cache = new ToolCache();
    cache.set('filesystem', mockTools);
    cache.clear();

    expect(cache.has('filesystem')).toBe(false);
  });

  it('deletes specific server cache', () => {
    const cache = new ToolCache();
    cache.set('filesystem', mockTools);
    cache.set('github', []);

    cache.delete('filesystem');

    expect(cache.has('filesystem')).toBe(false);
    expect(cache.has('github')).toBe(true);
  });
});
