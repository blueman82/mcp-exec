# For mcp-exec enhancement, should we implement Options A, B, C all at once or sequentially?

Option A: Add list_available_mcp_servers and get_mcp_tool_schema tools
Option B: Auto-inject TypeScript wrappers, better error messages  
Option C: Add execute_batch and execute_with_context

Current state: Working execute_code tool with mcp.callTool() global, 62 passing tests.

# AI Counsel Deliberation Transcript

**Status:** complete
**Mode:** quick
**Rounds Completed:** 1
**Participants:** claude-sonnet-4-5-20250929@claude, gemini-2.5-pro@gemini

---

## Summary

**Consensus:** No consensus information provided

### Key Agreements

- No specific agreements identified

### Key Disagreements

- No significant disagreements

**Final Recommendation:** No recommendation provided

---

## Voting Results

### Final Tally

- **Sequentially**: 1 vote(s) ✓

**Consensus Reached:** Yes

**Winning Option:** Sequentially

### Votes by Round

#### Round 1

**gemini-2.5-pro@gemini**
- Option: Sequentially
- Confidence: 1.00
- Continue Debate: Yes
- Rationale: The options have clear, logical dependencies (B depends on A; C benefits from A & B). A sequential approach respects these dependencies, reduces risk, and allows for incremental testing and value delivery. The existence of `wrapper-generator.ts` confirms that code generation (Option B) is an intended feature, which requires schema information from Option A as a prerequisite.


---

## Tool Executions

### read_file (Round 1)

**Requested by:** gemini-2.5-pro@gemini
**Timestamp:** 2025-12-09T10:56:18.564586

**Arguments:**
```json
{'path': 'packages/mcp-exec/src/codegen/wrapper-generator.ts'}
```

**Status:** ✅ Success

**Output:**
```
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
function primitiveToTs(type:
... (truncated)
```

### read_file (Round 1)

**Requested by:** gemini-2.5-pro@gemini
**Timestamp:** 2025-12-09T10:56:18.565311

**Arguments:**
```json
{'path': 'packages/mcp-exec/src/tools/execute-code.ts'}
```

**Status:** ✅ Success

**Output:**
```
/**
 * execute_code MCP tool handler
 * Orchestrates sandbox execution with MCP bridge for tool access
 */
import type { ServerPool } from '@meta-mcp/core';
import { SandboxExecutor, type SandboxExecutorConfig } from '../sandbox/index.js';
import { MCPBridge, type MCPBridgeConfig } from '../bridge/index.js';
import { DEFAULT_TIMEOUT_MS, type ExecuteCodeInput, type ExecutionResult } from '../types/execution.js';

/**
 * MCP Tool definition for execute_code
 */
export const executeCodeTool = {
  name: 'execute_code',
  description:
    'Execute TypeScript/JavaScript code in a sandboxed environment with access to MCP tools via HTTP bridge',
  inputSchema: {
    type: 'object' as const,
    properties: {
      code: {
        type: 'string',
        description: 'The TypeScript/JavaScript code to execute',
      },
      timeout_ms: {
        type: 'number',
        description: `Maximum execution time in milliseconds (default: ${DEFAULT_TIMEOUT_MS})`,
      },
    },
    required: ['code'],
  },
};

/**
 * CallToolResult content item
 */
export interface TextContent {
  type: 'text';
  text: string;
}

/**
 * Standard MCP CallToolResult format
 */
export interface CallToolResult {
  content: TextContent[];
  isError?: boolean;
}

/**
 * Configuration for the execute_code handler
 */
export interface ExecuteCodeHandlerConfig {
  /** Configuration for the sandbox executor */
  sandboxConfig?: SandboxExecutorConfig;
  /** Configuration for the MCP bridge */
  bridgeConfig?: MCPBridgeConfig;
}

/**
 * Singleton state for the bridge - shared across all handler invocations
 */
interface BridgeState {
  bridge: MCPBridge | null;
  starting: Promise<void> | null;
  port: number;
}

const bridgeState: BridgeState = {
  bridge: null,
  starting: null,
  port: 3000,
};

/**
 * Ensure the bridge is started (singleton pattern with lazy initialization)
 * Handles EADDRINUSE by checking if bridge is already running
 */
async function ensureBridgeStarted(pool: ServerPool, config: MCPB
... (truncated)
```

---

## Decision Graph Context

Similar past deliberations found: 2 decision(s) injected (2 strong)

*Past deliberations were analyzed for similar topics and their outcomes were considered in this deliberation.*

---

## Full Debate

### Round 1

**claude-sonnet-4-5-20250929@claude**



*2025-12-09T10:55:03.534354*

---

**gemini-2.5-pro@gemini**

The previous deliberations strongly favor a sequential approach, and I concur. My analysis will focus on providing concrete evidence from the codebase to support this conclusion, reinforcing the reasoning presented in the prior discussions.

The core of the question is about managing complexity and dependencies. Let's break down the options and their relationships:

*   **Option A (Discovery):** `list_available_mcp_servers` and `get_mcp_tool_schema`. This is the foundation for any advanced interaction. To use a tool, you must first know it exists and what its interface is.
*   **Option B (Developer Experience/Safety):** Auto-injected TypeScript wrappers and better error messages. To generate a typed wrapper, you *must* have the schema of the tool you are wrapping. Therefore, Option B is directly dependent on Option A.
*   **Option C (Advanced Execution):** `execute_batch` and `execute_with_context`. This introduces more complex execution patterns. While it could technically be implemented without A or B, doing so would be building on a fragile foundation. Batch-executing a series of untyped, undiscoverable tools is significantly more error-prone and harder to debug than executing a batch of well-defined, typed tools.

A sequential implementation respects these natural dependencies, reduces risk, and allows for incremental value delivery. The ideal order would be A -> B -> C.

To confirm this, I will examine the codebase for evidence of existing work that supports this path. The file tree provided shows `packages/mcp-exec/src/codegen/wrapper-generator.ts`. This file's existence is a strong indicator that the concept of code generation for tool wrappers (Option B) has already been considered and likely architected. Implementing the schema discovery (Option A) would be the natural prerequisite to make this wrapper generator fully functional.

TOOL_REQUEST: {"name": "read_file", "arguments": {"path": "packages/mcp-exec/src/codegen/wrapper-generator.ts"}}
TOOL_REQUEST: {"name": "read_file", "arguments": {"path": "packages/mcp-exec/src/tools/execute-code.ts"}}
VOTE: {"option": "Sequentially", "confidence": 1.0, "rationale": "The options have clear, logical dependencies (B depends on A; C benefits from A & B). A sequential approach respects these dependencies, reduces risk, and allows for incremental testing and value delivery. The existence of `wrapper-generator.ts` confirms that code generation (Option B) is an intended feature, which requires schema information from Option A as a prerequisite."}

*2025-12-09T10:56:18.565430*

---
