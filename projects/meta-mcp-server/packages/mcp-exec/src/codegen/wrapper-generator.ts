/**
 * TypeScript wrapper generator for MCP tools.
 * Generates type-safe wrapper functions that call bridge endpoint.
 */

import type { ToolDefinition } from '@justanothermldude/meta-mcp-core';

/**
 * Bridge endpoint URL for tool calls
 */
const BRIDGE_ENDPOINT = 'http://127.0.0.1:3000/call';

/**
 * JSON Schema property definition
 */
interface JsonSchemaProperty {
  type?: string | string[];
  description?: string;
  items?: JsonSchemaProperty;
  properties?: Record<string, JsonSchemaProperty>;
  required?: string[];
  enum?: unknown[];
  default?: unknown;
  $ref?: string;
}

/**
 * Convert a JSON Schema type to TypeScript type
 * @param prop - JSON Schema property definition
 * @param required - Whether the property is required
 * @returns TypeScript type string
 */
function jsonSchemaToTs(prop: JsonSchemaProperty | undefined, _required: boolean = true): string {
  if (!prop) {
    return 'unknown';
  }

  // Handle array of types (e.g., ["string", "null"])
  if (Array.isArray(prop.type)) {
    const types = prop.type.map((t) => primitiveToTs(t));
    return types.join(' | ');
  }

  // Handle enum types
  if (prop.enum) {
    return prop.enum.map((v) => JSON.stringify(v)).join(' | ');
  }

  // Handle object types with properties
  if (prop.type === 'object' && prop.properties) {
    const propLines = Object.entries(prop.properties).map(([key, value]) => {
      const isRequired = prop.required?.includes(key) ?? false;
      const tsType = jsonSchemaToTs(value as JsonSchemaProperty, isRequired);
      const optionalMark = isRequired ? '' : '?';
      return `${key}${optionalMark}: ${tsType}`;
    });
    return `{ ${propLines.join('; ')} }`;
  }

  // Handle array types
  if (prop.type === 'array') {
    const itemType = prop.items ? jsonSchemaToTs(prop.items, true) : 'unknown';
    return `${itemType}[]`;
  }

  // Handle primitive types
  return primitiveToTs(prop.type ?? 'unknown');
}

/**
 * Convert JSON Schema primitive type to TypeScript
 */
function primitiveToTs(type: string): string {
  switch (type) {
    case 'string':
      return 'string';
    case 'number':
    case 'integer':
      return 'number';
    case 'boolean':
      return 'boolean';
    case 'null':
      return 'null';
    case 'object':
      return 'Record<string, unknown>';
    case 'array':
      return 'unknown[]';
    default:
      return 'unknown';
  }
}

/**
 * Generate TypeScript interface from JSON Schema
 * @param name - Interface name
 * @param schema - JSON Schema object
 * @returns TypeScript interface definition
 */
function generateInterface(name: string, schema: { properties?: Record<string, unknown>; required?: string[] }): string {
  if (!schema.properties || Object.keys(schema.properties).length === 0) {
    return `interface ${name} {}`;
  }

  const lines: string[] = [];
  lines.push(`interface ${name} {`);

  for (const [propName, propValue] of Object.entries(schema.properties)) {
    const prop = propValue as JsonSchemaProperty;
    const isRequired = schema.required?.includes(propName) ?? false;
    const optionalMark = isRequired ? '' : '?';
    const tsType = jsonSchemaToTs(prop, isRequired);

    // Add JSDoc if description exists
    if (prop.description) {
      lines.push(`  /** ${prop.description} */`);
    }

    lines.push(`  ${propName}${optionalMark}: ${tsType};`);
  }

  lines.push('}');
  return lines.join('\n');
}

/**
 * Sanitize tool name to valid TypeScript identifier
 */
