/**
 * Unit tests for list_available_mcp_servers tool
 * Tests tool definition, handler with/without filter, and type guard
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  listAvailableMcpServersTool,
  createListServersHandler,
  isListServersInput,
  type ListServersInput,
} from '../src/tools/list-servers.js';

// Mock @justanothermldude/mcp-exec-oss-core
vi.mock('@justanothermldude/mcp-exec-oss-core', () => ({
  listServers: vi.fn(),
}));

import { listServers } from '@justanothermldude/mcp-exec-oss-core';

const mockListServers = vi.mocked(listServers);

describe('list_available_mcp_servers tool', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('tool definition', () => {
    it('should have correct name', () => {
      expect(listAvailableMcpServersTool.name).toBe('list_available_mcp_servers');
    });

    it('should have description', () => {
      expect(listAvailableMcpServersTool.description).toBeDefined();
      expect(listAvailableMcpServersTool.description).toContain('MCP servers');
    });

    it('should have correct inputSchema structure', () => {
      expect(listAvailableMcpServersTool.inputSchema.type).toBe('object');
      expect(listAvailableMcpServersTool.inputSchema.properties).toBeDefined();
      expect(listAvailableMcpServersTool.inputSchema.properties.filter).toBeDefined();
      expect(listAvailableMcpServersTool.inputSchema.properties.filter.type).toBe('string');
    });

    it('should not require any parameters', () => {
      expect(listAvailableMcpServersTool.inputSchema.required).toEqual([]);
    });
  });

  describe('createListServersHandler', () => {
    describe('without filter', () => {
      it('should return all servers when no filter provided', async () => {
        const mockServers = [
          { name: 'server1', description: 'First server', tags: ['tag1'] },
          { name: 'server2', description: 'Second server', tags: ['tag2'] },
        ];
        mockListServers.mockReturnValue(mockServers);

        const handler = createListServersHandler();
        const result = await handler({});

        expect(result.isError).toBe(false);
        expect(result.content).toHaveLength(1);
        expect(result.content[0].type).toBe('text');
        const text = result.content[0].text;
        expect(text).toContain('server1');
        expect(text).toContain('server2');
      });

      it('should return empty array when no servers available', async () => {
        mockListServers.mockReturnValue([]);

        const handler = createListServersHandler();
        const result = await handler({});

        expect(result.isError).toBe(false);
        expect(result.content[0].text).toContain('No servers');
      });
    });

    describe('with filter', () => {
      it('should filter servers by name', async () => {
        const mockServers = [
          { name: 'filesystem', description: 'File system server', tags: [] },
          { name: 'database', description: 'Database server', tags: [] },
          { name: 'filesync', description: 'File sync server', tags: [] },
        ];
        mockListServers.mockReturnValue(mockServers);

        const handler = createListServersHandler();
        const result = await handler({ filter: 'file' });

        expect(result.isError).toBe(false);
        const text = result.content[0].text;
        expect(text).toContain('filesystem');
        expect(text).toContain('filesync');
        expect(text).not.toContain('database');
      });

      it('should filter servers by description', async () => {
        const mockServers = [
          { name: 'server1', description: 'Handles authentication', tags: [] },
          { name: 'server2', description: 'Data processing', tags: [] },
        ];
        mockListServers.mockReturnValue(mockServers);

        const handler = createListServersHandler();
        const result = await handler({ filter: 'auth' });

        expect(result.isError).toBe(false);
        const text = result.content[0].text;
        expect(text).toContain('server1');
        expect(text).not.toContain('server2');
      });

      it('should filter servers by tags', async () => {
        const mockServers = [
          { name: 'server1', description: 'Server 1', tags: ['storage', 'files'] },
          { name: 'server2', description: 'Server 2', tags: ['network'] },
          { name: 'server3', description: 'Server 3', tags: ['storage', 'cloud'] },
        ];
        mockListServers.mockReturnValue(mockServers);

        const handler = createListServersHandler();
        const result = await handler({ filter: 'storage' });

        expect(result.isError).toBe(false);
        const text = result.content[0].text;
        expect(text).toContain('server1');
        expect(text).toContain('server3');
        expect(text).not.toContain('server2');
      });

      it('should be case-insensitive', async () => {
        const mockServers = [
          { name: 'FileSystem', description: 'File System', tags: ['Storage'] },
        ];
        mockListServers.mockReturnValue(mockServers);

        const handler = createListServersHandler();
        const result = await handler({ filter: 'FILESYSTEM' });

        expect(result.isError).toBe(false);
        expect(result.content[0].text).toContain('FileSystem');
      });

      it('should return empty array when filter matches nothing', async () => {
        const mockServers = [
          { name: 'server1', description: 'Description 1', tags: ['tag1'] },
        ];
        mockListServers.mockReturnValue(mockServers);

        const handler = createListServersHandler();
        const result = await handler({ filter: 'nonexistent' });

        expect(result.isError).toBe(false);
        expect(result.content[0].text).toContain('No servers matched filter');
      });
    });

    describe('error handling', () => {
      it('should handle listServers throwing an error', async () => {
        mockListServers.mockImplementation(() => {
          throw new Error('Registry not loaded');
        });

        const handler = createListServersHandler();
        const result = await handler({});

        expect(result.isError).toBe(true);
        expect(result.content[0].text).toContain('Error listing servers');
        expect(result.content[0].text).toContain('Registry not loaded');
      });

      it('should handle non-Error exceptions', async () => {
        mockListServers.mockImplementation(() => {
          throw 'string error';
        });

        const handler = createListServersHandler();
        const result = await handler({});

        expect(result.isError).toBe(true);
        expect(result.content[0].text).toContain('Error listing servers');
        expect(result.content[0].text).toContain('string error');
      });
    });

    describe('edge cases', () => {
      it('should handle servers without description', async () => {
        const mockServers = [
          { name: 'server1', tags: ['tag1'] },
        ];
        mockListServers.mockReturnValue(mockServers as any);

        const handler = createListServersHandler();
        const result = await handler({ filter: 'server' });

        expect(result.isError).toBe(false);
        expect(result.content[0].text).toContain('server1');
      });

      it('should handle servers without tags', async () => {
        const mockServers = [
          { name: 'server1', description: 'Description' },
        ];
        mockListServers.mockReturnValue(mockServers as any);

        const handler = createListServersHandler();
        const result = await handler({ filter: 'server' });

        expect(result.isError).toBe(false);
        expect(result.content[0].text).toContain('server1');
      });
    });
  });

  describe('isListServersInput type guard', () => {
    it('should return true for empty object', () => {
      expect(isListServersInput({})).toBe(true);
    });

    it('should return true for object with string filter', () => {
      expect(isListServersInput({ filter: 'test' })).toBe(true);
    });

    it('should return true for object with empty string filter', () => {
      expect(isListServersInput({ filter: '' })).toBe(true);
    });

    it('should return false for null', () => {
      expect(isListServersInput(null)).toBe(false);
    });

    it('should return false for undefined', () => {
      expect(isListServersInput(undefined)).toBe(false);
    });

    it('should return false for non-object types', () => {
      expect(isListServersInput('string')).toBe(false);
      expect(isListServersInput(123)).toBe(false);
      expect(isListServersInput(true)).toBe(false);
      expect(isListServersInput([])).toBe(false);
    });

    it('should return false when filter is not a string', () => {
      expect(isListServersInput({ filter: 123 })).toBe(false);
      expect(isListServersInput({ filter: true })).toBe(false);
      expect(isListServersInput({ filter: null })).toBe(false);
      expect(isListServersInput({ filter: {} })).toBe(false);
      expect(isListServersInput({ filter: [] })).toBe(false);
    });

    it('should ignore extra properties', () => {
      expect(isListServersInput({ filter: 'test', extra: 'value' })).toBe(true);
    });
  });
});
