/**
 * execute_code_with_wrappers MCP tool handler
 * Executes code with auto-generated typed wrappers for specified MCP servers
 */
import type { ServerPool } from '@justanothermldude/meta-mcp-core';
import { generateServerModule } from '../codegen/wrapper-generator.js';
import { SandboxExecutor, type SandboxExecutorConfig } from '../sandbox/index.js';
import { MCPBridge, type MCPBridgeConfig } from '../bridge/index.js';
import { DEFAULT_TIMEOUT_MS, type ExecutionResult } from '../types/execution.js';

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
 * MCP Tool definition for execute_code_with_wrappers
 */
export const executeCodeWithWrappersTool = {
  name: 'execute_code_with_wrappers',
  description:
    'Execute TypeScript/JavaScript code with auto-generated typed wrappers for specified MCP servers. ' +
    'Provides a typed API like github.createIssue({ title: "..." }) instead of raw mcp.callTool().',
  inputSchema: {
    type: 'object' as const,
    properties: {
      code: {
        type: 'string',
        description: 'The TypeScript/JavaScript code to execute',
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
 * Configuration for the execute_code_with_wrappers handler
 */
export interface ExecuteWithWrappersHandlerConfig {
  /** Configuration for the sandbox executor */
  sandboxConfig?: SandboxExecutorConfig;
  /** Configuration for the MCP bridge */
  bridgeConfig?: MCPBridgeConfig;
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
 * Generate the MCP helper preamble that provides the global `mcp` object
 * for calling MCP tools via the HTTP bridge
 */
function getMcpPreamble(bridgePort: number): string {
  return `
// MCP helper for calling tools via HTTP bridge
declare global {
  var mcp: {
    callTool: (server: string, tool: string, args?: Record<string, unknown>) => Promise<unknown[]>;
  };
}

globalThis.mcp = {
  callTool: async (server: string, tool: string, args: Record<string, unknown> = {}) => {
    const response = await fetch('http://localhost:${bridgePort}/call', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ server, tool, args }),
    });
    const data = await response.json() as { success: boolean; content?: unknown[]; error?: string };
    if (!data.success) {
      throw new Error(data.error || 'MCP tool call failed');
    }
    return data.content || [];
  },
};

`;
}

/**
 * Creates the execute_code_with_wrappers handler function
 *
 * @param pool - Server pool for MCP connections
 * @param config - Optional handler configuration
 * @returns Handler function for execute_code_with_wrappers tool
 */
export function createExecuteWithWrappersHandler(
  pool: ServerPool,
  config: ExecuteWithWrappersHandlerConfig = {}
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
   * Execute code with wrappers handler - generates wrappers, composes code, and executes
   */
  return async function executeWithWrappersHandler(
    args: ExecuteWithWrappersInput
  ): Promise<CallToolResult> {
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

    try {
      // Step 1: Generate typed wrappers for each requested server
      const wrapperModules: string[] = [];

      for (const serverName of wrappers) {
        try {
          // Get connection for this server
          const connection = await pool.getConnection(serverName);

          // Fetch tools from the server
          const tools = await connection.getTools();

          // Generate TypeScript module for this server
          const moduleCode = generateServerModule(tools, serverName, bridgePort);
          wrapperModules.push(moduleCode);

          // Release connection back to pool
          pool.releaseConnection(serverName);
        } catch (serverError) {
          const errorMessage = serverError instanceof Error ? serverError.message : String(serverError);
          return {
            content: [{ type: 'text', text: `Error generating wrapper for server '${serverName}': ${errorMessage}` }],
            isError: true,
          };
        }
      }

      // Step 2: Compose full code with wrappers + MCP preamble + user code
      const generatedWrappers = wrapperModules.join('\n\n');
      const mcpPreamble = getMcpPreamble(bridgePort);
      const fullCode = `${generatedWrappers}\n\n${mcpPreamble}\n${code}`;

      // Step 3: Start the MCP bridge server
      await bridge.start();

      // Step 4: Execute code in sandbox
      result = await executor.execute(fullCode, timeout_ms);

      // Step 5: Stop the bridge server
      await bridge.stop();

      // Step 6: Format and return result
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
