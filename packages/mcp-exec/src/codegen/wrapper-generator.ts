/**
 * TypeScript wrapper generator for MCP tools.
 * Generates type-safe wrapper functions that call bridge endpoint.
 */

import type { ToolDefinition } from '@meta-mcp/core';

/**
 * Bridge endpoint URL for tool calls
 */
const BRIDGE_ENDPOINT = 'http://localhost:3000/call';

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
    return `export interface ${name} {}`;
  }

  const lines: string[] = [];
  lines.push(`export interface ${name} {`);

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
 * Generate TypeScript wrapper code for a single MCP tool
 * @param tool - Tool definition from MCP server
 * @param serverName - Name of the MCP server
 * @returns TypeScript code string
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

  // Generate function signature
  const hasInput = tool.inputSchema?.properties && Object.keys(tool.inputSchema.properties).length > 0;
  const inputParam = hasInput ? `input: ${interfaceName}` : '';
  const inputArg = hasInput ? 'input' : '{}';

  lines.push(`export async function ${funcName}(${inputParam}): Promise<unknown> {`);
  lines.push(`  const response = await fetch('${BRIDGE_ENDPOINT}', {`);
  lines.push(`    method: 'POST',`);
  lines.push(`    headers: { 'Content-Type': 'application/json' },`);
  lines.push(`    body: JSON.stringify({`);
  lines.push(`      server_name: '${serverName}',`);
  lines.push(`      tool_name: '${tool.name}',`);
  lines.push(`      arguments: ${inputArg},`);
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
 * Generate a complete TypeScript module exporting all tools for a server
 * @param tools - Array of tool definitions
 * @param serverName - Name of the MCP server
 * @returns TypeScript code string (index.ts content)
 */
export function generateServerModule(tools: ToolDefinition[], serverName: string): string {
  const lines: string[] = [];

  // File header comment
  lines.push('/**');
  lines.push(` * Auto-generated TypeScript wrappers for ${serverName} MCP server tools.`);
  lines.push(' * Do not edit manually - regenerate using wrapper-generator.');
  lines.push(' */');
  lines.push('');

  // Generate each tool wrapper
  for (const tool of tools) {
    lines.push(generateToolWrapper(tool, serverName));
    lines.push('');
  }

  return lines.join('\n');
}
