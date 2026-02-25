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
      lines.push(`  /** ${sanitizeJsDoc(prop.description)} */`);
    }

    lines.push(`  ${propName}${optionalMark}: ${tsType};`);
  }

  lines.push('}');
  return lines.join('\n');
}

/**
 * Sanitize description text for safe inclusion in JSDoc comments.
 * Escapes star-slash sequences that would prematurely close the comment.
 * @param text - The description text to sanitize
 * @returns Sanitized text safe for JSDoc
 */
function sanitizeJsDoc(text: string): string {
  // Escape */ to prevent premature JSDoc comment closure
  // This handles glob patterns like "src/**/*.ts" in tool descriptions
  return text.replace(/\*\//g, '* /');
}

/**
 * Generate a recursive Proxy guard that warns on undefined field access on MCP responses.
 * Injected into generated wrapper code. On missing field: logs available fields to stderr.
 * Zero overhead on correct access (prop in target short-circuits).
 * Arrays are also wrapped so index access returns guarded items.
 */
function generateFieldGuard(): string {
  return `
function __guardFields(obj, label) {
  if (!obj || typeof obj !== 'object') return obj;
  if (Array.isArray(obj)) {
    return new Proxy(obj, {
      get(target, prop) {
        if (typeof prop === 'symbol') return target[prop];
        const idx = Number(prop);
        if (Number.isInteger(idx) && idx >= 0 && idx < target.length) {
          const item = target[idx];
          return item && typeof item === 'object' ? __guardFields(item, label + '[' + idx + ']') : item;
        }
        return target[prop];
      }
    });
  }
  return new Proxy(obj, {
    get(target, prop) {
      if (typeof prop === 'symbol' || prop === 'then' || prop === 'toJSON'
          || prop === 'length' || prop === 'constructor' || prop === 'nodeType'
          || prop === 'valueOf' || prop === 'toString' || prop === 'inspect') {
        return target[prop];
      }
      if (prop in target) {
        const val = target[prop];
        if (val && typeof val === 'object') {
          return __guardFields(val, label + '.' + String(prop));
        }
        return val;
      }
      const available = Object.keys(target).join(', ');
      console.error('⚠ No field "' + String(prop) + '" on ' + label + '. Available: ' + available);
      return undefined;
    }
  });
}
`;
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
 * Normalize a name for fuzzy matching by stripping hyphens, underscores, and lowercasing.
 * Used to match e.g. "getUser" to "get_user" or "get-user".
 * @param name - The name to normalize
 * @returns Normalized name for comparison
 */
export function normalizeName(name: string): string {
  return name.toLowerCase().replace(/[_-]/g, '');
}

/**
 * Generate a Proxy wrapper code string that enables fuzzy/case-agnostic property access.
 * The generated Proxy intercepts property access and:
 * 1. Fast-path: Returns exact match if property exists
 * 2. Fuzzy match: Normalizes requested property and searches for matching key
 * 3. Error: Throws TypeError with available options if no match found
 *
 * @param targetVarName - The variable name of the target object to wrap
 * @param contextName - Context name for error messages (e.g., server name)
 * @returns String containing Proxy code to be injected into generated wrapper
 */
export function generateFuzzyProxy(targetVarName: string, contextName: string): string {
  const safeContextName = JSON.stringify(contextName);
  return `new Proxy(${targetVarName}, {
  get(target, prop) {
    if (typeof prop !== 'string') return undefined;

    // Fast-path: exact match
    if (prop in target) return target[prop];

    // Fuzzy match: normalize and search
    const normalizedProp = prop.toLowerCase().replace(/[_-]/g, '');
    for (const key of Object.keys(target)) {
      const normalizedKey = key.toLowerCase().replace(/[_-]/g, '');
      if (normalizedKey === normalizedProp) {
        return target[key];
      }
    }

    // No match found - throw helpful error
    const available = Object.keys(target).join(', ');
    throw new TypeError(\`Property "\${prop}" not found on ${safeContextName}. Available: \${available}\`);
  }
})`;
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
    lines.push(`   * ${sanitizeJsDoc(tool.description)}`);
    if (tool.inputSchema?.properties) {
      for (const [propName, propValue] of Object.entries(tool.inputSchema.properties)) {
        const prop = propValue as JsonSchemaProperty;
        if (prop.description) {
          lines.push(`   * @param input.${propName} - ${sanitizeJsDoc(prop.description)}`);
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
  lines.push(`    const data = await response.json() as { success: boolean; content?: unknown; error?: string; isError?: boolean };`);
  lines.push(`    if (!data.success) {`);
  lines.push(`      throw new Error(data.error || 'Tool call failed');`);
  lines.push(`    }`);
  lines.push(`    if (data.isError) {`);
  lines.push(`      const errText = Array.isArray(data.content) && data.content[0]?.text ? data.content[0].text : 'Tool returned isError';`);
  lines.push(`      throw new Error(errText);`);
  lines.push(`    }`);
  lines.push(`    // Auto-parse JSON from MCP text content blocks for convenience`);
  lines.push(`    const content = data.content;`);
  lines.push(`    if (Array.isArray(content) && content.length === 1 && content[0]?.type === 'text') {`);
  lines.push(`      try {`);
  lines.push(`        const parsed = JSON.parse(content[0].text);`);
  lines.push(`        // Surface application-level errors (e.g. {success: false, error: "..."}) as thrown errors`);
  lines.push(`        if (parsed && typeof parsed === 'object' && parsed.success === false && parsed.error) {`);
  lines.push(`          throw new Error(parsed.error);`);
  lines.push(`        }`);
  lines.push(`        return typeof __guardFields === 'function' ? __guardFields(parsed, ${safeServerName} + '.' + ${safeToolName}) : parsed;`);
  lines.push(`      } catch (e) {`);
  lines.push(`        if (e instanceof Error && !(e instanceof SyntaxError)) throw e;`);
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
    lines.push(` * ${sanitizeJsDoc(tool.description)}`);
    if (tool.inputSchema?.properties) {
      lines.push(' *');
      for (const [propName, propValue] of Object.entries(tool.inputSchema.properties)) {
        const prop = propValue as JsonSchemaProperty;
        if (prop.description) {
          lines.push(` * @param input.${propName} - ${sanitizeJsDoc(prop.description)}`);
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
  lines.push(` * Case-insensitive: methodName, method_name, and method-name all work.`);
  lines.push(` * Access tools via: ${namespaceName}.methodName()`);
  lines.push(' */');
  lines.push('');

  // Inject field guard helper for undefined-field warnings on responses
  lines.push(generateFieldGuard());

  // Generate all interfaces first
  for (const tool of tools) {
    const interfaceCode = generateToolInterface(tool);
    if (interfaceCode) {
      lines.push(interfaceCode);
      lines.push('');
    }
  }

  // Generate the raw namespace object with all methods
  lines.push(`const ${namespaceName}_raw = {`);

  for (let i = 0; i < tools.length; i++) {
    const tool = tools[i];
    lines.push(generateMethodDefinition(tool, serverName, bridgePort));
    // No trailing comma after last method (already handled by generateMethodDefinition)
  }

  lines.push('};');
  lines.push('');

  // Wrap with fuzzy Proxy for case-agnostic access
  lines.push(`const ${namespaceName} = ${generateFuzzyProxy(`${namespaceName}_raw`, serverName)};`);
  lines.push('');

  return lines.join('\n');
}

/**
 * Generate the MCP dictionary code that maps server names to their namespace objects.
 * Creates a case-agnostic `mcp` dictionary with fuzzy matching for server name resolution.
 *
 * @param serverNames - Array of original server names
 * @returns TypeScript code string with mcp dictionary
 */
export function generateMcpDictionary(serverNames: string[]): string {
  const lines: string[] = [];

  // Generate comment header with server list for AI discoverability
  const sanitizedNames = serverNames.map(sanitizeIdentifier);
  lines.push('/**');
  lines.push(' * MCP Server Dictionary - Access all MCP servers via case-agnostic lookup.');
  lines.push(` * Available: ${serverNames.map((n) => `mcp['${n}']`).join(', ')}`);
  lines.push(` * Aliases: ${sanitizedNames.join(', ')}`);
  lines.push(' */');
  lines.push('');

  // Create raw dictionary mapping original names to sanitized namespace variables
  lines.push('const mcp_servers_raw: Record<string, unknown> = {');
  for (const serverName of serverNames) {
    const sanitized = sanitizeIdentifier(serverName);
    // Map original name to the namespace variable
    lines.push(`  ${JSON.stringify(serverName)}: ${sanitized},`);
  }
  lines.push('};');
  lines.push('');

  // Wrap with fuzzy Proxy for case-agnostic server name resolution
  lines.push(`const mcp = ${generateFuzzyProxy('mcp_servers_raw', 'mcp')};`);
  lines.push('');

  return lines.join('\n');
}
