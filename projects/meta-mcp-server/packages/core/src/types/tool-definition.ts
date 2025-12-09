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
 * Compatible with MCP SDK Tool interface
 */
export interface ToolDefinition {
  name: string;
  description?: string;
  inputSchema?: ToolSchema;
  serverId?: string;
}
