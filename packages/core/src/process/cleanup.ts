/**
 * Orphan process cleanup utilities for MCP server processes.
 * Shared by mcp-exec and meta-mcp-server to sweep stale instances on startup.
 */
import { execSync } from 'child_process';

/**
 * Check if a process is orphaned (parent is init/launchd, PID 1)
 */
export function isOrphanedProcess(pid: number): boolean {
  try {
    const ppid = execSync(`ps -p ${pid} -o ppid=`, { encoding: 'utf8' }).trim();
    return parseInt(ppid, 10) === 1;
  } catch {
    return false;
  }
}

/**
 * Find all PIDs matching a command pattern, excluding the current process.
 */
function getMatchingPids(pattern: string): number[] {
  try {
    const result = execSync(`pgrep -f '${pattern}'`, { encoding: 'utf8' }).trim();
    if (!result) return [];
    return result
      .split('\n')
      .filter(Boolean)
      .map((pid) => parseInt(pid, 10))
      .filter((pid) => !isNaN(pid) && pid !== process.pid);
  } catch {
    return [];
  }
}

/**
 * Kill all orphaned processes (PPID=1) whose command line matches the given pattern.
 * Call at startup to sweep stale instances left over from crashed/closed parent sessions.
 *
 * @param processPattern - Pattern passed to `pgrep -f` (e.g. 'mcp-exec', 'meta-mcp-server')
 * @returns Number of processes killed
 */
export async function cleanupOrphanedProcesses(processPattern: string): Promise<number> {
  const pids = getMatchingPids(processPattern);
  let killed = 0;

  for (const pid of pids) {
    if (isOrphanedProcess(pid)) {
      try {
        process.kill(pid, 'SIGTERM');
        killed++;
      } catch {
        // Already exited
      }
    }
  }

  if (killed > 0) {
    await new Promise((resolve) => setTimeout(resolve, 100));
  }

  return killed;
}
