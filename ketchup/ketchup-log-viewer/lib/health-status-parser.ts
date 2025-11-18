/**
 * Health Status Parser
 * Parses Docker container status to determine health state
 */

export type HealthStatus = 'healthy' | 'unhealthy' | 'starting' | 'restarting' | 'exited' | 'running';

export interface HealthInfo {
  status: HealthStatus;
  icon: string;
  color: string;
  label: string;
}

/**
 * Parse container status string and determine health
 * Examples:
 * - "Up 2 hours (healthy)" → healthy
 * - "Up 5 minutes (unhealthy)" → unhealthy
 * - "Up 1 hour (health: starting)" → starting
 * - "Restarting (1) 2 minutes ago" → restarting
 * - "Exited (0) 5 hours ago" → exited
 * - "Up 3 days" → running (no explicit health check)
 */
export function parseHealthStatus(status: string): HealthStatus {
  const lowerStatus = status.toLowerCase();

  // Check for explicit health states
  if (lowerStatus.includes('(healthy)')) {
    return 'healthy';
  }
  if (lowerStatus.includes('(unhealthy)')) {
    return 'unhealthy';
  }
  if (lowerStatus.includes('(health: starting)') || lowerStatus.includes('starting')) {
    return 'starting';
  }

  // Check for container states
  if (lowerStatus.includes('restarting')) {
    return 'restarting';
  }
  if (lowerStatus.includes('exited')) {
    return 'exited';
  }

  // Default: container is up but no explicit health check
  if (lowerStatus.includes('up')) {
    return 'running';
  }

  return 'running';
}

/**
 * Get health info with icon, color, and label
 */
export function getHealthInfo(status: HealthStatus): HealthInfo {
  switch (status) {
    case 'healthy':
      return {
        status: 'healthy',
        icon: '✅',
        color: 'bg-green-500',
        label: 'Healthy',
      };
    case 'unhealthy':
      return {
        status: 'unhealthy',
        icon: '⚠️',
        color: 'bg-yellow-500',
        label: 'Unhealthy',
      };
    case 'starting':
      return {
        status: 'starting',
        icon: '🔄',
        color: 'bg-blue-500',
        label: 'Starting',
      };
    case 'restarting':
      return {
        status: 'restarting',
        icon: '🔄',
        color: 'bg-blue-500 animate-spin',
        label: 'Restarting',
      };
    case 'exited':
      return {
        status: 'exited',
        icon: '❌',
        color: 'bg-red-500',
        label: 'Down',
      };
    case 'running':
    default:
      return {
        status: 'running',
        icon: '●',
        color: 'bg-green-500',
        label: 'Running',
      };
  }
}
