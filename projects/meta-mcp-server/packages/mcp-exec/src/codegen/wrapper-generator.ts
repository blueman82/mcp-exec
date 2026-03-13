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
  oneOf?: JsonSchemaProperty[];
  anyOf?: JsonSchemaProperty[];
  allOf?: JsonSchemaProperty[];
  const?: unknown;
  nullable?: boolean;
  additionalProperties?: boolean | JsonSchemaProperty;
  definitions?: Record<string, JsonSchemaProperty>;
}

/**
 * Convert a JSON Schema type to TypeScript type
 * @param prop - JSON Schema property definition
 * @param required - Whether the property is required
 * @param definitions - Root schema definitions for $ref resolution
 * @param visited - Set of already-visited $ref keys to prevent cycles
 * @returns TypeScript type string
 */
function jsonSchemaToTs(
  prop: JsonSchemaProperty | undefined,
  _required: boolean = true,
  definitions?: Record<string, JsonSchemaProperty>,
  visited: Set<string> = new Set()
): string {
  if (!prop) {
    return 'unknown';
  }

  // Handle $ref
  if (prop.$ref) {
    const refKey = prop.$ref.replace(/^#\/(definitions|\$defs)\//, '');
    if (definitions && refKey in definitions) {
      if (visited.has(refKey)) return 'unknown'; // break cycle
      const nextVisited = new Set(visited);
      nextVisited.add(refKey);
      return jsonSchemaToTs(definitions[refKey], _required, definitions, nextVisited);
    }
    return 'unknown';
  }

  // Handle const keyword
  if ('const' in prop && prop.const !== undefined) {
    return JSON.stringify(prop.const);
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

  // Handle oneOf
  if (prop.oneOf) {
    const types = prop.oneOf
      .map((s) => jsonSchemaToTs(s, _required, definitions, visited))
      .filter((t) => t !== 'unknown');
    if (types.length > 0) {
      return types.join(' | ');
    }
  }

  // Handle anyOf
  if (prop.anyOf) {
    const types = prop.anyOf
      .map((s) => jsonSchemaToTs(s, _required, definitions, visited))
      .filter((t) => t !== 'unknown');
    if (types.length > 0) {
      return types.join(' | ');
    }
  }

  // Handle allOf
  if (prop.allOf) {
    const types = prop.allOf
      .map((s) => jsonSchemaToTs(s, _required, definitions, visited))
      .filter((t) => t !== 'unknown');
    if (types.length > 0) {
      const primitives = ['string', 'number', 'boolean', 'null'];
      const incompatible = types.filter(t => primitives.includes(t)).length > 1;
      if (incompatible) return 'unknown';
      return types.join(' & ');
    }
  }

  // Handle object types with properties
  if (prop.type === 'object' && prop.properties) {
    const propLines = Object.entries(prop.properties).map(([key, value]) => {
      const isRequired = prop.required?.includes(key) ?? false;
      const tsType = jsonSchemaToTs(value as JsonSchemaProperty, isRequired, definitions, visited);
      const optionalMark = isRequired ? '' : '?';
      return `${key}${optionalMark}: ${tsType}`;
    });

    // Handle additionalProperties
    if (prop.additionalProperties === true) {
      propLines.push('[key: string]: unknown');
    } else if (typeof prop.additionalProperties === 'object' && prop.additionalProperties !== null) {
      // When named properties are present, the index signature must be a supertype of all
      // named property types. Using `unknown` is always valid and avoids TS4023 errors
      // (e.g., `id?: number` incompatible with `[key: string]: string`).
      propLines.push('[key: string]: unknown');
    } else if (Object.keys(prop.properties).length === 0 && !prop.additionalProperties) {
      // If no properties and no additionalProperties, return Record type
      return 'Record<string, unknown>';
    }

    return `{ ${propLines.join('; ')} }`;
  }

  // Handle object type without properties
  if (prop.type === 'object') {
    if (prop.additionalProperties === true || (typeof prop.additionalProperties === 'object' && prop.additionalProperties !== null)) {
      return 'Record<string, unknown>';
    }
  }

  // Handle array types
  if (prop.type === 'array') {
    const itemType = prop.items ? jsonSchemaToTs(prop.items, true, definitions, visited) : 'unknown';
    return `${itemType}[]`;
  }

  let result = primitiveToTs(prop.type ?? 'unknown');

  // Handle nullable: true (OpenAPI 3.0 style)
  if ((prop as any).nullable === true) {
    if (result !== 'unknown' && !result.includes('| null') && !result.includes('null |')) {
      result = `${result} | null`;
    }
  }

  return result;
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
 * @param definitions - Root schema definitions for $ref resolution
 * @returns TypeScript interface definition
 */
function generateInterface(name: string, schema: { properties?: Record<string, unknown>; required?: string[]; definitions?: Record<string, JsonSchemaProperty> }, definitions?: Record<string, JsonSchemaProperty>): string {
  const defs = definitions || (schema as any).definitions;

  if (!schema.properties || Object.keys(schema.properties).length === 0) {
    return `interface ${name} {}`;
  }

  const lines: string[] = [];
  lines.push(`interface ${name} {`);

  for (const [propName, propValue] of Object.entries(schema.properties)) {
    const prop = propValue as JsonSchemaProperty;
    const isRequired = schema.required?.includes(propName) ?? false;
    const optionalMark = isRequired ? '' : '?';
    const tsType = jsonSchemaToTs(prop, isRequired, defs);

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
      if (prop === '__proto__' || prop === 'prototype') return undefined;
      if (Object.prototype.hasOwnProperty.call(target, prop)) {
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
 * Escape a string for safe embedding inside a JavaScript template literal.
 * JSON.stringify does NOT escape backticks or ${}, which can break generated
 * template literals or enable code injection.
 */
function escapeForTemplateLiteral(s: string): string {
  return s.replace(/`/g, '\\`').replace(/\$\{/g, '\\${');
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
  const safeContextName = escapeForTemplateLiteral(JSON.stringify(contextName));
  return `new Proxy(${targetVarName}, {
  get(target, prop) {
    if (typeof prop !== 'string') return undefined;

    // Block prototype pollution vectors
    if (prop === '__proto__' || prop === 'constructor' || prop === 'prototype') return undefined;

    // Fast-path: exact match — use hasOwnProperty to avoid prototype chain leaks
    if (Object.prototype.hasOwnProperty.call(target, prop)) return target[prop];

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
 * @param rootDefinitions - Root schema definitions for $ref resolution
 * @returns Interface definition string or empty string
 */
function generateToolInterface(tool: ToolDefinition, rootDefinitions?: Record<string, JsonSchemaProperty>): string {
  const interfaceName = `${toPascalCase(tool.name)}Input`;

  if (tool.inputSchema?.properties && Object.keys(tool.inputSchema.properties).length > 0) {
    return generateInterface(interfaceName, tool.inputSchema, rootDefinitions);
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

  // Collect required and optional params for summary
  const requiredParams: string[] = [];
  const optionalParams: string[] = [];
  if (tool.inputSchema?.properties) {
    for (const propName of Object.keys(tool.inputSchema.properties)) {
      if (tool.inputSchema.required?.includes(propName)) {
        requiredParams.push(propName);
      } else {
        optionalParams.push(propName);
      }
    }
  }

  // Add JSDoc comment
  if (tool.description) {
    lines.push('  /**');
    lines.push(`   * ${sanitizeJsDoc(tool.description)}`);
    if (tool.inputSchema?.properties) {
      for (const [propName, propValue] of Object.entries(tool.inputSchema.properties)) {
        const prop = propValue as JsonSchemaProperty;
        const isRequired = tool.inputSchema.required?.includes(propName) ?? false;
        const marker = isRequired ? '[required]' : '[optional]';
        if (prop.description) {
          lines.push(`   * @param input.${propName} ${marker} - ${sanitizeJsDoc(prop.description)}`);
        } else {
          lines.push(`   * @param input.${propName} ${marker}`);
        }
      }
    }
    // Add required/optional summary
    if (requiredParams.length > 0 || optionalParams.length > 0) {
      lines.push(`   * Required: ${requiredParams.length > 0 ? requiredParams.join(', ') : 'none'}`);
      if (optionalParams.length > 0) {
        lines.push(`   * Optional: ${optionalParams.join(', ')}`);
      }
    }
    // Add @returns hint
    const safeServerName = JSON.stringify(serverName);
    const safeToolName = JSON.stringify(tool.name);
    lines.push(`   * @returns Promise<unknown>. To inspect response shape: get_mcp_tool_schema({ server: ${safeServerName}, tool: ${safeToolName} })`);
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
  // Use escapeForTemplateLiteral to prevent backtick/`${}` injection in error messages
  const tlSafe = (s: string) => escapeForTemplateLiteral(s);
  lines.push(`    if (!response.ok) {`);
  lines.push(`      throw new Error(\`[${tlSafe(safeServerName)}.${tlSafe(safeToolName)}] HTTP \${response.status}: \${response.statusText}\`);`);
  lines.push(`    }`);
  lines.push(`    const data = await response.json() as { success: boolean; content?: unknown; error?: string; isError?: boolean };`);
  lines.push(`    if (!data.success) {`);
  lines.push(`      throw new Error(\`[${tlSafe(safeServerName)}.${tlSafe(safeToolName)}] \${data.error || 'Tool call failed'}\`);`);
  lines.push(`    }`);
  lines.push(`    if (data.isError) {`);
  lines.push(`      const errText = Array.isArray(data.content) && data.content[0]?.text ? data.content[0].text : 'Tool returned isError';`);
  lines.push(`      throw new Error(\`[${tlSafe(safeServerName)}.${tlSafe(safeToolName)}] \${errText}\`);`);
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
 * @param variableNameOverride - Optional override for the namespace variable name
 * @returns TypeScript code string with namespace object
 */
export function generateServerModule(tools: ToolDefinition[], serverName: string, bridgePort: number = 3000, variableNameOverride?: string): string {
  const lines: string[] = [];
  const namespaceName = variableNameOverride ?? sanitizeIdentifier(serverName);

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
    const rootDefs = (tool.inputSchema as any)?.definitions ?? (tool.inputSchema as any)?.$defs;
    const interfaceCode = generateToolInterface(tool, rootDefs);
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
 * Generate MCP dictionary from a pre-computed name map.
 * Keys: original server names. Values: unique variable names used in generateServerModule.
 *
 * @param serverNames - Array of original server names
 * @param nameMap - Map of original server name → variable name
 * @returns TypeScript code string with mcp dictionary
 */
export function generateMcpDictionaryFromMap(serverNames: string[], nameMap: Map<string, string>): string {
  const lines: string[] = [];
  lines.push('/**');
  lines.push(' * MCP Server Dictionary - Access all MCP servers via case-agnostic lookup.');
  lines.push(` * Available: ${serverNames.map((n) => `mcp['${n}']`).join(', ')}`);
  lines.push(' */');
  lines.push('');
  lines.push('const mcp_servers_raw: Record<string, unknown> = {');
  for (const serverName of serverNames) {
    const varName = nameMap.get(serverName) ?? sanitizeIdentifier(serverName);
    lines.push(`  ${JSON.stringify(serverName)}: ${varName},`);
  }
  lines.push('};');
  lines.push('');
  lines.push(`const mcp = ${generateFuzzyProxy('mcp_servers_raw', 'mcp')};`);
  lines.push('');
  return lines.join('\n');
}

/**
 * Generate the MCP dictionary code that maps server names to their namespace objects.
 * Creates a case-agnostic `mcp` dictionary with fuzzy matching for server name resolution.
 * Detects and resolves sanitized name collisions by appending numeric suffixes.
 *
 * @param serverNames - Array of original server names
 * @returns TypeScript code string with mcp dictionary
 * @deprecated Use generateMcpDictionaryFromMap instead to ensure name consistency with generateServerModule
 */
export function generateMcpDictionary(serverNames: string[]): string {
  const lines: string[] = [];

  // Track sanitized names for collision detection
  const sanitizedToOriginal = new Map<string, string[]>();
  const uniqueNames = new Map<string, string>(); // original name -> unique variable name

  // First pass: collect all sanitized names and detect collisions
  for (let i = 0; i < serverNames.length; i++) {
    const originalName = serverNames[i];
    const sanitized = sanitizeIdentifier(originalName);

    if (!sanitizedToOriginal.has(sanitized)) {
      sanitizedToOriginal.set(sanitized, []);
    }
    sanitizedToOriginal.get(sanitized)!.push(originalName);
  }

  // Second pass: assign unique variable names, adding suffix on collision
  let collisionIndex = 0;
  for (const originalName of serverNames) {
    const sanitized = sanitizeIdentifier(originalName);
    const conflictingNames = sanitizedToOriginal.get(sanitized)!;

    if (conflictingNames.length > 1) {
      // Collision detected - use index suffix
      const uniqueName = `${sanitized}_${collisionIndex}`;
      uniqueNames.set(originalName, uniqueName);
      lines.push(`// WARNING: Server name collision: '${originalName}' and previous server both sanitize to '${sanitized}'. Using '${uniqueName}'.`);
      collisionIndex++;
    } else {
      // No collision - use standard sanitized name
      uniqueNames.set(originalName, sanitized);
    }
  }

  lines.push('');

  // Generate comment header with server list for AI discoverability
  const sanitizedNames = serverNames.map(sanitizeIdentifier);
  lines.push('/**');
  lines.push(' * MCP Server Dictionary - Access all MCP servers via case-agnostic lookup.');
  lines.push(` * Available: ${serverNames.map((n) => `mcp['${n}']`).join(', ')}`);
  lines.push(` * Aliases: ${sanitizedNames.join(', ')}`);
  lines.push(' */');
  lines.push('');

  // Create raw dictionary mapping original names to unique namespace variables
  lines.push('const mcp_servers_raw: Record<string, unknown> = {');
  for (const serverName of serverNames) {
    const uniqueName = uniqueNames.get(serverName)!;
    // Map original name to the namespace variable
    lines.push(`  ${JSON.stringify(serverName)}: ${uniqueName},`);
  }
  lines.push('};');
  lines.push('');

  // Wrap with fuzzy Proxy for case-agnostic server name resolution
  lines.push(`const mcp = ${generateFuzzyProxy('mcp_servers_raw', 'mcp')};`);
  lines.push('');

  return lines.join('\n');
}
