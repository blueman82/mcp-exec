# mcp-exec Tool-Calling Error Analysis & Fix Proposals

**Scope**: Identifies 5 critical error sources in mcp-exec wrapper generation and tool descriptions that cause LLM tool-call failures, with implementable server-side fixes baked into mcp-exec itself.

---

## Executive Summary

LLMs calling mcp-exec tools fail in three categories:

1. **Pre-execution errors** (wrong server/tool names) — preventable with better tool descriptions
2. **Generation errors** (incomplete JSDoc, missing schema constraints) — fixable in wrapper-generator.ts
3. **Post-execution errors** (ambiguous error messages, undefined field access) — fixable in execute-with-wrappers.ts and bridge/server.ts

All fixes are *server-side*, requiring no client-side system prompts.

---

## Problem 1: Server Name Discoverability in Tool Description

### Current Behavior

`executeCodeWithWrappersTool.description` (line 44-47 in execute-with-wrappers.ts):
```typescript
description:
  'Execute TypeScript/JavaScript code with auto-generated typed wrappers for specified MCP servers. ' +
  'Provides a typed API like github.createIssue({ title: "..." }) instead of raw mcp.callTool(). ' +
  'Multi-line code is supported - format naturally for readability.',
```

**Problem**: LLMs don't know server names without calling `list_available_mcp_servers` first. They guess names like "github", "jira", "splunk" that may not match actual server names ("adobe_jira", "jira_gateway", etc.). The description doesn't mention that `list_available_mcp_servers` exists or that exact names are required.

### Why This Causes Errors

- LLM guesses `wrappers: ["jira"]` but server is registered as `"adobe_jira"` → wrapper generation fails with "Error generating wrapper for server 'jira': not found"
- LLM doesn't realize it should call `list_available_mcp_servers` first
- Error message "Error generating wrapper for server 'jira': not found" doesn't suggest how to discover valid names

### Proposed Fix

**File**: `src/tools/execute-with-wrappers.ts` (lines 44-47)

**Change**: Enrich `executeCodeWithWrappersTool.description` with:
1. A hint that server names must be exact (discovered via `list_available_mcp_servers`)
2. Example of the wrapper API in action
3. Mention that fuzzy matching works (case-insensitive, hyphen/underscore variations)

```typescript
export const executeCodeWithWrappersTool = {
  name: 'execute_code_with_wrappers',
  description:
    'Execute TypeScript/JavaScript code with auto-generated typed wrappers for specified MCP servers. ' +
    'Provides a typed API like adobe_jira.search_issues({ jql: "..." }) instead of raw mcp.callTool(). ' +
    '\n\nREQUIRED: Use exact server names from list_available_mcp_servers (e.g., "adobe_jira", "splunk_api"). ' +
    'Fuzzy matching: "get_jira_issues", "getJiraIssues", and "get-jira-issues" all resolve to the same method. ' +
    '\n\nExample workflow: ' +
    '1) Call list_available_mcp_servers to discover server names ' +
    '2) Call execute_code_with_wrappers with those exact names in the wrappers array ' +
    '3) Write code like: const results = await adobe_jira.search_issues({ jql: "status=Open" }); ' +
    '\n\nMulti-line code is supported - format naturally for readability.',
  inputSchema: {
    type: 'object' as const,
    properties: {
      code: {
        type: 'string',
        description: 'The TypeScript/JavaScript code to execute. Multi-line supported - format for readability.',
      },
      wrappers: {
        type: 'array',
        items: { type: 'string' },
        description:
          'Array of exact MCP server names to generate typed wrappers for (e.g., ["adobe_jira", "splunk_api"]). ' +
          'Names must match exactly as returned by list_available_mcp_servers. ' +
          'Case-insensitive and hyphen/underscore variations work in code (e.g., adobe_jira.search_issues or adobe_jira.searchIssues).',
      },
      timeout_ms: {
        type: 'number',
        description: `Maximum execution time in milliseconds (default: ${DEFAULT_TIMEOUT_MS})`,
      },
    },
    required: ['code', 'wrappers'],
  },
};
```

**Why This Works**: LLMs now understand:
- Server names must come from `list_available_mcp_servers`
- The fuzzy matching fallback for method names (reduces subsequent errors)
- The full workflow (discover → execute)
- Example code patterns to follow

---

## Problem 2: Generated JSDoc Lacks Required/Optional Markers and Constraints

