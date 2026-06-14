import type { ToolDefinition } from './tool-definition.js';

/**
 * Connection state enum
 */
export enum ConnectionState {
  Disconnected = 'disconnected',
  Connecting = 'connecting',
  Connected = 'connected',
  Error = 'error',
}

/**
 * MCP client connection wrapper
 */
export interface MCPConnection {
  serverId: string;
  state: ConnectionState;
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
  isConnected: () => boolean;
  getTools: () => Promise<ToolDefinition[]>;
}
