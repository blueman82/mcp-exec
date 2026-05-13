/**
 * Sandbox configuration for OS-level code execution isolation
 * Uses @anthropic-ai/sandbox-runtime for security boundaries
 */
import type { SandboxRuntimeConfig, NetworkConfig, FilesystemConfig } from '@anthropic-ai/sandbox-runtime';
import { tmpdir } from 'node:os';

/**
 * Default MCP bridge port for sandbox communication
 */
export const DEFAULT_MCP_BRIDGE_PORT = 3000;

/**
 * Default network configuration - only allows localhost:3000 for MCP bridge
 */
export function createDefaultNetworkConfig(mcpBridgePort: number = DEFAULT_MCP_BRIDGE_PORT): NetworkConfig {
  return {
    allowedDomains: [`localhost:${mcpBridgePort}`],
    deniedDomains: [],
    allowLocalBinding: true,
  };
}

/**
 * Default filesystem configuration - only allows writes to temp directory
 */
export function createDefaultFilesystemConfig(additionalWritePaths: string[] = []): FilesystemConfig {
  return {
    denyRead: [],
    allowWrite: [tmpdir(), ...additionalWritePaths],
    denyWrite: [],
  };
}

/**
 * Configuration options for SandboxExecutor
 */
export interface SandboxExecutorConfig {
  /** Port for MCP bridge communication (default: 3000) */
  mcpBridgePort?: number;
  /** Additional paths to allow writes to */
  additionalWritePaths?: string[];
  /** Enable log monitoring for sandbox violations */
  enableLogMonitor?: boolean;
  /** Custom network configuration (overrides default) */
  networkConfig?: NetworkConfig;
  /** Custom filesystem configuration (overrides default) */
  filesystemConfig?: FilesystemConfig;
}

/**
 * Creates a complete SandboxRuntimeConfig from executor options
 */
export function createSandboxRuntimeConfig(options: SandboxExecutorConfig = {}): SandboxRuntimeConfig {
  const {
    mcpBridgePort = DEFAULT_MCP_BRIDGE_PORT,
    additionalWritePaths = [],
    networkConfig,
    filesystemConfig,
  } = options;

  return {
    network: networkConfig ?? createDefaultNetworkConfig(mcpBridgePort),
    filesystem: filesystemConfig ?? createDefaultFilesystemConfig(additionalWritePaths),
  };
}