### Current Behavior

Generated JSDoc in `generateMethodDefinition` (wrapper-generator.ts, lines 284-296):
```typescript
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
```

**Output** (example from Jira search):
```typescript
/**
 * Search for Jira issues using JQL
 * @param input.jql - The JQL (Jira Query Language) search string.
 * @param input.start_at - Starting index for pagination.
 * @param input.max_results - Maximum number of results to return.
 * @param input.fields - List of fields to include in the response.
 */
```

**Problem**: Missing information:
- No indication that `jql` is **required** but `start_at`, `max_results`, `fields` are optional
- No constraints: `jql` can't be empty, `max_results` must be > 0, `start_at` must be >= 0
- No enums: for `status`, LLM doesn't know allowed values ("Open", "In Progress", "Done")
- No example values: LLM invents invalid JQL strings

### Why This Causes Errors

- LLM calls `search_issues({})` with empty/missing required field → tool returns 400 with unhelpful error
- LLM calls `search_issues({ max_results: -1 })` → backend rejects negative
- LLM calls `search_issues({ status: "pending" })` when valid values are `["open", "inprogress", "done"]` → validation error
- LLM doesn't know field names for nested objects or their types

### Proposed Fix

**File**: `src/codegen/wrapper-generator.ts` (lines 273-343)

**Change**: Enhance `generateMethodDefinition` to include required/optional markers, constraints, enums, and examples in JSDoc.

```typescript
function generateMethodDefinition(tool: ToolDefinition, serverName: string, bridgePort: number): string {
  const methodName = sanitizeIdentifier(tool.name);
  const interfaceName = `${toPascalCase(tool.name)}Input`;
  const hasInput = tool.inputSchema?.properties && Object.keys(tool.inputSchema.properties).length > 0;
  const inputParam = hasInput ? `input: ${interfaceName}` : '';
  const inputArg = hasInput ? 'input' : '{}';

  const lines: string[] = [];

  // Add JSDoc comment with enhanced documentation
  if (tool.description) {
    lines.push('  /**');
    lines.push(`   * ${sanitizeJsDoc(tool.description)}`);

    if (tool.inputSchema?.properties) {
      lines.push('   *');
      const requiredFields = tool.inputSchema.required || [];

      for (const [propName, propValue] of Object.entries(tool.inputSchema.properties)) {
        const prop = propValue as JsonSchemaProperty;
        const isRequired = requiredFields.includes(propName);
        const requiredMarker = isRequired ? '[REQUIRED]' : '[optional]';

        let paramDoc = `   * @param input.${propName} - ${requiredMarker}`;

        if (prop.description) {
          paramDoc += ` ${sanitizeJsDoc(prop.description)}`;
        }

        // Add type hint from schema
        const typeHint = jsonSchemaToTs(prop, isRequired);
        if (typeHint && typeHint !== 'unknown') {
          paramDoc += ` (type: ${typeHint})`;
        }

        // Add enum values if present
        if (prop.enum && prop.enum.length > 0) {
          const enumStr = prop.enum.map(v => JSON.stringify(v)).join(' | ');
          paramDoc += ` Allowed: ${enumStr}.`;
        }

        // Add constraints if present
        if (prop.type === 'string' && (prop.minLength || prop.maxLength || prop.pattern)) {
          const constraints: string[] = [];
          if (prop.minLength !== undefined) constraints.push(`min ${prop.minLength} chars`);
          if (prop.maxLength !== undefined) constraints.push(`max ${prop.maxLength} chars`);
          if (prop.pattern) constraints.push(`matches pattern: ${prop.pattern}`);
          paramDoc += ` Constraints: ${constraints.join(', ')}.`;
        }

        if (prop.type === 'number' || prop.type === 'integer') {
          const constraints: string[] = [];
          if (prop.minimum !== undefined) constraints.push(`>= ${prop.minimum}`);
          if (prop.maximum !== undefined) constraints.push(`<= ${prop.maximum}`);
          if (prop.exclusiveMinimum !== undefined) constraints.push(`> ${prop.exclusiveMinimum}`);
          if (prop.exclusiveMaximum !== undefined) constraints.push(`< ${prop.exclusiveMaximum}`);
          if (constraints.length > 0) {
            paramDoc += ` Range: ${constraints.join(', ')}.`;
          }
        }

        // Add default value if present
        if (prop.default !== undefined) {
          paramDoc += ` Default: ${JSON.stringify(prop.default)}.`;
        }

        // Add example if available (from x-example or infer from type)
        if (prop.example !== undefined) {
          paramDoc += ` Example: ${JSON.stringify(prop.example)}.`;
        } else if (prop.type === 'string' && isRequired) {
          // Suggest example pattern for required strings
          if (propName.includes('jql') || propName.includes('query')) {
            paramDoc += ` Example: "status = Open AND assignee = currentUser()".`;
          } else if (propName.includes('key') || propName.includes('id')) {
            paramDoc += ` Example: "PROJ-123" or similar identifier.`;
          }
        }

        lines.push(paramDoc);
      }

      // Add return type documentation
      if (tool.outputSchema) {
        lines.push('   *');
        lines.push(`   * @returns ${sanitizeJsDoc(tool.outputSchema.description || 'Tool result')}`);
        if (tool.outputSchema.type) {
          lines.push(`   *   (type: ${tool.outputSchema.type})`);
        }
      }
    }

    lines.push('   */');
  }

  // ... rest of method generation unchanged ...
}
```

