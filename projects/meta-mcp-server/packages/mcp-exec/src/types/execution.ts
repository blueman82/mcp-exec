/**
 * Input for code execution requests
 */
export interface ExecuteCodeInput {
  /** The code to execute */
  code: string;
  /** Execution timeout in milliseconds (default: 30000) */
  timeout_ms?: number;
}

/**
 * Result of code execution
 */
export interface ExecutionResult {
  /** Output lines from execution */
  output: string[];
  /** Error message if execution failed */
  error?: string;
  /** Process exit code (0 = success). Undefined if process was killed/timed out. */
  exitCode?: number;
  /** Execution duration in milliseconds */
  durationMs: number;
}

/**
 * Default timeout for code execution (30 seconds)
 */
export const DEFAULT_TIMEOUT_MS = 30000;
