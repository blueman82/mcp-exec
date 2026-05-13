/**
 * Sandbox module exports for mcp-exec
 * Provides OS-level isolation for executing agent-generated code
 */

// Export executor class
export { SandboxExecutor } from './executor.js';

// Export configuration utilities and types
export {
  createSandboxRuntimeConfig,
  createDefaultNetworkConfig,
  createDefaultFilesystemConfig,
  DEFAULT_MCP_BRIDGE_PORT,
  type SandboxExecutorConfig,
} from './config.js';

// Re-export sandbox-runtime types for convenience
export type {
  SandboxRuntimeConfig,
  NetworkConfig,
  FilesystemConfig,
} from '@anthropic-ai/sandbox-runtime';
