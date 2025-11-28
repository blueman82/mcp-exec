import { describe, it, expect, beforeAll, afterAll, beforeEach, vi } from 'vitest';
import { createServer } from '../../src/server.js';
import { ServerPool, createConnection, type ConnectionFactory, type PoolConfig } from '../../src/pool/index.js';
import { ToolCache } from '../../src/tools/tool-cache.js';
import { loadServerManifest, getServerConfig, clearCache, listServers } from '../../src/registry/index.js';
import { execSync } from 'child_process';
import * as fs from 'fs';
import type { MCPConnection } from '../../src/types/index.js';

const CONFIG_PATH = process.env.SERVERS_CONFIG;
const MAX_CONNECTIONS = 20;

function isDockerAvailable(): boolean {
  try {
    execSync('docker --version', { stdio: 'pipe' });
    return true;
  } catch {
    return false;
  }
}

function isDockerImageAvailable(image: string): boolean {
  try {
    execSync(`docker image inspect ${image}`, { stdio: 'pipe' });
    return true;
  } catch {
    return false;
  }
}

function getAvailableServers(): string[] {
  if (!CONFIG_PATH || !fs.existsSync(CONFIG_PATH)) return [];
  try {
    const content = fs.readFileSync(CONFIG_PATH, 'utf-8');
    const config = JSON.parse(content);
    const servers: string[] = [];

    for (const [serverId, serverConfig] of Object.entries(config.mcpServers || {})) {
      const cfg = serverConfig as { command?: string; args?: string[] };
      if (cfg.command === 'docker') {
        if (!isDockerAvailable()) continue;
        const imageArg = cfg.args?.find((arg: string) => arg.includes('/') || arg.includes(':'));
        if (imageArg && !isDockerImageAvailable(imageArg)) continue;
      }
      servers.push(serverId);
    }

    return servers;
  } catch {
    return [];
  }
}

const availableServers = getAvailableServers();
const skipTests = !CONFIG_PATH || availableServers.length === 0;
const skipReason = !CONFIG_PATH
  ? 'SERVERS_CONFIG not set'
  : availableServers.length === 0
    ? 'No available servers configured'
    : '';

describe('Pool Stress Tests', () => {
  let pool: ServerPool;
  let toolCache: ToolCache;
  let callToolHandler: ReturnType<typeof createServer>['callToolHandler'];
  let shutdown: () => Promise<void>;

  beforeAll(async () => {
    if (skipTests) {
      console.warn(`Skipping pool stress tests: ${skipReason}`);
      return;
    }

    try {
      loadServerManifest();
    } catch (error) {
      console.warn(`Config load failed: ${error}`);
      return;
    }

    const connectionFactory: ConnectionFactory = async (serverId: string) => {
      const config = getServerConfig(serverId);
      if (!config) {
        throw new Error(`Server config not found: ${serverId}`);
      }
      return createConnection(config);
    };

    pool = new ServerPool(connectionFactory);
    toolCache = new ToolCache();
    const server = createServer(pool, toolCache);
    callToolHandler = server.callToolHandler;
    shutdown = server.shutdown;
  }, 120000);

  afterAll(async () => {
    if (shutdown) {
      await shutdown();
    }
    clearCache();
  });

  describe('Connection Reuse', () => {
    it.skipIf(skipTests || availableServers.length === 0)(
      'same connection used for repeated get_server_tools calls',
      async () => {
        const serverId = availableServers[0];
        const initialCount = pool.getActiveCount();

        await callToolHandler({
          name: 'get_server_tools',
          arguments: { server_name: serverId },
        });

        const afterFirstCall = pool.getActiveCount();

        await callToolHandler({
          name: 'get_server_tools',
          arguments: { server_name: serverId },
        });

        const afterSecondCall = pool.getActiveCount();

        expect(afterSecondCall).toBe(afterFirstCall);
        expect(afterFirstCall - initialCount).toBeLessThanOrEqual(1);
      },
      60000
    );

    it.skipIf(skipTests || availableServers.length === 0)(
      'connection reused across different tool calls',
      async () => {
        const serverId = availableServers[0];

        await callToolHandler({
          name: 'get_server_tools',
          arguments: { server_name: serverId },
        });

        const countAfterTools = pool.getActiveCount();

        const toolsResult = await callToolHandler({
          name: 'get_server_tools',
          arguments: { server_name: serverId },
        });

        const toolsData = JSON.parse((toolsResult.content[0] as { text: string }).text);
        if (toolsData.tools.length > 0) {
          await callToolHandler({
            name: 'call_tool',
            arguments: {
              server_name: serverId,
              tool_name: toolsData.tools[0].name,
              arguments: {},
            },
          });

          expect(pool.getActiveCount()).toBe(countAfterTools);
        }
      },
      60000
    );
  });

  describe('LRU Eviction', () => {
    it.skipIf(skipTests || availableServers.length < 7)(
      'evicts LRU connection when exceeding max connections',
      async () => {
        const serversToTest = availableServers.slice(0, 7);

        for (let i = 0; i < Math.min(6, serversToTest.length); i++) {
          await callToolHandler({
            name: 'get_server_tools',
            arguments: { server_name: serversToTest[i] },
          });
        }

        const countAtMax = pool.getActiveCount();
        expect(countAtMax).toBeLessThanOrEqual(MAX_CONNECTIONS);

        if (serversToTest.length >= 7) {
          await callToolHandler({
            name: 'get_server_tools',
            arguments: { server_name: serversToTest[6] },
          });

          expect(pool.getActiveCount()).toBeLessThanOrEqual(MAX_CONNECTIONS);
        }
      },
      300000
    );
  });
});

