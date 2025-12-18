import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import type { Transport } from '@modelcontextprotocol/sdk/shared/transport.js';
import type { ServerConfig, MCPConnection, ToolDefinition } from '../types/index.js';
import { ConnectionState, isUrlTransport } from '../types/index.js';
import { buildSpawnConfig } from './stdio-transport.js';
import { enhanceGatewayConfig, isGatewayServer, type GatewayAuthConfig } from '../auth/gateway-client.js';

export class SpawnError extends Error {
  constructor(
    message: string,
    public readonly command: string,
    public readonly args: string[],
    public readonly cause?: Error
  ) {
    super(message);
    this.name = 'SpawnError';
  }
}

export class TimeoutError extends Error {
  constructor(message: string, public readonly timeoutMs: number) {
    super(message);
    this.name = 'TimeoutError';
  }
}

export class UnexpectedExitError extends Error {
  constructor(
    message: string,
    public readonly exitCode: number | null,
    public readonly signal: string | null
  ) {
    super(message);
    this.name = 'UnexpectedExitError';
  }
}

interface ConnectionInternal extends MCPConnection {
  client: Client;
  transport: Transport;
}

/**
 * Options for connection creation
 */
export interface CreateConnectionOptions {
  /** Gateway auth configuration */
  gatewayAuth?: GatewayAuthConfig;
}

export async function createConnection(
  config: ServerConfig,
  options: CreateConnectionOptions = {}
): Promise<MCPConnection> {
  // Enhance config with Gateway auth if this is a Gateway server
  let enhancedConfig = config;
  if (isGatewayServer(config)) {
    enhancedConfig = await enhanceGatewayConfig(
      config.name,
      config,
      options.gatewayAuth
    );
  }
  let transport: Transport;

  if (isUrlTransport(enhancedConfig)) {
    // URL-based HTTP/SSE transport
    try {
      transport = new StreamableHTTPClientTransport(new URL(enhancedConfig.url!), {
        requestInit: enhancedConfig.headers ? { headers: enhancedConfig.headers } : undefined,
      });
    } catch (err) {
      throw new Error(
        `Failed to create HTTP transport for ${enhancedConfig.name}: ${err instanceof Error ? err.message : String(err)}`
      );
    }
  } else {
    // Stdio transport (spawn process)
    let spawnConfig;
    try {
      spawnConfig = buildSpawnConfig(enhancedConfig);
    } catch (err) {
      throw new SpawnError(
        `Failed to build spawn config for ${enhancedConfig.name}: ${err instanceof Error ? err.message : String(err)}`,
        enhancedConfig.command ?? '',
        enhancedConfig.args ?? [],
        err instanceof Error ? err : undefined
      );
    }

    try {
      transport = new StdioClientTransport({
        command: spawnConfig.command,
        args: spawnConfig.args,
        env: spawnConfig.env,
      });
    } catch (err) {
      throw new SpawnError(
        `Failed to create transport for ${enhancedConfig.name}: ${err instanceof Error ? err.message : String(err)}`,
        spawnConfig.command,
        spawnConfig.args,
        err instanceof Error ? err : undefined
      );
    }
  }

  const client = new Client(
    { name: 'meta-mcp-server', version: '0.1.0' },
    { capabilities: {} }
  );

  let state = ConnectionState.Disconnected;

  const connection: ConnectionInternal = {
    serverId: enhancedConfig.name,
    client,
    transport,
    get state() {
      return state;
    },
    set state(newState: ConnectionState) {
      state = newState;
    },

    async connect(): Promise<void> {
      if (state === ConnectionState.Connected) {
        return;
      }
      state = ConnectionState.Connecting;
      try {
        await client.connect(transport);
        state = ConnectionState.Connected;
      } catch (err) {
        state = ConnectionState.Error;
        const errorMsg = `Failed to connect to ${enhancedConfig.name}: ${err instanceof Error ? err.message : String(err)}`;
        if (isUrlTransport(enhancedConfig)) {
          throw new Error(errorMsg);
        } else {
          throw new SpawnError(
            errorMsg,
            enhancedConfig.command ?? '',
            enhancedConfig.args ?? [],
            err instanceof Error ? err : undefined
          );
        }
      }
    },

    async disconnect(): Promise<void> {
      if (state === ConnectionState.Disconnected) {
        return;
      }
      try {
        await client.close();
      } finally {
        state = ConnectionState.Disconnected;
      }
    },

    isConnected(): boolean {
      return state === ConnectionState.Connected;
    },

    async getTools(): Promise<ToolDefinition[]> {
      if (state !== ConnectionState.Connected) {
        throw new Error(`Cannot get tools: not connected (state: ${state})`);
      }
      const result = await client.listTools();
      return result.tools.map((tool) => ({
        ...tool,
        serverId: enhancedConfig.name,
      }));
    },
  };

  await connection.connect();
  return connection;
}

export async function closeConnection(connection: MCPConnection): Promise<void> {
  await connection.disconnect();
}
