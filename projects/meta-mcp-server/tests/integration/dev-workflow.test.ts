import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { createServer } from '../../src/server.js';
import { ServerPool, createConnection } from '../../src/pool/index.js';
import { ToolCache } from '../../src/tools/tool-cache.js';
import { loadServerManifest, getServerConfig, clearCache } from '../../src/registry/index.js';
import { execSync } from 'child_process';
import * as fs from 'fs';

const CONFIG_PATH = process.env.SERVERS_CONFIG;
const JIRA_SERVER = 'corp-jira';
const GITHUB_SERVER = 'corp-github';

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

function isServerAvailable(serverId: string): boolean {
  if (!hasServerConfig(serverId)) return false;

  if (!CONFIG_PATH || !fs.existsSync(CONFIG_PATH)) return false;
  try {
    const content = fs.readFileSync(CONFIG_PATH, 'utf-8');
    const config = JSON.parse(content);
    const serverConfig = config.mcpServers?.[serverId];

    if (serverConfig?.command === 'docker') {
      if (!isDockerAvailable()) return false;
      const image = getDockerImage(serverId);
      if (image && !isDockerImageAvailable(image)) return false;
    }

    return true;
  } catch {
    return false;
  }
}

const jiraAvailable = isServerAvailable(JIRA_SERVER);
const githubAvailable = isServerAvailable(GITHUB_SERVER);
const skipTests = !CONFIG_PATH || !jiraAvailable || !githubAvailable;
const skipReason = !CONFIG_PATH
  ? 'SERVERS_CONFIG not set'
  : !jiraAvailable
    ? `${JIRA_SERVER} not available`
    : !githubAvailable
      ? `${GITHUB_SERVER} not available`
      : '';

describe('Dev Workflow Integration', () => {
  let pool: ServerPool;
  let toolCache: ToolCache;
  let callToolHandler: ReturnType<typeof createServer>['callToolHandler'];
  let shutdown: () => Promise<void>;

  beforeAll(async () => {
    if (skipTests) {
      console.warn(`Skipping dev workflow tests: ${skipReason}`);
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
  }, 120000);

  afterAll(async () => {
    if (shutdown) {
      await shutdown();
    }
    clearCache();
  });

  describe('E2E: Jira + GitHub cross-server workflow', () => {
    it.skipIf(skipTests)('list_servers includes both corp-jira and corp-github', async () => {
      const result = await callToolHandler({
        name: 'list_servers',
        arguments: {},
      });

      expect(result.content).toBeDefined();
      expect(result.content[0]).toHaveProperty('type', 'text');

      const data = JSON.parse((result.content[0] as { text: string }).text);
      const serverNames = data.servers.map((s: { name: string }) => s.name);

      expect(serverNames).toContain(JIRA_SERVER);
      expect(serverNames).toContain(GITHUB_SERVER);
    });

    it.skipIf(skipTests)(
      'get_server_tools returns tools from both jira and github',
      async () => {
        const jiraResult = await callToolHandler({
          name: 'get_server_tools',
          arguments: { server_name: JIRA_SERVER },
        });

        expect(jiraResult.content).toBeDefined();
        const jiraData = JSON.parse((jiraResult.content[0] as { text: string }).text);
        expect(jiraData.tools.length).toBeGreaterThan(0);

        const githubResult = await callToolHandler({
          name: 'get_server_tools',
          arguments: { server_name: GITHUB_SERVER },
        });

        expect(githubResult.content).toBeDefined();
        const githubData = JSON.parse((githubResult.content[0] as { text: string }).text);
        expect(githubData.tools.length).toBeGreaterThan(0);
      },
      180000
    );

    it.skipIf(skipTests)(
      'complete workflow: discover servers → get tools → execute on both',
      async () => {
        const listResult = await callToolHandler({
          name: 'list_servers',
          arguments: {},
        });
        const listData = JSON.parse((listResult.content[0] as { text: string }).text);
        expect(listData.servers.length).toBeGreaterThanOrEqual(2);

        const jiraTools = await callToolHandler({
          name: 'get_server_tools',
          arguments: { server_name: JIRA_SERVER },
        });
        const jiraToolsData = JSON.parse((jiraTools.content[0] as { text: string }).text);

        const jiraAuthTool = jiraToolsData.tools.find(
          (t: { name: string }) => t.name === 'test_jira_auth'
        );

        if (jiraAuthTool) {
          const jiraExec = await callToolHandler({
            name: 'call_tool',
            arguments: {
              server_name: JIRA_SERVER,
              tool_name: 'test_jira_auth',
              arguments: {},
            },
          });
          expect(jiraExec.content).toBeDefined();
          expect(jiraExec.isError).not.toBe(true);
        }

        const githubTools = await callToolHandler({
          name: 'get_server_tools',
          arguments: { server_name: GITHUB_SERVER },
        });
        const githubToolsData = JSON.parse((githubTools.content[0] as { text: string }).text);
        expect(githubToolsData.tools.length).toBeGreaterThan(0);

        expect(pool.getActiveCount()).toBeGreaterThanOrEqual(2);
      },
      240000
    );

    it.skipIf(skipTests)(
      'simulates jira + github cross-server workflow',
      async () => {
        // Test Jira auth (no arguments required)
        const jiraExec = await callToolHandler({
          name: 'call_tool',
          arguments: {
            server_name: JIRA_SERVER,
            tool_name: 'test_jira_auth',
            arguments: {},
          },
        });
        expect(jiraExec.content).toBeDefined();
        expect(jiraExec.isError).not.toBe(true);

        // Get GitHub tools (verifies connection works)
        const githubTools = await callToolHandler({
          name: 'get_server_tools',
          arguments: { server_name: GITHUB_SERVER },
        });
        const githubData = JSON.parse((githubTools.content[0] as { text: string }).text);
        expect(githubData.tools.length).toBeGreaterThan(0);

        // Verify both connections active
        expect(pool.getActiveCount()).toBeGreaterThanOrEqual(2);
      },
      300000
    );
  });

  describe('Connection efficiency in workflow', () => {
    it.skipIf(skipTests)('maintains connection reuse across workflow steps', async () => {
      await callToolHandler({
        name: 'get_server_tools',
        arguments: { server_name: JIRA_SERVER },
      });

      await callToolHandler({
        name: 'get_server_tools',
        arguments: { server_name: GITHUB_SERVER },
      });

      const countAfterInit = pool.getActiveCount();

      await callToolHandler({
        name: 'get_server_tools',
        arguments: { server_name: JIRA_SERVER },
      });

      await callToolHandler({
        name: 'get_server_tools',
        arguments: { server_name: GITHUB_SERVER },
      });

      expect(pool.getActiveCount()).toBe(countAfterInit);
    });

    it.skipIf(skipTests)('both servers remain accessible throughout workflow', async () => {
      for (let i = 0; i < 3; i++) {
        const jiraResult = await callToolHandler({
          name: 'get_server_tools',
          arguments: { server_name: JIRA_SERVER },
        });
        expect(jiraResult.content).toBeDefined();

        const githubResult = await callToolHandler({
          name: 'get_server_tools',
          arguments: { server_name: GITHUB_SERVER },
        });
        expect(githubResult.content).toBeDefined();
      }
    });
  });
});
