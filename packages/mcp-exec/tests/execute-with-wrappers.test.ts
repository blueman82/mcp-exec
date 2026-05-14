/**
 * Tests for execute_code_with_wrappers tool
 * Tests tool definition, wrapper generation, code composition, and error handling
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  createExecuteCodeWithWrappersToolDefinition,
  isExecuteWithWrappersInput,
  createExecuteWithWrappersHandler,
  type ExecuteWithWrappersInput,
} from '../src/tools/execute-with-wrappers.js';
import { generateToolWrapper, generateServerModule, generateMcpDictionary, normalizeName } from '../src/codegen/index.js';
import type { ServerPool, ToolDefinition } from '@justanothermldude/mcp-exec-oss-core';
import { ConnectionState } from '@justanothermldude/mcp-exec-oss-core';

/**
 * Create a mock ServerPool for testing
 */
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
          content: [{ type: 'text', text: 'result' }],
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

/**
 * Create sample tool definitions for testing
 */
function createSampleTools(): ToolDefinition[] {
  return [
    {
      name: 'read_file',
      description: 'Read a file from the filesystem',
      inputSchema: {
        type: 'object',
        properties: {
          path: {
            type: 'string',
            description: 'Path to the file to read',
          },
        },
        required: ['path'],
      },
    },
    {
      name: 'write_file',
      description: 'Write content to a file',
      inputSchema: {
        type: 'object',
        properties: {
          path: {
            type: 'string',
            description: 'Path to the file to write',
          },
          content: {
            type: 'string',
            description: 'Content to write to the file',
          },
        },
        required: ['path', 'content'],
      },
    },
  ];
}

describe('createExecuteCodeWithWrappersToolDefinition', () => {
  const tool = createExecuteCodeWithWrappersToolDefinition();

  it('should have correct tool name', () => {
    expect(tool.name).toBe('execute_code_with_wrappers');
  });

  it('should have descriptive description', () => {
    expect(tool.description).toContain('Execute TypeScript/JavaScript code');
    expect(tool.description).toContain('auto-generated typed wrappers');
  });

  it('should have correct inputSchema structure', () => {
    expect(tool.inputSchema).toBeDefined();
    expect(tool.inputSchema.type).toBe('object');
    expect(tool.inputSchema.properties).toBeDefined();
  });

  it('should have required fields: code and wrappers', () => {
    expect(tool.inputSchema.required).toContain('code');
    expect(tool.inputSchema.required).toContain('wrappers');
  });

  it('should have code property as string type', () => {
    const codeProperty = tool.inputSchema.properties.code;
    expect(codeProperty).toBeDefined();
    expect(codeProperty.type).toBe('string');
    expect(codeProperty.description).toBeDefined();
  });

  it('should have wrappers property as array type', () => {
    const wrappersProperty = tool.inputSchema.properties.wrappers;
    expect(wrappersProperty).toBeDefined();
    expect(wrappersProperty.type).toBe('array');
    expect(wrappersProperty.items).toEqual({ type: 'string' });
  });

  it('should have optional timeout_ms property as number type', () => {
    const timeoutProperty = tool.inputSchema.properties.timeout_ms;
    expect(timeoutProperty).toBeDefined();
    expect(timeoutProperty.type).toBe('number');
    expect(tool.inputSchema.required).not.toContain('timeout_ms');
  });
});

