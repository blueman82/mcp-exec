// @justanothermldude/meta-mcp-core - Core utilities and shared types

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
  CreateConnectionOptions,
} from './pool/index.js';

// Tools
export { ToolCache } from './tools/index.js';

// Auth
export {
  getBackendAuthHeader,
  resolveBackendAuth,
  EnvVarNotFoundError,
  // Cursor token extraction
  extractCursorToken,
  isTokenExtractionSupported,
  getPlatformName,
  // Gateway client
  resolveGatewayAuth,
  enhanceGatewayConfig,
  isGatewayServer,
} from './auth/index.js';

export type {
  CursorOAuthToken,
  TokenExtractionResult,
  GatewayAuthConfig,
  GatewayAuthResult,
} from './auth/index.js';

// Process utilities
export { isOrphanedProcess, cleanupOrphanedProcesses } from './process/cleanup.js';
