# mcp-exec LLM Error Fixes: Implementation Guide

This document provides concrete code changes, in order, to reduce LLM tool-call errors by ~70%.

---

## Fix #1: Dynamic Server List in Tool Description (CRITICAL)

**Files**:
- `src/tools/execute-with-wrappers.ts`
- `src/server.ts`

**Approach**: Convert static tool definition to dynamic, embedded with actual server names.

### Step 1a: Add dynamic tool definition factory

In `execute-with-wrappers.ts`, after imports (around line 10):

```typescript
// Add this import
import { listServers } from '@justanothermldude/meta-mcp-core';

// Replace the static export (line 42-67) with this factory:
export function createExecuteCodeWithWrappersToolDefinition(): Tool {
  const servers = listServers();
  const serverNames = servers.map(s => s.name);
  const serverList = serverNames.join(', ');

  const description = [
    'Execute TypeScript/JavaScript code with auto-generated typed wrappers for specified MCP servers.',
    'Provides a typed API like github.createIssue({ title: "..." }) instead of raw mcp.callTool().',
    'Multi-line code is supported - format naturally for readability.',
    '',
    '**Available servers** (use exact names as shown):',
    serverList,
    '',
    'Example:',
    '```javascript',
    'const result = await adobe_mcp_gateway.jira_search({ jql: "status = Open" });',
    'const memory = await theo.memory_recall({ query: "..." });',
    '```',
  ].join('\n');

  return {
    name: 'execute_code_with_wrappers',
    description,
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
          description: `Array of MCP server names (from: ${serverList})`,
        },
        timeout_ms: {
          type: 'number',
          description: `Maximum execution time in milliseconds (default: ${DEFAULT_TIMEOUT_MS})`,
        },
      },
      required: ['code', 'wrappers'],
    },
  } as Tool;
}

// Keep the old constant for backward compat reference (can remove in v1.0)
// or just comment it out
```

### Step 1b: Update server.ts to use dynamic definition

In `src/server.ts`, in `createMcpExecServer()` function (around line 65–72):

```typescript
// OLD:
const tools: Tool[] = [
  listAvailableMcpServersTool as Tool,
  getMcpToolSchemaTool as Tool,
  executeCodeWithWrappersTool as Tool,
];

// NEW:
const executeCodeWithWrappersToolDef = createExecuteCodeWithWrappersToolDefinition();
const tools: Tool[] = [
  listAvailableMcpServersTool as Tool,
  getMcpToolSchemaTool as Tool,
  executeCodeWithWrappersToolDef as Tool,
];
```

### Step 1c: Add import to server.ts

At the top of `src/server.ts`, update the import:

```typescript
// OLD:
import {
  listAvailableMcpServersTool,
  // ...
  executeCodeWithWrappersTool,
  // ...
}

