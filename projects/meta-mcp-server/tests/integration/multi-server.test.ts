import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { createServer } from '../../src/server.js';
import { ServerPool, createConnection } from '../../src/pool/index.js';
import { ToolCache } from '../../src/tools/tool-cache.js';
import { loadServerManifest, getServerConfig, clearCache } from '../../src/registry/index.js';
import { execSync } from 'child_process';
import * as fs from 'fs';

const CONFIG_PATH = process.env.SERVERS_CONFIG;
const NODE_SERVER = 'corp-jira';
const DOCKER_SERVERS = ['corp-github', 'splunk-async'];

function isDockerAvailable(): boolean {
  try {
    execSync('docker --version', { stdio: 'pipe' });
    return true;
  } catch {
    return false;
  }
}

function hasServerConfig(serverId: string): boolean {
  if (!CONFIG_PATH || !fs.existsSync(CONFIG_PATH)) {
    return false;
  }
  try {
    const content = fs.readFileSync(CONFIG_PATH, 'utf-8');
    const config = JSON.parse(content);
    return !!config.mcpServers?.[serverId];
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

function getDockerImage(serverId: string): string | null {
  if (!CONFIG_PATH || !fs.existsSync(CONFIG_PATH)) return null;
  try {
    const content = fs.readFileSync(CONFIG_PATH, 'utf-8');
    const config = JSON.parse(content);
    const serverConfig = config.mcpServers?.[serverId];
    if (serverConfig?.command !== 'docker' || !serverConfig?.args) return null;
    
    // Docker image is the last non-flag argument after 'run'
    const args = serverConfig.args as string[];
    const flagsWithValues = ['--env-file', '-e'];
    let i = args.indexOf('run') + 1;
    while (i < args.length) {
      const arg = args[i];
      if (arg.startsWith('-')) {
        if (flagsWithValues.some(f => arg === f)) {
          i += 2;
        } else {
          i += 1;
        }
      } else {
        return arg;
      }
    }
    return null;
  } catch {
    return null;
  }
}

function hasAvailableDockerServer(): string | null {
  for (const serverId of DOCKER_SERVERS) {
    const image = getDockerImage(serverId);
    if (image && isDockerImageAvailable(image)) {
      return serverId;
    }
  }
  return null;
}

const skipTests =
  !CONFIG_PATH ||
  !hasServerConfig(NODE_SERVER) ||
  !isDockerAvailable() ||
  !hasAvailableDockerServer();

const skipReason = !CONFIG_PATH
  ? 'SERVERS_CONFIG not set'
  : !hasServerConfig(NODE_SERVER)
    ? `${NODE_SERVER} not configured`
    : !isDockerAvailable()
      ? 'Docker not available'
      : !hasAvailableDockerServer()
        ? 'No Docker servers with available images'
        : '';

describe('Multi-Server Integration', () => {
  let pool: ServerPool;
  let toolCache: ToolCache;
  let callToolHandler: ReturnType<typeof createServer>['callToolHandler'];
  let shutdown: () => Promise<void>;
  let dockerServerId: string | null;

  beforeAll(async () => {
    if (skipTests) {
      console.warn(`Skipping multi-server tests: ${skipReason}`);
      return;
    }

    dockerServerId = hasAvailableDockerServer();

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
  }, 120000);

  afterAll(async () => {
    if (shutdown) {
      await shutdown();
    }
    clearCache();
  });

  describe('Mixed server type connections', () => {
    it.skipIf(skipTests)(
      'connects to Node + Docker servers simultaneously',
      async () => {
        const nodeResult = await callToolHandler({
          name: 'get_server_tools',
          arguments: { server_name: NODE_SERVER },
        });

        expect(nodeResult.content).toBeDefined();
        expect(nodeResult.content[0]).toHaveProperty('type', 'text');
        const nodeData = JSON.parse((nodeResult.content[0] as { text: string }).text);
        expect(nodeData.tools.length).toBeGreaterThan(0);

        const dockerResult = await callToolHandler({
          name: 'get_server_tools',
          arguments: { server_name: dockerServerId! },
        });

        expect(dockerResult.content).toBeDefined();
        expect(dockerResult.content[0]).toHaveProperty('type', 'text');
        const dockerData = JSON.parse((dockerResult.content[0] as { text: string }).text);
        expect(dockerData.tools.length).toBeGreaterThan(0);

        expect(pool.getActiveCount()).toBeGreaterThanOrEqual(2);
      },
      180000
    );

    it.skipIf(skipTests)(
      'executes tools on different server types in sequence',
      async () => {
        const jiraTools = await callToolHandler({
          name: 'get_server_tools',
          arguments: { server_name: NODE_SERVER },
        });

        const jiraData = JSON.parse((jiraTools.content[0] as { text: string }).text);
        const jiraAuthTool = jiraData.tools.find(
          (t: { name: string }) => t.name === 'test_jira_auth'
        );

        if (jiraAuthTool) {
          const jiraCallResult = await callToolHandler({
            name: 'call_tool',
            arguments: {
              server_name: NODE_SERVER,
              tool_name: 'test_jira_auth',
              arguments: {},
            },
          });
          expect(jiraCallResult.content).toBeDefined();
          expect(jiraCallResult.isError).not.toBe(true);
        }

        const dockerTools = await callToolHandler({
          name: 'get_server_tools',
          arguments: { server_name: dockerServerId! },
        });

        const dockerData = JSON.parse((dockerTools.content[0] as { text: string }).text);
        expect(dockerData.tools.length).toBeGreaterThan(0);
      },
      180000
    );
  });

  describe('Connection state across server types', () => {
    it.skipIf(skipTests)('maintains separate connections per server', async () => {
      await callToolHandler({
        name: 'get_server_tools',
        arguments: { server_name: NODE_SERVER },
      });

      const afterNode = pool.getActiveCount();

      await callToolHandler({
        name: 'get_server_tools',
        arguments: { server_name: dockerServerId! },
      });

      const afterDocker = pool.getActiveCount();
      expect(afterDocker).toBeGreaterThanOrEqual(afterNode);
    });

    it.skipIf(skipTests)('tool cache works across server types', async () => {
      await callToolHandler({
        name: 'get_server_tools',
        arguments: { server_name: NODE_SERVER },
      });

      await callToolHandler({
        name: 'get_server_tools',
        arguments: { server_name: dockerServerId! },
      });

      const cachedNode = await callToolHandler({
        name: 'get_server_tools',
        arguments: { server_name: NODE_SERVER },
      });

      const cachedDocker = await callToolHandler({
        name: 'get_server_tools',
        arguments: { server_name: dockerServerId! },
      });

      expect(cachedNode.content).toBeDefined();
      expect(cachedDocker.content).toBeDefined();
    });
  });
});
