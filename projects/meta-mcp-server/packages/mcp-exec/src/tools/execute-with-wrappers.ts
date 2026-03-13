/**
 * execute_code_with_wrappers MCP tool handler
 * Executes code with auto-generated typed wrappers for specified MCP servers
 */
import type { ServerPool, MCPConnection } from '@justanothermldude/meta-mcp-core';
import { listServers } from '@justanothermldude/meta-mcp-core';
import { generateServerModule, generateMcpDictionaryFromMap, generateFieldGuard } from '../codegen/index.js';
import { SandboxExecutor, type SandboxExecutorConfig } from '../sandbox/index.js';
import { MCPBridge, type MCPBridgeConfig } from '../bridge/index.js';
import { DEFAULT_TIMEOUT_MS, type ExecutionResult } from '../types/execution.js';
import { updateCatalogForServer, buildCatalogString } from './tool-catalog.js';

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
 * Input for execute_code_with_wrappers tool
 */
export interface ExecuteWithWrappersInput {
  /** The code to execute */
  code: string;
  /** Array of server names to generate wrappers for */
  wrappers: string[];
  /** Execution timeout in milliseconds (default: 30000) */
  timeout_ms?: number;
}

/**
 * MCP Tool definition for execute_code_with_wrappers (static fallback)
 */
export const executeCodeWithWrappersTool = {
  name: 'execute_code_with_wrappers',
  description:
    'Execute TypeScript/JavaScript code with auto-generated typed wrappers for specified MCP servers. ' +
    'Provides a typed API like github.createIssue({ title: "..." }) instead of raw mcp.callTool(). ' +
    'Multi-line code is supported - format naturally for readability.',
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
        description: 'Array of MCP server names to generate typed wrappers for',
      },
      timeout_ms: {
        type: 'number',
        description: `Maximum execution time in milliseconds (default: ${DEFAULT_TIMEOUT_MS})`,
      },
    },
    required: ['code', 'wrappers'],
  },
};

/**
 * Build dynamic server list string for tool description
 */
function buildServerListString(): string {
  try {
    const servers = listServers();
    if (!servers || servers.length === 0) {
      return '';
    }

    // Build bullet list of first few servers with descriptions
    const serverLines = servers.slice(0, 7).map((s) => {
      const desc = s.description || 'No description';
      return `  • ${s.name} — ${desc}`;
    });

    const moreCount = Math.max(0, servers.length - 7);
    const moreStr = moreCount > 0 ? `\n  [+${moreCount} more]` : '';

    return `
Available MCP servers (use exact names in wrappers array):
${serverLines.join('\n')}${moreStr}

Use list_available_mcp_servers to discover tools on each server before calling execute_code_with_wrappers.`;
  } catch {
    // Fallback if listServers() fails
    return '';
  }
}

/**
 * Create the execute_code_with_wrappers tool definition with dynamic server list embedded
 */
export function createExecuteCodeWithWrappersToolDefinition() {
  const baseDescription =
    'Execute TypeScript/JavaScript code with auto-generated typed wrappers for specified MCP servers. ' +
    'Provides a typed API like github.createIssue({ title: "..." }) instead of raw mcp.callTool(). ' +
    'Multi-line code is supported - format naturally for readability.';

  const serverList = buildServerListString();

  const catalogNote = buildCatalogString();

  const environmentNote =
    '\n\nExecution environment: Node.js (not browser). Top-level await is supported.\n' +
    '- Server namespaces are pre-injected: use serverName.toolName({params}) directly\n' +
    '- mcp is the server dictionary: mcp["server-name"].toolName({params}) for dynamic lookup\n' +
    '- DO NOT use mcp__server__tool() syntax — that is the MCP protocol layer, not the sandbox API\n' +
    '- DO NOT guess tool or parameter names — use ONLY exact names from the API reference below\n' +
    '- Available globals: fetch, console, process, Buffer, setTimeout, clearTimeout\n' +
    '- import/export NOT supported — modules are pre-injected as namespace variables\n' +
    '- DO NOT use require(), __dirname, __filename, or browser APIs' +
    catalogNote;

  return {
    name: 'execute_code_with_wrappers',
    description: baseDescription + serverList + environmentNote,
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
          description: 'Array of MCP server names to generate typed wrappers for',
        },
        timeout_ms: {
          type: 'number',
          description: `Maximum execution time in milliseconds (default: ${DEFAULT_TIMEOUT_MS})`,
        },
      },
      required: ['code', 'wrappers'],
    },
  };
}

