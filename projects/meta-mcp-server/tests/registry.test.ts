import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as fs from 'fs';
import { loadServerManifest, getServerConfig, listServers } from '../src/registry/loader.js';
import { ConfigNotFoundError, ConfigParseError, ConfigValidationError } from '../src/registry/loader.js';

vi.mock('fs');

const validBackendsJson = {
  mcpServers: {
    'filesystem': {
      type: 'stdio',
      command: 'node',
      args: ['server.js'],
      description: 'File system operations',
      tags: ['filesystem', 'files']
    },
    'docker-server': {
      type: 'stdio',
      command: 'docker',
      args: ['run', '-i', '--rm', 'mcp/server:latest'],
      description: 'Docker-based server',
      tags: ['docker']
    },
    'uvx-server': {
      type: 'stdio',
      command: 'uvx',
      args: ['mcp-server'],
      description: 'UVX server',
      tags: ['python']
    }
  }
};

describe('Registry loader', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    process.env.SERVERS_CONFIG = '/path/to/servers.json';
  });

  afterEach(() => {
    delete process.env.SERVERS_CONFIG;
  });

  it('loadServerManifest parses valid servers.json', () => {
    vi.mocked(fs.readFileSync).mockReturnValue(JSON.stringify(validBackendsJson));
    vi.mocked(fs.existsSync).mockReturnValue(true);

    const manifest = loadServerManifest();

    expect(manifest).toBeDefined();
    expect(manifest.servers).toHaveProperty('filesystem');
    expect(manifest.servers).toHaveProperty('docker-server');
    expect(manifest.servers).toHaveProperty('uvx-server');
  });

  it('getServerConfig returns correct config', () => {
    vi.mocked(fs.readFileSync).mockReturnValue(JSON.stringify(validBackendsJson));
    vi.mocked(fs.existsSync).mockReturnValue(true);

    loadServerManifest();
    const config = getServerConfig('filesystem');

    expect(config).toBeDefined();
    expect(config?.type).toBe('stdio');
    expect(config?.command).toBe('node');
    expect(config?.args).toEqual(['server.js']);
  });

  it('listServers returns lightweight list', () => {
    vi.mocked(fs.readFileSync).mockReturnValue(JSON.stringify(validBackendsJson));
    vi.mocked(fs.existsSync).mockReturnValue(true);

    loadServerManifest();
    const list = listServers();

    expect(list).toHaveLength(3);
    expect(list[0]).toHaveProperty('name');
    expect(list[0]).toHaveProperty('description');
    expect(list[0]).toHaveProperty('tags');
    expect(list[0]).not.toHaveProperty('command');
    expect(list[0]).not.toHaveProperty('args');
  });

  it('handles missing config file', () => {
    vi.mocked(fs.existsSync).mockReturnValue(false);

    expect(() => loadServerManifest()).toThrow(ConfigNotFoundError);
  });

  it('handles invalid JSON', () => {
    vi.mocked(fs.readFileSync).mockReturnValue('not valid json {{{');
    vi.mocked(fs.existsSync).mockReturnValue(true);

    expect(() => loadServerManifest()).toThrow(ConfigParseError);
  });

  it('handles invalid structure', () => {
    vi.mocked(fs.readFileSync).mockReturnValue(JSON.stringify({ invalid: 'structure' }));
    vi.mocked(fs.existsSync).mockReturnValue(true);

    expect(() => loadServerManifest()).toThrow(ConfigValidationError);
  });

  it('returns undefined for unknown server', () => {
    vi.mocked(fs.readFileSync).mockReturnValue(JSON.stringify(validBackendsJson));
    vi.mocked(fs.existsSync).mockReturnValue(true);

    loadServerManifest();
    const config = getServerConfig('nonexistent');

    expect(config).toBeUndefined();
  });
});
