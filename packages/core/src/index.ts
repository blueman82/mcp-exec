// mcp-exec-core - Core utilities and shared types

// Types
export type {
  ServerSpawnConfig,
  ServerConfig,
  ToolSchema,
  ToolDefinition,
  MCPConnection,
} from './types/index.js';

export { isUrlTransport, ConnectionState } from './types/index.js';

// Registry
export {
  loadServerManifest,
  getServerConfig,
  listServers,
  clearCache,
  ConfigNotFoundError,
  ConfigParseError,
  ConfigValidationError,
  generateManifest,
} from './registry/index.js';

export type {
  ServerManifest,
  ServerManifestEntry,
  ServerConfigWithMeta,
} from './registry/index.js';

// Pool
export {
  ServerPool,
  ConnectionError,
  PoolExhaustedError,
  createConnection,
  closeConnection,
  SpawnError,
  TimeoutError,
  UnexpectedExitError,
  buildSpawnConfig,
} from './pool/index.js';

export type {
  ConnectionFactory,
  PoolConfig,
  SpawnConfig,
} from './pool/index.js';

// Tools
export { ToolCache } from './tools/index.js';

// Auth — generic env->HTTP-header injection
export {
  getBackendAuthHeader,
  resolveBackendAuth,
  EnvVarNotFoundError,
} from './auth/backend-auth.js';

// Process utilities
export { isOrphanedProcess, cleanupOrphanedProcesses } from './process/cleanup.js';