/**
 * Configuration for the execute_code_with_wrappers handler
 */
export interface ExecuteWithWrappersHandlerConfig {
  /** Configuration for the sandbox executor */
  sandboxConfig?: SandboxExecutorConfig;
  /** Configuration for the MCP bridge */
  bridgeConfig?: MCPBridgeConfig;
}

/**
 * Sanitize identifier: replace non-alphanumeric chars with underscore,
 * ensure starts with letter. Matches logic in wrapper-generator.ts.
 */
function sanitizeIdentifier(name: string): string {
  let s = name.replace(/[^a-zA-Z0-9_]/g, '_');
  if (/^[0-9]/.test(s)) {
    s = '_' + s;
  }
  return s;
}

/**
 * Pre-compute collision-aware variable names for all servers.
 * Detects when multiple server names sanitize to the same identifier
 * and appends numeric suffixes to resolve collisions.
 *
 * @param names - Array of original server names
 * @returns Map from original name to unique variable name
 */
function buildUniqueNameMap(names: string[]): Map<string, string> {
  const sanitizedToOriginals = new Map<string, string[]>();

  // First pass: group originals by their sanitized form
  for (const name of names) {
    const s = sanitizeIdentifier(name);
    if (!sanitizedToOriginals.has(s)) {
      sanitizedToOriginals.set(s, []);
    }
    sanitizedToOriginals.get(s)!.push(name);
  }

  // Second pass: assign unique names, adding suffix on collision
  const nameMap = new Map<string, string>();
  for (const name of names) {
    const s = sanitizeIdentifier(name);
    const group = sanitizedToOriginals.get(s)!;
    if (group.length === 1) {
      // No collision - use sanitized name
      nameMap.set(name, s);
    } else {
      // Collision - append index within group
      const idx = group.indexOf(name);
      nameMap.set(name, `${s}_${idx}`);
    }
  }

  return nameMap;
}

/**
 * Type guard for ExecuteWithWrappersInput
 */
export function isExecuteWithWrappersInput(args: unknown): args is ExecuteWithWrappersInput {
  return (
    typeof args === 'object' &&
    args !== null &&
    'code' in args &&
    typeof (args as ExecuteWithWrappersInput).code === 'string' &&
    'wrappers' in args &&
    Array.isArray((args as ExecuteWithWrappersInput).wrappers) &&
    (args as ExecuteWithWrappersInput).wrappers.every((w) => typeof w === 'string')
  );
}

/**
 * REPL-like return value capture: if the last expression of userCode is a bare
 * expression statement (not a declaration or control-flow keyword), transform it
 * to an async IIFE that returns that expression and prints the result.
 *
 * Handles common cases:
 *   `42`                 → prints 42
 *   `someVar`            → prints value of someVar
 *   `await mcp.callTool(...)` → prints result
 *
 * Skips if last statement starts with const/let/var/function/class/return/throw/if/for/…
 */