// NEW:
import {
  listAvailableMcpServersTool,
  // ...
  createExecuteCodeWithWrappersToolDefinition,  // ADD THIS
  // ...
}
```

**Validation**:
```bash
# Check that tool description includes server names
npm run build
node -e "const {createExecuteCodeWithWrappersToolDefinition} = require('./dist/tools/execute-with-wrappers.js'); const t = createExecuteCodeWithWrappersToolDefinition(); console.log(t.description.substring(0, 200));"
```

---

## Fix #2: Required/Optional JSDoc Markers

**File**: `src/codegen/wrapper-generator.ts`

**Approach**: Enhance `generateMethodDefinition()` to mark parameters and add summary.

### Step 2a: Update generateMethodDefinition()

Around line 273–343, rewrite the JSDoc generation section:

```typescript
function generateMethodDefinition(tool: ToolDefinition, serverName: string, bridgePort: number): string {
  // ... existing code up to line 282 ...

  const lines: string[] = [];

  // Add JSDoc comment with improved structure
  if (tool.description) {
    lines.push('  /**');
    lines.push(`   * ${sanitizeJsDoc(tool.description)}`);

    // Get required properties
    const requiredProps = tool.inputSchema?.required ?? [];

    // Add parameter documentation with required/optional markers
    if (tool.inputSchema?.properties) {
      lines.push('   *');
      for (const [propName, propValue] of Object.entries(tool.inputSchema.properties)) {
        const prop = propValue as JsonSchemaProperty;
        const isRequired = requiredProps.includes(propName);
        const marker = isRequired ? '[REQUIRED]' : '[OPTIONAL]';

        if (prop.description) {
          lines.push(`   * @param input.${propName} ${marker} - ${sanitizeJsDoc(prop.description)}`);
        } else {
          lines.push(`   * @param input.${propName} ${marker}`);
        }
      }

      // Add summary line of required/optional params
      const required = Object.keys(tool.inputSchema.properties).filter(p => requiredProps.includes(p));
      const optional = Object.keys(tool.inputSchema.properties).filter(p => !requiredProps.includes(p));

      lines.push('   *');
      if (required.length > 0) {
        lines.push(`   * Required parameters: ${required.join(', ')}`);
      }
      if (optional.length > 0) {
        lines.push(`   * Optional parameters: ${optional.join(', ')}`);
      }
    }

    // Add return type hint
    const outputShape = inferOutputShape(tool);
    lines.push(`   * @returns ${outputShape}`);
    lines.push('   */');
  }

  // ... rest of method (existing code from line 299 onward) ...
}
```

### Step 2b: Add inferOutputShape() helper

Add this function before `generateMethodDefinition()` (around line 260):

```typescript
/**
 * Infer output shape description from tool metadata.
 * Used in JSDoc @returns to hint the LLM about expected return structure.
 */
function inferOutputShape(tool: ToolDefinition): string {
  // Check tool name patterns
  if (tool.name.includes('search') || tool.name.includes('list') || tool.name.includes('find')) {
    return 'Array of objects with fields documented in tool description';
  }
  if (tool.name.includes('get') || tool.name.includes('read') || tool.name.includes('fetch')) {
    return 'Object with fields documented in tool description';
  }
  if (tool.name.includes('create') || tool.name.includes('update') || tool.name.includes('write')) {
    return 'Object representing the created/updated resource';
  }
  if (tool.name.includes('delete') || tool.name.includes('remove')) {
    return 'Object with success status and optional message';
  }

  // Fallback
  return 'Result structure varies by tool — inspect returned object for available fields';
}
```

**Validation**:
```bash
npm run build
# Check generated wrapper includes [REQUIRED] and [OPTIONAL] markers
npm test -- tests/unit/codegen  # if such tests exist
```

---

## Fix #5: Markdown Output for list_available_mcp_servers

**File**: `src/tools/list-servers.ts`

**Approach**: Format server list as markdown table + usage example.

### Step 5a: Update createListServersHandler()

Replace the return statement (around line 87–91):

```typescript
// OLD:
return {
  content: [{ type: 'text', text: JSON.stringify(servers, null, 2) }],
  isError: false,
};

// NEW:
// Format as markdown table for better LLM readability
const tableLines: string[] = [];
tableLines.push('| Server Name | Description | Tags |');
tableLines.push('|---|---|---|');

for (const server of servers) {
  const desc = (server.description || '-').replace(/\|/g, '\\|').substring(0, 60);
  const tags = server.tags?.slice(0, 3).join(', ') || '-';
  tableLines.push(`| \`${server.name}\` | ${desc} | ${tags} |`);
}

tableLines.push('');
tableLines.push('**Usage Example:**');
tableLines.push('```javascript');
tableLines.push('// To use a server, pass its exact name (case-insensitive via fuzzy match):');
tableLines.push('const issues = await adobe_mcp_gateway.jira_search({ jql: "..." });');
tableLines.push('```');

