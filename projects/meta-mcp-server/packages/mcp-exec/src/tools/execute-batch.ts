/**
 * execute_batch MCP tool handler
 * Executes multiple code snippets in sequence with dependency ordering
 */
import type { ServerPool } from '@meta-mcp/core';
import { SandboxExecutor, type SandboxExecutorConfig } from '../sandbox/index.js';
import { MCPBridge, type MCPBridgeConfig } from '../bridge/index.js';
import { DEFAULT_TIMEOUT_MS, type ExecutionResult } from '../types/execution.js';
import type { CallToolResult } from './execute-code.js';

/**
 * Individual code snippet with optional dependencies
 */
export interface Snippet {
  /** Unique identifier for this snippet */
  id: string;
  /** The code to execute */
  code: string;
  /** IDs of snippets that must execute before this one */
  depends_on?: string[];
}

/**
 * Input for execute_batch tool
 */
export interface ExecuteBatchInput {
  /** Array of code snippets to execute */
  snippets: Snippet[];
  /** Execution timeout in milliseconds per snippet (default: 30000) */
  timeout_ms?: number;
  /** Stop execution on first error (default: true) */
  stop_on_error?: boolean;
}

/**
 * Result for a single snippet execution
 */
export interface SnippetResult {
  /** The snippet ID */
  id: string;
  /** Output from execution */
  output: string[];
  /** Error message if execution failed */
  error?: string;
  /** Execution duration in milliseconds */
  durationMs: number;
}

/**
 * MCP Tool definition for execute_batch
 */
export const executeBatchTool = {
  name: 'execute_batch',
  description:
    'Execute multiple code snippets in sequence with dependency ordering. ' +
    'Snippets can declare dependencies on other snippets via depends_on. ' +
    'The handler performs topological sort to determine execution order.',
  inputSchema: {
    type: 'object' as const,
    properties: {
      snippets: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            id: {
              type: 'string',
              description: 'Unique identifier for this snippet',
            },
            code: {
              type: 'string',
              description: 'The TypeScript/JavaScript code to execute',
            },
            depends_on: {
              type: 'array',
              items: { type: 'string' },
              description: 'IDs of snippets that must execute before this one',
            },
          },
          required: ['id', 'code'],
        },
        description: 'Array of code snippets to execute',
      },
      timeout_ms: {
        type: 'number',
        description: `Maximum execution time in milliseconds per snippet (default: ${DEFAULT_TIMEOUT_MS})`,
      },
      stop_on_error: {
        type: 'boolean',
        description: 'Stop execution on first error (default: true)',
      },
    },
    required: ['snippets'],
  },
};

/**
 * Configuration for the execute_batch handler
 */
export interface ExecuteBatchHandlerConfig {
  /** Configuration for the sandbox executor */
  sandboxConfig?: SandboxExecutorConfig;
  /** Configuration for the MCP bridge */
  bridgeConfig?: MCPBridgeConfig;
}

/**
 * Type guard for ExecuteBatchInput
 */
export function isExecuteBatchInput(args: unknown): args is ExecuteBatchInput {
  if (typeof args !== 'object' || args === null) {
    return false;
  }

  const input = args as ExecuteBatchInput;

  if (!('snippets' in input) || !Array.isArray(input.snippets)) {
    return false;
  }

  // Validate each snippet has required id and code
  for (const snippet of input.snippets) {
    if (typeof snippet !== 'object' || snippet === null) {
      return false;
    }
    if (typeof snippet.id !== 'string' || typeof snippet.code !== 'string') {
      return false;
    }
    if (snippet.depends_on !== undefined && !Array.isArray(snippet.depends_on)) {
      return false;
    }
    if (snippet.depends_on && !snippet.depends_on.every((d: unknown) => typeof d === 'string')) {
      return false;
    }
  }

  return true;
}

/**
 * Performs topological sort using Kahn's algorithm
 * Returns sorted snippet IDs or throws if circular dependency detected
 */
function topologicalSort(snippets: Snippet[]): string[] {
  // Build adjacency list and in-degree map
  const snippetMap = new Map<string, Snippet>();
  const inDegree = new Map<string, number>();
  const adjacencyList = new Map<string, string[]>();

  // Initialize maps
  for (const snippet of snippets) {
    snippetMap.set(snippet.id, snippet);
    inDegree.set(snippet.id, 0);
    adjacencyList.set(snippet.id, []);
  }

  // Build graph edges
  for (const snippet of snippets) {
    if (snippet.depends_on) {
      for (const dep of snippet.depends_on) {
        if (!snippetMap.has(dep)) {
          throw new Error(`Snippet '${snippet.id}' depends on unknown snippet '${dep}'`);
        }
        // Edge from dep -> snippet.id (dep must come before snippet)
        adjacencyList.get(dep)!.push(snippet.id);
        inDegree.set(snippet.id, inDegree.get(snippet.id)! + 1);
      }
    }
  }

  // Kahn's algorithm: process nodes with zero in-degree
  const queue: string[] = [];
  const sorted: string[] = [];

  // Find all nodes with zero in-degree
  for (const [id, degree] of inDegree) {
    if (degree === 0) {
      queue.push(id);
    }
  }

  while (queue.length > 0) {
    const current = queue.shift()!;
    sorted.push(current);

    // Reduce in-degree for all neighbors
    for (const neighbor of adjacencyList.get(current)!) {
      const newDegree = inDegree.get(neighbor)! - 1;
      inDegree.set(neighbor, newDegree);
      if (newDegree === 0) {
        queue.push(neighbor);
      }
    }
  }

  // Check for circular dependencies
  if (sorted.length !== snippets.length) {
    const remaining = snippets.filter((s) => !sorted.includes(s.id)).map((s) => s.id);
    throw new Error(`Circular dependency detected involving snippets: ${remaining.join(', ')}`);
  }

  return sorted;
}

