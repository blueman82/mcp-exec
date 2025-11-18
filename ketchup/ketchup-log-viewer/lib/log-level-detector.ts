/**
 * Log Level Detection Utility
 * Detects and classifies log severity levels from log content
 */

export type LogLevel = 'error' | 'warn' | 'info' | 'debug' | 'trace' | 'none';

export interface LogLevelMatch {
  level: LogLevel;
  matched: boolean;
}

/**
 * Detect log level from log line content
 * Matches common log level patterns (case-insensitive)
 */
export function detectLogLevel(content: string): LogLevelMatch {
  const upperContent = content.toUpperCase();

  // Error/Fatal patterns
  if (
    /\b(ERROR|FATAL|CRIT|CRITICAL|EMERGENCY|SEVERE)\b/.test(upperContent) ||
    /\[ERROR\]|\[FATAL\]|\[CRIT\]/.test(upperContent) ||
    /"level":\s*"(error|fatal)"/.test(content) // JSON log format
  ) {
    return { level: 'error', matched: true };
  }

  // Warning patterns
  if (
    /\b(WARN|WARNING)\b/.test(upperContent) ||
    /\[WARN\]|\[WARNING\]/.test(upperContent) ||
    /"level":\s*"warn(ing)?"/.test(content)
  ) {
    return { level: 'warn', matched: true };
  }

  // Info patterns
  if (
    /\b(INFO|INFORMATION)\b/.test(upperContent) ||
    /\[INFO\]/.test(upperContent) ||
    /"level":\s*"info"/.test(content)
  ) {
    return { level: 'info', matched: true };
  }

  // Debug patterns
  if (
    /\b(DEBUG)\b/.test(upperContent) ||
    /\[DEBUG\]/.test(upperContent) ||
    /"level":\s*"debug"/.test(content)
  ) {
    return { level: 'debug', matched: true };
  }

  // Trace patterns
  if (
    /\b(TRACE)\b/.test(upperContent) ||
    /\[TRACE\]/.test(upperContent) ||
    /"level":\s*"trace"/.test(content)
  ) {
    return { level: 'trace', matched: true };
  }

  // No log level detected
  return { level: 'none', matched: false };
}

/**
 * Get background color as inline style for log level
 * Using inline styles to avoid Tailwind JIT purging issues
 */
export function getLogLevelBgColor(level: LogLevel): string {
  switch (level) {
    case 'error':
      return 'rgba(127, 29, 29, 0.3)'; // red-900 with 30% opacity
    case 'warn':
      return 'rgba(113, 63, 18, 0.2)'; // yellow-900 with 20% opacity
    case 'info':
      return '';
    case 'debug':
      return 'rgba(20, 83, 45, 0.15)'; // green-900 with 15% opacity
    case 'trace':
      return 'rgba(30, 58, 138, 0.15)'; // blue-900 with 15% opacity
    default:
      return '';
  }
}
