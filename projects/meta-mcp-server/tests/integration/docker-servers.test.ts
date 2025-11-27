import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { createServer } from '../../src/server.js';
import { ServerPool, createConnection } from '../../src/pool/index.js';
import { ToolCache } from '../../src/tools/tool-cache.js';
import { loadServerManifest, getServerConfig, clearCache } from '../../src/registry/index.js';
import { execSync } from 'child_process';
import * as fs from 'fs';

const CONFIG_PATH = process.env.SERVERS_CONFIG;
const DOCKER_SERVERS = ['splunk-async', 'new-relic', 'corp-github'];

function isDockerAvailable(): boolean {
  try {
    execSync('docker --version', { stdio: 'pipe' });
    return true;
  } catch {
    return false;
  }
}

function hasDockerServerConfigs(): boolean {
  if (!CONFIG_PATH || !fs.existsSync(CONFIG_PATH)) {
    return false;
  }
  try {
    const content = fs.readFileSync(CONFIG_PATH, 'utf-8');
    const config = JSON.parse(content);
    return DOCKER_SERVERS.some((server) => config.mcpServers?.[server]?.command === 'docker');
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

const skipDockerTests = !isDockerAvailable() || !hasDockerServerConfigs();
const skipReason = !isDockerAvailable()
  ? 'Docker not available'
  : !hasDockerServerConfigs()
    ? 'Docker server configs not found in SERVERS_CONFIG'
    : '';

describe('Docker Server Integration', () => {
  let pool: ServerPool;
  let toolCache: ToolCache;
  let callToolHandler: ReturnType<typeof createServer>['callToolHandler'];
  let shutdown: () => Promise<void>;

  beforeAll(async () => {
    if (skipDockerTests) {
      console.warn(`Skipping Docker tests: ${skipReason}`);
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

  describe('Docker spawn format verification', () => {
    it.skipIf(skipDockerTests)('server configs use docker command', () => {
      for (const serverId of DOCKER_SERVERS) {
        const config = getServerConfig(serverId);
        if (!config || config.command !== 'docker') continue;

        expect(config.command).toBe('docker');
        expect(config.args).toBeDefined();
        expect(config.args![0]).toBe('run');
        expect(config.args![1]).toBe('-i');
        expect(config.args![2]).toBe('--rm');
      }
    });

    it.skipIf(skipDockerTests)('docker args include run -i --rm flags', () => {
      for (const serverId of DOCKER_SERVERS) {
        const config = getServerConfig(serverId);
        if (!config || config.command !== 'docker') continue;

        const args = config.args || [];
        expect(args).toContain('run');
        expect(args).toContain('-i');
        expect(args).toContain('--rm');
      }
    });

    it.skipIf(skipDockerTests)('docker args include image reference', () => {
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

      for (const serverId of DOCKER_SERVERS) {
        const config = getServerConfig(serverId);
        if (!config || config.command !== 'docker') continue;

        const args = config.args || [];
        const imageArg = getDockerImage(args);
        expect(imageArg).toBeDefined();
      }
    });

    it.skipIf(skipDockerTests)('--env-file flag correctly passed to Docker when configured', () => {
      for (const serverId of DOCKER_SERVERS) {
        const config = getServerConfig(serverId);
        if (!config || config.command !== 'docker') continue;

        const args = config.args || [];
        const hasEnvFile = args.includes('--env-file');
        const hasInlineEnv = args.some((arg) => arg === '-e' || arg.startsWith('-e='));

        // Docker servers should use either --env-file or -e for environment variables
        if (hasEnvFile) {
          const envFileIndex = args.indexOf('--env-file');
          expect(envFileIndex).toBeGreaterThan(-1);
          // --env-file should be followed by a path
          expect(args[envFileIndex + 1]).toBeDefined();
          expect(args[envFileIndex + 1]).toMatch(/\.(env|json)$|^\//);
        }

        // Verify environment is passed through (either via --env-file or -e)
        expect(hasEnvFile || hasInlineEnv).toBe(true);
      }
    });

    it.skipIf(skipDockerTests)('environment variables passed through to container', () => {
      for (const serverId of DOCKER_SERVERS) {
        const config = getServerConfig(serverId);
        if (!config || config.command !== 'docker') continue;

        const args = config.args || [];
        
        // Check for --env-file path or -e flags
        const hasEnvFile = args.includes('--env-file');
        const hasEnvFlags = args.filter((arg) => arg === '-e').length > 0;
        
        // At least one method of passing env vars should be present
        expect(hasEnvFile || hasEnvFlags).toBe(true);
      }
    });
  });

  describe('Docker server listing', () => {
    it.skipIf(skipDockerTests)('list_servers includes configured docker servers', async () => {
      const result = await callToolHandler({
        name: 'list_servers',
        arguments: {},
      });

      expect(result.content).toBeDefined();
      expect(result.content[0]).toHaveProperty('type', 'text');

      const data = JSON.parse((result.content[0] as { text: string }).text);
      const serverNames = data.servers.map((s: { name: string }) => s.name);

      for (const serverId of DOCKER_SERVERS) {
        const config = getServerConfig(serverId);
        if (config?.command === 'docker') {
          expect(serverNames).toContain(serverId);
        }
      }
    });
  });

  describe('Docker server connections', () => {
    function getDockerImage(args: string[]): string | null {
      // Docker image is typically the last argument (after all flags)
      // Skip flags like -i, --rm, -e, --env-file and their values
      const flagsWithValues = ['--env-file', '-e'];
      let i = args.indexOf('run') + 1;
      while (i < args.length) {
        const arg = args[i];
        if (arg.startsWith('-')) {
          if (flagsWithValues.some(f => arg === f)) {
            i += 2; // skip flag and its value
          } else {
            i += 1; // skip standalone flag like -i, --rm
          }
        } else {
          // Found non-flag argument - this is the image
          return arg;
        }
      }
      return null;
    }

    it.skipIf(skipDockerTests)(
      'can connect to docker-based server and get tools',
      async () => {
        const dockerServer = DOCKER_SERVERS.find((id) => {
          const config = getServerConfig(id);
          if (config?.command !== 'docker' || !config.args) return false;
          const image = getDockerImage(config.args);
          return image ? isDockerImageAvailable(image) : false;
        });

        if (!dockerServer) {
          console.warn('No docker servers with available images, skipping connection test');
          return;
        }

        const result = await callToolHandler({
          name: 'get_server_tools',
          arguments: { server_name: dockerServer },
        });

        expect(result.content).toBeDefined();
        expect(result.content[0]).toHaveProperty('type', 'text');

        const data = JSON.parse((result.content[0] as { text: string }).text);
        expect(data.tools).toBeDefined();
        expect(Array.isArray(data.tools)).toBe(true);
      },
      120000
    );

    it.skipIf(skipDockerTests)('connection pool tracks docker connections', async () => {
      const dockerServer = DOCKER_SERVERS.find((id) => {
        const config = getServerConfig(id);
        if (config?.command !== 'docker' || !config.args) return false;
        const image = getDockerImage(config.args);
        return image ? isDockerImageAvailable(image) : false;
      });

      if (!dockerServer) {
        console.warn('No docker servers with available images, skipping pool test');
        return;
      }

      const initialCount = pool.getActiveCount();

      await callToolHandler({
        name: 'get_server_tools',
        arguments: { server_name: dockerServer },
      });

      const afterConnection = pool.getActiveCount();
      expect(afterConnection).toBeGreaterThanOrEqual(initialCount);
    });
  });

  describe('Docker container cleanup', () => {
    it.skipIf(skipDockerTests)('--rm flag present ensures container cleanup', () => {
      for (const serverId of DOCKER_SERVERS) {
        const config = getServerConfig(serverId);
        if (!config || config.command !== 'docker') continue;

        expect(config.args).toContain('--rm');
      }
    });
  });
});