/**
 * Creates the execute_batch handler function
 *
 * @param pool - Server pool for MCP connections
 * @param config - Optional handler configuration
 * @returns Handler function for execute_batch tool
 */
export function createExecuteBatchHandler(
  pool: ServerPool,
  config: ExecuteBatchHandlerConfig = {}
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
   * Execute batch handler - performs topological sort and executes snippets in order
   */
  return async function executeBatchHandler(
    args: ExecuteBatchInput
  ): Promise<CallToolResult> {
    const { snippets, timeout_ms = DEFAULT_TIMEOUT_MS, stop_on_error = true } = args;

    // Validate input
    if (!snippets || !Array.isArray(snippets)) {
      return {
        content: [{ type: 'text', text: 'Error: snippets parameter is required and must be an array' }],
        isError: true,
      };
    }

    if (snippets.length === 0) {
      return {
        content: [{ type: 'text', text: 'Error: snippets array must contain at least one snippet' }],
        isError: true,
      };
    }

    // Validate each snippet
    for (const snippet of snippets) {
      if (!snippet.id || typeof snippet.id !== 'string') {
        return {
          content: [{ type: 'text', text: 'Error: each snippet must have a string id' }],
          isError: true,
        };
      }
      if (!snippet.code || typeof snippet.code !== 'string') {
        return {
          content: [{ type: 'text', text: `Error: snippet '${snippet.id}' must have a string code` }],
          isError: true,
        };
      }
    }

    // Check for duplicate IDs
    const ids = snippets.map((s) => s.id);
    const duplicates = ids.filter((id, index) => ids.indexOf(id) !== index);
    if (duplicates.length > 0) {
      return {
        content: [{ type: 'text', text: `Error: duplicate snippet IDs: ${[...new Set(duplicates)].join(', ')}` }],
        isError: true,
      };
    }

    if (timeout_ms !== undefined && (typeof timeout_ms !== 'number' || timeout_ms <= 0)) {
      return {
        content: [{ type: 'text', text: 'Error: timeout_ms must be a positive number' }],
        isError: true,
      };
    }

    // Perform topological sort
    let sortedIds: string[];
    try {
      sortedIds = topologicalSort(snippets);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      return {
        content: [{ type: 'text', text: `Error: ${errorMessage}` }],
        isError: true,
      };
    }

    // Create snippet map for quick lookup
    const snippetMap = new Map<string, Snippet>();
    for (const snippet of snippets) {
      snippetMap.set(snippet.id, snippet);
    }

    // Execute snippets in sorted order
    const results: SnippetResult[] = [];
    let hasError = false;

    try {
      // Start the MCP bridge server
      await bridge.start();

      for (const id of sortedIds) {
        const snippet = snippetMap.get(id)!;

        try {
          const result: ExecutionResult = await executor.execute(snippet.code, timeout_ms);

          const snippetResult: SnippetResult = {
            id,
            output: result.output,
            durationMs: result.durationMs,
          };

          if (result.error) {
            snippetResult.error = result.error;
            hasError = true;
          }

          results.push(snippetResult);

          // Stop on error if configured
          if (result.error && stop_on_error) {
            break;
          }
        } catch (execError) {
          const errorMessage = execError instanceof Error ? execError.message : String(execError);
          results.push({
            id,
            output: [],
            error: errorMessage,
            durationMs: 0,
          });
          hasError = true;

          if (stop_on_error) {
            break;
          }
        }
      }

      // Stop the bridge server
      await bridge.stop();

      // Format and return results
      return formatBatchResult(results, hasError);
    } catch (error) {
      // Ensure bridge is stopped on error
      try {
        if (bridge.isRunning()) {
          await bridge.stop();
        }
      } catch {
        // Ignore cleanup errors
      }

      const errorMessage = error instanceof Error ? error.message : String(error);
      return formatBatchErrorResult(errorMessage, results);
    }
  };
}

/**
 * Format batch execution results
 */
function formatBatchResult(results: SnippetResult[], hasError: boolean): CallToolResult {
  const lines: string[] = [];

  for (const result of results) {
    lines.push(`=== Snippet '${result.id}' ===`);

    if (result.output.length > 0) {
      lines.push(...result.output);
    }

    if (result.error) {
      lines.push(`[stderr]: ${result.error}`);
    }

    lines.push(`[Completed in ${result.durationMs}ms]`);
    lines.push('');
  }

  const totalDuration = results.reduce((sum, r) => sum + r.durationMs, 0);
  lines.push(`[Batch completed: ${results.length} snippet(s) in ${totalDuration}ms]`);

  return {
    content: [{ type: 'text', text: lines.join('\n') }],
    isError: hasError,
  };
}

/**
 * Format batch error result with partial results
 */
function formatBatchErrorResult(errorMessage: string, partialResults: SnippetResult[]): CallToolResult {
  const lines: string[] = [];

  if (partialResults.length > 0) {
    lines.push('[Partial results]:');
    for (const result of partialResults) {
      lines.push(`=== Snippet '${result.id}' ===`);
      if (result.output.length > 0) {
        lines.push(...result.output);
      }
      if (result.error) {
        lines.push(`[stderr]: ${result.error}`);
      }
      lines.push(`[Completed in ${result.durationMs}ms]`);
      lines.push('');
    }
  }

  lines.push(`Error: ${errorMessage}`);

  return {
    content: [{ type: 'text', text: lines.join('\n') }],
    isError: true,
  };
}