describe('isExecuteWithWrappersInput type guard', () => {
  describe('valid inputs', () => {
    it('should return true for minimal valid input', () => {
      const input = {
        code: 'console.log("hello")',
        wrappers: ['github'],
      };
      expect(isExecuteWithWrappersInput(input)).toBe(true);
    });

    it('should return true for input with multiple wrappers', () => {
      const input = {
        code: 'const result = await github.listRepos()',
        wrappers: ['github', 'filesystem', 'slack'],
      };
      expect(isExecuteWithWrappersInput(input)).toBe(true);
    });

    it('should return true for input with timeout_ms', () => {
      const input = {
        code: 'console.log("test")',
        wrappers: ['test-server'],
        timeout_ms: 5000,
      };
      expect(isExecuteWithWrappersInput(input)).toBe(true);
    });

    it('should return true for input with empty wrappers array', () => {
      // Note: The type guard allows empty array, validation happens in handler
      const input = {
        code: 'console.log("test")',
        wrappers: [],
      };
      expect(isExecuteWithWrappersInput(input)).toBe(true);
    });
  });

  describe('invalid inputs', () => {
    it('should return false for null', () => {
      expect(isExecuteWithWrappersInput(null)).toBe(false);
    });

    it('should return false for undefined', () => {
      expect(isExecuteWithWrappersInput(undefined)).toBe(false);
    });

    it('should return false for empty object', () => {
      expect(isExecuteWithWrappersInput({})).toBe(false);
    });

    it('should return false for missing code property', () => {
      const input = {
        wrappers: ['github'],
      };
      expect(isExecuteWithWrappersInput(input)).toBe(false);
    });

    it('should return false for missing wrappers property', () => {
      const input = {
        code: 'console.log("test")',
      };
      expect(isExecuteWithWrappersInput(input)).toBe(false);
    });

    it('should return false for non-string code', () => {
      const input = {
        code: 123,
        wrappers: ['github'],
      };
      expect(isExecuteWithWrappersInput(input)).toBe(false);
    });

    it('should return false for non-array wrappers', () => {
      const input = {
        code: 'console.log("test")',
        wrappers: 'github', // should be array
      };
      expect(isExecuteWithWrappersInput(input)).toBe(false);
    });

    it('should return false for wrappers array with non-string items', () => {
      const input = {
        code: 'console.log("test")',
        wrappers: [123, 'github'], // first item is not string
      };
      expect(isExecuteWithWrappersInput(input)).toBe(false);
    });

    it('should return false for primitive types', () => {
      expect(isExecuteWithWrappersInput('string')).toBe(false);
      expect(isExecuteWithWrappersInput(123)).toBe(false);
      expect(isExecuteWithWrappersInput(true)).toBe(false);
    });
  });
});

describe('generateToolWrapper', () => {
  it('should generate wrapper with correct function name', () => {
    const tool: ToolDefinition = {
      name: 'read_file',
      description: 'Read a file',
      inputSchema: { type: 'object', properties: {}, required: [] },
    };
    const wrapper = generateToolWrapper(tool, 'filesystem');
    expect(wrapper).toContain('async function read_file');
  });

  it('should generate wrapper with typed interface for input', () => {
    const tool: ToolDefinition = {
      name: 'create_issue',
      description: 'Create a GitHub issue',
      inputSchema: {
        type: 'object',
        properties: {
          title: { type: 'string', description: 'Issue title' },
          body: { type: 'string', description: 'Issue body' },
        },
        required: ['title'],
      },
    };
    const wrapper = generateToolWrapper(tool, 'github');

    // Should generate interface (without export keyword)
    expect(wrapper).toContain('interface CreateIssueInput');
    expect(wrapper).toContain('title: string');
    expect(wrapper).toContain('body?: string'); // optional since not in required
  });

  it('should include JSDoc with description', () => {
    const tool: ToolDefinition = {
      name: 'list_repos',
      description: 'List all repositories for the authenticated user',
      inputSchema: { type: 'object', properties: {}, required: [] },
    };
    const wrapper = generateToolWrapper(tool, 'github');

    expect(wrapper).toContain('/**');
    expect(wrapper).toContain('List all repositories for the authenticated user');
    expect(wrapper).toContain('*/');
  });

  it('should generate fetch call with correct server and tool names', () => {
    const tool: ToolDefinition = {
      name: 'send_message',
      description: 'Send a message',
      inputSchema: { type: 'object', properties: {}, required: [] },
    };
    const wrapper = generateToolWrapper(tool, 'slack');

    expect(wrapper).toContain("server: 'slack'");
    expect(wrapper).toContain("tool: 'send_message'");
    expect(wrapper).toContain('http://127.0.0.1:3000/call');
  });

  it('should handle tool names with special characters', () => {
    const tool: ToolDefinition = {
      name: 'get-user-info',
      description: 'Get user info',
      inputSchema: { type: 'object', properties: {}, required: [] },
    };
    const wrapper = generateToolWrapper(tool, 'api');

    // Should sanitize to valid identifier
    expect(wrapper).toContain('async function get_user_info');
  });

  it('should handle array type properties', () => {
    const tool: ToolDefinition = {
      name: 'batch_process',
      description: 'Process multiple items',
      inputSchema: {
        type: 'object',
        properties: {
          items: {
            type: 'array',
            items: { type: 'string' },
            description: 'Items to process',
          },
        },
        required: ['items'],
      },
    };
    const wrapper = generateToolWrapper(tool, 'processor');

    expect(wrapper).toContain('items: string[]');
  });
});

