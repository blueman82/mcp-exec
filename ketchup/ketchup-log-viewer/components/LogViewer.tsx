/**
 * LogViewer Component
 * Displays container logs with virtual scrolling and ANSI color support
 */

'use client';

import { useEffect, useRef, useState, useTransition, useOptimistic } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { parseAnsi, stripAnsi, segmentToStyle } from '@/lib/ansi-parser';
import { detectLogLevel, getLogLevelBgColor } from '@/lib/log-level-detector';
import { formatTimestamp, formatFullTimestamp, type TimestampMode } from '@/lib/timestamp-formatter';
import { connectionQueueManager } from '@/lib/connection-queue-manager';
import type { LogLine } from '@/types';

interface LogViewerProps {
  container: string;
  server: 'prod1' | 'prod2';
  autoScroll?: boolean;
  theme: 'dark' | 'light';
  connectionDelay?: number;
}

export default function LogViewer({
  container,
  server,
  autoScroll = true,
  theme,
  connectionDelay = 0,
}: LogViewerProps) {
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  // React 19: useOptimistic for instant search feedback
  const [optimisticSearch, setOptimisticSearch] = useOptimistic(searchTerm);
  const [timestampMode, setTimestampMode] = useState<TimestampMode>('relative');
  const [levelFilter, setLevelFilter] = useState<'all' | 'error' | 'warn' | 'info' | 'debug'>('all');
  const [isPaused, setIsPaused] = useState(false);
  const [jumpInput, setJumpInput] = useState('');
  const [highlightedIndex, setHighlightedIndex] = useState<number | null>(null);
  const [showCriticalOnly, setShowCriticalOnly] = useState(false);
  const [savedViews, setSavedViews] = useState<Array<{name: string; searchTerm: string; levelFilter: typeof levelFilter; timestampMode: TimestampMode}>>([]);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [viewName, setViewName] = useState('');
  const [showMetrics, setShowMetrics] = useState(false);
  const [logsPerSecond, setLogsPerSecond] = useState(0);
  const [connectionStartTime, setConnectionStartTime] = useState<Date | null>(null);
  const [toasts, setToasts] = useState<Array<{id: number; message: string; type: 'success' | 'error' | 'info' | 'warning'}>>([]);
  const toastIdRef = useRef(0);
  const [wrapLines, setWrapLines] = useState(false);
  const [isQueued, setIsQueued] = useState(false);
  const [queuePosition, setQueuePosition] = useState(0);
  const parentRef = useRef<HTMLDivElement>(null);
  const autoScrollEnabled = useRef(autoScroll);
  const eventSourceRef = useRef<EventSource | null>(null);
  const logCountRef = useRef(0);
  const lastLogCountRef = useRef(0);
  const connectionId = `${server}-${container}`;

  // Load saved views from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem(`savedViews-${container}-${server}`);
    if (stored) {
      try {
        setSavedViews(JSON.parse(stored));
      } catch (e) {
        console.error('Failed to load saved views:', e);
      }
    }
  }, [container, server]);

  // Calculate logs per second
  useEffect(() => {
    const interval = setInterval(() => {
      const currentCount = logs.length;
      const newLogs = currentCount - lastLogCountRef.current;
      setLogsPerSecond(newLogs);
      lastLogCountRef.current = currentCount;
    }, 1000);

    return () => clearInterval(interval);
  }, [logs.length]);

  // Save current view
  const saveCurrentView = () => {
    if (!viewName.trim()) return;

    const newView = {
      name: viewName.trim(),
      searchTerm,
      levelFilter,
      timestampMode,
    };

    const updated = [...savedViews.filter(v => v.name !== newView.name), newView];
    setSavedViews(updated);
    localStorage.setItem(`savedViews-${container}-${server}`, JSON.stringify(updated));
    setViewName('');
    setShowSaveDialog(false);
    showToast(`View "${newView.name}" saved`, 'success');
  };

  // Load a saved view
  const loadView = (view: typeof savedViews[0]) => {
    setSearchTerm(view.searchTerm);
    setLevelFilter(view.levelFilter);
    setTimestampMode(view.timestampMode);
    setShowCriticalOnly(false); // Reset critical filter so saved view can apply
    setShowSaveDialog(false); // Close dialog to see the changes
    showToast(`View "${view.name}" loaded`, 'info');
  };

  // Delete a saved view
  const deleteView = (name: string) => {
    const updated = savedViews.filter(v => v.name !== name);
    setSavedViews(updated);
    localStorage.setItem(`savedViews-${container}-${server}`, JSON.stringify(updated));
    showToast(`View "${name}" deleted`, 'info');
  };

  // Copy line content to clipboard
  const copyLineContent = (log: LogLine) => {
    const content = stripAnsi(log.content);
    navigator.clipboard.writeText(content);
    showToast('Line content copied', 'success');
  };

  // Copy full line with timestamp
  const copyFullLine = (log: LogLine) => {
    const timestamp = formatFullTimestamp(log.timestamp);
    const content = stripAnsi(log.content);
    const fullLine = `[${timestamp}] ${content}`;
    navigator.clipboard.writeText(fullLine);
    showToast('Line copied with timestamp', 'success');
  };

  // Show toast notification
  const showToast = (message: string, type: 'success' | 'error' | 'info' | 'warning') => {
    const id = toastIdRef.current++;
    setToasts((prev) => [...prev, { id, message, type }]);

    // Auto-dismiss after 3 seconds
    setTimeout(() => {
      setToasts((prev) => prev.filter((toast) => toast.id !== id));
    }, 3000);
  };

  // Download logs as text file
  const downloadLogs = () => {
    // Create text content with stripped ANSI codes
    const logText = filteredLogs
      .map((log) => {
        const timestamp = formatFullTimestamp(log.timestamp);
        const content = stripAnsi(log.content);
        return `[${timestamp}] ${content}`;
      })
      .join('\n');

    // Create blob and download
    const blob = new Blob([logText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;

    // Generate filename: container-YYYY-MM-DD_HH-MM-SS.log
    const now = new Date();
    const timestamp = now.toISOString().replace(/[:.]/g, '-').slice(0, 19);
    link.download = `${container}-${timestamp}.log`;

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    showToast(`Downloaded ${filteredLogs.length} logs`, 'success');
  };

  // Jump to timestamp
  const handleJumpToTimestamp = () => {
    if (!jumpInput.trim()) return;

    const input = jumpInput.trim().toLowerCase();
    let targetTime: Date | null = null;

    // Parse relative time (e.g., "5m", "5m ago", "2h", "2h ago", "30s", "30s ago")
    const relativeMatch = input.match(/^(\d+)(s|m|h|d)(\s*ago)?$/);
    if (relativeMatch) {
      const value = parseInt(relativeMatch[1]);
      const unit = relativeMatch[2];
      const now = new Date();

      switch (unit) {
        case 's':
          targetTime = new Date(now.getTime() - value * 1000);
          break;
        case 'm':
          targetTime = new Date(now.getTime() - value * 60 * 1000);
          break;
        case 'h':
          targetTime = new Date(now.getTime() - value * 60 * 60 * 1000);
          break;
        case 'd':
          targetTime = new Date(now.getTime() - value * 24 * 60 * 60 * 1000);
          break;
      }
    }
    // Parse absolute time (HH:MM:SS or HH:MM)
    else if (input.match(/^\d{1,2}:\d{2}(:\d{2})?$/)) {
      const today = new Date();
      const parts = input.split(':');
      const hours = parseInt(parts[0]);
      const minutes = parseInt(parts[1]);
      const seconds = parts[2] ? parseInt(parts[2]) : 0;

      targetTime = new Date(today);
      targetTime.setHours(hours, minutes, seconds, 0);
    }

    if (!targetTime) {
      setError('Invalid timestamp format. Use "5m ago", "2h ago", or "15:03:51"');
      setTimeout(() => setError(null), 3000);
      return;
    }

    // Find log closest to target time (before or after)
    let closestIndex = -1;
    let minDiff = Infinity;

    filteredLogs.forEach((log, idx) => {
      const logTime = new Date(log.timestamp);
      const diff = Math.abs(logTime.getTime() - targetTime!.getTime());

      if (diff < minDiff) {
        minDiff = diff;
        closestIndex = idx;
      }
    });

    if (closestIndex !== -1) {
      const foundLog = filteredLogs[closestIndex];
      const foundTime = new Date(foundLog.timestamp);
      const diffSeconds = Math.abs(Math.round((foundTime.getTime() - targetTime!.getTime()) / 1000));

      setHighlightedIndex(closestIndex);
      virtualizer.scrollToIndex(closestIndex, { align: 'center' });

      // Show feedback about what was found
      if (diffSeconds > 0) {
        setError(`Closest match: ${diffSeconds}s ${foundTime > targetTime! ? 'after' : 'before'} target`);
        setTimeout(() => setError(null), 3000);
      }

      // Clear highlight after 3 seconds
      setTimeout(() => setHighlightedIndex(null), 3000);
    } else {
      setError('No logs found near that timestamp');
      setTimeout(() => setError(null), 3000);
    }
  };

  // Highlight search matches within text
  const highlightMatches = (text: string, search: string) => {
    if (!search.trim()) {
      return <>{text}</>;
    }

    const lowerText = text.toLowerCase();
    const lowerSearch = search.toLowerCase();
    const parts: React.JSX.Element[] = [];
    let lastIndex = 0;

    let index = lowerText.indexOf(lowerSearch);
    while (index !== -1) {
      // Add text before match
      if (index > lastIndex) {
        parts.push(<span key={`text-${lastIndex}`}>{text.slice(lastIndex, index)}</span>);
      }

      // Add highlighted match
      parts.push(
        <span
          key={`match-${index}`}
          className="bg-yellow-500 text-black font-bold px-0.5 rounded"
        >
          {text.slice(index, index + search.length)}
        </span>
      );

      lastIndex = index + search.length;
      index = lowerText.indexOf(lowerSearch, lastIndex);
    }

    // Add remaining text
    if (lastIndex < text.length) {
      parts.push(<span key={`text-${lastIndex}`}>{text.slice(lastIndex)}</span>);
    }

    return <>{parts}</>;
  };

  // Critical patterns list
  const criticalPatterns = ['error', 'timeout', 'failed', 'exception', 'fatal', 'critical'];

  // Filter logs based on search term and log level
  const filteredLogs = logs.filter((log) => {
    const content = stripAnsi(log.content).toLowerCase();

    // Critical-only filter (overrides other filters when active)
    if (showCriticalOnly) {
      return criticalPatterns.some(pattern => content.includes(pattern));
    }

    // Search filter
    if (searchTerm && !content.includes(searchTerm.toLowerCase())) {
      return false;
    }

    // Level filter
    if (levelFilter !== 'all' && log.level !== levelFilter) {
      return false;
    }

    return true;
  });

  // Count critical patterns in filtered logs
  const patternCounts = filteredLogs.reduce((acc, log) => {
    const content = stripAnsi(log.content).toLowerCase();
    criticalPatterns.forEach(pattern => {
      if (content.includes(pattern)) {
        acc[pattern] = (acc[pattern] || 0) + 1;
      }
    });
    return acc;
  }, {} as Record<string, number>);

  // Count unique log lines containing any critical pattern (not total pattern occurrences)
  const totalCritical = filteredLogs.filter(log => {
    const content = stripAnsi(log.content).toLowerCase();
    return criticalPatterns.some(pattern => content.includes(pattern));
  }).length;

  // React 19: useTransition for smooth filtering
  const [isPending, startTransition] = useTransition();

  // Virtual scrolling with dynamic size estimation
  const virtualizer = useVirtualizer({
    count: filteredLogs.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => (wrapLines ? 80 : 24), // Dynamic: 80px for wrap, 24px for truncate
    overscan: 10,
  });

  // Connect to SSE stream with queue management + staggered delay
  useEffect(() => {
    // Don't connect if paused
    if (isPaused) {
      if (eventSourceRef.current) {
        connectionQueueManager.releaseConnection(connectionId);
        eventSourceRef.current = null;
        setIsConnected(false);
        setIsQueued(false);
      }
      return;
    }

    // Request connection through queue manager with staggered delay
    const connectAsync = async () => {
      try {
        // Show queued status
        const status = connectionQueueManager.getStatus();
        if (status.active >= status.capacity) {
          setIsQueued(true);
          setQueuePosition(status.queued + 1);
        }

        // Request connection (will queue if at capacity)
        const eventSource = await connectionQueueManager.requestConnection(
          connectionId,
          `/api/logs/stream?container=${container}&server=${server}&tail=1000`
        );

        eventSourceRef.current = eventSource;
        setIsQueued(false);

        eventSource.onopen = () => {
          setIsConnected(true);
          setError(null);
          setConnectionStartTime(new Date());
        };

        eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);

            if (data.error) {
              setError(data.error);
              setIsConnected(false);
              return;
            }

            const { level } = detectLogLevel(data.content);

            const logLine: LogLine = {
              timestamp: data.timestamp,
              content: data.content,
              container: data.container,
              server: data.server,
              level,
            };

            setLogs((prev) => [...prev, logLine]);

            // Auto-scroll to bottom
            if (autoScrollEnabled.current && parentRef.current) {
              setTimeout(() => {
                if (parentRef.current) {
                  parentRef.current.scrollTop = parentRef.current.scrollHeight;
                }
              }, 100);
            }
          } catch (err) {
            console.error('Failed to parse log event:', err);
          }
        };

        eventSource.onerror = () => {
          setError('Connection lost. Attempting to reconnect...');
          setIsConnected(false);
        };
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to connect');
        setIsQueued(false);
      }
    };

    // Add staggered delay to prevent all containers hitting queue simultaneously
    const timeoutId = setTimeout(() => {
      connectAsync();
    }, connectionDelay);

    return () => {
      clearTimeout(timeoutId);
      connectionQueueManager.releaseConnection(connectionId);
      eventSourceRef.current = null;
      setIsQueued(false);
    };
  }, [container, server, isPaused, connectionId, connectionDelay]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-700 bg-gray-800">
        <div className="flex items-center space-x-4">
          <h3 className="font-mono text-sm font-bold text-white">
            {container}
            <span className="ml-2 text-xs text-gray-400">({server})</span>
          </h3>
          <div className="flex items-center space-x-2">
            <div
              className={`w-2 h-2 rounded-full ${
                isConnected
                  ? 'bg-green-500'
                  : isQueued
                  ? 'bg-yellow-500 animate-pulse'
                  : 'bg-red-500'
              }`}
            />
            <span className="text-xs text-gray-400">
              {isConnected
                ? 'Connected'
                : isQueued
                ? `Queued (${queuePosition}/${connectionQueueManager.getStatus().capacity})`
                : 'Disconnected'}
            </span>
          </div>
          {isConnected && !isPaused && (
            <div className="flex items-center space-x-1 px-2 py-1 bg-red-600 rounded">
              <div className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
              <span className="text-xs font-bold text-white">LIVE</span>
            </div>
          )}
          {isPaused && (
            <div className="flex items-center space-x-1 px-2 py-1 bg-yellow-600 rounded">
              <span className="text-xs font-bold text-white">PAUSED</span>
            </div>
          )}
          {/* Pause/Resume Button */}
          <button
            onClick={() => setIsPaused(!isPaused)}
            className="px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded border border-gray-600"
            title={isPaused ? 'Resume streaming' : 'Pause streaming'}
          >
            {isPaused ? '▶️ Resume' : '⏸️ Pause'}
          </button>
          {/* Download Button */}
          <button
            onClick={downloadLogs}
            className="px-3 py-1 text-xs bg-green-700 hover:bg-green-600 text-white rounded border border-green-600"
            title="Download logs as text file"
          >
            💾 Download
          </button>
          {/* Wrap Lines Toggle */}
          <button
            onClick={() => setWrapLines(!wrapLines)}
            className={`px-3 py-1 text-xs rounded border transition-colors ${
              wrapLines
                ? 'bg-orange-600 border-orange-500 text-white'
                : 'bg-gray-700 border-gray-600 text-gray-300 hover:bg-gray-600'
            }`}
            title={wrapLines ? 'Truncate long lines' : 'Wrap long lines'}
          >
            {wrapLines ? '↩️ Wrap' : '➡️ Truncate'}
          </button>
        </div>

        <div className="flex items-center space-x-4">
          {/* Log Level Filter Buttons */}
          <div className="flex items-center space-x-1">
            {(['all', 'error', 'warn', 'info', 'debug'] as const).map((level) => (
              <button
                key={level}
                onClick={() => setLevelFilter(level)}
                className={`px-2 py-1 text-xs rounded border transition-colors ${
                  levelFilter === level
                    ? 'bg-blue-600 border-blue-500 text-white font-bold'
                    : 'bg-gray-800 border-gray-600 text-gray-400 hover:bg-gray-700 hover:border-gray-500'
                }`}
                title={`Filter ${level === 'all' ? 'all logs' : level + ' level logs'}`}
              >
                {level === 'all' ? 'All' : level.charAt(0).toUpperCase() + level.slice(1)}
              </button>
            ))}
          </div>

          {/* Search with React 19 optimistic updates */}
          <input
            type="text"
            placeholder="Search logs..."
            value={optimisticSearch}
            onChange={(e) => {
              const value = e.target.value;
              // Instant UI feedback
              setOptimisticSearch(value);
              // Smooth transition for actual filter
              startTransition(() => {
                setSearchTerm(value);
              });
            }}
            className="px-3 py-1 text-sm bg-gray-900 border border-gray-600 rounded text-gray-300 focus:outline-none focus:border-blue-500"
          />

          {/* Jump to Timestamp */}
          <div className="flex items-center space-x-1">
            <input
              type="text"
              placeholder="Jump: 5m ago, 15:03"
              value={jumpInput}
              onChange={(e) => setJumpInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleJumpToTimestamp()}
              className="px-3 py-1 text-sm bg-gray-900 border border-gray-600 rounded text-gray-300 focus:outline-none focus:border-purple-500 w-36"
            />
            <button
              onClick={handleJumpToTimestamp}
              className="px-2 py-1 text-xs bg-purple-700 hover:bg-purple-600 text-white rounded border border-purple-600"
              title="Jump to timestamp"
            >
              🎯
            </button>
          </div>

          {/* Timestamp toggle */}
          <button
            onClick={() => setTimestampMode(timestampMode === 'relative' ? 'absolute' : 'relative')}
            className="px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded border border-gray-600"
            title={`Switch to ${timestampMode === 'relative' ? 'absolute' : 'relative'} timestamps`}
          >
            {timestampMode === 'relative' ? '🕐 Relative' : '📅 Absolute'}
          </button>

          {/* Auto-scroll toggle */}
          <label className="flex items-center space-x-2 text-sm text-gray-400 cursor-pointer">
            <input
              type="checkbox"
              checked={autoScrollEnabled.current}
              onChange={(e) => {
                autoScrollEnabled.current = e.target.checked;
              }}
              className="w-4 h-4"
            />
            <span>Auto-scroll</span>
          </label>

          {/* Log count */}
          <span className="text-xs text-gray-500">
            {filteredLogs.length} lines
          </span>

          {/* Pattern alerts badge */}
          {totalCritical > 0 && (
            <button
              onClick={() => setShowCriticalOnly(!showCriticalOnly)}
              className={`flex items-center space-x-1 px-2 py-1 rounded border transition-colors ${
                showCriticalOnly
                  ? 'bg-red-700 border-red-600 ring-2 ring-red-400'
                  : 'bg-red-600 border-red-500 hover:bg-red-700'
              }`}
              title={`${showCriticalOnly ? 'Click to show all logs' : 'Click to filter critical patterns only'}\n\nCritical patterns found:\n${Object.entries(patternCounts).map(([pattern, count]) => `${pattern}: ${count}`).join('\n')}`}
            >
              <span className="text-xs font-bold text-white">⚠️ {totalCritical}</span>
            </button>
          )}

          {/* Saved Views Button */}
          <button
            onClick={() => setShowSaveDialog(!showSaveDialog)}
            className="px-3 py-1 text-xs bg-blue-700 hover:bg-blue-600 text-white rounded border border-blue-600"
            title="Save/Load Views"
          >
            💾 Views {savedViews.length > 0 && `(${savedViews.length})`}
          </button>

          {/* Performance Metrics Toggle */}
          <button
            onClick={() => setShowMetrics(!showMetrics)}
            className={`px-3 py-1 text-xs rounded border transition-colors ${
              showMetrics
                ? 'bg-purple-700 border-purple-600 text-white'
                : 'bg-gray-700 border-gray-600 text-gray-300 hover:bg-gray-600'
            }`}
            title="Toggle performance metrics overlay"
          >
            📊 Metrics
          </button>
        </div>
      </div>

      {/* Save View Dialog - React 19 Actions API */}
      {showSaveDialog && (
        <div className="p-3 bg-gray-800 border-b border-gray-700">
          <form
            action={async (formData) => {
              const name = formData.get('viewName') as string;
              if (!name?.trim()) return;

              const newView = {
                name: name.trim(),
                searchTerm,
                levelFilter,
                timestampMode,
              };

              const updated = [...savedViews.filter(v => v.name !== newView.name), newView];
              setSavedViews(updated);
              localStorage.setItem(`savedViews-${container}-${server}`, JSON.stringify(updated));
              setViewName('');
              setShowSaveDialog(false);
              showToast(`View "${newView.name}" saved`, 'success');
            }}
            className="flex items-center space-x-2 mb-2"
          >
            <input
              type="text"
              name="viewName"
              placeholder="View name..."
              value={viewName}
              onChange={(e) => setViewName(e.target.value)}
              className="flex-1 px-3 py-1 text-sm bg-gray-900 border border-gray-600 rounded text-gray-300 focus:outline-none focus:border-blue-500"
            />
            <button
              type="submit"
              disabled={!viewName.trim()}
              className="px-3 py-1 text-xs bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded"
            >
              Save Current
            </button>
            <button
              type="button"
              onClick={() => setShowSaveDialog(false)}
              className="px-3 py-1 text-xs bg-gray-600 hover:bg-gray-700 text-white rounded"
            >
              Close
            </button>
          </form>

          {/* Saved Views List */}
          {savedViews.length > 0 && (
            <div className="space-y-1">
              <div className="text-xs text-gray-400 mb-1">Saved Views:</div>
              {savedViews.map((view) => (
                <div key={view.name} className="flex items-center justify-between p-2 bg-gray-900 rounded">
                  <button
                    onClick={() => loadView(view)}
                    className="flex-1 text-left text-sm text-gray-300 hover:text-white"
                  >
                    <span className="font-bold">{view.name}</span>
                    <span className="text-xs text-gray-500 ml-2">
                      ({view.levelFilter}, {view.timestampMode}{view.searchTerm ? `, "${view.searchTerm}"` : ''})
                    </span>
                  </button>
                  <button
                    onClick={() => deleteView(view.name)}
                    className="ml-2 px-2 py-1 text-xs bg-red-600 hover:bg-red-700 text-white rounded"
                    title="Delete view"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className="p-3 bg-red-900 border-b border-red-700 text-red-200 text-sm">
          {error}
        </div>
      )}

      {/* Performance Metrics Overlay */}
      {showMetrics && (
        <div className="p-4 bg-gradient-to-r from-purple-900 to-indigo-900 border-b border-purple-700">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {/* Logs per second */}
            <div className="bg-black bg-opacity-30 p-3 rounded border border-purple-600">
              <div className="text-xs text-purple-300 mb-1">Throughput</div>
              <div className="text-2xl font-bold text-white">{logsPerSecond}</div>
              <div className="text-xs text-purple-400">logs/sec</div>
            </div>

            {/* Total logs */}
            <div className="bg-black bg-opacity-30 p-3 rounded border border-purple-600">
              <div className="text-xs text-purple-300 mb-1">Total Logs</div>
              <div className="text-2xl font-bold text-white">{logs.length.toLocaleString()}</div>
              <div className="text-xs text-purple-400">lines</div>
            </div>

            {/* Filtered logs */}
            <div className="bg-black bg-opacity-30 p-3 rounded border border-purple-600">
              <div className="text-xs text-purple-300 mb-1">Filtered</div>
              <div className="text-2xl font-bold text-white">{filteredLogs.length.toLocaleString()}</div>
              <div className="text-xs text-purple-400">
                {logs.length > 0 ? `${Math.round((filteredLogs.length / logs.length) * 100)}%` : '0%'}
              </div>
            </div>

            {/* Connection uptime */}
            <div className="bg-black bg-opacity-30 p-3 rounded border border-purple-600">
              <div className="text-xs text-purple-300 mb-1">Uptime</div>
              <div className="text-2xl font-bold text-white">
                {connectionStartTime
                  ? (() => {
                      const uptime = Math.floor((Date.now() - connectionStartTime.getTime()) / 1000);
                      const hours = Math.floor(uptime / 3600);
                      const minutes = Math.floor((uptime % 3600) / 60);
                      const seconds = uptime % 60;
                      return hours > 0
                        ? `${hours}h ${minutes}m`
                        : minutes > 0
                        ? `${minutes}m ${seconds}s`
                        : `${seconds}s`;
                    })()
                  : '--'}
              </div>
              <div className="text-xs text-purple-400">
                {isConnected ? 'connected' : 'disconnected'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Log content - conditional virtualization */}
      <div
        ref={parentRef}
        className={`flex-1 overflow-auto ${theme === 'dark' ? 'bg-black' : 'bg-gray-50'}`}
        style={{ contain: wrapLines ? 'none' : 'strict' }}
      >
        {wrapLines ? (
          // Wrap mode: Disable virtualization for proper height calculation
          <div className="w-full">
            {filteredLogs.map((log, index) => {
              const segments = parseAnsi(log.content);
              const bgColor = log.level ? getLogLevelBgColor(log.level) : '';
              const isHighlighted = highlightedIndex === index;

              return (
                <div
                  key={index}
                  style={{
                    minHeight: '24px',
                    lineHeight: '1.5',
                    whiteSpace: 'pre-wrap',
                    overflowWrap: 'break-word',
                    wordBreak: 'normal',
                    backgroundColor: isHighlighted ? 'rgba(147, 51, 234, 0.3)' : bgColor,
                    borderLeft: isHighlighted ? '3px solid rgb(168, 85, 247)' : 'none',
                    paddingTop: '4px',
                    paddingBottom: '4px',
                  }}
                  className={`px-4 font-mono text-xs ${
                    theme === 'dark'
                      ? 'text-gray-300 hover:bg-gray-900'
                      : 'text-gray-800 hover:bg-gray-200'
                  }`}
                >
                  <span
                    className={`mr-3 cursor-pointer select-none ${
                      theme === 'dark'
                        ? 'text-gray-600 hover:text-blue-400'
                        : 'text-gray-400 hover:text-blue-600'
                    }`}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (e.shiftKey) {
                        copyFullLine(log);
                      } else {
                        copyLineContent(log);
                      }
                    }}
                    title={`Click to copy line content\nShift+Click to copy with timestamp`}
                  >
                    {index + 1}
                  </span>
                  <span
                    className={theme === 'dark' ? 'text-gray-500 mr-3' : 'text-gray-500 mr-3'}
                    title={formatFullTimestamp(log.timestamp)}
                  >
                    [{formatTimestamp(log.timestamp, timestampMode)}]
                  </span>
                  {segments.map((segment, idx) => (
                    <span key={idx} style={segmentToStyle(segment)}>
                      {highlightMatches(segment.text, searchTerm)}
                    </span>
                  ))}
                </div>
              );
            })}
          </div>
        ) : (
          // Truncate mode: Use virtual scrolling for performance
          <div
            style={{
              height: `${virtualizer.getTotalSize()}px`,
              width: '100%',
              position: 'relative',
            }}
          >
            {virtualizer.getVirtualItems().map((virtualItem) => {
              const log = filteredLogs[virtualItem.index];
              const segments = parseAnsi(log.content);
              const bgColor = log.level ? getLogLevelBgColor(log.level) : '';
              const isHighlighted = highlightedIndex === virtualItem.index;

              return (
                <div
                  key={virtualItem.index}
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: '24px',
                    lineHeight: '24px',
                    overflow: 'hidden',
                    whiteSpace: 'nowrap',
                    transform: `translateY(${virtualItem.start}px)`,
                    backgroundColor: isHighlighted ? 'rgba(147, 51, 234, 0.3)' : bgColor,
                    borderLeft: isHighlighted ? '3px solid rgb(168, 85, 247)' : 'none',
                  }}
                  className={`px-4 font-mono text-xs ${
                    theme === 'dark'
                      ? 'text-gray-300 hover:bg-gray-900'
                      : 'text-gray-800 hover:bg-gray-200'
                  }`}
                >
                <span
                  className={`mr-3 cursor-pointer select-none ${
                    theme === 'dark'
                      ? 'text-gray-600 hover:text-blue-400'
                      : 'text-gray-400 hover:text-blue-600'
                  }`}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (e.shiftKey) {
                      copyFullLine(log);
                    } else {
                      copyLineContent(log);
                    }
                  }}
                  title={`Click to copy line content\nShift+Click to copy with timestamp`}
                >
                  {virtualItem.index + 1}
                </span>
                <span
                  className={theme === 'dark' ? 'text-gray-500 mr-3' : 'text-gray-500 mr-3'}
                  title={formatFullTimestamp(log.timestamp)}
                >
                  [{formatTimestamp(log.timestamp, timestampMode)}]
                </span>
                {segments.map((segment, idx) => (
                  <span key={idx} style={segmentToStyle(segment)}>
                    {highlightMatches(segment.text, searchTerm)}
                  </span>
                ))}
              </div>
            );
          })}
        </div>
        )}
      </div>

      {/* Toast notifications */}
      <div className="fixed top-4 right-4 z-50 space-y-2">
        {toasts.map((toast) => {
          const bgColor = toast.type === 'success'
            ? 'bg-green-600'
            : toast.type === 'error'
            ? 'bg-red-600'
            : toast.type === 'warning'
            ? 'bg-yellow-600'
            : 'bg-blue-600';

          const icon = toast.type === 'success'
            ? '✓'
            : toast.type === 'error'
            ? '✕'
            : toast.type === 'warning'
            ? '⚠'
            : 'ℹ';

          return (
            <div
              key={toast.id}
              className={`${bgColor} text-white px-4 py-3 rounded shadow-lg flex items-center space-x-3 min-w-[250px] max-w-[400px] animate-slide-in-right`}
            >
              <span className="text-lg font-bold">{icon}</span>
              <span className="flex-1">{toast.message}</span>
              <button
                onClick={() => setToasts((prev) => prev.filter((t) => t.id !== toast.id))}
                className="text-white hover:text-gray-200 ml-2"
              >
                ✕
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
