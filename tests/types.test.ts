import { describe, it, expect } from 'vitest';
import type { ServerConfig, ToolDefinition, MCPConnection } from '../src/types/index.js';

describe('Type definitions', () => {
  it('ServerConfig matches mcp.json structure', () => {
    const config: ServerConfig = {
      name: 'test-server',
      type: 'stdio',
      command: 'docker',
      args: ['run', '-i', '--rm', 'myserver:latest'],
      env: {
        FOO: 'bar',
      },
    };
    expect(config.name).toBe('test-server');
    expect(config.type).toBe('stdio');
    expect(config.command).toBe('docker');
  });

  it('ToolDefinition is compatible with MCP SDK', () => {
    const tool: ToolDefinition = {
      name: 'test-tool',
      description: 'A test tool',
      inputSchema: {
        type: 'object',
        properties: {
          arg1: { type: 'string' },
        },
      },
      serverId: 'server-1',
    };
    expect(tool.name).toBe('test-tool');
    expect(tool.serverId).toBe('server-1');
  });

  it('MCPConnection has required methods', () => {
    const mockConnection: MCPConnection = {
      serverId: 'test-server',
      state: 'disconnected' as any,
      connect: async () => {},
      disconnect: async () => {},
      isConnected: () => false,
      getTools: async () => [],
    };
    expect(mockConnection.serverId).toBe('test-server');
    expect(typeof mockConnection.connect).toBe('function');
    expect(typeof mockConnection.disconnect).toBe('function');
  });

  it('Types compile without errors', () => {
    const config: ServerConfig = {
      name: 'server',
      command: 'node',
      args: ['index.js'],
      type: 'stdio',
      env: {},
    };
    expect(config).toBeDefined();
  });
});