describe('generateServerModule', () => {
  it('should generate module header comment', () => {
    const tools: ToolDefinition[] = [];
    const module = generateServerModule(tools, 'test-server');

    expect(module).toContain('Auto-generated TypeScript wrappers');
    expect(module).toContain('test-server MCP server tools');
  });

  it('should generate namespace object with methods for all tools', () => {
    const tools = createSampleTools();
    const module = generateServerModule(tools, 'filesystem');

    // Should create raw namespace object with _raw suffix
    expect(module).toContain('const filesystem_raw = {');
    // Should create fuzzy Proxy wrapper for case-agnostic access
    expect(module).toContain('const filesystem = new Proxy(filesystem_raw');
    // Should use original tool names (snake_case) so discovery matches usage
    expect(module).toContain('read_file:');
    expect(module).toContain('write_file:');
  });

  it('should include interfaces for tools with properties', () => {
    const tools = createSampleTools();
    const module = generateServerModule(tools, 'filesystem');

    // Interfaces without export keyword
    expect(module).toContain('interface ReadFileInput');
    expect(module).toContain('interface WriteFileInput');
  });

  it('should handle empty tools array', () => {
    const module = generateServerModule([], 'empty-server');

    expect(module).toContain('Auto-generated TypeScript wrappers');
    expect(module).toContain('empty-server');
    // Should not contain any function definitions (empty tools array)
    expect(module).not.toContain('async (');
  });
});

