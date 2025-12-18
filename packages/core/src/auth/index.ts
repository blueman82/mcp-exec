export {
  resolveBackendAuth,
  getBackendAuthHeader,
  parseEnvFile,
  EnvVarNotFoundError,
} from './backend-auth.js';

export {
  extractCursorToken,
  isTokenExtractionSupported,
  getPlatformName,
  type CursorOAuthToken,
  type TokenExtractionResult,
} from './cursor-token-reader.js';

export {
  formatBackendAuthHeaders,
} from './pat-matcher.js';

export {
  resolveGatewayAuth,
  enhanceGatewayConfig,
  isGatewayServer,
  type GatewayAuthConfig,
  type GatewayAuthResult,
} from './gateway-client.js';