function sanitizeIdentifier(name: string): string {
  // Replace non-alphanumeric chars with underscore, ensure starts with letter
  let sanitized = name.replace(/[^a-zA-Z0-9_]/g, '_');
  if (/^[0-9]/.test(sanitized)) {
    sanitized = '_' + sanitized;
  }
  return sanitized;
}

/**
 * Convert tool name to PascalCase for interface name
 */
function toPascalCase(name: string): string {
  return name
    .split(/[^a-zA-Z0-9]+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join('');
}

/**
 * Generate interface definition for a tool (if it has input properties)
 * @param tool - Tool definition from MCP server
 * @returns Interface definition string or empty string
 */
function generateToolInterface(tool: ToolDefinition): string {
  const interfaceName = `${toPascalCase(tool.name)}Input`;

  if (tool.inputSchema?.properties && Object.keys(tool.inputSchema.properties).length > 0) {
    return generateInterface(interfaceName, tool.inputSchema);
  }
  return '';
}

/**
 * Generate a method definition for the namespace object
 * @param tool - Tool definition from MCP server
 * @param serverName - Name of the MCP server
 * @param bridgePort - Port for the MCP bridge
 * @returns Method definition string for inclusion in namespace object
 */
function generateMethodDefinition(tool: ToolDefinition, serverName: string, bridgePort: number): string {
  // Use original tool name (sanitized) so discovery matches usage
  // e.g., get_jira_issuetype stays as get_jira_issuetype, not getJiraIssuetype
  const methodName = sanitizeIdentifier(tool.name);
  const interfaceName = `${toPascalCase(tool.name)}Input`;
  const hasInput = tool.inputSchema?.properties && Object.keys(tool.inputSchema.properties).length > 0;
  const inputParam = hasInput ? `input: ${interfaceName}` : '';
  const inputArg = hasInput ? 'input' : '{}';

  const lines: string[] = [];

  // Add JSDoc comment
  if (tool.description) {
    lines.push('  /**');
    lines.push(`   * ${tool.description}`);
    if (tool.inputSchema?.properties) {
      for (const [propName, propValue] of Object.entries(tool.inputSchema.properties)) {
        const prop = propValue as JsonSchemaProperty;
        if (prop.description) {
          lines.push(`   * @param input.${propName} - ${prop.description}`);
        }
      }
    }
    lines.push('   */');
  }

  // Escape server/tool names to prevent code injection via malicious names
  const safeServerName = JSON.stringify(serverName);
  const safeToolName = JSON.stringify(tool.name);

  lines.push(`  ${methodName}: async (${inputParam}): Promise<unknown> => {`);
  lines.push(`    const response = await fetch('http://127.0.0.1:${bridgePort}/call', {`);
  lines.push(`      method: 'POST',`);
  lines.push(`      headers: { 'Content-Type': 'application/json' },`);
  lines.push(`      body: JSON.stringify({`);
  lines.push(`        server: ${safeServerName},`);
  lines.push(`        tool: ${safeToolName},`);
  lines.push(`        args: ${inputArg},`);
  lines.push(`      }),`);
  lines.push(`    });`);
  lines.push(`    if (!response.ok) {`);
  lines.push('      throw new Error(`Tool call failed: ${response.statusText}`);');
  lines.push(`    }`);
  lines.push(`    const data = await response.json() as { success: boolean; content?: unknown; error?: string };`);
  lines.push(`    if (!data.success) {`);
  lines.push(`      throw new Error(data.error || 'Tool call failed');`);
  lines.push(`    }`);
  lines.push(`    // Auto-parse JSON from MCP text content blocks for convenience`);
  lines.push(`    const content = data.content;`);
  lines.push(`    if (Array.isArray(content) && content.length === 1 && content[0]?.type === 'text') {`);
  lines.push(`      try {`);
  lines.push(`        return JSON.parse(content[0].text);`);
  lines.push(`      } catch {`);
  lines.push(`        return content[0].text;`);
  lines.push(`      }`);
  lines.push(`    }`);
  lines.push(`    return content;`);
  lines.push(`  },`);

  return lines.join('\n');
}

/**
 * Generate TypeScript wrapper code for a single MCP tool (legacy - kept for compatibility)
 * @param tool - Tool definition from MCP server
 * @param serverName - Name of the MCP server
 * @returns TypeScript code string
 * @deprecated Use generateServerModule instead for namespace-based wrappers
 */
export function generateToolWrapper(tool: ToolDefinition, serverName: string): string {
  const funcName = sanitizeIdentifier(tool.name);
  const interfaceName = `${toPascalCase(tool.name)}Input`;

  const lines: string[] = [];

  // Generate input interface if there are properties
  if (tool.inputSchema?.properties && Object.keys(tool.inputSchema.properties).length > 0) {
    lines.push(generateInterface(interfaceName, tool.inputSchema));
    lines.push('');
  }

  // Add JSDoc comment
  if (tool.description) {
    lines.push('/**');
    lines.push(` * ${tool.description}`);
    if (tool.inputSchema?.properties) {
      lines.push(' *');
      for (const [propName, propValue] of Object.entries(tool.inputSchema.properties)) {
        const prop = propValue as JsonSchemaProperty;
        if (prop.description) {
          lines.push(` * @param input.${propName} - ${prop.description}`);
        }
      }
    }
    lines.push(' * @returns Promise resolving to tool result');
    lines.push(' */');
  }

  // Generate function signature (no export - for inline execution)
  const hasInput = tool.inputSchema?.properties && Object.keys(tool.inputSchema.properties).length > 0;
  const inputParam = hasInput ? `input: ${interfaceName}` : '';
  const inputArg = hasInput ? 'input' : '{}';

  lines.push(`async function ${funcName}(${inputParam}): Promise<unknown> {`);
  lines.push(`  const response = await fetch('${BRIDGE_ENDPOINT}', {`);
  lines.push(`    method: 'POST',`);
  lines.push(`    headers: { 'Content-Type': 'application/json' },`);
  lines.push(`    body: JSON.stringify({`);
  lines.push(`      server: '${serverName}',`);
  lines.push(`      tool: '${tool.name}',`);
  lines.push(`      args: ${inputArg},`);
  lines.push(`    }),`);
  lines.push(`  });`);
  lines.push('');
  lines.push('  if (!response.ok) {');
  lines.push('    throw new Error(`Tool call failed: ${response.statusText}`);');
  lines.push('  }');
  lines.push('');
  lines.push('  return response.json();');
  lines.push('}');

  return lines.join('\n');
}

/**
 * Generate a complete TypeScript module with a namespace object for all tools
 * @param tools - Array of tool definitions
 * @param serverName - Name of the MCP server
 * @param bridgePort - Port for the MCP bridge (default: 3000)
 * @returns TypeScript code string with namespace object
 */
export function generateServerModule(tools: ToolDefinition[], serverName: string, bridgePort: number = 3000): string {
  const lines: string[] = [];
  const namespaceName = sanitizeIdentifier(serverName);

  // File header comment
  lines.push('/**');
  lines.push(` * Auto-generated TypeScript wrappers for ${serverName} MCP server tools.`);
  lines.push(` * Access tools via: ${namespaceName}.methodName()`);
  lines.push(' */');
  lines.push('');

  // Generate all interfaces first
  for (const tool of tools) {
    const interfaceCode = generateToolInterface(tool);
    if (interfaceCode) {
      lines.push(interfaceCode);
      lines.push('');
    }
  }

  // Generate the namespace object with all methods
  lines.push(`const ${namespaceName} = {`);

  for (let i = 0; i < tools.length; i++) {
    const tool = tools[i];
    lines.push(generateMethodDefinition(tool, serverName, bridgePort));
    // No trailing comma after last method (already handled by generateMethodDefinition)
  }

  lines.push('};');
  lines.push('');

  return lines.join('\n');
}