**Enhanced JSDoc Example Output**:
```typescript
/**
 * Search for Jira issues using JQL
 *
 * @param input.jql - [REQUIRED] The JQL (Jira Query Language) search string. (type: string) Constraints: max 500 chars. Example: "status = Open AND assignee = currentUser()".
 * @param input.start_at - [optional] Starting index for pagination (type: number) Range: >= 0. Default: 0.
 * @param input.max_results - [optional] Maximum number of results to return (type: number) Range: >= 1, <= 100. Default: 50.
 * @param input.fields - [optional] List of fields to include in the response (type: string[]). Example: ["summary", "status", "assignee"].
 *
 * @returns Array of matching Jira issues with requested fields
 *   (type: array)
 */
```

**Why This Works**: LLMs now see:
- Which fields are required (won't omit critical fields)
- Constraints on numeric/string fields (knows max_results must be positive)
- Enum values and patterns (uses valid status names)
- Example values (reduces hallucination of invalid JQL)
- Return type shape (can predict what fields the result will have)

---

## Problem 3: Error Messages Lack Tool Call Context

### Current Behavior

When a tool call fails, the error bubbles up from the bridge (bridge/server.ts) as stderr:

**Bridge error response** (line 163-169 in bridge/server.ts):
```typescript
const data = await response.json() as { success: boolean; content?: unknown[]; error?: string };
if (!data.success) {
  throw new Error(data.error || 'MCP tool call failed');
}
```

**Wrapper error catch** (wrapper-generator.ts, lines 317-322):
```typescript
if (!data.success) {
  throw new Error(data.error || 'Tool call failed');
}
if (data.isError) {
  const errText = Array.isArray(data.content) && data.content[0]?.text ? data.content[0].text : 'Tool returned isError';
  throw new Error(errText);
}
```

**What LLM sees** (from execute-with-wrappers.ts formatResult, line 339):
```
[stderr]: Tool call failed: 400 Bad Request (or similar)
```

**Problem**: The LLM sees:
- No indication which server/tool was called
- No indication which argument was wrong
- No context about what it sent
- Generic "failed" messages without actionable hints

Example:
```
[stderr]: JQL syntax error at position 42
```

LLM doesn't know: Was it `search_issues`? Was it the `jql` parameter? What was the actual JQL sent?

### Why This Causes Errors

- LLM can't correlate error to specific tool call in multi-step code
- LLM doesn't know which parameter to fix
- LLM retries with same broken code expecting different result
- If code calls multiple tools, error context is lost

### Proposed Fix

**File 1**: `src/codegen/wrapper-generator.ts` (lines 303-323)

**Change**: Wrap tool calls in try/catch with enhanced error context.

```typescript
function generateMethodDefinition(tool: ToolDefinition, serverName: string, bridgePort: number): string {
  // ... interface and JSDoc code ...

  const safeServerName = JSON.stringify(serverName);
  const safeToolName = JSON.stringify(tool.name);
  const inputParamStr = hasInput ? 'input' : '{}'; // For logging

  lines.push(`  ${methodName}: async (${inputParam}): Promise<unknown> => {`);

  // Add error context wrapper
  lines.push(`    const toolCallContext = { server: ${safeServerName}, tool: ${safeToolName}, args: ${inputParamStr} };`);
  lines.push(`    try {`);

  lines.push(`      const response = await fetch('http://127.0.0.1:${bridgePort}/call', {`);
  lines.push(`        method: 'POST',`);
  lines.push(`        headers: { 'Content-Type': 'application/json' },`);
  lines.push(`        body: JSON.stringify({`);
  lines.push(`          server: ${safeServerName},`);
  lines.push(`          tool: ${safeToolName},`);
  lines.push(`          args: ${inputParamStr},`);
  lines.push(`        }),`);
  lines.push(`      });`);

  lines.push(`      if (!response.ok) {`);
  lines.push(`        const statusText = response.statusText || 'Unknown error';`);
  lines.push(`        const errorMsg = 'Tool call failed: ' + statusText;`);
  lines.push(`        const contextStr = JSON.stringify(toolCallContext, null, 2);`);
  lines.push(`        throw new Error(errorMsg + '\\n[Context]\\n' + contextStr);`);
  lines.push(`      }`);

  lines.push(`      const data = await response.json() as { success: boolean; content?: unknown; error?: string; isError?: boolean };`);

  lines.push(`      if (!data.success) {`);
  lines.push(`        const contextStr = JSON.stringify(toolCallContext, null, 2);`);
  lines.push(`        const errorDetails = data.error || 'Tool call failed';`);
  lines.push(`        throw new Error(errorDetails + '\\n[Context]\\n' + contextStr);`);
  lines.push(`      }`);

  lines.push(`      if (data.isError) {`);
  lines.push(`        const errText = Array.isArray(data.content) && data.content[0]?.text ? data.content[0].text : 'Tool returned isError';`);
  lines.push(`        const contextStr = JSON.stringify(toolCallContext, null, 2);`);
  lines.push(`        throw new Error(errText + '\\n[Context]\\n' + contextStr);`);
  lines.push(`      }`);

  lines.push(`      // ... rest of response parsing ...`);
  lines.push(`      return content;`);

  lines.push(`    } catch (err) {`);
  lines.push(`      // Re-throw with enhanced context if not already enhanced`);
  lines.push(`      const errMsg = err instanceof Error ? err.message : String(err);`);
  lines.push(`      if (!errMsg.includes('[Context]')) {`);
  lines.push(`        const contextStr = JSON.stringify(toolCallContext, null, 2);`);
  lines.push(`        throw new Error(errMsg + '\\n[Context]\\n' + contextStr);`);
  lines.push(`      }`);
  lines.push(`      throw err;`);
  lines.push(`    }`);
  lines.push(`  },`);

  return lines.join('\n');
}
```

**File 2**: `src/tools/execute-with-wrappers.ts` (lines 329-351)

**Change**: Extract tool context from errors and surface it clearly.

```typescript
function formatResult(result: ExecutionResult): CallToolResult {
  const lines: string[] = [];

  // Add output
  if (result.output.length > 0) {
    lines.push(...result.output);
  }

  // Add error if present (non-fatal stderr) with context parsing
  if (result.error) {
    // Try to parse tool context from error
    const contextMatch = result.error.match(/\[Context\]\s+([\s\S]*?)$/);
    if (contextMatch) {
      lines.push(`[stderr]: ${result.error.split('\n[Context]')[0]}`);
      lines.push(`[Tool Context]:`);
      lines.push(contextMatch[1]);
    } else {
      lines.push(`[stderr]: ${result.error}`);
    }
  }

  // Add execution time
  lines.push(`[Execution completed in ${result.durationMs}ms]`);

  const hasError = !!result.error;

  return {
    content: [{ type: 'text', text: lines.join('\n') }],
    isError: hasError,
  };
}
```

**Example Output to LLM**:
```
[stderr]: JQL syntax error at position 42

[Tool Context]:
{
  "server": "adobe_jira",
  "tool": "search_issues",
  "args": {
    "jql": "status = Open AND assignee = currentUser()"
  }
}
```

**Why This Works**: LLM now:
- Sees exactly which server/tool was called
- Sees the exact arguments passed
- Can correlate error to specific line in multi-tool code
- Can identify which parameter caused the issue
- Can self-correct with better values

---

## Problem 4: Static Tool Description Doesn't Include Available Servers/Tools

### Current Behavior

The `execute_code_with_wrappers` tool description is static. LLMs must:
1. Call `list_available_mcp_servers` (1 round-trip)
2. Parse response, pick a server
3. Call `get_mcp_tool_schema` to list tools (another round-trip)
4. Finally call `execute_code_with_wrappers`

**Result**: 3+ round-trips for a single task.

### Why This Causes Errors

- LLM forgets which servers were available after context window management
- LLM calls `execute_code_with_wrappers` with server names from previous session (stale)
- LLM makes typos in server names it had to remember
- Slow → model gives up and hallucinates

### Proposed Fix

**File**: `src/tools/execute-with-wrappers.ts` (lines 42-67)

**Change**: Dynamically inject server inventory into tool description at MCP server startup.

Create a new function in `execute-with-wrappers.ts`:
```typescript
/**
 * Generate a summary of available servers and key tools for inclusion in tool description.
 * Limits to 2000 chars to avoid bloating description beyond LLM token budget.
 * @param pool - Server pool for discovering available servers
 * @returns Formatted summary string for tool description
 */
async function generateAvailableServersSummary(pool: ServerPool): Promise<string> {
  try {
    const servers = listServers(); // From meta-mcp-core
    if (servers.length === 0) {
      return 'No MCP servers currently configured.';
    }

    const lines: string[] = ['Available MCP servers:'];
    let charCount = 0;

    for (const server of servers.slice(0, 10)) { // Limit to 10 servers
      const line = `\n- ${server.name}: ${server.description || '(no description)'}`;
      if (charCount + line.length > 1500) break; // Leave room for other content
      lines.push(line);
      charCount += line.length;

      // Try to add 1-2 key tools for each server
      try {
        const connection = await pool.getConnection(server.name);
        const tools = await connection.getTools();
        pool.releaseConnection(server.name);

        const toolNames = tools.slice(0, 2).map(t => t.name).join(', ');
        if (toolNames) {
          const toolLine = `  Tools: ${toolNames}`;
          if (charCount + toolLine.length > 1500) break;
          lines.push(toolLine);
          charCount += toolLine.length;
        }
      } catch {
        // Skip tool listing if server unavailable
      }
    }

    if (servers.length > 10) {
      lines.push(`\n... and ${servers.length - 10} more servers.`);
    }
    lines.push('\nUse exact server names from this list in the wrappers parameter.');

    return lines.join('\n');
  } catch {
    return 'Unable to load server inventory. Call list_available_mcp_servers to discover servers.';
  }
}
```

Then modify `createExecuteWithWrappersHandler` to populate description at startup:
```typescript
export function createExecuteWithWrappersHandler(
  pool: ServerPool,
  config: ExecuteWithWrappersHandlerConfig = {}
) {
  let inventorySummary = '';

  // Generate inventory summary once at startup
  generateAvailableServersSummary(pool)
    .then(summary => {
      inventorySummary = summary;
    })
    .catch(() => {
      inventorySummary = 'Use list_available_mcp_servers to discover available servers.';
    });

  const handler = async (args: ExecuteWithWrappersInput) => {
    // ... existing handler code ...
  };

  return {
    handler,
    stopActiveBridge,
    getToolDescription: () => executeCodeWithWrappersTool.description + '\n\n' + inventorySummary,
  };
}
```

Finally, update `server.ts` to use dynamic description:
```typescript
export function createMcpExecServer(pool: ServerPool, config: McpExecServerConfig = {}) {
  // ... existing setup ...

  const { handler: executeWithWrappersHandler, stopActiveBridge, getToolDescription } =
    createExecuteWithWrappersHandler(pool, config.handlerConfig);

  // Wrap tools in a list that updates description dynamically
  const listToolsHandler = async () => ({
    tools: [
      listAvailableMcpServersTool as Tool,
      getMcpToolSchemaTool as Tool,
      {
        ...executeCodeWithWrappersTool,
        description: getToolDescription(),
      } as Tool,
    ],
  });

  // ... rest of server.ts ...
}
```

**Example Dynamic Description**:
```
Execute TypeScript/JavaScript code with auto-generated typed wrappers for specified MCP servers.
...
Available MCP servers:
- adobe_jira: Search, create, and manage Jira issues
  Tools: search_issues, create_issue
- splunk_api: Query Splunk logs and events
  Tools: search_logs, get_summary
- slack_workspace: Post messages and manage channels
  Tools: post_message, list_channels

Use exact server names from this list in the wrappers parameter.
```

**Why This Works**: LLM now:
- Sees available servers without extra round-trips
- Doesn't need to call `list_available_mcp_servers` (though it still can)
- Has context of what each server does
- Uses exact names immediately
- Reduces latency and context switching

---

## Problem 5: Return Value Shape Ambiguity & Undefined Field Access Warnings

### Current Behavior

Generated wrappers return `unknown`. The `__guardFields` Proxy (wrapper-generator.ts, lines 143-181) warns on stderr when LLM accesses undefined fields:

```
⚠ No field "issueKey" on adobe_jira.search_issues. Available: issues, total, startAt, maxResults
```

**Problem**:
- This warning is written to stderr and mixes with tool output
- No schema context in JSDoc to help LLM predict what fields exist
- LLM still guesses field names: `result.issues[0].issueKey` (doesn't exist, it's `.key`)
- The Proxy returns `undefined` but LLM continues, leading to cascading errors

### Why This Causes Errors

- Warnings get buried in output → LLM misses them
- JSDoc has no `@returns` documentation → LLM doesn't know response shape
- Field names are discovered via trial-and-error → multiple retries
- Chained property access fails silently: `result.issues[0].issueKey.name` → `undefined.name` → crash

### Proposed Fix

**File 1**: `src/codegen/wrapper-generator.ts` (lines 273-343)

**Change**: Add `@returns` documentation with response schema.

```typescript
function generateMethodDefinition(tool: ToolDefinition, serverName: string, bridgePort: number): string {
  // ... existing JSDoc code for parameters ...

  // Add return type documentation from outputSchema
  if (tool.outputSchema) {
    lines.push('   *');
    const outputDesc = tool.outputSchema.description || 'Tool result';
    lines.push(`   * @returns {Promise<${buildReturnTypeString(tool.outputSchema)}>} ${sanitizeJsDoc(outputDesc)}`);

    // If outputSchema has properties, document the fields
    if (tool.outputSchema.type === 'object' && tool.outputSchema.properties) {
      lines.push('   *');
      lines.push('   * Response fields:');
      for (const [fieldName, fieldSchema] of Object.entries(tool.outputSchema.properties)) {
        const fieldType = jsonSchemaToTs(fieldSchema as JsonSchemaProperty, false);
        const fieldDesc = (fieldSchema as JsonSchemaProperty).description || '';
        lines.push(`   *   - ${fieldName}: ${fieldType} — ${sanitizeJsDoc(fieldDesc)}`);
      }
    }

    // If outputSchema is an array, document array item shape
    if (tool.outputSchema.type === 'array' && tool.outputSchema.items) {
      lines.push('   *');
      lines.push('   * Each array item:');
      const items = tool.outputSchema.items as JsonSchemaProperty;
      if (items.properties) {
        for (const [fieldName, fieldSchema] of Object.entries(items.properties)) {
          const fieldType = jsonSchemaToTs(fieldSchema as JsonSchemaProperty, false);
          const fieldDesc = (fieldSchema as JsonSchemaProperty).description || '';
          lines.push(`   *   - ${fieldName}: ${fieldType} — ${sanitizeJsDoc(fieldDesc)}`);
        }
      }
    }
  }

  lines.push('   */');
  // ... rest of method generation ...
}

/**
 * Build TypeScript return type string from output schema
 */
function buildReturnTypeString(schema: any): string {
  if (!schema) return 'unknown';

  if (schema.type === 'array') {
    if (schema.items?.properties) {
      const props = Object.keys(schema.items.properties).join(' | ');
      return `Array<{ ${props} }>`;
    }
    return 'unknown[]';
  }

  if (schema.type === 'object' && schema.properties) {
    const propCount = Object.keys(schema.properties).length;
    return propCount <= 5 ? 'object with fields' : 'object';
  }

  return 'unknown';
}
```

**File 2**: `src/codegen/wrapper-generator.ts` (lines 143-181)

**Change**: Enhance `__guardFields` to log to console.error with prefixed context, and document in JSDoc that it warns on typos.

```typescript
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
      // Log to stderr with structured format for LLM parsing
      const fieldStr = String(prop);
      console.error('⚠ [FIELD_NOT_FOUND] Property "' + fieldStr + '" does not exist on ' + label);
      console.error('   Available fields: ' + available);
      return undefined;
    }
  });
}
`;
}
```