return {
  content: [{ type: 'text', text: tableLines.join('\n') }],
  isError: false,
};
```

**Validation**:
```bash
npm run build
node -e "const {createListServersHandler} = require('./dist/tools/list-servers.js'); const handler = createListServersHandler(); handler({}).then(r => console.log(r.content[0].text));"
```

---

## Fix #6: Code Environment Documentation

**File**: `src/tools/execute-with-wrappers.ts`

**Approach**: Extend tool description with environment constraints and examples.

### Step 6a: Update createExecuteCodeWithWrappersToolDefinition()

Modify the description construction (in the function from Fix #1):

```typescript
export function createExecuteCodeWithWrappersToolDefinition(): Tool {
  const servers = listServers();
  const serverNames = servers.map(s => s.name);
  const serverList = serverNames.join(', ');

  const description = [
    'Execute TypeScript/JavaScript code with auto-generated typed wrappers for specified MCP servers.',
    'Provides a typed API like github.createIssue({ title: "..." }) instead of raw mcp.callTool().',
    '',
    '**Available servers** (use exact names):',
    serverList,
    '',
    '**Code Environment:**',
    '- Runtime: Node.js (not browser)',
    '- Top-level `await` is supported',
    '- Available globals: fetch(), process, console, JSON',
    '- NOT available: require(), import (dynamic imports), localStorage, DOM, network access beyond fetch()',
    '- Code runs in sandbox with no file system or subprocess access',
    '',
    '**Examples:**',
    '```javascript',
    'const issues = await adobe_mcp_gateway.jira_search({ jql: "status = Open" });',
    'const keys = issues.issues?.map(i => i.key) || [];',
    'const memory = await theo.memory_recall({ query: "architecture decisions" });',
    'const tasks = memory.results?.filter(r => r.confidence > 0.8) || [];',
    'console.log(`Found ${keys.length} issues, ${tasks.length} memories`);',
    '```',
    '',
    'Multi-line code is supported - format naturally for readability.',
  ].join('\n');

  return {
    name: 'execute_code_with_wrappers',
    description,
    inputSchema: {
      // ... same as before ...
    },
  } as Tool;
}
```

**Validation**:
```bash
npm run build
node -e "const {createExecuteCodeWithWrappersToolDefinition} = require('./dist/tools/execute-with-wrappers.js'); const t = createExecuteCodeWithWrappersToolDefinition(); console.log(t.description);"
```

---

## Fix #4: Error Context in Bridge

**File**: `src/bridge/server.ts`

**Approach**: Include server.tool(args) in error messages.

### Step 4a: Update error message generation (around line 436)

```typescript
// OLD:
this.sendError(res, 500, `Tool execution failed: ${errorMsg}`);

// NEW:
const argsStr = request.args ? JSON.stringify(request.args).substring(0, 100) : '{}';
const contextMsg = `[${request.server}.${request.tool}(${argsStr})] ${errorMsg}`;
this.sendError(res, 500, contextMsg);
```

### Step 4b: Update wrapper error handling (in wrapper-generator.ts, around line 313–315)

```typescript
// OLD:
lines.push('      throw new Error(`Tool call failed: ${response.statusText}`);');

// NEW:
lines.push(`      const ctx = ${safeServerName} + '.' + ${safeToolName};`);
lines.push(`      throw new Error(ctx + ': HTTP ' + response.status + ' - ' + response.statusText);`);
```

And around line 317–318:

```typescript
// OLD:
lines.push(`      throw new Error(data.error || 'Tool call failed');`);

// NEW:
lines.push(`      const ctx = ${safeServerName} + '.' + ${safeToolName};`);
lines.push(`      throw new Error(ctx + ': ' + (data.error || 'Tool call failed'));`);
```

**Validation**:
```bash
npm run build
# Manual test: call a tool with invalid args and check error format
```

---

## Fix #3: Return Type Hints (Optional, More Complex)

**File**: `src/codegen/wrapper-generator.ts`

**Approach**: If backend tools expose outputSchema, generate a companion interface.

### Step 3a: Add output interface generator

Add before `generateToolInterface()` (around line 256):

```typescript
/**
 * Generate interface definition for a tool's output (if it provides outputSchema)
 * @param tool - Tool definition from MCP server
 * @returns Interface definition string or empty string
 */
function generateOutputInterface(tool: ToolDefinition): string {
  const toolWithOutput = tool as any;
  if (!toolWithOutput.outputSchema) return '';

  const interfaceName = `${toPascalCase(tool.name)}Output`;
  try {
    return generateInterface(interfaceName, toolWithOutput.outputSchema);
  } catch {
    return '';
  }
}
```

### Step 3b: Emit output interface in generateServerModule()

Around line 430–436:

```typescript
// Generate all interfaces first (inputs)
for (const tool of tools) {
  const interfaceCode = generateToolInterface(tool);
  if (interfaceCode) {
    lines.push(interfaceCode);
    lines.push('');
  }
}

