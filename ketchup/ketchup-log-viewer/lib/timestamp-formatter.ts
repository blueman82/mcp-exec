/**
 * Timestamp Formatting Utility
 * Converts timestamps to relative time (e.g., "2s ago", "5m ago")
 */

export type TimestampMode = 'relative' | 'absolute';

/**
 * Format timestamp as relative time (e.g., "2 seconds ago")
 */
export function formatRelativeTime(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);

  // Future timestamps
  if (diffSeconds < 0) {
    return 'just now';
  }

  // Less than 1 minute
  if (diffSeconds < 60) {
    return `${diffSeconds}s ago`;
  }

  // Less than 1 hour
  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) {
    return `${diffMinutes}m ago`;
  }

  // Less than 24 hours
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours}h ago`;
  }

  // Days
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) {
    return `${diffDays}d ago`;
  }

  // Weeks
  const diffWeeks = Math.floor(diffDays / 7);
  if (diffWeeks < 4) {
    return `${diffWeeks}w ago`;
  }

  // Months
  const diffMonths = Math.floor(diffDays / 30);
  return `${diffMonths}mo ago`;
}

/**
 * Format timestamp as absolute time (HH:MM:SS)
 */
export function formatAbsoluteTime(timestamp: string): string {
  const date = new Date(timestamp);
  const hours = date.getHours().toString().padStart(2, '0');
  const minutes = date.getMinutes().toString().padStart(2, '0');
  const seconds = date.getSeconds().toString().padStart(2, '0');
  return `${hours}:${minutes}:${seconds}`;
}

/**
 * Format timestamp as full ISO string for tooltip
 */
export function formatFullTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toISOString();
}

/**
 * Format timestamp based on current mode
 */
export function formatTimestamp(
  timestamp: string,
  mode: TimestampMode
): string {
  return mode === 'relative'
    ? formatRelativeTime(timestamp)
    : formatAbsoluteTime(timestamp);
}