**File 3**: `src/tools/execute-with-wrappers.ts` (lines 329-351)

**Change**: Parse field-not-found errors and surface them prominently.

```typescript
function formatResult(result: ExecutionResult): CallToolResult {
  const lines: string[] = [];

  // Add output
  if (result.output.length > 0) {
    lines.push(...result.output);
  }

  // Parse and surface field-not-found warnings prominently
  if (result.error) {
    const fieldErrors = result.error
      .split('\n')
      .filter(line => line.includes('[FIELD_NOT_FOUND]') || line.includes('Available fields:'));

    if (fieldErrors.length > 0) {
      lines.push('');
      lines.push('[Field Access Warnings] - Check for typos in property names:');
      fieldErrors.forEach(err => lines.push(err));
    } else {
      lines.push(`[stderr]: ${result.error}`);
    }
  }

  lines.push(`[Execution completed in ${result.durationMs}ms]`);

  const hasError = !!result.error;

  return {
    content: [{ type: 'text', text: lines.join('\n') }],
    isError: hasError,
  };
}
```

**Example Enhanced JSDoc & Output**:

Generated JSDoc:
```typescript
/**
 * Search for Jira issues using JQL
 *
 * @returns {Promise<Array<{
 *   key: string,
 *   summary: string,
 *   status: string,
 *   assignee: string
 * }>>} Array of matching issues
 *
 * Response fields:
 *   - key: string — Issue identifier (e.g., "PROJ-123")
 *   - summary: string — Issue title
 *   - status: string — Current status (Open, In Progress, Done)
 *   - assignee: string — Assigned person's name
 */
```