function wrapUserCodeForReturnCapture(code: string): string {
  const trimmed = code.trimEnd();
  if (!trimmed) return code;

  // If the code ends with } it closes a block statement — nothing to capture.
  // This single check handles try/catch, if/else, loops, functions, etc.
  if (trimmed.replace(/;+$/, '').endsWith('}')) return code;

  // Find last non-empty, non-comment line
  const lines = trimmed.split('\n');
  let lastIdx = lines.length - 1;
  while (lastIdx >= 0) {
    const t = lines[lastIdx].trim();
    if (t && !t.startsWith('//') && !t.startsWith('*') && !t.startsWith('/*')) break;
    lastIdx--;
  }
  if (lastIdx < 0) return code;

  const lastTrimmed = lines[lastIdx].trim();

  // Skip declaration and control-flow keywords
  if (/^(const|let|var|function\s|class\s|import\s|export\s|return\b|throw\b|if\s*\(|else\b|for\s*[\({]|while\s*\(|do\s*\{|switch\s*\(|try\s*\{|catch\s*\(|finally\s*\{|break\b|continue\b)/.test(lastTrimmed)) {
    return code;
  }

  // Skip multi-line continuations: closing brackets, method chains, index access
  // These indicate the last line is a continuation of a prior expression, not standalone
  if (lines.length > 1 && /^[}\])\.\[?]/.test(lastTrimmed)) return code;

  const expr = lastTrimmed.replace(/;$/, '');
  const indent = lines[lastIdx].match(/^(\s*)/)?.[1] ?? '';

  // Use collision-resistant variable name to avoid shadowing user code
  lines[lastIdx] = `${indent}const __mcp_exec_capture__ = await Promise.resolve(${expr});
${indent}if (__mcp_exec_capture__ !== undefined) {
${indent}  const __mcp_exec_out__ = typeof __mcp_exec_capture__ === 'string' ? __mcp_exec_capture__ : JSON.stringify(__mcp_exec_capture__, null, 2);
${indent}  process.stdout.write(__mcp_exec_out__ + '\\n');
${indent}}`;

  return lines.join('\n');
}

/**
 * Creates the execute_code_with_wrappers handler function
 *
 * @param pool - Server pool for MCP connections
 * @param config - Optional handler configuration
 * @returns Object with handler function and stopActiveBridge for graceful shutdown
 */
export function createExecuteWithWrappersHandler(
  pool: ServerPool,
  config: ExecuteWithWrappersHandlerConfig = {}
) {
  // Preferred port (actual port determined at runtime via dynamic allocation)
  const preferredPort = config.bridgeConfig?.port ?? 3000;

  // Track the bridge that is currently running (at most one per handler instance)
  let activeBridge: MCPBridge | null = null;

  /**
   * Stop the currently active bridge, if any. Called during graceful shutdown.
   */
  async function stopActiveBridge(): Promise<void> {
    if (activeBridge?.isRunning()) {
      try {
        await activeBridge.stop();
      } catch {
        // Ignore — process is shutting down anyway
      }
    }
    activeBridge = null;
  }

  /**
   * Execute code with wrappers handler - generates wrappers, composes code, and executes
   */
  async function executeWithWrappersHandler(
    args: ExecuteWithWrappersInput
  ): Promise<CallToolResult> {
    const TOOLS_FETCH_TIMEOUT_MS = 15000;
    const { code, wrappers, timeout_ms = DEFAULT_TIMEOUT_MS } = args;

    // Validate input
    if (!code || typeof code !== 'string') {
      return {
        content: [{ type: 'text', text: 'Error: code parameter is required and must be a string' }],
        isError: true,
      };
    }

    if (!wrappers || !Array.isArray(wrappers)) {
      return {
        content: [{ type: 'text', text: 'Error: wrappers parameter is required and must be an array of strings' }],
        isError: true,
      };
    }

    if (wrappers.length === 0) {
      return {
        content: [{ type: 'text', text: 'Error: wrappers array must contain at least one server name' }],
        isError: true,
      };
    }

    if (timeout_ms !== undefined && (typeof timeout_ms !== 'number' || timeout_ms <= 0)) {
      return {
        content: [{ type: 'text', text: 'Error: timeout_ms must be a positive number' }],
        isError: true,
      };
    }

    let result: ExecutionResult | null = null;

    // Create bridge per execution (allows dynamic port allocation)
    const bridge = new MCPBridge(pool, {
      ...config.bridgeConfig,
      port: preferredPort,
    });
    activeBridge = bridge;

    try {
      // Step 1: Start the MCP bridge server (gets dynamic port)
      await bridge.start();
      const actualPort = bridge.getPort();

      // Step 2: Pre-compute collision-aware variable names for all servers
      const uniqueNameMap = buildUniqueNameMap(wrappers);

      // Step 3: Generate typed wrappers for each requested server using actual port
      const wrapperModules: string[] = [];

      for (const serverName of wrappers) {
        let connection: MCPConnection | undefined;
        try {
          // Get connection for this server
          connection = await pool.getConnection(serverName);
          const conn = connection;

          // Fetch tools from the server with proper timeout cleanup
          const tools = await new Promise<Awaited<ReturnType<MCPConnection['getTools']>>>((resolve, reject) => {
            const timeoutHandle = setTimeout(() => {
              reject(
                new Error(
                  `Timed out fetching tools from server '${serverName}' after ${TOOLS_FETCH_TIMEOUT_MS}ms`
                )
              );
            }, TOOLS_FETCH_TIMEOUT_MS);

            conn.getTools().then(
              (result) => { clearTimeout(timeoutHandle); resolve(result); },
              (err: unknown) => { clearTimeout(timeoutHandle); reject(err); }
            );
          });

          // Cache tools to disk for catalog embedding in tool description
          updateCatalogForServer(serverName, tools);

          // Get the collision-aware variable name for this server
          const uniqueName = uniqueNameMap.get(serverName) ?? sanitizeIdentifier(serverName);

          // Generate TypeScript module for this server with actual port and unique variable name
          const moduleCode = generateServerModule(tools, serverName, actualPort, uniqueName);
          wrapperModules.push(moduleCode);

          // Release connection back to pool
          pool.releaseConnection(serverName);
        } catch (serverError) {
          const errorMessage = serverError instanceof Error ? serverError.message : String(serverError);
          // Only release if connection was successfully obtained; getConnection may have thrown
          // before assigning, in which case there is nothing in the pool to release.
          if (connection !== undefined) {
            pool.releaseConnection(serverName);
          }
          await bridge.stop();
          activeBridge = null;
          return {
            content: [{ type: 'text', text: `Error generating wrapper for server '${serverName}': ${errorMessage}` }],
            isError: true,
          };
        }
      }

      // Step 4: Compose full code with wrappers + MCP dictionary + user code
      // Note: executor.ts prepends its own globalThis.mcp callTool preamble using actualPort
      const generatedWrappers = generateFieldGuard() + '\n\n' + wrapperModules.join('\n\n');
      const mcpDictionary = generateMcpDictionaryFromMap(wrappers, uniqueNameMap);
      const instrumentedCode = wrapUserCodeForReturnCapture(code);
      const fullCode = `${generatedWrappers}\n\n${mcpDictionary}\n\n${instrumentedCode}`;

      // Step 5: Create executor with actual port for sandbox network config
      const sandboxConfig: SandboxExecutorConfig = {
        ...config.sandboxConfig,
        mcpBridgePort: actualPort,
      };
      const executor = new SandboxExecutor(sandboxConfig);

      // Step 6: Execute code in sandbox
      result = await executor.execute(fullCode, timeout_ms);

      // Step 7: Stop the bridge server
      await bridge.stop();
      activeBridge = null;

      // Step 8: Format and return result
      return formatResult(result);
    } catch (error) {
      // Ensure bridge is stopped on error
      try {
        if (bridge.isRunning()) {
          await bridge.stop();
        }
      } catch {
        // Ignore cleanup errors
      }
      activeBridge = null;

      // Return error with any partial output
      const errorMessage = error instanceof Error ? error.message : String(error);
      return formatErrorResult(errorMessage, result);
    }
  }

  return { handler: executeWithWrappersHandler, stopActiveBridge };
}

/**
 * Format a successful execution result
 */
function formatResult(result: ExecutionResult): CallToolResult {
  const lines: string[] = [];

  // Add output
  if (result.output.length > 0) {
    lines.push(...result.output);
  }

  // Add stderr if present (may be warnings even on success)
  if (result.error) {
    lines.push(`[stderr]: ${result.error}`);
  }

  // Add execution time
  lines.push(`[Execution completed in ${result.durationMs}ms]`);

  // Use exit code for error determination — stderr alone (e.g. deprecation warnings) is not an error
  const hasError = result.exitCode !== undefined ? result.exitCode !== 0 : !!result.error;

  return {
    content: [{ type: 'text', text: lines.join('\n') }],
    isError: hasError,
  };
}

/**
 * Format an error result with optional partial output
 */
function formatErrorResult(errorMessage: string, partialResult: ExecutionResult | null): CallToolResult {
  const lines: string[] = [];

  // Add partial output if available
  if (partialResult?.output.length) {
    lines.push('[Partial output]:');
    lines.push(...partialResult.output);
    lines.push('');
  }

  // Add error message
  lines.push(`Error: ${errorMessage}`);

  // Add duration if available
  if (partialResult?.durationMs) {
    lines.push(`[Execution failed after ${partialResult.durationMs}ms]`);
  }

  return {
    content: [{ type: 'text', text: lines.join('\n') }],
    isError: true,
  };
}
