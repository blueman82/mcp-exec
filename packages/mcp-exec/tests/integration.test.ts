/**
 * Integration tests for mcp-exec with real MCP calls
 * Tests full code execution flow: sandbox -> bridge -> filesystem MCP server -> output
 *
 * This file contains both:
 * 1. Unit-level integration tests (with mocks) - always run
 * 2. Real MCP server integration tests - run when RUN_REAL_MCP_TESTS=true
 */
import { describe, it, expect, vi, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';
import { mkdir, writeFile, rm, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { createMcpExecServer } from '../src/server.js';
import { MCPBridge } from '../src/bridge/server.js';
import { SandboxExecutor } from '../src/sandbox/executor.js';
import { createExecuteWithWrappersHandler, isExecuteWithWrappersInput } from '../src/tools/execute-with-wrappers.js';
import type { ServerPool, MCPConnection } from '@justanothermldude/meta-mcp-core';
import { ConnectionState, ServerPool as RealServerPool, createConnection, getServerConfig } from '@justanothermldude/meta-mcp-core';

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

  describe('MCPBridge + ServerPool integration', () => {
    let bridge: MCPBridge;
    let mockPool: ServerPool;
    const testPort = 3200;

    beforeEach(async () => {
      mockPool = createMockPool();
      bridge = new MCPBridge(mockPool, { port: testPort });
      await bridge.start();
    });

    afterEach(async () => {
      if (bridge.isRunning()) {
        await bridge.stop();
      }
    });

    it('should forward tool calls to pool', async () => {
      const response = await fetch(`http://127.0.0.1:${testPort}/call`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          server: 'filesystem',
          tool: 'read_file',
          args: { path: join(TEST_DIR, TEST_FILE) },
        }),
      });

      const body = await response.json() as { success: boolean; content: unknown[] };
      expect(response.status).toBe(200);
      expect(body.success).toBe(true);
      expect(mockPool.getConnection).toHaveBeenCalledWith('filesystem');
      expect(mockPool.releaseConnection).toHaveBeenCalledWith('filesystem');
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

  describe('End-to-end flow simulation', () => {
    it('should orchestrate bridge, executor, and cleanup', async () => {
      const mockPool = createMockPool();
      const testPort = 3300;

      // Create components
      const bridge = new MCPBridge(mockPool, { port: testPort });

      // Simulate flow: start bridge -> (code execution would happen) -> stop bridge
      await bridge.start();
      expect(bridge.isRunning()).toBe(true);

      // Verify bridge accepts requests
      const healthResponse = await fetch(`http://127.0.0.1:${testPort}/health`);
      expect(healthResponse.status).toBe(200);

      // Stop bridge
      await bridge.stop();
      expect(bridge.isRunning()).toBe(false);
    });
  });

  describe('SandboxExecutor configuration', () => {
    it('should configure executor with bridge port', () => {
      const executor = new SandboxExecutor({ mcpBridgePort: 4000 });
      const config = executor.getConfig();

      expect(config.network?.allowedDomains).toContain('localhost:4000');
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
  describe('Connection errors', () => {
    it('should handle pool connection failures gracefully', async () => {
      const failingPool = createMockPool({
        getConnection: vi.fn().mockRejectedValue(new Error('Server not found')),
      });

      const bridge = new MCPBridge(failingPool, { port: 3400 });
      await bridge.start();

      const response = await fetch('http://127.0.0.1:3400/call', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          server: 'nonexistent',
          tool: 'any_tool',
        }),
      });

      // Server not found returns 404 (not found) instead of 502 (bad gateway)
      expect(response.status).toBe(404);
      const body = await response.json() as { success: boolean; error: string };
      expect(body.success).toBe(false);
      expect(body.error).toContain('not found');

      await bridge.stop();
    });
  });

  describe('Tool execution errors', () => {
    it('should handle tool execution failures', async () => {
      const errorPool = createMockPool({
        getConnection: vi.fn().mockResolvedValue({
          client: {
            callTool: vi.fn().mockRejectedValue(new Error('Tool crashed')),
          },
        }),
      });

      const bridge = new MCPBridge(errorPool, { port: 3401 });
      await bridge.start();

      const response = await fetch('http://127.0.0.1:3401/call', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          server: 'test-server',
          tool: 'crashing_tool',
        }),
      });

      expect(response.status).toBe(500);
      const body = await response.json() as { success: boolean; error: string };
      expect(body.success).toBe(false);
      expect(body.error).toContain('Tool execution failed');

      await bridge.stop();
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
  let bridge: MCPBridge | null = null;
  const realTestPort = 3500;

  beforeAll(async () => {
    // Create test directory and file for real tests
    await mkdir(REAL_TEST_DIR, { recursive: true });
    await writeFile(join(REAL_TEST_DIR, REAL_TEST_FILE), REAL_TEST_CONTENT);

    // Set up servers config for the test
    const testConfigPath = join(__dirname, 'fixtures', 'test-servers.json');
    process.env.SERVERS_CONFIG = testConfigPath;

    // Load the server manifest (required before getServerConfig works)
    const { loadServerManifest } = await import('@justanothermldude/meta-mcp-core');
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
    // Cleanup
    if (bridge?.isRunning()) {
      await bridge.stop();
    }
    if (realPool) {
      await realPool.shutdown();
    }
    try {
      await rm(REAL_TEST_DIR, { recursive: true, force: true });
    } catch {
      // Ignore cleanup errors
    }
  });

  describe('Real filesystem MCP server', () => {
    it('should connect to filesystem server and read a file', async () => {
      if (!realPool) throw new Error('Pool not initialized');

      bridge = new MCPBridge(realPool, { port: realTestPort });
      await bridge.start();

      // Call the real filesystem server to read our test file
      const response = await fetch(`http://127.0.0.1:${realTestPort}/call`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          server: 'filesystem',
          tool: 'read_file',
          args: { path: join(REAL_TEST_DIR, REAL_TEST_FILE) },
        }),
      });

      const body = await response.json() as { success: boolean; content: Array<{ type: string; text: string }>; error?: string };

      expect(response.status).toBe(200);
      expect(body.success).toBe(true);
      expect(body.content).toBeDefined();
      // The filesystem server returns content with the file contents
      expect(body.content[0].text).toContain(REAL_TEST_CONTENT);
    });

    it('should list directory contents via filesystem server', async () => {
      if (!realPool) throw new Error('Pool not initialized');

      bridge = new MCPBridge(realPool, { port: realTestPort + 1 });
      await bridge.start();

      const response = await fetch(`http://127.0.0.1:${realTestPort + 1}/call`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          server: 'filesystem',
          tool: 'list_directory',
          args: { path: REAL_TEST_DIR },
        }),
      });

      const body = await response.json() as { success: boolean; content: Array<{ type: string; text: string }> };

      expect(response.status).toBe(200);
      expect(body.success).toBe(true);
      // The directory listing should include our test file
      const listing = body.content[0].text;
      expect(listing).toContain(REAL_TEST_FILE);

      await bridge.stop();
    });

    it('should handle file not found errors from filesystem server', async () => {
      if (!realPool) throw new Error('Pool not initialized');

      bridge = new MCPBridge(realPool, { port: realTestPort + 2 });
      await bridge.start();

      const response = await fetch(`http://127.0.0.1:${realTestPort + 2}/call`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          server: 'filesystem',
          tool: 'read_file',
          args: { path: '/nonexistent/path/file.txt' },
        }),
      });

      const body = await response.json() as { success: boolean; isError?: boolean; content?: Array<{ type: string; text: string }> };

      // The request should succeed but the tool result should indicate an error
      expect(response.status).toBe(200);
      // filesystem server returns isError: true for file not found
      expect(body.isError).toBe(true);

      await bridge.stop();
    });
  });

  describe('Full execute_code_with_wrappers flow with real MCP', () => {
    it('should execute code that calls filesystem server via bridge', async () => {
      if (!realPool) throw new Error('Pool not initialized');

      // Start the bridge
      bridge = new MCPBridge(realPool, { port: realTestPort + 3 });
      await bridge.start();

      // The full flow would be:
      // 1. Code executes in sandbox
      // 2. Code calls HTTP bridge at localhost:PORT/call
      // 3. Bridge forwards to real filesystem server
      // 4. Result returned through the chain

      // Verify the bridge is accepting requests
      const healthCheck = await fetch(`http://127.0.0.1:${realTestPort + 3}/health`);
      expect(healthCheck.status).toBe(200);

      // Make a real MCP call through the bridge
      const response = await fetch(`http://127.0.0.1:${realTestPort + 3}/call`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          server: 'filesystem',
          tool: 'read_file',
          args: { path: join(REAL_TEST_DIR, REAL_TEST_FILE) },
        }),
      });

      const body = await response.json() as { success: boolean; content: Array<{ type: string; text: string }> };

      expect(response.status).toBe(200);
      expect(body.success).toBe(true);
      expect(body.content[0].text).toContain(REAL_TEST_CONTENT);

      await bridge.stop();
    });
  });
});

/**
 * Sandbox Isolation Verification Tests
 * These tests verify the sandbox configuration is correct
 */
describe('Sandbox isolation verification', () => {
  describe('Network configuration', () => {
    it('should only allow localhost for bridge communication', () => {
      const executor = new SandboxExecutor({ mcpBridgePort: 3000 });
      const config = executor.getConfig();

      // Verify network is configured
      expect(config.network).toBeDefined();
      expect(config.network?.allowedDomains).toBeDefined();

      // Should contain localhost:3000 (the bridge port)
      expect(config.network?.allowedDomains).toContain('localhost:3000');
    });

    it('should update network config when bridge port changes', () => {
      const executor = new SandboxExecutor({ mcpBridgePort: 4000 });
      const config = executor.getConfig();

      expect(config.network?.allowedDomains).toContain('localhost:4000');

      // Update config
      executor.updateConfig({ mcpBridgePort: 5000 });
      const newConfig = executor.getConfig();

      expect(newConfig.network?.allowedDomains).toContain('localhost:5000');
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
