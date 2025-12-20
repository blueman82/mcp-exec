/**
 * Port cleanup utilities for handling stale mcp-exec processes
 */
import { execSync } from 'child_process';

/**
 * Check if a process is an mcp-exec process by examining its command line
 */
function isMcpExecProcess(pid: number): boolean {
  try {
    const cmdline = execSync(`ps -p ${pid} -o command=`, { encoding: 'utf8' }).trim();
    return cmdline.includes('mcp-exec') || cmdline.includes('meta-mcp');
  } catch {
    return false;
  }
}

/**
 * Get PIDs of processes listening on a specific port
 */
function getProcessesOnPort(port: number): number[] {
  try {
    const result = execSync(`lsof -ti :${port}`, { encoding: 'utf8' }).trim();
    if (!result) return [];
    return result
      .split('\n')
      .filter(Boolean)
      .map((pid) => parseInt(pid, 10))
      .filter((pid) => !isNaN(pid));
  } catch {
    return [];
  }
}

/**
 * Attempt to clean up stale mcp-exec processes on a specific port
 * Only kills processes that match mcp-exec/meta-mcp in their command line
 * 
 * @param port - Port number to check for stale processes
 * @returns true if any processes were killed, false otherwise
 */
export async function cleanupStaleProcess(port: number): Promise<boolean> {
  const pids = getProcessesOnPort(port);
  if (pids.length === 0) return false;

  let killedAny = false;

  for (const pid of pids) {
    if (isMcpExecProcess(pid)) {
      try {
        process.kill(pid, 'SIGTERM');
        killedAny = true;
      } catch {
        // Process may have already exited
      }
    }
  }

  if (killedAny) {
    // Give processes time to terminate
    await new Promise((resolve) => setTimeout(resolve, 100));
  }

  return killedAny;
}

/**
 * Check if a port is currently in use
 * 
 * @param port - Port number to check
 * @returns true if port is in use, false otherwise
 */
export function isPortInUse(port: number): boolean {
  return getProcessesOnPort(port).length > 0;
}