describe('createExecuteWithWrappersHandler', () => {
  let mockPool: ServerPool;

  beforeEach(() => {
    mockPool = createMockPool();
  });

  it('should create a handler function', () => {
    const { handler } = createExecuteWithWrappersHandler(mockPool);
    expect(typeof handler).toBe('function');
  });

  describe('input validation', () => {
    it('should return error for missing code', async () => {
      const { handler } = createExecuteWithWrappersHandler(mockPool);
      const result = await handler({ code: '', wrappers: ['test'] } as ExecuteWithWrappersInput);

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain('code parameter is required');
    });

    it('should return error for missing wrappers', async () => {
      const { handler } = createExecuteWithWrappersHandler(mockPool);
      const result = await handler({ code: 'console.log(1)', wrappers: null } as unknown as ExecuteWithWrappersInput);

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain('wrappers parameter is required');
    });

    it('should return error for empty wrappers array', async () => {
      const { handler } = createExecuteWithWrappersHandler(mockPool);
      const result = await handler({ code: 'console.log(1)', wrappers: [] });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain('wrappers array must contain at least one server name');
    });

    it('should return error for invalid timeout_ms', async () => {
      const { handler } = createExecuteWithWrappersHandler(mockPool);
      const result = await handler({
        code: 'console.log(1)',
        wrappers: ['test'],
        timeout_ms: -1,
      });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain('timeout_ms must be a positive number');
    });

    it('should return error for zero timeout_ms', async () => {
      const { handler } = createExecuteWithWrappersHandler(mockPool);
      const result = await handler({
        code: 'console.log(1)',
        wrappers: ['test'],
        timeout_ms: 0,
      });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain('timeout_ms must be a positive number');
    });
  });

  describe('server connection errors', () => {
    it('should return error when server is not found', async () => {
      const errorPool = createMockPool({
        getConnection: vi.fn().mockRejectedValue(new Error('Server not found: unknown-server')),
      });

      const { handler } = createExecuteWithWrappersHandler(errorPool);
      const result = await handler({
        code: 'console.log(1)',
        wrappers: ['unknown-server'],
      });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain("Error generating wrapper for server 'unknown-server'");
    });

    it('should return error when connection times out', async () => {
      const timeoutPool = createMockPool({
        getConnection: vi.fn().mockRejectedValue(new Error('Connection timeout')),
      });

      const { handler } = createExecuteWithWrappersHandler(timeoutPool);
      const result = await handler({
        code: 'console.log(1)',
        wrappers: ['slow-server'],
      });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain("Error generating wrapper for server 'slow-server'");
      expect((result.content[0] as { text: string }).text).toContain('Connection timeout');
    });
  });

  describe('tool fetching', () => {
    it('should call getTools for each server in wrappers array', async () => {
      const mockGetTools = vi.fn().mockResolvedValue(createSampleTools());
      const mockConnection = {
        serverId: 'test-server',
        state: ConnectionState.Connected,
        connect: vi.fn().mockResolvedValue(undefined),
        disconnect: vi.fn().mockResolvedValue(undefined),
        isConnected: vi.fn().mockReturnValue(true),
        getTools: mockGetTools,
        client: {
          callTool: vi.fn().mockResolvedValue({
            content: [{ type: 'text', text: 'result' }],
            isError: false,
          }),
        },
      };

      const pool = createMockPool({
        getConnection: vi.fn().mockResolvedValue(mockConnection),
      });

      const { handler } = createExecuteWithWrappersHandler(pool);

      // The handler will fail at execution stage (no real sandbox), but we can verify
      // that getConnection and getTools were called
      try {
        await handler({
          code: 'console.log("test")',
          wrappers: ['server1', 'server2'],
        });
      } catch {
        // Expected to fail at execution stage
      }

      // Verify getConnection was called for each server
      expect(pool.getConnection).toHaveBeenCalledWith('server1');
    });

    it('should handle getTools failure gracefully', async () => {
      const mockConnection = {
        serverId: 'failing-server',
        state: ConnectionState.Connected,
        connect: vi.fn().mockResolvedValue(undefined),
        disconnect: vi.fn().mockResolvedValue(undefined),
        isConnected: vi.fn().mockReturnValue(true),
        getTools: vi.fn().mockRejectedValue(new Error('Failed to fetch tools')),
        client: {
          callTool: vi.fn(),
        },
      };

      const pool = createMockPool({
        getConnection: vi.fn().mockResolvedValue(mockConnection),
      });

      const { handler } = createExecuteWithWrappersHandler(pool);
      const result = await handler({
        code: 'console.log("test")',
        wrappers: ['failing-server'],
      });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain("Error generating wrapper for server 'failing-server'");
      expect((result.content[0] as { text: string }).text).toContain('Failed to fetch tools');
    });
  });

  describe('connection management', () => {
    it('should release connection after fetching tools', async () => {
      const mockConnection = {
        serverId: 'test-server',
        state: ConnectionState.Connected,
        connect: vi.fn().mockResolvedValue(undefined),
        disconnect: vi.fn().mockResolvedValue(undefined),
        isConnected: vi.fn().mockReturnValue(true),
        getTools: vi.fn().mockResolvedValue([]),
        client: {
          callTool: vi.fn().mockResolvedValue({
            content: [{ type: 'text', text: 'result' }],
            isError: false,
          }),
        },
      };

      const pool = createMockPool({
        getConnection: vi.fn().mockResolvedValue(mockConnection),
      });

      const { handler } = createExecuteWithWrappersHandler(pool);

      try {
        await handler({
          code: 'console.log("test")',
          wrappers: ['test-server'],
        });
      } catch {
        // Expected to fail at execution stage
      }

      // Verify releaseConnection was called
      expect(pool.releaseConnection).toHaveBeenCalledWith('test-server');
    });
  });
});