If LLM tries `result.issues[0].issueKey`:
```
[Field Access Warnings] - Check for typos in property names:
⚠ [FIELD_NOT_FOUND] Property "issueKey" does not exist on adobe_jira.search_issues[0]
   Available fields: key, summary, status, assignee
```

**Why This Works**: LLM now:
- Sees response shape in JSDoc before writing code
- Matches field names exactly from documentation
- Gets immediate, clear feedback on typos (not buried in stderr)
- Can self-correct without retries
- Reduces cascading errors from wrong field access

---

## Summary of Changes

| File | Change | Impact |
|------|--------|--------|
| `execute-with-wrappers.ts` | **P1**: Enrich tool description with server names, workflow, fuzzy matching hints | Prevents wrong server name errors; 1 round-trip saved |
| `wrapper-generator.ts` | **P2**: Add required/optional, constraints, enums, examples to JSDoc | Eliminates invalid argument errors; LLM knows valid values |
| `wrapper-generator.ts` | **P3**: Wrap tool calls with context tracking | Errors now include which server/tool/args were called |
| `execute-with-wrappers.ts` | **P3**: Extract and surface tool context from errors | LLM can self-correct without re-running |
| `execute-with-wrappers.ts` | **P4**: Inject available servers into description at startup | No need for discovery round-trips; LLM sees current inventory |
| `wrapper-generator.ts` | **P5**: Add @returns documentation with response field schema | LLM doesn't guess field names; knows response shape |
| `wrapper-generator.ts` | **P5**: Enhance `__guardFields` warning format | Field access errors are clear and actionable |

---

## Implementation Order (for prioritization)

1. **P1 + P2**: Improve JSDoc and description (highest ROI) — prevent most argument/server name errors
2. **P3**: Add tool context to errors — enables self-correction without re-execution
3. **P5**: Response shape documentation — reduces field access trial-and-error
4. **P4**: Dynamic server summary — convenience optimization (lower impact)

---

## Backward Compatibility

All changes are **backward compatible**:
- JSDoc enhancements are additive (more comments, same code)
- Error messages are more informative but preserve original info
- Dynamic description doesn't break existing code
- Return type `unknown` unchanged; Proxy behavior only improved
- No API surface changes

---

## Validation Checklist

Once implemented, verify:
- [ ] LLM can call `execute_code_with_wrappers` with correct server names on first try
- [ ] JSDoc shows required fields, constraints, enums, and examples in IDE
- [ ] Failed tool calls include `[Context]` with server/tool/args
- [ ] LLM self-corrects errors without re-running code
- [ ] Response shape documented in JSDoc
- [ ] Field access warnings are clear and actionable
- [ ] No increase in tool description token count (stay under 1000 chars for P1 + P4)