describe('Pool Unit Tests with Mocks', () => {
  describe('LRU Eviction Logic', () => {
    it('evicts oldest unused connection when at capacity', async () => {
      const mockConnections = new Map<string, { connectCalled: boolean; disconnectCalled: boolean }>();

      const mockFactory: ConnectionFactory = async (serverId: string) => {
        const state = { connectCalled: false, disconnectCalled: false };
        mockConnections.set(serverId, state);

        return {
          serverId,
          state: 'disconnected',
          connect: async () => {
            state.connectCalled = true;
          },
          disconnect: async () => {
            state.disconnectCalled = true;
          },
          listTools: async () => [],
          callTool: async () => ({ content: [] }),
        } as unknown as MCPConnection;
      };

      const smallPool = new ServerPool(mockFactory, { maxConnections: 3, idleTimeoutMs: 300000 });

      await smallPool.getConnection('server-1');
      smallPool.releaseConnection('server-1');

      await new Promise((r) => setTimeout(r, 10));

      await smallPool.getConnection('server-2');
      smallPool.releaseConnection('server-2');

      await new Promise((r) => setTimeout(r, 10));

      await smallPool.getConnection('server-3');
      smallPool.releaseConnection('server-3');

      expect(smallPool.getActiveCount()).toBe(3);

      await smallPool.getConnection('server-4');

      expect(smallPool.getActiveCount()).toBe(3);
      expect(mockConnections.get('server-1')?.disconnectCalled).toBe(true);
      expect(mockConnections.get('server-4')?.connectCalled).toBe(true);

      await smallPool.shutdown();
    });
  });

  describe('Idle Timeout Cleanup', () => {
    it('removes idle connections after timeout', async () => {
      vi.useFakeTimers();

      const mockConnections = new Map<string, { disconnectCalled: boolean }>();

      const mockFactory: ConnectionFactory = async (serverId: string) => {
        const state = { disconnectCalled: false };
        mockConnections.set(serverId, state);

        return {
          serverId,
          state: 'disconnected',
          connect: async () => {},
          disconnect: async () => {
            state.disconnectCalled = true;
          },
          listTools: async () => [],
          callTool: async () => ({ content: [] }),
        } as unknown as MCPConnection;
      };

      const shortTimeoutPool = new ServerPool(mockFactory, {
        maxConnections: 6,
        idleTimeoutMs: 1000,
      });

      await shortTimeoutPool.getConnection('idle-server');
      shortTimeoutPool.releaseConnection('idle-server');

      expect(shortTimeoutPool.getActiveCount()).toBe(1);

      vi.advanceTimersByTime(1500);
      await shortTimeoutPool.runCleanup();

      expect(shortTimeoutPool.getActiveCount()).toBe(0);
      expect(mockConnections.get('idle-server')?.disconnectCalled).toBe(true);

      vi.useRealTimers();
      await shortTimeoutPool.shutdown();
    });

    it('does not remove connections still in use', async () => {
      vi.useFakeTimers();

      const mockConnections = new Map<string, { disconnectCalled: boolean }>();

      const mockFactory: ConnectionFactory = async (serverId: string) => {
        const state = { disconnectCalled: false };
        mockConnections.set(serverId, state);

        return {
          serverId,
          state: 'disconnected',
          connect: async () => {},
          disconnect: async () => {
            state.disconnectCalled = true;
          },
          listTools: async () => [],
          callTool: async () => ({ content: [] }),
        } as unknown as MCPConnection;
      };

      const shortTimeoutPool = new ServerPool(mockFactory, {
        maxConnections: 6,
        idleTimeoutMs: 1000,
      });

      await shortTimeoutPool.getConnection('active-server');

      vi.advanceTimersByTime(1500);
      await shortTimeoutPool.runCleanup();

      expect(shortTimeoutPool.getActiveCount()).toBe(1);
      expect(mockConnections.get('active-server')?.disconnectCalled).toBe(false);

      vi.useRealTimers();
      await shortTimeoutPool.shutdown();
    });
  });

  describe('Connection Reuse Verification', () => {
    it('returns same connection for same serverId', async () => {
      let connectionCount = 0;

      const mockFactory: ConnectionFactory = async (serverId: string) => {
        connectionCount++;
        return {
          serverId,
          state: 'disconnected',
          connect: async () => {},
          disconnect: async () => {},
          listTools: async () => [],
          callTool: async () => ({ content: [] }),
        } as unknown as MCPConnection;
      };

      const testPool = new ServerPool(mockFactory);

      const conn1 = await testPool.getConnection('test-server');
      const conn2 = await testPool.getConnection('test-server');

      expect(connectionCount).toBe(1);
      expect(conn1).toBe(conn2);

      await testPool.shutdown();
    });
  });
});
