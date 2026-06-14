/**
 * Sandbox configuration for OS-level code execution isolation
 * Uses @anthropic-ai/sandbox-runtime for security boundaries
 *
 * Network note: MCP tool calls now use inherited file descriptors (fd 3 + fd 4),
 * not TCP loopback. The default network config denies all outbound domains —
 * the sandbox has no legitimate reason to make TCP connections.
 */
import type { SandboxRuntimeConfig, NetworkConfig, FilesystemConfig } from '@anthropic-ai/sandbox-runtime';
import { tmpdir } from 'node:os';

/**
 * @deprecated No longer used. MCP tool calls use the fd transport, not TCP.
 * Kept to avoid breaking external callers of SandboxExecutorConfig.mcpBridgePort.
 */
export const DEFAULT_MCP_BRIDGE_PORT = 3000;

/**
 * Default network configuration.
 * No TCP domains are allowed — MCP tool calls go via inherited fds, not HTTP.
 */
export function createDefaultNetworkConfig(): NetworkConfig {
  return {
    allowedDomains: [],
    deniedDomains: [],
    allowLocalBinding: false,
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
  /**
   * @deprecated No longer used. Tool calls use the fd transport, not TCP.
   * Kept for backward compatibility only.
   */
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
    additionalWritePaths = [],
    networkConfig,
    filesystemConfig,
  } = options;

  return {
    network: networkConfig ?? createDefaultNetworkConfig(),
    filesystem: filesystemConfig ?? createDefaultFilesystemConfig(additionalWritePaths),
  };
}
