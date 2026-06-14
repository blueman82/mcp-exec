/**
 * SandboxExecutor - Executes code in an OS-level sandbox using @anthropic-ai/sandbox-runtime
 * Provides isolation for running agent-generated code safely with network and filesystem restrictions.
 *
 * Transport: MCP tool calls use inherited file descriptors (fd 3 + fd 4), not TCP.
 * This allows the sandboxed process to call tools even on Linux where bwrap
 * isolates the network namespace (making loopback TCP unreachable).
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
import { attachFdTransport, buildFdPreamble, type DispatchFn } from './fd-transport.js';

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
   * Execute TypeScript/JavaScript code in the sandbox.
   *
   * @param code - The code to execute (already includes typed wrapper preamble from caller)
   * @param timeoutMs - Maximum execution time in milliseconds
   * @param dispatch - Optional tool dispatch function for MCP tool calls via fd transport.
   *                   When provided, the sandbox can call MCP tools through inherited fds.
   * @returns ExecutionResult with output, error, and duration
   */
  async execute(code: string, timeoutMs: number, dispatch?: DispatchFn): Promise<ExecutionResult> {
    const startTime = Date.now();

    // Ensure sandbox is initialized
    if (!this.initialized) {
      await this.initialize();
    }

    // Generate unique temp file names
    const fileId = randomUUID();
    const tsFilePath = join(this.tempDir, `${fileId}.ts`);
    const jsFilePath = join(this.tempDir, `${fileId}.mjs`);

    // Wrap the user code in an async IIFE that calls process.exit(0) on success
    // and process.exit(1) on error.
    //
    // When dispatch is provided, prepend the fd-transport preamble.  The preamble
    // opens net.Socket handles on fd 3 and fd 4 — which only exist when the child is
    // spawned with a 5-element stdio array.  Without dispatch the spawn uses 3-element
    // stdio (no fd 3/4), so the preamble must be omitted to avoid ENOTTY.
    const wrappedCode = `(async () => {\n${code}\n})().then(() => process.exit(0), (e) => { process.stderr.write(e.stack || e.message); process.exit(1); });`;
    const fullCode = dispatch ? buildFdPreamble() + wrappedCode : wrappedCode;

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
        const result = await this.executeCommand(sandboxedCommand, abortController.signal, dispatch);

        clearTimeout(timeoutId);

        return {
          output: result.stdout,
          error: result.stderr || undefined,
          exitCode: result.exitCode,
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
   * Spawn the sandboxed command and capture output.
   * When dispatch is provided, attaches the fd RPC transport (fd 3 + fd 4)
   * so the sandbox can call MCP tools without using the network.
   */
  private executeCommand(
    command: string,
    abortSignal: AbortSignal,
    dispatch?: DispatchFn
  ): Promise<{ stdout: string[]; stderr: string | null; exitCode: number }> {
    return new Promise((resolve, reject) => {
      // Spawn with fd 3 + fd 4 for the RPC channel when dispatch is available.
      // 'pipe' creates a pair of unidirectional kernel pipes; from the host:
      //   stdio[3] = readable (child writes requests)
      //   stdio[4] = writable (host writes responses)
      // Cast to 'pipe' array to satisfy Node's StdioOptions overloads.
      const stdioOption = (
        dispatch
          ? ['pipe', 'pipe', 'pipe', 'pipe', 'pipe']
          : ['pipe', 'pipe', 'pipe']
      ) as Array<'pipe'>;

      const child = spawn('sh', ['-c', command], {
        signal: abortSignal,
        stdio: stdioOption,
      });

      // Attach fd transport BEFORE reading any output, so no frames are dropped
      if (dispatch) {
        attachFdTransport(child, dispatch);
      }

      const stdout: string[] = [];
      let stderr = '';

      child.stdout!.on('data', (data: Buffer) => {
        const lines = data.toString().split('\n').filter(line => line.length > 0);
        stdout.push(...lines);
      });

      child.stderr!.on('data', (data: Buffer) => {
        stderr += data.toString();
      });

      child.on('close', (code) => {
        if (code === 0) {
          resolve({ stdout, stderr: stderr || null, exitCode: 0 });
        } else {
          resolve({ stdout, stderr: stderr || `Process exited with code ${code}`, exitCode: code ?? 1 });
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
