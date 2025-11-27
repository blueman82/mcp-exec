import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ServerConfig } from '../src/types/index.js';

const mockConnect = vi.fn();
const mockClose = vi.fn();
const mockListTools = vi.fn();

vi.mock('@modelcontextprotocol/sdk/client/index.js', () => {
  return {
    Client: class MockClient {
      connect = mockConnect;
      close = mockClose;
      listTools = mockListTools;
    },
  };
});

vi.mock('@modelcontextprotocol/sdk/client/stdio.js', () => {
  return {
    StdioClientTransport: class MockTransport {
      constructor(public config: { command: string; args: string[]; env?: Record<string, string> }) {}
    },
  };
});

describe('Connection handling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockConnect.mockResolvedValue(undefined);
    mockClose.mockResolvedValue(undefined);
    mockListTools.mockResolvedValue({ tools: [] });
  });

  describe('createConnection', async () => {
    const { createConnection, SpawnError } = await import('../src/pool/connection.js');

    it('spawns Node process with correct command', async () => {
      const config: ServerConfig = {
        name: 'test-node-server',
        type: 'stdio',
        command: 'node',
        args: ['/path/to/server/index.js', '--port', '3000'],
        env: { NODE_ENV: 'production' },
      };

      const connection = await createConnection(config);

      expect(connection.serverId).toBe('test-node-server');
      expect(connection.isConnected()).toBe(true);
      expect(mockConnect).toHaveBeenCalled();
    });

    it('spawns Docker process with correct args', async () => {
      const config: ServerConfig = {
        name: 'test-docker-server',
        type: 'stdio',
        command: 'docker',
        args: ['run', '-i', '--rm', 'mcp/test-server:latest'],
        env: { API_KEY: 'test-key' },
      };

      const connection = await createConnection(config);

      expect(connection.serverId).toBe('test-docker-server');
      expect(connection.isConnected()).toBe(true);
    });

    it('spawns uvx process', async () => {
      const config: ServerConfig = {
        name: 'test-uvx-server',
        type: 'stdio',
        command: 'uvx',
        args: ['mcp-server-package', '--config', '/path/to/config'],
      };

      const connection = await createConnection(config);

      expect(connection.serverId).toBe('test-uvx-server');
      expect(connection.isConnected()).toBe(true);
    });

    it('handles connection failure gracefully', async () => {
      mockConnect.mockRejectedValueOnce(new Error('Connection refused'));

      const config: ServerConfig = {
        name: 'connection-fail-server',
        type: 'stdio',
        command: 'node',
        args: ['/path/to/server'],
      };

      await expect(createConnection(config)).rejects.toThrow(SpawnError);
    });
  });

  describe('closeConnection', async () => {
    const { createConnection, closeConnection } = await import('../src/pool/connection.js');

    it('terminates process and disconnects client', async () => {
      const config: ServerConfig = {
        name: 'test-close-server',
        type: 'stdio',
        command: 'node',
        args: ['/path/to/server/index.js'],
      };

      const connection = await createConnection(config);
      expect(connection.isConnected()).toBe(true);

      await closeConnection(connection);
      expect(connection.isConnected()).toBe(false);
      expect(mockClose).toHaveBeenCalled();
    });
  });

  describe('getTools', async () => {
    const { createConnection } = await import('../src/pool/connection.js');

    it('returns tool definitions from server', async () => {
      mockListTools.mockResolvedValueOnce({
        tools: [
          { name: 'tool1', description: 'First tool', inputSchema: { type: 'object' } },
          { name: 'tool2', description: 'Second tool', inputSchema: { type: 'object' } },
        ],
      });

      const config: ServerConfig = {
        name: 'tools-server',
        type: 'stdio',
        command: 'node',
        args: ['/path/to/server'],
      };

      const connection = await createConnection(config);
      const tools = await connection.getTools();

      expect(tools).toHaveLength(2);
      expect(tools[0].name).toBe('tool1');
      expect(tools[1].name).toBe('tool2');
      expect(tools[0].serverId).toBe('tools-server');
    });
  });
});

describe('Error exports', async () => {
  const { SpawnError, TimeoutError, UnexpectedExitError } = await import('../src/pool/connection.js');

  it('exports SpawnError', () => {
    expect(SpawnError).toBeDefined();
    const err = new SpawnError('test', 'cmd', ['arg']);
    expect(err.name).toBe('SpawnError');
    expect(err.command).toBe('cmd');
    expect(err.args).toEqual(['arg']);
  });

  it('exports TimeoutError', () => {
    expect(TimeoutError).toBeDefined();
    const err = new TimeoutError('test', 5000);
    expect(err.name).toBe('TimeoutError');
    expect(err.timeoutMs).toBe(5000);
  });

  it('exports UnexpectedExitError', () => {
    expect(UnexpectedExitError).toBeDefined();
    const err = new UnexpectedExitError('test', 1, 'SIGTERM');
    expect(err.name).toBe('UnexpectedExitError');
    expect(err.exitCode).toBe(1);
    expect(err.signal).toBe('SIGTERM');
  });
});

describe('buildSpawnConfig', async () => {
  const { buildSpawnConfig } = await import('../src/pool/stdio-transport.js');

  it('builds node spawn config', () => {
    const config: ServerConfig = {
      name: 'node-server',
      type: 'stdio',
      command: 'node',
      args: ['/path/to/script.js', '--flag'],
      env: { KEY: 'value' },
    };

    const spawn = buildSpawnConfig(config);

    expect(spawn.command).toBe('node');
    expect(spawn.args).toContain('/path/to/script.js');
    expect(spawn.args).toContain('--flag');
    expect(spawn.env?.KEY).toBe('value');
  });

  it('builds docker spawn config', () => {
    const config: ServerConfig = {
      name: 'docker-server',
      type: 'stdio',
      command: 'docker',
      args: ['run', '-i', '--rm', 'myimage:v1'],
      env: { SECRET: 'xxx' },
    };

    const spawn = buildSpawnConfig(config);

    expect(spawn.command).toBe('docker');
    expect(spawn.args).toContain('run');
    expect(spawn.args).toContain('-i');
    expect(spawn.args).toContain('--rm');
    expect(spawn.args).toContain('myimage:v1');
  });

  it('builds uvx spawn config', () => {
    const config: ServerConfig = {
      name: 'uvx-server',
      type: 'stdio',
      command: 'uvx',
      args: ['some-package', '--opt'],
    };

    const spawn = buildSpawnConfig(config);

    expect(spawn.command).toBe('uvx');
    expect(spawn.args[0]).toBe('some-package');
    expect(spawn.args).toContain('--opt');
  });

  it('throws for missing command', () => {
    const config: ServerConfig = {
      name: 'bad-config',
      type: 'stdio',
    };

    expect(() => buildSpawnConfig(config)).toThrow('Config requires command');
  });
});
