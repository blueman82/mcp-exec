/**
 * execute_code MCP tool handler
 * Orchestrates sandbox execution with MCP bridge for tool access
 */
import type { ServerPool } from '@justanothermldude/meta-mcp-core';
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
 * Creates the execute_code handler function
 *
 * @param pool - Server pool for MCP connections
 * @param config - Optional handler configuration
 * @returns Handler function for execute_code tool
 */
export function createExecuteCodeHandler(
  pool: ServerPool,
  config: ExecuteCodeHandlerConfig = {}
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
   * Execute code handler - orchestrates bridge, executor, and cleanup
   */
  return async function executeCodeHandler(
    args: ExecuteCodeInput
  ): Promise<CallToolResult> {
    const { code, timeout_ms = DEFAULT_TIMEOUT_MS } = args;

    // Validate input
    if (!code || typeof code !== 'string') {
      return {
        content: [{ type: 'text', text: 'Error: code parameter is required and must be a string' }],
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

    try {
      // Step 1: Start the MCP bridge server
      await bridge.start();

      // Step 2: Execute code in sandbox
      result = await executor.execute(code, timeout_ms);

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
 * Type guard for ExecuteCodeInput
 */
export function isExecuteCodeInput(args: unknown): args is ExecuteCodeInput {
  return (
    typeof args === 'object' &&
    args !== null &&
    'code' in args &&
    typeof (args as ExecuteCodeInput).code === 'string'
  );
}