describe('Code composition', () => {
  it('should verify wrapper generation includes server-specific code', () => {
    const tools: ToolDefinition[] = [
      {
        name: 'test_tool',
        description: 'A test tool',
        inputSchema: {
          type: 'object',
          properties: {
            param1: { type: 'string' },
          },
          required: ['param1'],
        },
      },
    ];

    const module = generateServerModule(tools, 'my-server');

    // Verify server name is embedded in the wrapper (JSON.stringify uses double quotes)
    expect(module).toContain('server: "my-server"');
    expect(module).toContain('tool: "test_tool"');
  });

  it('should preserve parameter descriptions in generated code', () => {
    const tools: ToolDefinition[] = [
      {
        name: 'documented_tool',
        description: 'A well-documented tool',
        inputSchema: {
          type: 'object',
          properties: {
            importantParam: {
              type: 'string',
              description: 'This parameter is very important',
            },
          },
          required: ['importantParam'],
        },
      },
    ];

    const module = generateServerModule(tools, 'docs-server');

    // Verify description is included in JSDoc
    expect(module).toContain('This parameter is very important');
  });
});

describe('Edge cases', () => {
  it('should handle tools with no inputSchema', () => {
    const tool: ToolDefinition = {
      name: 'simple_tool',
      description: 'A tool with no parameters',
      inputSchema: undefined as unknown as ToolDefinition['inputSchema'],
    };

    // Should not throw
    const wrapper = generateToolWrapper(tool, 'simple-server');
    expect(wrapper).toContain('async function simple_tool');
    // Should have empty args
    expect(wrapper).toContain('args: {}');
  });

  it('should handle tools with empty properties', () => {
    const tool: ToolDefinition = {
      name: 'empty_props_tool',
      description: 'A tool with empty properties',
      inputSchema: {
        type: 'object',
        properties: {},
        required: [],
      },
    };

    const wrapper = generateToolWrapper(tool, 'empty-server');
    expect(wrapper).toContain('async function empty_props_tool');
    // Should not generate interface for empty properties
    expect(wrapper).not.toContain('interface ');
  });

  it('should handle tools with numeric-prefixed names', () => {
    const tool: ToolDefinition = {
      name: '123_tool',
      description: 'A tool with numeric prefix',
      inputSchema: { type: 'object', properties: {}, required: [] },
    };

    const wrapper = generateToolWrapper(tool, 'numeric-server');
    // Should prefix with underscore to make valid identifier
    expect(wrapper).toContain('async function _123_tool');
  });

  it('should handle nested object properties', () => {
    const tool: ToolDefinition = {
      name: 'nested_tool',
      description: 'A tool with nested properties',
      inputSchema: {
        type: 'object',
        properties: {
          config: {
            type: 'object',
            properties: {
              nested: { type: 'string' },
            },
          },
        },
        required: [],
      },
    };

    const wrapper = generateToolWrapper(tool, 'nested-server');
    expect(wrapper).toContain('config?:');
    // Nested object is rendered inline: { nested?: string }
    expect(wrapper).toContain('nested?:');
    expect(wrapper).toContain('string');
  });
});

/**
 * Tests for case-agnostic wrapper resolution
 */
describe('normalizeName', () => {
  it('should convert hyphenated names to lowercase without separators', () => {
    expect(normalizeName('brave-search')).toBe('bravesearch');
  });

  it('should convert underscored names to lowercase without separators', () => {
    expect(normalizeName('brave_search')).toBe('bravesearch');
  });

  it('should convert camelCase names to lowercase', () => {
    expect(normalizeName('braveSearch')).toBe('bravesearch');
  });

  it('should convert PascalCase names to lowercase', () => {
    expect(normalizeName('BraveSearch')).toBe('bravesearch');
  });

  it('should handle mixed formats consistently', () => {
    // All variations should normalize to the same string
    const variations = ['brave-search', 'brave_search', 'braveSearch', 'BraveSearch', 'BRAVE-SEARCH', 'BRAVE_SEARCH'];
    const normalized = variations.map(normalizeName);
    expect(new Set(normalized).size).toBe(1);
    expect(normalized[0]).toBe('bravesearch');
  });

  it('should handle already normalized names', () => {
    expect(normalizeName('bravesearch')).toBe('bravesearch');
  });

  it('should handle empty string', () => {
    expect(normalizeName('')).toBe('');
  });

  it('should handle names with multiple separators', () => {
    expect(normalizeName('my-brave-search-server')).toBe('mybravesearchserver');
    expect(normalizeName('my_brave_search_server')).toBe('mybravesearchserver');
  });

  it('should handle names with numbers', () => {
    expect(normalizeName('server-1')).toBe('server1');
    expect(normalizeName('server_2')).toBe('server2');
  });
});

