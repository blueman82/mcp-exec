/**
 * Unit tests for execute_batch tool
 * Tests tool definition, type guards, input validation, and dependency ordering logic
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  executeBatchTool,
  isExecuteBatchInput,
  createExecuteBatchHandler,
  type Snippet,
  type ExecuteBatchInput,
} from '../src/tools/execute-batch.js';
import type { ServerPool } from '@meta-mcp/core';
import { ConnectionState } from '@meta-mcp/core';

// Mock modules with factory functions (must be hoisted)
vi.mock('@anthropic-ai/sandbox-runtime', () => ({
  SandboxManager: {
    initialize: vi.fn().mockResolvedValue(undefined),
    reset: vi.fn().mockResolvedValue(undefined),
    wrapWithSandbox: vi.fn().mockImplementation((cmd: string) => Promise.resolve(cmd)),
    annotateStderrWithSandboxFailures: vi.fn().mockImplementation((_: string, err: string) => err),
    checkDependencies: vi.fn().mockReturnValue(true),
    isSandboxingEnabled: vi.fn().mockReturnValue(true),
    updateConfig: vi.fn(),
  },
}));

// Mock esbuild transformSync
vi.mock('esbuild', () => ({
  transformSync: vi.fn().mockImplementation((code: string) => ({
    code: code.replace(/: string/g, '').replace(/: number/g, ''),
  })),
}));

// Mock child_process
vi.mock('node:child_process', () => ({
  spawn: vi.fn().mockImplementation(() => ({
    stdout: { on: vi.fn() },
    stderr: { on: vi.fn() },
    on: vi.fn(),
    kill: vi.fn(),
  })),
}));

// Mock fs operations
vi.mock('node:fs/promises', () => ({
  writeFile: vi.fn().mockResolvedValue(undefined),
  unlink: vi.fn().mockResolvedValue(undefined),
  mkdir: vi.fn().mockResolvedValue(undefined),
}));

// Mock ServerPool for unit tests
function createMockPool(overrides: Partial<ServerPool> = {}): ServerPool {
  return {
    getConnection: vi.fn().mockResolvedValue({
      serverId: 'test-server',
      state: ConnectionState.Connected,
      connect: vi.fn().mockResolvedValue(undefined),
      disconnect: vi.fn().mockResolvedValue(undefined),
      isConnected: vi.fn().mockReturnValue(true),
      getTools: vi.fn().mockResolvedValue([]),
      client: {
        callTool: vi.fn().mockResolvedValue({
          content: [{ type: 'text', text: 'mock result' }],
          isError: false,
        }),
      },
    }),
    releaseConnection: vi.fn(),
    shutdown: vi.fn().mockResolvedValue(undefined),
    getActiveCount: vi.fn().mockReturnValue(0),
    runCleanup: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  } as unknown as ServerPool;
}

describe('execute_batch tool', () => {
  describe('executeBatchTool definition', () => {
    it('should have correct name and description', () => {
      expect(executeBatchTool.name).toBe('execute_batch');
      expect(executeBatchTool.description).toContain('Execute multiple code snippets');
      expect(executeBatchTool.description).toContain('dependency ordering');
      expect(executeBatchTool.description).toContain('topological sort');
    });

    it('should have correct input schema type', () => {
      expect(executeBatchTool.inputSchema.type).toBe('object');
      expect(executeBatchTool.inputSchema.required).toContain('snippets');
    });

    it('should have snippets property in schema', () => {
      expect(executeBatchTool.inputSchema.properties.snippets).toBeDefined();
      expect(executeBatchTool.inputSchema.properties.snippets.type).toBe('array');
    });

    it('should have timeout_ms property in schema', () => {
      expect(executeBatchTool.inputSchema.properties.timeout_ms).toBeDefined();
      expect(executeBatchTool.inputSchema.properties.timeout_ms.type).toBe('number');
    });

    it('should have stop_on_error property in schema', () => {
      expect(executeBatchTool.inputSchema.properties.stop_on_error).toBeDefined();
      expect(executeBatchTool.inputSchema.properties.stop_on_error.type).toBe('boolean');
    });

    it('should define snippet item schema with id, code, and depends_on', () => {
      const snippetSchema = executeBatchTool.inputSchema.properties.snippets.items as {
        properties: Record<string, unknown>;
        required: string[];
      };
      expect(snippetSchema.properties.id).toBeDefined();
      expect(snippetSchema.properties.code).toBeDefined();
      expect(snippetSchema.properties.depends_on).toBeDefined();
      expect(snippetSchema.required).toContain('id');
      expect(snippetSchema.required).toContain('code');
    });
  });

  describe('isExecuteBatchInput type guard', () => {
    it('should return true for valid input with snippets', () => {
      const validInput: ExecuteBatchInput = {
        snippets: [
          { id: 'a', code: 'console.log("a")' },
          { id: 'b', code: 'console.log("b")' },
        ],
      };
      expect(isExecuteBatchInput(validInput)).toBe(true);
    });

    it('should return true for input with depends_on', () => {
      const validInput: ExecuteBatchInput = {
        snippets: [
          { id: 'a', code: 'console.log("a")' },
          { id: 'b', code: 'console.log("b")', depends_on: ['a'] },
        ],
      };
      expect(isExecuteBatchInput(validInput)).toBe(true);
    });

    it('should return true for input with optional parameters', () => {
      const validInput: ExecuteBatchInput = {
        snippets: [{ id: 'a', code: 'console.log("a")' }],
        timeout_ms: 5000,
        stop_on_error: false,
      };
      expect(isExecuteBatchInput(validInput)).toBe(true);
    });

    it('should return true for single snippet', () => {
      expect(
        isExecuteBatchInput({ snippets: [{ id: 'single', code: 'console.log(1)' }] })
      ).toBe(true);
    });

    it('should return true for complex dependency graph', () => {
      const validInput: ExecuteBatchInput = {
        snippets: [
          { id: 'a', code: 'const a = 1' },
          { id: 'b', code: 'const b = 2', depends_on: ['a'] },
          { id: 'c', code: 'const c = 3', depends_on: ['a', 'b'] },
          { id: 'd', code: 'const d = 4', depends_on: ['c'] },
        ],
      };
      expect(isExecuteBatchInput(validInput)).toBe(true);
    });

    it('should return false for missing snippets', () => {
      expect(isExecuteBatchInput({})).toBe(false);
    });

    it('should return false for non-array snippets', () => {
      expect(isExecuteBatchInput({ snippets: 'not-an-array' })).toBe(false);
      expect(isExecuteBatchInput({ snippets: { id: 'a', code: 'test' } })).toBe(false);
    });

    it('should return false for snippets without id', () => {
      expect(isExecuteBatchInput({ snippets: [{ code: 'console.log(1)' }] })).toBe(false);
    });

    it('should return false for snippets without code', () => {
      expect(isExecuteBatchInput({ snippets: [{ id: 'a' }] })).toBe(false);
    });

    it('should return false for non-string id', () => {
      expect(isExecuteBatchInput({ snippets: [{ id: 123, code: 'test' }] })).toBe(false);
    });

    it('should return false for non-string code', () => {
      expect(isExecuteBatchInput({ snippets: [{ id: 'a', code: 123 }] })).toBe(false);
    });

    it('should return false for non-string depends_on items', () => {
      expect(
        isExecuteBatchInput({
          snippets: [{ id: 'a', code: 'console.log(1)', depends_on: [123] }],
        })
      ).toBe(false);
    });

    it('should return false for non-array depends_on', () => {
      expect(
        isExecuteBatchInput({
          snippets: [{ id: 'a', code: 'console.log(1)', depends_on: 'invalid' }],
        })
      ).toBe(false);
    });

    it('should return false for null input', () => {
      expect(isExecuteBatchInput(null)).toBe(false);
    });

    it('should return false for undefined input', () => {
      expect(isExecuteBatchInput(undefined)).toBe(false);
    });

    it('should return false for non-object snippet items', () => {
      expect(isExecuteBatchInput({ snippets: ['string-snippet'] })).toBe(false);
      expect(isExecuteBatchInput({ snippets: [null] })).toBe(false);
    });
  });

  describe('createExecuteBatchHandler validation', () => {
    let mockPool: ServerPool;

    beforeEach(() => {
      vi.clearAllMocks();
      mockPool = createMockPool();
    });

    it('should create handler function', () => {
      const handler = createExecuteBatchHandler(mockPool);
      expect(typeof handler).toBe('function');
    });

    it('should return error for empty snippets array', async () => {
      const handler = createExecuteBatchHandler(mockPool);
      const result = await handler({ snippets: [] });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain(
        'snippets array must contain at least one snippet'
      );
    });

    it('should return error for missing snippets', async () => {
      const handler = createExecuteBatchHandler(mockPool);
      const result = await handler({ snippets: null as unknown as Snippet[] });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain(
        'snippets parameter is required'
      );
    });

    it('should return error for snippet without id', async () => {
      const handler = createExecuteBatchHandler(mockPool);
      const result = await handler({
        snippets: [{ id: '', code: 'console.log(1)' }],
      });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain('must have a string id');
    });

    it('should return error for snippet without code', async () => {
      const handler = createExecuteBatchHandler(mockPool);
      const result = await handler({
        snippets: [{ id: 'a', code: '' }],
      });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain('must have a string code');
    });

    it('should return error for duplicate snippet IDs', async () => {
      const handler = createExecuteBatchHandler(mockPool);
      const result = await handler({
        snippets: [
          { id: 'a', code: 'console.log("a")' },
          { id: 'a', code: 'console.log("b")' },
        ],
      });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain('duplicate snippet IDs');
    });

    it('should return error for invalid timeout_ms (negative)', async () => {
      const handler = createExecuteBatchHandler(mockPool);
      const result = await handler({
        snippets: [{ id: 'a', code: 'console.log(1)' }],
        timeout_ms: -100,
      });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain(
        'timeout_ms must be a positive number'
      );
    });

    it('should return error for zero timeout_ms', async () => {
      const handler = createExecuteBatchHandler(mockPool);
      const result = await handler({
        snippets: [{ id: 'a', code: 'console.log(1)' }],
        timeout_ms: 0,
      });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain(
        'timeout_ms must be a positive number'
      );
    });

    it('should return error for non-numeric timeout_ms', async () => {
      const handler = createExecuteBatchHandler(mockPool);
      const result = await handler({
        snippets: [{ id: 'a', code: 'console.log(1)' }],
        timeout_ms: 'invalid' as unknown as number,
      });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain(
        'timeout_ms must be a positive number'
      );
    });
  });

  describe('dependency ordering validation', () => {
    let mockPool: ServerPool;

    beforeEach(() => {
      vi.clearAllMocks();
      mockPool = createMockPool();
    });

    it('should return error for unknown dependency', async () => {
      const handler = createExecuteBatchHandler(mockPool);

      const result = await handler({
        snippets: [{ id: 'a', code: 'console.log("a")', depends_on: ['nonexistent'] }],
      });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain(
        "depends on unknown snippet 'nonexistent'"
      );
    });

    it('should return error for multiple unknown dependencies', async () => {
      const handler = createExecuteBatchHandler(mockPool);

      const result = await handler({
        snippets: [
          { id: 'a', code: 'console.log("a")', depends_on: ['x', 'y'] },
        ],
      });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain('depends on unknown snippet');
    });
  });

  describe('circular dependency detection', () => {
    let mockPool: ServerPool;

    beforeEach(() => {
      vi.clearAllMocks();
      mockPool = createMockPool();
    });

    it('should detect simple circular dependency A -> B -> A', async () => {
      const handler = createExecuteBatchHandler(mockPool);

      const result = await handler({
        snippets: [
          { id: 'a', code: 'console.log("a")', depends_on: ['b'] },
          { id: 'b', code: 'console.log("b")', depends_on: ['a'] },
        ],
      });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain(
        'Circular dependency detected'
      );
    });

    it('should detect self-referencing dependency', async () => {
      const handler = createExecuteBatchHandler(mockPool);

      const result = await handler({
        snippets: [{ id: 'a', code: 'console.log("a")', depends_on: ['a'] }],
      });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain(
        'Circular dependency detected'
      );
    });

    it('should detect complex circular dependency A -> B -> C -> A', async () => {
      const handler = createExecuteBatchHandler(mockPool);

      const result = await handler({
        snippets: [
          { id: 'a', code: 'console.log("a")', depends_on: ['c'] },
          { id: 'b', code: 'console.log("b")', depends_on: ['a'] },
          { id: 'c', code: 'console.log("c")', depends_on: ['b'] },
        ],
      });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain(
        'Circular dependency detected'
      );
    });

    it('should detect partial circular dependency in larger graph', async () => {
      const handler = createExecuteBatchHandler(mockPool);

      const result = await handler({
        snippets: [
          { id: 'a', code: 'console.log("a")' },
          { id: 'b', code: 'console.log("b")', depends_on: ['a'] },
          { id: 'c', code: 'console.log("c")', depends_on: ['d'] },
          { id: 'd', code: 'console.log("d")', depends_on: ['c'] }, // circular: c <-> d
        ],
      });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain(
        'Circular dependency detected'
      );
    });

    it('should include involved snippets in circular dependency error', async () => {
      const handler = createExecuteBatchHandler(mockPool);

      const result = await handler({
        snippets: [
          { id: 'x', code: 'console.log("x")', depends_on: ['y'] },
          { id: 'y', code: 'console.log("y")', depends_on: ['x'] },
        ],
      });

      expect(result.isError).toBe(true);
      const errorText = (result.content[0] as { text: string }).text;
      expect(errorText).toContain('Circular dependency detected');
      // The error message should mention the involved snippets
      expect(errorText).toMatch(/x|y/);
    });
  });
});
