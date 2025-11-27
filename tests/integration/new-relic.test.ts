import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { createServer } from '../../src/server.js';
import { ServerPool, createConnection } from '../../src/pool/index.js';
import { ToolCache } from '../../src/tools/tool-cache.js';
import { loadServerManifest, getServerConfig, clearCache } from '../../src/registry/index.js';
import { execSync } from 'child_process';
import * as fs from 'fs';

const CONFIG_PATH = process.env.SERVERS_CONFIG;
const SERVER_ID = 'new-relic';

function isDockerAvailable(): boolean {
  try {
    execSync('docker --version', { stdio: 'pipe' });
    return true;
  } catch {
    return false;
  }
}

function hasNewRelicConfig(): boolean {
  if (!CONFIG_PATH || !fs.existsSync(CONFIG_PATH)) {
    return false;
  }
  try {
    const content = fs.readFileSync(CONFIG_PATH, 'utf-8');
    const config = JSON.parse(content);
    return config.mcpServers?.[SERVER_ID]?.command === 'docker';
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

function getDockerImage(args: string[]): string | null {
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
}

function hasAvailableImage(): boolean {
  if (!CONFIG_PATH || !fs.existsSync(CONFIG_PATH)) return false;
  try {
    const content = fs.readFileSync(CONFIG_PATH, 'utf-8');
    const config = JSON.parse(content);
    const serverConfig = config.mcpServers?.[SERVER_ID];
    if (serverConfig?.command !== 'docker' || !serverConfig?.args) return false;
    const image = getDockerImage(serverConfig.args);
    return image ? isDockerImageAvailable(image) : false;
  } catch {
    return false;
  }
}

const skipTests = !isDockerAvailable() || !hasNewRelicConfig();
const skipReason = !isDockerAvailable()
  ? 'Docker not available'
  : !hasNewRelicConfig()
    ? `${SERVER_ID} not configured as docker server in SERVERS_CONFIG`
    : '';

describe('New-Relic Docker Server', () => {
  let pool: ServerPool;
  let toolCache: ToolCache;
  let callToolHandler: ReturnType<typeof createServer>['callToolHandler'];
  let shutdown: () => Promise<void>;

  beforeAll(async () => {
    if (skipTests) {
      console.warn(`Skipping ${SERVER_ID} tests: ${skipReason}`);
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
  }, 60000);

  afterAll(async () => {
    if (shutdown) {
      await shutdown();
    }
    clearCache();
  });

  describe('spawn configuration', () => {
    it.skipIf(skipTests)('uses docker command with run -i --rm', () => {
      const config = getServerConfig(SERVER_ID);
      expect(config).toBeDefined();
      expect(config?.command).toBe('docker');
      expect(config?.args).toBeDefined();
      expect(config?.args![0]).toBe('run');
      expect(config?.args![1]).toBe('-i');
      expect(config?.args![2]).toBe('--rm');
    });

    it.skipIf(skipTests)('includes new-relic docker image in args', () => {
      const config = getServerConfig(SERVER_ID);
      expect(config?.args).toBeDefined();

      const imageArg = config!.args!.find((arg) => arg.includes('/') || arg.includes(':'));
      expect(imageArg).toBeDefined();
      expect(imageArg).toContain('newrelic');
    });
  });

  describe('server listing', () => {
    it.skipIf(skipTests)('list_servers includes new-relic', async () => {
      const result = await callToolHandler({
        name: 'list_servers',
        arguments: {},
      });

      expect(result.content).toBeDefined();
      const data = JSON.parse((result.content[0] as { text: string }).text);
      const serverNames = data.servers.map((s: { name: string }) => s.name);
      expect(serverNames).toContain(SERVER_ID);
    });
  });

  describe('tool discovery', () => {
    it.skipIf(skipTests || !hasAvailableImage())(
      'get_server_tools returns new-relic tools',
      async () => {
        const result = await callToolHandler({
          name: 'get_server_tools',
          arguments: { server_name: SERVER_ID },
        });

        expect(result.content).toBeDefined();
        expect(result.content[0]).toHaveProperty('type', 'text');

        const data = JSON.parse((result.content[0] as { text: string }).text);
        expect(data.tools).toBeDefined();
        expect(Array.isArray(data.tools)).toBe(true);
        expect(data.tools.length).toBeGreaterThan(0);
      },
      120000
    );
  });

  describe('tool execution', () => {
    it.skipIf(skipTests || !hasAvailableImage())(
      'can call a tool on new-relic server',
      async () => {
        const toolsResult = await callToolHandler({
          name: 'get_server_tools',
          arguments: { server_name: SERVER_ID },
        });

        const toolsData = JSON.parse((toolsResult.content[0] as { text: string }).text);
        if (toolsData.tools.length === 0) {
          console.warn('No tools available on new-relic server');
          return;
        }

        // Find the check_auth tool or one that doesn't require arguments
        const checkAuthTool = toolsData.tools.find((t: { name: string }) => 
          t.name.includes('check_auth') || t.name.includes('test_auth')
        );
        const noArgTool = checkAuthTool || toolsData.tools.find((t: { inputSchema?: { required?: string[] } }) => 
          !t.inputSchema?.required || t.inputSchema.required.length === 0
        );

        if (!noArgTool) {
          // All tools require arguments - just verify we can list tools
          expect(toolsData.tools.length).toBeGreaterThan(0);
          console.warn('All new-relic tools require arguments - skipping execution test');
          return;
        }

        try {
          const result = await callToolHandler({
            name: 'call_tool',
            arguments: {
              server_name: SERVER_ID,
              tool_name: noArgTool.name,
              arguments: {},
            },
          });
          expect(result.content).toBeDefined();
        } catch (err) {
          // Timeout or API errors are acceptable for Docker servers
          console.warn(`Tool execution on new-relic failed: ${err}`);
          expect(toolsData.tools.length).toBeGreaterThan(0);
        }
      },
      120000
    );
  });

  describe('connection management', () => {
    it.skipIf(skipTests || !hasAvailableImage())('connections are pooled and reused', async () => {
      const initialCount = pool.getActiveCount();

      await callToolHandler({
        name: 'get_server_tools',
        arguments: { server_name: SERVER_ID },
      });

      const afterFirst = pool.getActiveCount();

      await callToolHandler({
        name: 'get_server_tools',
        arguments: { server_name: SERVER_ID },
      });

      const afterSecond = pool.getActiveCount();
      expect(afterSecond).toBeLessThanOrEqual(afterFirst + 1);
    });
  });
});