describe('generateMcpDictionary', () => {
  it('should generate mcp_servers_raw object', () => {
    const dictionary = generateMcpDictionary(['github', 'filesystem']);
    expect(dictionary).toContain('const mcp_servers_raw');
  });

  it('should wrap with Proxy for case-agnostic access', () => {
    const dictionary = generateMcpDictionary(['github']);
    expect(dictionary).toContain('new Proxy');
    expect(dictionary).toContain('const mcp = new Proxy(mcp_servers_raw');
  });

  it('should include comment header with server list', () => {
    const dictionary = generateMcpDictionary(['github', 'filesystem']);
    expect(dictionary).toContain('MCP Server Dictionary');
    expect(dictionary).toContain("mcp['github']");
    expect(dictionary).toContain("mcp['filesystem']");
  });

  it('should map original server names to namespace variables', () => {
    const dictionary = generateMcpDictionary(['brave-search', 'github']);
    expect(dictionary).toContain('"brave-search": brave_search');
    expect(dictionary).toContain('"github": github');
  });

  it('should handle empty server list', () => {
    const dictionary = generateMcpDictionary([]);
    expect(dictionary).toContain('const mcp_servers_raw');
    expect(dictionary).toContain('const mcp = new Proxy');
  });

  it('should include aliases in comments', () => {
    const dictionary = generateMcpDictionary(['brave-search']);
    expect(dictionary).toContain('Aliases:');
    expect(dictionary).toContain('brave_search');
  });
});

describe('generateServerModule Proxy wrapping', () => {
  it('should generate raw namespace with _raw suffix', () => {
    const tools = createSampleTools();
    const module = generateServerModule(tools, 'github');
    expect(module).toContain('const github_raw = {');
  });

  it('should wrap raw namespace with Proxy', () => {
    const tools = createSampleTools();
    const module = generateServerModule(tools, 'github');
    expect(module).toContain('const github = new Proxy(github_raw');
  });

  it('should include case-insensitive access comment', () => {
    const tools = createSampleTools();
    const module = generateServerModule(tools, 'github');
    expect(module).toContain('Case-insensitive');
    expect(module).toContain('methodName, method_name, and method-name all work');
  });

  it('should generate Proxy with fuzzy matching logic', () => {
    const tools = createSampleTools();
    const module = generateServerModule(tools, 'github');
    // Verify Proxy handler structure
    expect(module).toContain('get(target, prop)');
    expect(module).toContain('hasOwnProperty.call(target, prop)');
    expect(module).toContain('normalizedProp');
    expect(module).toContain('normalizedKey');
  });

  it('should handle server names with hyphens', () => {
    const tools = createSampleTools();
    const module = generateServerModule(tools, 'brave-search');
    expect(module).toContain('const brave_search_raw = {');
    expect(module).toContain('const brave_search = new Proxy(brave_search_raw');
  });
});

describe('Proxy Symbol passthrough', () => {
  it('should handle non-string property access in Proxy', () => {
    const tools = createSampleTools();
    const module = generateServerModule(tools, 'test-server');
    // Verify Symbol handling code exists
    expect(module).toContain("typeof prop !== 'string'");
    expect(module).toContain('return undefined');
  });
});

describe('Proxy error message content', () => {
  it('should include available options in error message', () => {
    const tools = createSampleTools();
    const module = generateServerModule(tools, 'test-server');
    // Verify error message includes available options
    expect(module).toContain('Object.keys(target)');
    expect(module).toContain('throw new TypeError');
    expect(module).toContain('Available:');
  });

  it('should include context name in error message', () => {
    const tools = createSampleTools();
    const module = generateServerModule(tools, 'my-custom-server');
    // Verify the server name is in the error message
    expect(module).toContain('my-custom-server');
  });

  it('should include the invalid property name in error message', () => {
    const tools = createSampleTools();
    const module = generateServerModule(tools, 'test-server');
    // Verify the error message template includes the requested property
    expect(module).toContain('${prop}');
    expect(module).toContain('not found on');
  });
});
