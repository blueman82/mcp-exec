/**
 * Integration tests for mcp-exec with real MCP calls
 * Tests full code execution flow: sandbox -> fd transport -> filesystem MCP server -> output
 *
 * This file contains both:
 * 1. Unit-level integration tests (with mocks) - always run
 * 2. Real MCP server integration tests - run when RUN_REAL_MCP_TESTS=true
 *
 * NOTE: MCPBridge (HTTP TCP bridge) was retired in favour of the fd transport.
 * Tests that exercised MCPBridge have been removed.
 */
import { describe, it, expect, vi, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';
import { mkdir, writeFile, rm, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { createMcpExecServer } from '../src/server.js';
import { SandboxExecutor } from '../src/sandbox/executor.js';
import { createExecuteWithWrappersHandler, isExecuteWithWrappersInput } from '../src/tools/execute-with-wrappers.js';
import type { ServerPool, MCPConnection } from 'mcp-exec-core';
import { ConnectionState, ServerPool as RealServerPool, createConnection, getServerConfig } from 'mcp-exec-core';

// Test directory for filesystem operations
const TEST_DIR = join(tmpdir(), 'mcp-exec-integration-test');
const TEST_FILE = 'test.txt';
const TEST_CONTENT = 'Hello from integration test';

// Check if we should run real MCP tests
const RUN_REAL_MCP_TESTS = process.env.RUN_REAL_MCP_TESTS === 'true';

// Mock ServerPool for unit-level integration tests
function createMockPool(overrides: Partial<ServerPool> = {}): ServerPool {
  return {
    getConnection: vi.fn().mockResolvedValue({
      serverId: 'filesystem',
      state: ConnectionState.Connected,
      connect: vi.fn().mockResolvedValue(undefined),
      disconnect: vi.fn().mockResolvedValue(undefined),
      isConnected: vi.fn().mockReturnValue(true),
      getTools: vi.fn().mockResolvedValue([]),
      client: {
        callTool: vi.fn().mockResolvedValue({
          content: [{ type: 'text', text: TEST_CONTENT }],
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

describe('mcp-exec Integration Tests', () => {
  beforeAll(async () => {
    // Create test directory and file
    await mkdir(TEST_DIR, { recursive: true });
    await writeFile(join(TEST_DIR, TEST_FILE), TEST_CONTENT);
  });

  afterAll(async () => {
    // Cleanup test directory
    try {
      await rm(TEST_DIR, { recursive: true, force: true });
    } catch {
      // Ignore cleanup errors
    }
  });

  describe('createMcpExecServer', () => {
    let mockPool: ServerPool;

    beforeEach(() => {
      mockPool = createMockPool();
    });

    it('should create server with tools', () => {
      const { server, listToolsHandler, callToolHandler, shutdown } = createMcpExecServer(mockPool);

      expect(server).toBeDefined();
      expect(listToolsHandler).toBeDefined();
      expect(callToolHandler).toBeDefined();
      expect(shutdown).toBeDefined();
    });

    it('should list all 3 tools', async () => {
      const { listToolsHandler, shutdown } = createMcpExecServer(mockPool);
      const result = await listToolsHandler();

      expect(result.tools).toHaveLength(3);
      const toolNames = result.tools.map((t) => t.name);
      expect(toolNames).toContain('list_available_mcp_servers');
      expect(toolNames).toContain('get_mcp_tool_schema');
      expect(toolNames).toContain('execute_code_with_wrappers');
      expect(result.tools[0].inputSchema).toBeDefined();

      await shutdown();
    });

    it('should return error for unknown tool', async () => {
      const { callToolHandler, shutdown } = createMcpExecServer(mockPool);
      const result = await callToolHandler({
        name: 'unknown_tool',
        arguments: {},
      });

      expect(result.isError).toBe(true);
      expect(result.content[0]).toHaveProperty('text');
      expect((result.content[0] as { type: string; text: string }).text).toContain('Unknown tool');

      await shutdown();
    });

    it('should validate execute_code_with_wrappers arguments', async () => {
      const { callToolHandler, shutdown } = createMcpExecServer(mockPool);
      const result = await callToolHandler({
        name: 'execute_code_with_wrappers',
        arguments: {}, // Missing required 'code' and 'wrappers' fields
      });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { type: string; text: string }).text).toContain('Invalid arguments');

      await shutdown();
    });
  });

  describe('isExecuteWithWrappersInput type guard', () => {
    it('should return true for valid input', () => {
      expect(isExecuteWithWrappersInput({ code: 'console.log(1)', wrappers: ['server1'] })).toBe(true);
      expect(isExecuteWithWrappersInput({ code: 'console.log(1)', wrappers: ['s1', 's2'], timeout_ms: 5000 })).toBe(true);
    });

    it('should return false for invalid input', () => {
      expect(isExecuteWithWrappersInput({})).toBe(false);
      expect(isExecuteWithWrappersInput({ code: 'test' })).toBe(false); // missing wrappers
      expect(isExecuteWithWrappersInput({ wrappers: ['s1'] })).toBe(false); // missing code
      expect(isExecuteWithWrappersInput({ code: 123, wrappers: ['s1'] })).toBe(false);
      expect(isExecuteWithWrappersInput(null)).toBe(false);
      expect(isExecuteWithWrappersInput(undefined)).toBe(false);
    });
  });

  describe('createExecuteWithWrappersHandler', () => {
    let mockPool: ServerPool;

    beforeEach(() => {
      mockPool = createMockPool();
    });

    it('should create handler function', () => {
      const { handler } = createExecuteWithWrappersHandler(mockPool);
      expect(typeof handler).toBe('function');
    });

    it('should return error for missing code', async () => {
      const { handler } = createExecuteWithWrappersHandler(mockPool);
      const result = await handler({ code: '', wrappers: ['test'] });

      expect(result.isError).toBe(true);
      expect(result.content[0]).toHaveProperty('text');
      expect((result.content[0] as { text: string }).text).toContain('code parameter is required');
    });

    it('should return error for empty wrappers', async () => {
      const { handler } = createExecuteWithWrappersHandler(mockPool);
      const result = await handler({ code: 'console.log(1)', wrappers: [] });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain('wrappers array must contain at least one');
    });

    it('should return error for invalid timeout', async () => {
      const { handler } = createExecuteWithWrappersHandler(mockPool);
      const result = await handler({ code: 'console.log(1)', wrappers: ['test'], timeout_ms: -1 });

      expect(result.isError).toBe(true);
      expect((result.content[0] as { text: string }).text).toContain('timeout_ms must be a positive number');
    });
  });

  describe('SandboxExecutor configuration', () => {
    it('mcpBridgePort is deprecated and does not add a localhost domain (fd transport)', () => {
      // mcpBridgePort is a deprecated no-op; MCP calls go via inherited fds, not TCP.
      const executor = new SandboxExecutor({ mcpBridgePort: 4000 });
      const config = executor.getConfig();

      expect(config.network?.allowedDomains).toBeDefined();
      expect(config.network?.allowedDomains).not.toContain('localhost:4000');
      expect(config.network?.allowedDomains).toHaveLength(0);
    });

    it('should configure executor with additional write paths', () => {
      const executor = new SandboxExecutor({
        additionalWritePaths: [TEST_DIR],
      });
      const config = executor.getConfig();

      expect(config.filesystem?.allowWrite).toContain(TEST_DIR);
    });
  });

  describe('Test server configuration', () => {
    it('should have valid test-servers.json structure', async () => {
      const configPath = join(__dirname, 'fixtures', 'test-servers.json');
      const content = await readFile(configPath, 'utf-8');
      const config = JSON.parse(content);

      expect(config.mcpServers).toBeDefined();
      expect(config.mcpServers.filesystem).toBeDefined();
      expect(config.mcpServers.filesystem.command).toBe('npx');
      expect(config.mcpServers.filesystem.args).toContain('@modelcontextprotocol/server-filesystem');
    });
  });
});

describe('Error handling', () => {
  describe('Connection errors via fd transport', () => {
    it('should handle pool connection failures gracefully (direct dispatch)', async () => {
      const { dispatchToolCall } = await import('../src/bridge/dispatch.js');
      const failingPool = createMockPool({
        getConnection: vi.fn().mockRejectedValue(new Error('Server not found')),
      }) as unknown as import('mcp-exec-core').ServerPool;

      const result = await dispatchToolCall(failingPool as never, {
        server: 'nonexistent',
        tool: 'any_tool',
      });

      expect(result.success).toBe(false);
      expect(result.error).toContain('not found');
    });
  });

  describe('Tool execution errors via fd transport', () => {
    it('should handle tool execution failures (direct dispatch)', async () => {
      const { dispatchToolCall } = await import('../src/bridge/dispatch.js');
      const errorPool = createMockPool({
        getConnection: vi.fn().mockResolvedValue({
          client: {
            callTool: vi.fn().mockRejectedValue(new Error('Tool crashed')),
          },
          getTools: vi.fn().mockResolvedValue([]),
        }),
      }) as unknown as import('mcp-exec-core').ServerPool;

      const result = await dispatchToolCall(errorPool as never, {
        server: 'test-server',
        tool: 'crashing_tool',
      });

      expect(result.success).toBe(false);
      expect(result.error).toContain('Tool execution failed');
    });
  });
});

/**
 * Real MCP Server Integration Tests
 * These tests connect to actual MCP servers and verify real integration
 * Run with: RUN_REAL_MCP_TESTS=true npm test
 */
describe.skipIf(!RUN_REAL_MCP_TESTS)('Real MCP Server Integration', () => {
  // Use /private/tmp directly on macOS because /tmp is a symlink to /private/tmp
  // and the filesystem server resolves paths, so /tmp != /private/tmp for access checks
  const REAL_TEST_DIR = '/private/tmp/mcp-exec-real-test';
  const REAL_TEST_FILE = 'real-test.txt';
  const REAL_TEST_CONTENT = 'Real MCP integration test content';

  let realPool: RealServerPool | null = null;
  const realTestPort = 3500;

  beforeAll(async () => {
    // Create test directory and file for real tests
    await mkdir(REAL_TEST_DIR, { recursive: true });
    await writeFile(join(REAL_TEST_DIR, REAL_TEST_FILE), REAL_TEST_CONTENT);

    // Set up servers config for the test
    const testConfigPath = join(__dirname, 'fixtures', 'test-servers.json');
    process.env.SERVERS_CONFIG = testConfigPath;

    // Load the server manifest (required before getServerConfig works)
    const { loadServerManifest } = await import('mcp-exec-core');
    loadServerManifest();

    // Create real connection factory using test servers.json
    const connectionFactory = async (serverId: string) => {
      const config = getServerConfig(serverId);
      if (!config) {
        throw new Error(`Server config not found: ${serverId}`);
      }
      return createConnection(config);
    };

    // Create real ServerPool
    realPool = new RealServerPool(connectionFactory);
  });

  afterAll(async () => {
    if (realPool) {
      await realPool.shutdown();
    }
    try {
      await rm(REAL_TEST_DIR, { recursive: true, force: true });
    } catch {
      // Ignore cleanup errors
    }
  });

  describe('Real filesystem MCP server via dispatchToolCall', () => {
    it('should connect to filesystem server and read a file', async () => {
      if (!realPool) throw new Error('Pool not initialized');

      const { dispatchToolCall } = await import('../src/bridge/dispatch.js');
      const result = await dispatchToolCall(realPool as never, {
        server: 'filesystem',
        tool: 'read_file',
        args: { path: join(REAL_TEST_DIR, REAL_TEST_FILE) },
      });

      expect(result.success).toBe(true);
      expect(result.content).toBeDefined();
      const text = (result.content as Array<{ type: string; text: string }>)[0].text;
      expect(text).toContain(REAL_TEST_CONTENT);
    });

    it('should list directory contents via filesystem server', async () => {
      if (!realPool) throw new Error('Pool not initialized');

      const { dispatchToolCall } = await import('../src/bridge/dispatch.js');
      const result = await dispatchToolCall(realPool as never, {
        server: 'filesystem',
        tool: 'list_directory',
        args: { path: REAL_TEST_DIR },
      });

      expect(result.success).toBe(true);
      const listing = (result.content as Array<{ type: string; text: string }>)[0].text;
      expect(listing).toContain(REAL_TEST_FILE);
    });

    it('should handle file not found errors from filesystem server', async () => {
      if (!realPool) throw new Error('Pool not initialized');

      const { dispatchToolCall } = await import('../src/bridge/dispatch.js');
      const result = await dispatchToolCall(realPool as never, {
        server: 'filesystem',
        tool: 'read_file',
        args: { path: '/nonexistent/path/file.txt' },
      });

      // The filesystem server returns isError:true for file not found
      expect(result.isError).toBe(true);
    });
  });
});

/**
 * Sandbox Isolation Verification Tests
 * These tests verify the sandbox configuration is correct
 */
describe('Sandbox isolation verification', () => {
  describe('Network configuration', () => {
    it('should deny all TCP domains — MCP calls use fd transport, not HTTP', () => {
      // fd transport replaced the HTTP bridge; the sandbox has no TCP endpoints to allow.
      const executor = new SandboxExecutor({ mcpBridgePort: 3000 });
      const config = executor.getConfig();

      expect(config.network).toBeDefined();
      expect(config.network?.allowedDomains).toBeDefined();
      expect(config.network?.allowedDomains).toHaveLength(0);
    });

    it('mcpBridgePort changes do not affect network config (deprecated field)', () => {
      // Deprecated: mcpBridgePort no longer gates any domain in allowedDomains.
      const executor = new SandboxExecutor({ mcpBridgePort: 4000 });
      const config = executor.getConfig();

      expect(config.network?.allowedDomains).toHaveLength(0);

      executor.updateConfig({ mcpBridgePort: 5000 });
      const newConfig = executor.getConfig();

      expect(newConfig.network?.allowedDomains).toHaveLength(0);
    });
  });

  describe('Filesystem configuration', () => {
    it('should configure allowed write paths', () => {
      const writePaths = ['/tmp/test', '/var/data'];
      const executor = new SandboxExecutor({
        additionalWritePaths: writePaths,
      });
      const config = executor.getConfig();

      expect(config.filesystem).toBeDefined();
      expect(config.filesystem?.allowWrite).toContain('/tmp/test');
      expect(config.filesystem?.allowWrite).toContain('/var/data');
    });

    it('should have default temp directory in write paths', () => {
      const executor = new SandboxExecutor();
      const config = executor.getConfig();

      // Should include a temp directory by default
      expect(config.filesystem?.allowWrite).toBeDefined();
      expect(config.filesystem!.allowWrite!.length).toBeGreaterThan(0);
    });
  });
});

/**
 * Executor-level fd-transport integration test.
 *
 * Uses the real SandboxExecutor.execute() with the full production composition:
 * fd-transport preamble + generated wrappers + MCP dictionary from generateMcpDictionaryFromMap.
 * This mirrors the real code path in executeWithWrappersHandler.
 *
 * Verifies that typed wrapper calls (server.toolName) correctly route through
 * __mcpFdCall and demux by id over concurrent Promise.all calls.
 *
 * This is the authoritative macOS proof that the real composition works end-to-end.
 */
describe('SandboxExecutor fd-transport full composition', () => {
  it('typed wrapper calls with concurrent Promise.all round-trip through fd transport', async () => {
    const { generateFieldGuard, generateServerModule, generateMcpDictionaryFromMap } = await import('../src/codegen/index.js');
    const executor = new SandboxExecutor();

    let callCount = 0;
    const dispatch = async (req: { server: string; tool: string; args?: Record<string, unknown> }) => {
      callCount++;
      // Small delay to force real concurrency
      await new Promise(r => setTimeout(r, 5));
      return {
        success: true as const,
        content: [{ type: 'text', text: 'RESULT:' + req.tool }],
      };
    };

    // Simulate the production composition: wrappers + dictionary + user code
    const fieldGuard = generateFieldGuard();
    const wrappersCode = generateServerModule(
      [
        { name: 'tool_A', description: 'Tool A', inputSchema: { type: 'object', properties: {}, required: [] } },
        { name: 'tool_B', description: 'Tool B', inputSchema: { type: 'object', properties: {}, required: [] } },
        { name: 'tool_C', description: 'Tool C', inputSchema: { type: 'object', properties: {}, required: [] } },
      ],
      'testserver',
      0, // bridgePort ignored
      'testserver'
    );
    const mcpDictionary = generateMcpDictionaryFromMap(['testserver'], new Map([['testserver', 'testserver']]));
    const userCode = `
const [r1, r2, r3] = await Promise.all([
  testserver.tool_A({}),
  testserver.tool_B({}),
  testserver.tool_C({}),
]);
// Wrapper auto-parses single text content blocks: returns string directly (not {text:...})
const ok = r1 === 'RESULT:tool_A'
         && r2 === 'RESULT:tool_B'
         && r3 === 'RESULT:tool_C';
console.log('full_composition:' + (ok ? 'OK' : 'FAIL'));
`;
    const fullCode = `${fieldGuard}\n\n${wrappersCode}\n\n${mcpDictionary}\n\n${userCode}`;

    const result = await executor.execute(fullCode, 15000, dispatch);

    expect(result.exitCode).toBe(0);
    expect(result.output).toContain('full_composition:OK');
    expect(callCount).toBe(3);

    await executor.reset();
  }, 20000);
});
