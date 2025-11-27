import { Tool } from '@modelcontextprotocol/sdk/types.js';

/**
 * Tool schema defining input parameters
 */
export interface ToolSchema {
  type: 'object';
  properties?: Record<string, unknown>;
  required?: string[];
}

/**
 * Extended tool definition with server context
 */
export interface ToolDefinition extends Tool {
  serverId?: string;
}
