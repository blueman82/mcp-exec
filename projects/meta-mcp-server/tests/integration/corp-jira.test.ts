import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { createServer } from '../../src/server.js';
import { ServerPool, createConnection } from '../../src/pool/index.js';
import { ToolCache } from '../../src/tools/tool-cache.js';
import { loadServerManifest, getServerConfig, clearCache } from '../../src/registry/index.js';

const CORP_JIRA_SERVER = 'corp-jira';
const CONFIG_PATH = process.env.SERVERS_CONFIG;

describe('Corp-Jira Integration', () => {
  let pool: ServerPool;
  let toolCache: ToolCache;
  let callToolHandler: ReturnType<typeof createServer>['callToolHandler'];
  let shutdown: () => Promise<void>;

  beforeAll(async () => {
    if (!CONFIG_PATH) {
      console.warn('SERVERS_CONFIG not set, skipping integration tests');
      return;
    }

    try {
      loadServerManifest();
    } catch (error) {
      console.warn(`Config load failed: ${error}`);
      return;
    }

    const connectionFactory = async (serverId: string) => {
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
  });

  afterAll(async () => {
    if (shutdown) {
      await shutdown();
    }
    clearCache();
  });

  it.skipIf(!CONFIG_PATH)('list_servers includes corp-jira', async () => {
    const result = await callToolHandler({
      name: 'list_servers',
      arguments: {},
    });

    expect(result.content).toBeDefined();
    expect(result.content[0]).toHaveProperty('type', 'text');

    const data = JSON.parse((result.content[0] as { text: string }).text);
    const serverNames = data.servers.map((s: { name: string }) => s.name);
    expect(serverNames).toContain(CORP_JIRA_SERVER);
  });

  it.skipIf(!CONFIG_PATH)('get_server_tools returns jira tools', async () => {
    const result = await callToolHandler({
      name: 'get_server_tools',
      arguments: { server_name: CORP_JIRA_SERVER },
    });

    expect(result.content).toBeDefined();
    expect(result.content[0]).toHaveProperty('type', 'text');

    const data = JSON.parse((result.content[0] as { text: string }).text);
    expect(data.tools.length).toBeGreaterThanOrEqual(25);
  });

  it.skipIf(!CONFIG_PATH)('call_tool executes test_jira_auth', async () => {
    const result = await callToolHandler({
      name: 'call_tool',
      arguments: {
        server_name: CORP_JIRA_SERVER,
        tool_name: 'test_jira_auth',
        arguments: {},
      },
    });

    expect(result.content).toBeDefined();
    expect(result.isError).not.toBe(true);
  });

  it.skipIf(!CONFIG_PATH)('connections are reused', async () => {
    const initialCount = pool.getActiveCount();

    await callToolHandler({
      name: 'get_server_tools',
      arguments: { server_name: CORP_JIRA_SERVER },
    });

    const afterFirstCall = pool.getActiveCount();

    await callToolHandler({
      name: 'get_server_tools',
      arguments: { server_name: CORP_JIRA_SERVER },
    });

    const afterSecondCall = pool.getActiveCount();

    expect(afterSecondCall).toBeLessThanOrEqual(afterFirstCall);
    expect(afterSecondCall - initialCount).toBeLessThanOrEqual(1);
  });
});
