/**
 * SandboxExecutor - Executes code in an OS-level sandbox using @anthropic-ai/sandbox-runtime
 * Provides isolation for running agent-generated code safely with network and filesystem restrictions
 */
import { SandboxManager, type SandboxRuntimeConfig } from '@anthropic-ai/sandbox-runtime';
import { spawn } from 'node:child_process';
import { writeFile, unlink, mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { randomUUID } from 'node:crypto';
import { transformSync } from 'esbuild';
import type { ExecutionResult } from '../types/execution.js';
import { createSandboxRuntimeConfig, type SandboxExecutorConfig } from './config.js';

/**
 * SandboxExecutor class for executing code in an isolated environment
 */
export class SandboxExecutor {
  private config: SandboxRuntimeConfig;
  private executorConfig: SandboxExecutorConfig;
  private initialized: boolean = false;
  private tempDir: string;

  constructor(options: SandboxExecutorConfig = {}) {
    this.executorConfig = options;
    this.config = createSandboxRuntimeConfig(options);
    this.tempDir = join(tmpdir(), 'mcp-exec');
  }

  /**
   * Initialize the sandbox manager with configured restrictions
   */
  async initialize(): Promise<void> {
    if (this.initialized) {
      return;
    }

    // Ensure temp directory exists
    await mkdir(this.tempDir, { recursive: true });

    // Initialize SandboxManager with our config
    await SandboxManager.initialize(
      this.config,
      undefined, // No ask callback - deny by default
      this.executorConfig.enableLogMonitor ?? false
    );

    this.initialized = true;
  }

  /**
   * Generate the MCP helper preamble that provides the global `mcp` object
   * for calling MCP tools via the HTTP bridge
   */
  private getMcpPreamble(): string {
    const bridgePort = this.executorConfig.mcpBridgePort ?? 3000;
    return `
// ============================================================================
// MCP-EXEC SANDBOX API
// ============================================================================
// Available: mcp.callTool(serverName, toolName, args)
//
// Usage:
//   const result = await mcp.callTool('github', 'list_repos', { org: 'foo' });
//   const issues = await mcp.callTool('jira', 'search_issues', { jql: 'project=X' });
//
// For long-running queries, prefer async patterns:
//   const job = await mcp.callTool('splunk-async', 'create_search_job', { query: '...' });
//   const results = await mcp.callTool('splunk-async', 'get_search_results', { job_id: job.sid });
// ============================================================================

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
   * Execute TypeScript/JavaScript code in the sandbox
   *
   * @param code - The code to execute
   * @param timeoutMs - Maximum execution time in milliseconds
   * @returns ExecutionResult with output, error, and duration
   */
  async execute(code: string, timeoutMs: number): Promise<ExecutionResult> {
    const startTime = Date.now();

    // Ensure sandbox is initialized
    if (!this.initialized) {
      await this.initialize();
    }

    // Generate unique temp file names
    const fileId = randomUUID();
    const tsFilePath = join(this.tempDir, `${fileId}.ts`);
    const jsFilePath = join(this.tempDir, `${fileId}.js`);

    // Prepend MCP helper preamble to user code
    const fullCode = this.getMcpPreamble() + code;

    try {
      // Write TypeScript code to temp file
      await writeFile(tsFilePath, fullCode, 'utf-8');

      // Transpile TypeScript to JavaScript using esbuild
      const transpiled = transformSync(fullCode, {
        loader: 'ts',
        format: 'esm',
        target: 'node20',
      });

      // Write transpiled JavaScript
      await writeFile(jsFilePath, transpiled.code, 'utf-8');

      // Create AbortController for timeout enforcement
      const abortController = new AbortController();
      const timeoutId = setTimeout(() => {
        abortController.abort();
      }, timeoutMs);

      try {
        // Get sandboxed command
        const baseCommand = `node "${jsFilePath}"`;
        const sandboxedCommand = await SandboxManager.wrapWithSandbox(
          baseCommand,
          undefined, // Use default shell
          undefined, // Use default config
          abortController.signal
        );

        // Execute the sandboxed command
        const result = await this.executeCommand(sandboxedCommand, abortController.signal);

        clearTimeout(timeoutId);

        return {
          output: result.stdout,
          error: result.stderr || undefined,
          durationMs: Date.now() - startTime,
        };
      } catch (execError) {
        clearTimeout(timeoutId);

        // Check if aborted due to timeout
        if (abortController.signal.aborted) {
          return {
            output: [],
            error: `Execution timed out after ${timeoutMs}ms`,
            durationMs: Date.now() - startTime,
          };
        }

        // Annotate error with sandbox failure information
        const errorMessage = execError instanceof Error ? execError.message : String(execError);
        const annotatedError = SandboxManager.annotateStderrWithSandboxFailures(
          `node "${jsFilePath}"`,
          errorMessage
        );

        return {
          output: [],
          error: annotatedError,
          durationMs: Date.now() - startTime,
        };
      }
    } finally {
      // Cleanup temp files
      await this.cleanup(tsFilePath, jsFilePath);
    }
  }

  /**
   * Execute a command and capture its output
   */
  private executeCommand(
    command: string,
    abortSignal: AbortSignal
  ): Promise<{ stdout: string[]; stderr: string | null }> {
    return new Promise((resolve, reject) => {
      const child = spawn('sh', ['-c', command], {
        signal: abortSignal,
      });

      const stdout: string[] = [];
      let stderr = '';

      child.stdout.on('data', (data: Buffer) => {
        const lines = data.toString().split('\n').filter(line => line.length > 0);
        stdout.push(...lines);
      });

      child.stderr.on('data', (data: Buffer) => {
        stderr += data.toString();
      });

      child.on('close', (code) => {
        if (code === 0) {
          resolve({ stdout, stderr: stderr || null });
        } else {
          resolve({ stdout, stderr: stderr || `Process exited with code ${code}` });
        }
      });

      child.on('error', (error) => {
        if (error.name === 'AbortError') {
          child.kill('SIGKILL');
          reject(new Error('Execution aborted'));
        } else {
          reject(error);
        }
      });
    });
  }

  /**
   * Cleanup temporary files
   */
  private async cleanup(...filePaths: string[]): Promise<void> {
    await Promise.all(
      filePaths.map(async (filePath) => {
        try {
          await unlink(filePath);
        } catch {
          // Ignore cleanup errors
        }
      })
    );
  }

  /**
   * Reset the sandbox manager (useful for testing)
   */
  async reset(): Promise<void> {
    await SandboxManager.reset();
    this.initialized = false;
  }

  /**
   * Check if sandbox dependencies are available
   */
  checkDependencies(): boolean {
    return SandboxManager.checkDependencies();
  }

  /**
   * Check if sandboxing is enabled on this platform
   */
  isSandboxingEnabled(): boolean {
    return SandboxManager.isSandboxingEnabled();
  }

  /**
   * Get the current sandbox configuration
   */
  getConfig(): SandboxRuntimeConfig {
    return this.config;
  }

  /**
   * Update sandbox configuration (requires re-initialization)
   */
  updateConfig(newConfig: Partial<SandboxExecutorConfig>): void {
    this.executorConfig = { ...this.executorConfig, ...newConfig };
    this.config = createSandboxRuntimeConfig(this.executorConfig);
    SandboxManager.updateConfig(this.config);
  }
}
