import path from 'node:path';
import type { ServerConfig } from '../types/index.js';

export interface SpawnConfig {
  command: string;
  args: string[];
  env?: Record<string, string>;
  cwd?: string;
}

/** Allowed commands that can be spawned by MCP servers */
const ALLOWED_COMMANDS = new Set([
  'node',
  'python',
  'python3',
  'docker',
  'uvx',
  'npx',
  'deno',
  'bun',
]);

/** Environment variables that are safe to pass to child processes */
const SAFE_ENV_VARS = new Set([
  'PATH',
  'HOME',
  'USER',
  'SHELL',
  'LANG',
  'LC_ALL',
  'TERM',
  'NODE_ENV',
  'PYTHONPATH',
  'VIRTUAL_ENV',
]);

/**
 * Filter environment variables to only include safe ones plus server-specific overrides.
 * Prevents leaking sensitive env vars like API keys, tokens, and credentials.
 */
function filterEnvVars(serverEnv?: Record<string, string>): Record<string, string> {
  const filtered: Record<string, string> = {};

  // Copy only safe vars from process.env
  for (const key of SAFE_ENV_VARS) {
    if (process.env[key]) {
      filtered[key] = process.env[key]!;
    }
  }

  // Server-specific env vars override (these are explicitly configured)
  if (serverEnv) {
    Object.assign(filtered, serverEnv);
  }

  return filtered;
}

/**
 * Infer working directory from script paths in arguments.
 * Looks for absolute paths ending in common script extensions (.js, .ts, .py, .mjs, .cjs)
 * and returns the parent directory.
 *
 * @param args - Command arguments to search for script paths
 * @returns The inferred directory path, or undefined if no suitable path found
 */
export function inferCwd(args: string[]): string | undefined {
  // Pattern matches absolute paths ending in script extensions
  const scriptExtensions = /\.(js|ts|py|mjs|cjs)$/;

  for (const arg of args) {
    // Must be an absolute path (starts with /)
    if (arg.startsWith('/') && scriptExtensions.test(arg)) {
      return path.dirname(arg);
    }
  }

  return undefined;
}

export function buildSpawnConfig(config: ServerConfig): SpawnConfig {
  const { command, args = [], env, cwd } = config;

  if (!command) {
    throw new Error('Config requires command');
  }

  // Validate command against allowlist
  const baseCommand = command.split('/').pop() || command;
  if (!ALLOWED_COMMANDS.has(baseCommand)) {
    throw new Error(
      `Command '${baseCommand}' is not allowed. Allowed commands: ${[...ALLOWED_COMMANDS].join(', ')}`
    );
  }

  // Use filtered environment variables
  const filteredEnv = filterEnvVars(env);

  // Use explicit cwd if provided, otherwise infer from script paths
  // Docker doesn't need cwd (container handles its own filesystem)
  const resolvedCwd = command === 'docker' ? undefined : (cwd ?? inferCwd(args));

  // Infer spawn type from command
  if (command === 'docker') {
    return {
      command: 'docker',
      args: args,
      env: filteredEnv,
    };
  }

  if (command === 'uvx' || command === 'npx') {
    return {
      command,
      args: args,
      env: filteredEnv,
      cwd: resolvedCwd,
    };
  }

  // Default: direct command execution (node, python, etc.)
  return {
    command,
    args: args,
    env: filteredEnv,
    cwd: resolvedCwd,
  };
}
