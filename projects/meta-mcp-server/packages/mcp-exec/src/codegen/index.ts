/**
 * Code generation utilities for MCP tool wrappers
 */

export { generateToolWrapper, generateServerModule, generateMcpDictionary, normalizeName } from './wrapper-generator.js';
export {
  VirtualModuleResolver,
  generateFromManifest,
  createModuleResolver,
  type GenerateFromManifestOptions,
} from './module-resolver.js';
