/**
 * execute_with_context MCP tool handler
 * Executes code with pre-injected context variables
 */
import type { ServerPool } from '@justanothermldude/meta-mcp-core';
import { SandboxExecutor, type SandboxExecutorConfig } from '../sandbox/index.js';
import { MCPBridge, type MCPBridgeConfig } from '../bridge/index.js';
import { DEFAULT_TIMEOUT_MS, type ExecutionResult } from '../types/execution.js';

/**
 * Input for execute_with_context requests
 */
export interface ExecuteWithContextInput {
  /** The code to execute */
  code: string;
  /** Context object to inject into code execution */
  context?: Record<string, unknown>;
  /** Execution timeout in milliseconds (default: 30000) */
  timeout_ms?: number;
}

/**
 * MCP Tool definition for execute_with_context
 */
export const executeWithContextTool = {
  name: 'execute_with_context',
  description:
    'Execute TypeScript/JavaScript code with pre-injected context variables. The context object is available as a global `context` variable in the executed code.',
  inputSchema: {
    type: 'object' as const,
    properties: {
      code: {
        type: 'string',
        description: 'The TypeScript/JavaScript code to execute',
      },
      context: {
        type: 'object',
        description: 'Context object to inject into code execution (available as global `context` variable)',
        additionalProperties: true,
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
 * Configuration for the execute_with_context handler
 */
export interface ExecuteWithContextHandlerConfig {
  /** Configuration for the sandbox executor */
  sandboxConfig?: SandboxExecutorConfig;
  /** Configuration for the MCP bridge */
  bridgeConfig?: MCPBridgeConfig;
}

/**
 * Serialize context to JSON with error handling for circular references
 * @param context - The context object to serialize
 * @returns Serialized JSON string
 * @throws Error if context contains non-serializable values
 */
function serializeContext(context: Record<string, unknown>): string {
  try {
    return JSON.stringify(context);
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('circular')) {
      throw new Error('Context contains circular references and cannot be serialized');
    }
    throw new Error(`Failed to serialize context: ${error instanceof Error ? error.message : String(error)}`);
  }
}

/**
 * Generate context injection code that creates a global `context` variable.
 * Uses Base64 encoding to prevent injection attacks via malicious context values.
 * @param context - The context object to inject
 * @returns Code string that declares the context variable
 */
function generateContextInjection(context: Record<string, unknown>): string {
  const serializedContext = serializeContext(context);
  const base64Context = Buffer.from(serializedContext, 'utf-8').toString('base64');

  return `// Context injection (Base64 encoded for security)
declare global {
  var context: Record<string, unknown>;
}
globalThis.context = JSON.parse(Buffer.from('${base64Context}', 'base64').toString('utf-8'));

`;
}

/**
 * Creates the execute_with_context handler function
 *
 * @param pool - Server pool for MCP connections
 * @param config - Optional handler configuration
 * @returns Handler function for execute_with_context tool
 */
export function createExecuteWithContextHandler(
  pool: ServerPool,
  config: ExecuteWithContextHandlerConfig = {}
) {
  // Ensure bridge port matches sandbox network config
  const bridgePort = config.bridgeConfig?.port ?? 3000;
  const sandboxConfig: SandboxExecutorConfig = {
    ...config.sandboxConfig,
    mcpBridgePort: bridgePort,
  };

  const executor = new SandboxExecutor(sandboxConfig);
  const bridge = new MCPBridge(pool, {
    ...config.bridgeConfig,
    port: bridgePort,
  });

  /**
   * Execute with context handler - orchestrates context injection, bridge, executor, and cleanup
   */
  return async function executeWithContextHandler(
    args: ExecuteWithContextInput
  ): Promise<CallToolResult> {
    const { code, context = {}, timeout_ms = DEFAULT_TIMEOUT_MS } = args;

    // Validate input
    if (!code || typeof code !== 'string') {
      return {
        content: [{ type: 'text', text: 'Error: code parameter is required and must be a string' }],
        isError: true,
      };
    }

    if (context !== undefined && (typeof context !== 'object' || context === null || Array.isArray(context))) {
      return {
        content: [{ type: 'text', text: 'Error: context must be an object' }],
        isError: true,
      };
    }

    if (timeout_ms !== undefined && (typeof timeout_ms !== 'number' || timeout_ms <= 0)) {
      return {
        content: [{ type: 'text', text: 'Error: timeout_ms must be a positive number' }],
        isError: true,
      };
    }

    // Generate context injection code
    let contextInjection = '';
    try {
      if (Object.keys(context).length > 0) {
        contextInjection = generateContextInjection(context);
      } else {
        // Provide empty context object if no context provided
        contextInjection = `// Empty context
declare global {
  var context: Record<string, unknown>;
}
globalThis.context = {};

`;
      }
    } catch (error) {
      return {
        content: [{ type: 'text', text: `Error: ${error instanceof Error ? error.message : String(error)}` }],
        isError: true,
      };
    }

    // Compose final code: context injection prepended to user code
    // The executor will add MCP preamble after context injection
    const composedCode = contextInjection + code;

    let result: ExecutionResult | null = null;

    try {
      // Step 1: Start the MCP bridge server
      await bridge.start();

      // Step 2: Execute code in sandbox (executor adds MCP preamble)
      result = await executor.execute(composedCode, timeout_ms);

      // Step 3: Stop the bridge server
      await bridge.stop();

      // Step 4: Format and return result
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

      // Return error with any partial output
      const errorMessage = error instanceof Error ? error.message : String(error);
      return formatErrorResult(errorMessage, result);
    }
  };
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

  // Add error if present (non-fatal stderr)
  if (result.error) {
    lines.push(`[stderr]: ${result.error}`);
  }

  // Add execution time
  lines.push(`[Execution completed in ${result.durationMs}ms]`);

  const hasError = !!result.error;

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

/**
 * Type guard for ExecuteWithContextInput
 */
export function isExecuteWithContextInput(args: unknown): args is ExecuteWithContextInput {
  if (typeof args !== 'object' || args === null) {
    return false;
  }

  const input = args as Record<string, unknown>;

  // code must be a string
  if (typeof input.code !== 'string') {
    return false;
  }

  // context, if provided, must be an object (not array, not null)
  if (input.context !== undefined) {
    if (typeof input.context !== 'object' || input.context === null || Array.isArray(input.context)) {
      return false;
    }
  }

  return true;
}
