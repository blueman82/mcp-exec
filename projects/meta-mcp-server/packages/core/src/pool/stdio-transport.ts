import type { ServerConfig } from '../types/index.js';

export interface SpawnConfig {
  command: string;
  args: string[];
  env?: Record<string, string>;
}

export function buildSpawnConfig(config: ServerConfig): SpawnConfig {
  const { command, args = [], env } = config;

  if (!command) {
    throw new Error('Config requires command');
  }

  // Infer spawn type from command
  if (command === 'docker') {
    // Docker: pass args directly (they include run, -i, --rm, image, etc.)
    return {
      command: 'docker',
      args: args,
      env: { ...process.env as Record<string, string>, ...env },
    };
  }

  if (command === 'uvx' || command === 'npx') {
    // uvx/npx: pass args directly
    return {
      command,
      args: args,
      env: { ...process.env as Record<string, string>, ...env },
    };
  }

  // Default: direct command execution (node, python, etc.)
  // Command is the executable path, args are the arguments
  return {
    command,
    args: args,
    env: { ...process.env as Record<string, string>, ...env },
  };
}