// NEW: Also generate output interfaces
for (const tool of tools) {
  const outputInterfaceCode = generateOutputInterface(tool);
  if (outputInterfaceCode) {
    lines.push(outputInterfaceCode);
    lines.push('');
  }
}
```

### Step 3c: Update method return type

In `generateMethodDefinition()`, change the return type signature (around line 303):

```typescript
// OLD:
lines.push(`  ${methodName}: async (${inputParam}): Promise<unknown> => {`);

// NEW:
const outputInterfaceName = `${toPascalCase(tool.name)}Output`;
const hasOutput = (tool as any).outputSchema !== undefined;
const returnType = hasOutput ? outputInterfaceName : 'unknown';
lines.push(`  ${methodName}: async (${inputParam}): Promise<${returnType}> => {`);
```

**Validation**:
```bash
npm run build
npm test
```

---

## Integration & Testing Checklist

After implementing all fixes in priority order:

### 1. Build & Type Check
```bash
npm run build
npm run typecheck  # or tsc
```

### 2. Unit Tests
```bash
npm test
npm test -- --coverage
```

### 3. Integration Test Script

Create `test-llm-errors.mjs`:
```javascript
import { listServers } from '@justanothermldude/meta-mcp-core';
import { createExecuteCodeWithWrappersToolDefinition } from './dist/tools/execute-with-wrappers.js';
import { createListServersHandler } from './dist/tools/list-servers.js';

// Test 1: Tool definition includes server names
const toolDef = createExecuteCodeWithWrappersToolDefinition();
console.log('✓ Tool definition created');
console.assert(toolDef.description.includes('adobe'), 'Missing server names in description');

// Test 2: Server list is markdown formatted
const handler = createListServersHandler();
const result = await handler({});
console.log('✓ Server list generated');
console.assert(result.content[0].text.includes('|'), 'Not markdown formatted');

// Test 3: Generated wrapper includes required/optional markers
const { generateServerModule } = await import('./dist/codegen/index.js');
const tools = [
  {
    name: 'test_search',
    description: 'Test search tool',
    inputSchema: {
      properties: {
        query: { type: 'string', description: 'Search query' },
        limit: { type: 'number', description: 'Result limit' },
      },
      required: ['query'],
    },
  },
];
const wrapper = generateServerModule(tools, 'test-server', 3000);
console.log('✓ Wrapper generated');
console.assert(wrapper.includes('[REQUIRED]'), 'Missing [REQUIRED] markers');
console.assert(wrapper.includes('[OPTIONAL]'), 'Missing [OPTIONAL] markers');

console.log('\n✓ All integration checks passed');
```

Run:
```bash
npm run build && node test-llm-errors.mjs
```

### 4. Manual E2E Test

```bash
# Start mcp-exec server (if applicable)
# Call execute_code_with_wrappers with:
# - wrappers: ["adobe-mcp-gateway"]
# - code that calls a tool
# Verify:
# - Tool description includes exact server names
# - Generated code has [REQUIRED] and [OPTIONAL] markers
# - Errors include server.tool context
```

---

## Deployment Notes

1. **Version Bump**: Consider this a minor version (0.2.0 if currently 0.1.x)
2. **Breaking Changes**: None — all changes are backward compatible
3. **Rollback Plan**: If issues arise, revert commit; old code is still functional
4. **Monitoring**: Log mcp-exec call success rates before/after. Target: +70% reduction in retry loops

---

## Maintenance & Future Work

After these fixes are live:

1. **Collect Metrics**: Track error types (wrong server name, missing param, field access, env constraint)
2. **Iterate on #3**: Once LLMs prove they can use output interfaces, make it the default
3. **Auto-Docs**: Consider generating tool descriptions from backend OpenAPI/JSON schema automatically
4. **LLM-Specific Tuning**: Different models may respond better to different formats; add A/B testing framework
