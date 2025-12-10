/**
 * Unit tests for execute_with_context tool
 * Tests tool definition, type guards, input validation, and context serialization
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  executeWithContextTool,
  isExecuteWithContextInput,
  createExecuteWithContextHandler,
  type ExecuteWithContextInput,
} from '../src/tools/execute-with-context.js';
import type { ServerPool } from '@justanothermldude/meta-mcp-core';
import { ConnectionState } from '@justanothermldude/meta-mcp-core';

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

describe('execute_with_context tool', () => {
  describe('executeWithContextTool definition', () => {
    it('should have correct name and description', () => {
      expect(executeWithContextTool.name).toBe('execute_with_context');
      expect(executeWithContextTool.description).toContain('pre-injected context variables');
      expect(executeWithContextTool.description).toContain('global `context` variable');
    });

    it('should have correct input schema type', () => {
      expect(executeWithContextTool.inputSchema.type).toBe('object');
      expect(executeWithContextTool.inputSchema.required).toContain('code');
    });

    it('should have code property in schema', () => {
      expect(executeWithContextTool.inputSchema.properties.code).toBeDefined();
      expect(executeWithContextTool.inputSchema.properties.code.type).toBe('string');
    });

    it('should have context property in schema', () => {
      expect(executeWithContextTool.inputSchema.properties.context).toBeDefined();
      expect(executeWithContextTool.inputSchema.properties.context.type).toBe('object');
    });

    it('should have timeout_ms property in schema', () => {
      expect(executeWithContextTool.inputSchema.properties.timeout_ms).toBeDefined();
      expect(executeWithContextTool.inputSchema.properties.timeout_ms.type).toBe('number');
    });

    it('should allow additional properties in context schema', () => {
      expect(executeWithContextTool.inputSchema.properties.context.additionalProperties).toBe(true);
    });

    it('should have code as required field', () => {
      expect(executeWithContextTool.inputSchema.required).toEqual(['code']);
      expect(executeWithContextTool.inputSchema.required).not.toContain('context');
      expect(executeWithContextTool.inputSchema.required).not.toContain('timeout_ms');
    });
  });

  describe('isExecuteWithContextInput type guard', () => {
    it('should return true for valid input with code only', () => {
      const validInput: ExecuteWithContextInput = {
        code: 'console.log("hello")',
      };
      expect(isExecuteWithContextInput(validInput)).toBe(true);
    });

    it('should return true for valid input with code and context', () => {
      const validInput: ExecuteWithContextInput = {
        code: 'console.log(context.name)',
        context: { name: 'test', value: 42 },
      };
      expect(isExecuteWithContextInput(validInput)).toBe(true);
    });

    it('should return true for valid input with all parameters', () => {
      const validInput: ExecuteWithContextInput = {
        code: 'console.log(context.data)',
        context: { data: [1, 2, 3] },
        timeout_ms: 5000,
      };
      expect(isExecuteWithContextInput(validInput)).toBe(true);
    });

    it('should return true for input with empty context object', () => {
      const validInput: ExecuteWithContextInput = {
        code: 'console.log("hello")',
        context: {},
      };
      expect(isExecuteWithContextInput(validInput)).toBe(true);
    });

    it('should return true for complex nested context', () => {
      const validInput: ExecuteWithContextInput = {
        code: 'console.log(context)',
        context: {
          user: {
            name: 'John',
            address: {
              city: 'NYC',
              zip: 10001,
            },
          },
          items: [1, 2, 3],
          active: true,
        },
      };
      expect(isExecuteWithContextInput(validInput)).toBe(true);
    });

    it('should return false for missing code', () => {
      expect(isExecuteWithContextInput({})).toBe(false);
      expect(isExecuteWithContextInput({ context: { foo: 'bar' } })).toBe(false);
    });

    it('should return false for non-string code', () => {
      expect(isExecuteWithContextInput({ code: 123 })).toBe(false);
      expect(isExecuteWithContextInput({ code: null })).toBe(false);
      expect(isExecuteWithContextInput({ code: ['log'] })).toBe(false);
      expect(isExecuteWithContextInput({ code: true })).toBe(false);
    });

    it('should return false for array context', () => {
      expect(isExecuteWithContextInput({ code: 'test', context: [1, 2, 3] })).toBe(false);
    });

    it('should return false for null context', () => {
      expect(isExecuteWithContextInput({ code: 'test', context: null })).toBe(false);
    });

    it('should return false for primitive context', () => {
      expect(isExecuteWithContextInput({ code: 'test', context: 'string' })).toBe(false);
      expect(isExecuteWithContextInput({ code: 'test', context: 42 })).toBe(false);
      expect(isExecuteWithContextInput({ code: 'test', context: true })).toBe(false);
    });

    it('should return false for null input', () => {
      expect(isExecuteWithContextInput(null)).toBe(false);
    });

    it('should return false for undefined input', () => {
      expect(isExecuteWithContextInput(undefined)).toBe(false);
    });

    it('should return false for non-object input', () => {
      expect(isExecuteWithContextInput('string')).toBe(false);
      expect(isExecuteWithContextInput(123)).toBe(false);
      expect(isExecuteWithContextInput(true)).toBe(false);
    });
  });

  describe('createExecuteWithContextHandler validation', () => {
    let mockPool: ServerPool;

    beforeEach(() => {
      vi.clearAllMocks();
      mockPool = createMockPool();
    });

    it('should create handler function', () => {
      const handler = createExecuteWithContextHandler(mockPool);
      expect(typeof handler).toBe('function');
    });

    it('should return error for missing code', async () => {
      const handler = createExecuteWithContextHandler(mockPool);
      const result = await handler({ code: '' });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain(
        'code parameter is required'
      );
    });

    it('should return error for non-string code', async () => {
      const handler = createExecuteWithContextHandler(mockPool);
      const result = await handler({ code: 123 as unknown as string });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain(
        'code parameter is required and must be a string'
      );
    });

    it('should return error for null code', async () => {
      const handler = createExecuteWithContextHandler(mockPool);
      const result = await handler({ code: null as unknown as string });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain(
        'code parameter is required and must be a string'
      );
    });

    it('should return error for array context', async () => {
      const handler = createExecuteWithContextHandler(mockPool);
      const result = await handler({
        code: 'console.log(1)',
        context: [1, 2, 3] as unknown as Record<string, unknown>,
      });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain('context must be an object');
    });

    it('should return error for null context', async () => {
      const handler = createExecuteWithContextHandler(mockPool);
      const result = await handler({
        code: 'console.log(1)',
        context: null as unknown as Record<string, unknown>,
      });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain('context must be an object');
    });

    it('should return error for string context', async () => {
      const handler = createExecuteWithContextHandler(mockPool);
      const result = await handler({
        code: 'console.log(1)',
        context: 'invalid' as unknown as Record<string, unknown>,
      });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain('context must be an object');
    });

    it('should return error for invalid timeout_ms (negative)', async () => {
      const handler = createExecuteWithContextHandler(mockPool);
      const result = await handler({
        code: 'console.log(1)',
        timeout_ms: -100,
      });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain(
        'timeout_ms must be a positive number'
      );
    });

    it('should return error for zero timeout_ms', async () => {
      const handler = createExecuteWithContextHandler(mockPool);
      const result = await handler({
        code: 'console.log(1)',
        timeout_ms: 0,
      });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain(
        'timeout_ms must be a positive number'
      );
    });

    it('should return error for non-numeric timeout_ms', async () => {
      const handler = createExecuteWithContextHandler(mockPool);
      const result = await handler({
        code: 'console.log(1)',
        timeout_ms: 'invalid' as unknown as number,
      });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain(
        'timeout_ms must be a positive number'
      );
    });
  });

  describe('context serialization tests', () => {
    let mockPool: ServerPool;

    beforeEach(() => {
      vi.clearAllMocks();
      mockPool = createMockPool();
    });

    it('should return error for circular reference in context', async () => {
      const handler = createExecuteWithContextHandler(mockPool);

      // Create circular reference
      const circularObj: Record<string, unknown> = { name: 'test' };
      circularObj.self = circularObj;

      const result = await handler({
        code: 'console.log(context)',
        context: circularObj,
      });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain(
        'circular references'
      );
    });

    it('should return error for deeply nested circular reference', async () => {
      const handler = createExecuteWithContextHandler(mockPool);

      // Create deeply nested circular reference
      const obj: Record<string, unknown> = {
        level1: {
          level2: {
            level3: {},
          },
        },
      };
      ((obj.level1 as Record<string, unknown>).level2 as Record<string, unknown>).level3 = obj;

      const result = await handler({
        code: 'console.log(context)',
        context: obj,
      });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain(
        'circular references'
      );
    });

    it('should return error for circular reference via array', async () => {
      const handler = createExecuteWithContextHandler(mockPool);

      // Create circular reference via array
      const arr: unknown[] = [];
      const obj = { items: arr };
      arr.push(obj);

      const result = await handler({
        code: 'console.log(context)',
        context: obj,
      });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain(
        'circular references'
      );
    });
  });

  describe('context value types', () => {
    it('should validate context with string values', () => {
      const input = {
        code: 'console.log(context.message)',
        context: { message: 'hello world' },
      };
      expect(isExecuteWithContextInput(input)).toBe(true);
    });

    it('should validate context with numeric values', () => {
      const input = {
        code: 'console.log(context.value)',
        context: { value: 42, decimal: 3.14, negative: -10 },
      };
      expect(isExecuteWithContextInput(input)).toBe(true);
    });

    it('should validate context with boolean values', () => {
      const input = {
        code: 'console.log(context.flag)',
        context: { flag: true, disabled: false },
      };
      expect(isExecuteWithContextInput(input)).toBe(true);
    });

    it('should validate context with null values', () => {
      const input = {
        code: 'console.log(context.empty)',
        context: { empty: null, another: 'value' },
      };
      expect(isExecuteWithContextInput(input)).toBe(true);
    });

    it('should validate context with array values', () => {
      const input = {
        code: 'console.log(context.items)',
        context: { items: [1, 2, 3], tags: ['a', 'b'] },
      };
      expect(isExecuteWithContextInput(input)).toBe(true);
    });

    it('should validate context with nested object values', () => {
      const input = {
        code: 'console.log(context.user)',
        context: {
          user: {
            name: 'John',
            profile: {
              email: 'john@example.com',
            },
          },
        },
      };
      expect(isExecuteWithContextInput(input)).toBe(true);
    });

    it('should validate context with mixed types', () => {
      const input = {
        code: 'console.log(context)',
        context: {
          string: 'text',
          number: 123,
          boolean: true,
          nullValue: null,
          array: [1, 'two', true],
          object: { nested: 'value' },
        },
      };
      expect(isExecuteWithContextInput(input)).toBe(true);
    });

    it('should validate context with special string values', () => {
      const input = {
        code: 'console.log(context)',
        context: {
          withQuotes: 'Hello "World"',
          withSingleQuotes: "It's working",
          withBackslash: 'path\\to\\file',
          withNewline: 'line1\nline2',
          withTab: 'col1\tcol2',
        },
      };
      expect(isExecuteWithContextInput(input)).toBe(true);
    });

    it('should validate context with unicode strings', () => {
      const input = {
        code: 'console.log(context.emoji)',
        context: {
          emoji: 'Hello World!',
          japanese: '',
          chinese: '',
        },
      };
      expect(isExecuteWithContextInput(input)).toBe(true);
    });

    it('should validate context with empty string values', () => {
      const input = {
        code: 'console.log(context.empty)',
        context: { empty: '', nonEmpty: 'value' },
      };
      expect(isExecuteWithContextInput(input)).toBe(true);
    });

    it('should validate context with large array values', () => {
      const input = {
        code: 'console.log(context.numbers.length)',
        context: { numbers: Array.from({ length: 1000 }, (_, i) => i) },
      };
      expect(isExecuteWithContextInput(input)).toBe(true);
    });
  });
});
