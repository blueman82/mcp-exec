import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as fs from 'fs';
import { listServersHandler, listServersTool } from '../../src/tools/list-servers.js';
import { clearCache } from '@meta-mcp/core';

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
    'slack': {
      type: 'stdio',
      command: 'npx',
      args: ['@modelcontextprotocol/server-slack'],
      description: 'Slack integration',
      tags: ['slack', 'messaging']
    },
    'postgres': {
      type: 'stdio',
      command: 'docker',
      args: ['run', '-i', '--rm', 'mcp/postgres:latest'],
      description: 'PostgreSQL database access',
      tags: ['database', 'sql', 'postgres']
    },
    'redis': {
      type: 'stdio',
      command: 'docker',
      args: ['run', '-i', '--rm', 'mcp/redis:latest'],
      description: 'Redis cache operations',
      tags: ['database', 'cache', 'redis']
    },
    'brave-search': {
      type: 'stdio',
      command: 'uvx',
      args: ['mcp-server-brave-search'],
      description: 'Brave search API',
      tags: ['search', 'api']
    },
    'fetch': {
      type: 'stdio',
      command: 'uvx',
      args: ['mcp-server-fetch'],
      description: 'HTTP fetch operations',
      tags: ['http', 'fetch', 'api']
    },
    'memory': {
      type: 'stdio',
      command: 'npx',
      args: ['@modelcontextprotocol/server-memory'],
      description: 'Knowledge graph memory',
      tags: ['memory', 'knowledge']
    },
    'puppeteer': {
      type: 'stdio',
      command: 'npx',
      args: ['@modelcontextprotocol/server-puppeteer'],
      description: 'Browser automation',
      tags: ['browser', 'automation']
    },
    'sqlite': {
      type: 'stdio',
      command: 'uvx',
      args: ['mcp-server-sqlite'],
      description: 'SQLite database access',
      tags: ['database', 'sql', 'sqlite']
    },
    'time': {
      type: 'stdio',
      command: 'uvx',
      args: ['mcp-server-time'],
      description: 'Time and timezone utilities',
      tags: ['time', 'utilities']
    }
  }
};

describe('list_servers tool', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    clearCache();
    process.env.SERVERS_CONFIG = '/path/to/servers.json';
  });

  afterEach(() => {
    delete process.env.SERVERS_CONFIG;
    clearCache();
  });

  it('returns all servers', async () => {
    vi.mocked(fs.readFileSync).mockReturnValue(JSON.stringify(testBackendsJson));
    vi.mocked(fs.existsSync).mockReturnValue(true);

    const result = await listServersHandler({});

    expect(result.servers).toHaveLength(11);
    expect(result.servers.map(s => s.name)).toContain('filesystem');
    expect(result.servers.map(s => s.name)).toContain('github');
    expect(result.servers.map(s => s.name)).toContain('time');
  });

  it('filter by name substring', async () => {
    vi.mocked(fs.readFileSync).mockReturnValue(JSON.stringify(testBackendsJson));
    vi.mocked(fs.existsSync).mockReturnValue(true);

    const result = await listServersHandler({ filter: 'sql' });

    expect(result.servers).toHaveLength(2);
    expect(result.servers.map(s => s.name)).toContain('postgres');
    expect(result.servers.map(s => s.name)).toContain('sqlite');
  });

  it('filter by tag', async () => {
    vi.mocked(fs.readFileSync).mockReturnValue(JSON.stringify(testBackendsJson));
    vi.mocked(fs.existsSync).mockReturnValue(true);

    const result = await listServersHandler({ filter: 'database' });

    expect(result.servers).toHaveLength(3);
    expect(result.servers.map(s => s.name)).toContain('postgres');
    expect(result.servers.map(s => s.name)).toContain('redis');
    expect(result.servers.map(s => s.name)).toContain('sqlite');
  });

  it('empty filter returns all', async () => {
    vi.mocked(fs.readFileSync).mockReturnValue(JSON.stringify(testBackendsJson));
    vi.mocked(fs.existsSync).mockReturnValue(true);

    const result = await listServersHandler({ filter: '' });

    expect(result.servers).toHaveLength(11);
  });

  it('returns empty list with warning when config not loaded', async () => {
    vi.mocked(fs.existsSync).mockReturnValue(false);

    const result = await listServersHandler({});

    expect(result.servers).toHaveLength(0);
    expect(result.warning).toBeDefined();
  });

  it('returns lightweight response without schemas', async () => {
    vi.mocked(fs.readFileSync).mockReturnValue(JSON.stringify(testBackendsJson));
    vi.mocked(fs.existsSync).mockReturnValue(true);

    const result = await listServersHandler({});

    for (const server of result.servers) {
      expect(server).toHaveProperty('name');
      expect(server).toHaveProperty('description');
      expect(server).toHaveProperty('tags');
      expect(server).not.toHaveProperty('command');
      expect(server).not.toHaveProperty('args');
      expect(server).not.toHaveProperty('docker');
      expect(server).not.toHaveProperty('env');
    }
  });

  it('tool definition has correct structure', () => {
    expect(listServersTool.name).toBe('list_servers');
    expect(listServersTool.description).toBeDefined();
    expect(listServersTool.inputSchema).toBeDefined();
    expect(listServersTool.inputSchema.type).toBe('object');
  });
});
