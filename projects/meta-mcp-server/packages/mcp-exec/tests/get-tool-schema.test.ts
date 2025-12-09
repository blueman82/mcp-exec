/**
 * Unit tests for get_mcp_tool_schema tool
 * Tests tool definition, handler success/failure, error messages, and type guard
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  getMcpToolSchemaTool,
  createGetToolSchemaHandler,
  isGetToolSchemaInput,
  type GetToolSchemaInput,
} from '../src/tools/get-tool-schema.js';
import type { ServerPool, MCPConnection, ToolDefinition } from '@meta-mcp/core';

// Helper to create mock connection
function createMockConnection(tools: ToolDefinition[] = []): MCPConnection {
  return {
    serverId: 'test-server',
    state: 1, // ConnectionState.Connected
    connect: vi.fn().mockResolvedValue(undefined),
    disconnect: vi.fn().mockResolvedValue(undefined),
    isConnected: vi.fn().mockReturnValue(true),
    getTools: vi.fn().mockResolvedValue(tools),
    client: {
      callTool: vi.fn(),
    },
  } as unknown as MCPConnection;
}

// Helper to create mock pool
function createMockPool(overrides: Partial<ServerPool> = {}): ServerPool {
  return {
    getConnection: vi.fn().mockResolvedValue(createMockConnection()),
    releaseConnection: vi.fn(),
    shutdown: vi.fn().mockResolvedValue(undefined),
    getActiveCount: vi.fn().mockReturnValue(0),
    runCleanup: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  } as unknown as ServerPool;
}

describe('get_mcp_tool_schema tool', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('tool definition', () => {
    it('should have correct name', () => {
      expect(getMcpToolSchemaTool.name).toBe('get_mcp_tool_schema');
    });

    it('should have description', () => {
      expect(getMcpToolSchemaTool.description).toBeDefined();
      expect(getMcpToolSchemaTool.description).toContain('schema');
    });

    it('should have correct inputSchema structure', () => {
      expect(getMcpToolSchemaTool.inputSchema.type).toBe('object');
      expect(getMcpToolSchemaTool.inputSchema.properties).toBeDefined();
      expect(getMcpToolSchemaTool.inputSchema.properties.server).toBeDefined();
      expect(getMcpToolSchemaTool.inputSchema.properties.server.type).toBe('string');
      expect(getMcpToolSchemaTool.inputSchema.properties.tool).toBeDefined();
      expect(getMcpToolSchemaTool.inputSchema.properties.tool.type).toBe('string');
    });

    it('should require server and tool parameters', () => {
      expect(getMcpToolSchemaTool.inputSchema.required).toContain('server');
      expect(getMcpToolSchemaTool.inputSchema.required).toContain('tool');
    });
  });

  describe('createGetToolSchemaHandler', () => {
    describe('success cases', () => {
      it('should return tool schema when tool is found', async () => {
        const mockTool: ToolDefinition = {
          name: 'read_file',
          description: 'Read a file from the filesystem',
          inputSchema: {
            type: 'object',
            properties: {
              path: { type: 'string', description: 'Path to the file' },
            },
            required: ['path'],
          },
        };
        const mockConnection = createMockConnection([mockTool]);
        const mockPool = createMockPool({
          getConnection: vi.fn().mockResolvedValue(mockConnection),
        });

        const handler = createGetToolSchemaHandler(mockPool);
        const result = await handler({ server: 'filesystem', tool: 'read_file' });

        expect(result.isError).toBe(false);
        expect(result.content).toHaveLength(1);
        expect(result.content[0].type).toBe('text');
        const parsed = JSON.parse(result.content[0].text);
        expect(parsed.name).toBe('read_file');
        expect(parsed.description).toBe('Read a file from the filesystem');
        expect(parsed.inputSchema).toBeDefined();
      });

      it('should call getConnection with correct server name', async () => {
        const mockPool = createMockPool();

        const handler = createGetToolSchemaHandler(mockPool);
        await handler({ server: 'my-server', tool: 'my-tool' });

        expect(mockPool.getConnection).toHaveBeenCalledWith('my-server');
      });

      it('should return full tool schema including inputSchema', async () => {
        const complexSchema = {
          type: 'object',
          properties: {
            query: { type: 'string' },
            limit: { type: 'number', default: 10 },
            options: {
              type: 'object',
              properties: {
                sort: { type: 'string', enum: ['asc', 'desc'] },
              },
            },
          },
          required: ['query'],
        };
        const mockTool: ToolDefinition = {
          name: 'search',
          description: 'Search for items',
          inputSchema: complexSchema,
        };
        const mockConnection = createMockConnection([mockTool]);
        const mockPool = createMockPool({
          getConnection: vi.fn().mockResolvedValue(mockConnection),
        });

        const handler = createGetToolSchemaHandler(mockPool);
        const result = await handler({ server: 'search-server', tool: 'search' });

        expect(result.isError).toBe(false);
        const parsed = JSON.parse(result.content[0].text);
        expect(parsed.inputSchema).toEqual(complexSchema);
      });
    });

    describe('tool not found', () => {
      it('should return error when tool is not found', async () => {
        const mockTools: ToolDefinition[] = [
          { name: 'tool1', description: 'Tool 1', inputSchema: { type: 'object' } },
          { name: 'tool2', description: 'Tool 2', inputSchema: { type: 'object' } },
        ];
        const mockConnection = createMockConnection(mockTools);
        const mockPool = createMockPool({
          getConnection: vi.fn().mockResolvedValue(mockConnection),
        });

        const handler = createGetToolSchemaHandler(mockPool);
        const result = await handler({ server: 'test-server', tool: 'nonexistent' });

        expect(result.isError).toBe(true);
        expect(result.content[0].text).toContain("Tool 'nonexistent' not found");
        expect(result.content[0].text).toContain("'test-server'");
      });

      it('should list available tools when tool is not found', async () => {
        const mockTools: ToolDefinition[] = [
          { name: 'read_file', description: 'Read file', inputSchema: { type: 'object' } },
          { name: 'write_file', description: 'Write file', inputSchema: { type: 'object' } },
          { name: 'list_directory', description: 'List dir', inputSchema: { type: 'object' } },
        ];
        const mockConnection = createMockConnection(mockTools);
        const mockPool = createMockPool({
          getConnection: vi.fn().mockResolvedValue(mockConnection),
        });

        const handler = createGetToolSchemaHandler(mockPool);
        const result = await handler({ server: 'filesystem', tool: 'delete_file' });

        expect(result.isError).toBe(true);
        expect(result.content[0].text).toContain('Available tools:');
        expect(result.content[0].text).toContain('list_directory');
        expect(result.content[0].text).toContain('read_file');
        expect(result.content[0].text).toContain('write_file');
      });

      it('should return sorted list of available tools', async () => {
        const mockTools: ToolDefinition[] = [
          { name: 'zebra', description: 'Z tool', inputSchema: { type: 'object' } },
          { name: 'alpha', description: 'A tool', inputSchema: { type: 'object' } },
          { name: 'beta', description: 'B tool', inputSchema: { type: 'object' } },
        ];
        const mockConnection = createMockConnection(mockTools);
        const mockPool = createMockPool({
          getConnection: vi.fn().mockResolvedValue(mockConnection),
        });

        const handler = createGetToolSchemaHandler(mockPool);
        const result = await handler({ server: 'test', tool: 'missing' });

        expect(result.isError).toBe(true);
        // Should list tools in alphabetical order
        expect(result.content[0].text).toContain('alpha, beta, zebra');
      });
    });

    describe('connection errors', () => {
      it('should handle server not found error', async () => {
        const mockPool = createMockPool({
          getConnection: vi.fn().mockRejectedValue(new Error('Server not found: unknown-server')),
        });

        const handler = createGetToolSchemaHandler(mockPool);
        const result = await handler({ server: 'unknown-server', tool: 'some-tool' });

        expect(result.isError).toBe(true);
        expect(result.content[0].text).toContain("Error connecting to server 'unknown-server'");
        expect(result.content[0].text).toContain('list_available_mcp_servers');
      });

      it('should handle unknown server error', async () => {
        const mockPool = createMockPool({
          getConnection: vi.fn().mockRejectedValue(new Error('unknown server')),
        });

        const handler = createGetToolSchemaHandler(mockPool);
        const result = await handler({ server: 'bad-server', tool: 'some-tool' });

        expect(result.isError).toBe(true);
        expect(result.content[0].text).toContain("Error connecting to server 'bad-server'");
        expect(result.content[0].text).toContain('list_available_mcp_servers');
      });

      it('should handle generic connection errors', async () => {
        const mockPool = createMockPool({
          getConnection: vi.fn().mockRejectedValue(new Error('Connection timeout')),
        });

        const handler = createGetToolSchemaHandler(mockPool);
        const result = await handler({ server: 'slow-server', tool: 'some-tool' });

        expect(result.isError).toBe(true);
        expect(result.content[0].text).toContain('Error getting tool schema');
        expect(result.content[0].text).toContain('Connection timeout');
      });

      it('should handle getTools throwing an error', async () => {
        const mockConnection = createMockConnection();
        (mockConnection.getTools as ReturnType<typeof vi.fn>).mockRejectedValue(
          new Error('Failed to fetch tools')
        );
        const mockPool = createMockPool({
          getConnection: vi.fn().mockResolvedValue(mockConnection),
        });

        const handler = createGetToolSchemaHandler(mockPool);
        const result = await handler({ server: 'test-server', tool: 'some-tool' });

        expect(result.isError).toBe(true);
        expect(result.content[0].text).toContain('Error getting tool schema');
        expect(result.content[0].text).toContain('Failed to fetch tools');
      });

      it('should handle non-Error exceptions', async () => {
        const mockPool = createMockPool({
          getConnection: vi.fn().mockRejectedValue('string error'),
        });

        const handler = createGetToolSchemaHandler(mockPool);
        const result = await handler({ server: 'test-server', tool: 'some-tool' });

        expect(result.isError).toBe(true);
        expect(result.content[0].text).toContain('string error');
      });
    });

    describe('edge cases', () => {
      it('should handle server with no tools', async () => {
        const mockConnection = createMockConnection([]);
        const mockPool = createMockPool({
          getConnection: vi.fn().mockResolvedValue(mockConnection),
        });

        const handler = createGetToolSchemaHandler(mockPool);
        const result = await handler({ server: 'empty-server', tool: 'any-tool' });

        expect(result.isError).toBe(true);
        expect(result.content[0].text).toContain("Tool 'any-tool' not found");
        expect(result.content[0].text).toContain('Available tools:');
      });

      it('should handle tool with minimal schema', async () => {
        const minimalTool: ToolDefinition = {
          name: 'simple_tool',
          description: '',
          inputSchema: { type: 'object' },
        };
        const mockConnection = createMockConnection([minimalTool]);
        const mockPool = createMockPool({
          getConnection: vi.fn().mockResolvedValue(mockConnection),
        });

        const handler = createGetToolSchemaHandler(mockPool);
        const result = await handler({ server: 'test', tool: 'simple_tool' });

        expect(result.isError).toBe(false);
        const parsed = JSON.parse(result.content[0].text);
        expect(parsed.name).toBe('simple_tool');
      });
    });
  });

  describe('isGetToolSchemaInput type guard', () => {
    it('should return true for valid input with both server and tool', () => {
      expect(isGetToolSchemaInput({ server: 'test', tool: 'mytool' })).toBe(true);
    });

    it('should return true for input with empty strings', () => {
      expect(isGetToolSchemaInput({ server: '', tool: '' })).toBe(true);
    });

    it('should return false for null', () => {
      expect(isGetToolSchemaInput(null)).toBe(false);
    });

    it('should return false for undefined', () => {
      expect(isGetToolSchemaInput(undefined)).toBe(false);
    });

    it('should return false for non-object types', () => {
      expect(isGetToolSchemaInput('string')).toBe(false);
      expect(isGetToolSchemaInput(123)).toBe(false);
      expect(isGetToolSchemaInput(true)).toBe(false);
      expect(isGetToolSchemaInput([])).toBe(false);
    });

    it('should return false when server is missing', () => {
      expect(isGetToolSchemaInput({ tool: 'mytool' })).toBe(false);
    });

    it('should return false when tool is missing', () => {
      expect(isGetToolSchemaInput({ server: 'test' })).toBe(false);
    });

    it('should return false when both are missing', () => {
      expect(isGetToolSchemaInput({})).toBe(false);
    });

    it('should return false when server is not a string', () => {
      expect(isGetToolSchemaInput({ server: 123, tool: 'mytool' })).toBe(false);
      expect(isGetToolSchemaInput({ server: null, tool: 'mytool' })).toBe(false);
      expect(isGetToolSchemaInput({ server: {}, tool: 'mytool' })).toBe(false);
    });

    it('should return false when tool is not a string', () => {
      expect(isGetToolSchemaInput({ server: 'test', tool: 123 })).toBe(false);
      expect(isGetToolSchemaInput({ server: 'test', tool: null })).toBe(false);
      expect(isGetToolSchemaInput({ server: 'test', tool: [] })).toBe(false);
    });

    it('should return false when both are not strings', () => {
      expect(isGetToolSchemaInput({ server: 123, tool: 456 })).toBe(false);
    });

    it('should ignore extra properties', () => {
      expect(isGetToolSchemaInput({ server: 'test', tool: 'mytool', extra: 'value' })).toBe(true);
    });
  });
});
