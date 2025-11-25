/**
 * MergedLogViewer Component
 * Displays logs from multiple containers across multiple servers in chronological order
 */

'use client';

import { useEffect, useRef, useState, useTransition, useOptimistic } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { parseAnsi, stripAnsi, segmentToStyle } from '@/lib/ansi-parser';
import { detectLogLevel, getLogLevelBgColor } from '@/lib/log-level-detector';
import { formatTimestamp, formatFullTimestamp, type TimestampMode } from '@/lib/timestamp-formatter';
import { connectionQueueManager } from '@/lib/connection-queue-manager';
import type { LogLine } from '@/types';

interface ContainerSelection {
  container: string;
  server: 'prod1' | 'prod2';
}

interface MergedLogViewerProps {
  selections: ContainerSelection[];
  autoScroll?: boolean;
  theme: 'dark' | 'light';
}

interface MergedLogLine extends LogLine {
  selectionKey: string; // For tracking which stream this came from
}

export default function MergedLogViewer({
  selections,
  autoScroll = true,
  theme,
}: MergedLogViewerProps) {
  const [logs, setLogs] = useState<MergedLogLine[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<Map<string, 'connected' | 'queued' | 'disconnected'>>(new Map());
  const [queuePositions, setQueuePositions] = useState<Map<string, number>>(new Map());
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [optimisticSearch, setOptimisticSearch] = useOptimistic(searchTerm);
  const [timestampMode, setTimestampMode] = useState<TimestampMode>('relative');
  const [levelFilter, setLevelFilter] = useState<'all' | 'error' | 'warn' | 'info' | 'debug'>('all');
  const [serverFilter, setServerFilter] = useState<'all' | 'prod1' | 'prod2'>('all');
  const [isPaused, setIsPaused] = useState(false);
  const [jumpInput, setJumpInput] = useState('');
  const [highlightedIndex, setHighlightedIndex] = useState<number | null>(null);
  const [showCriticalOnly, setShowCriticalOnly] = useState(false);
  const [savedViews, setSavedViews] = useState<Array<{name: string; searchTerm: string; levelFilter: typeof levelFilter; serverFilter: typeof serverFilter; timestampMode: TimestampMode}>>([]);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [viewName, setViewName] = useState('');
  const [showMetrics, setShowMetrics] = useState(false);
  const [logsPerSecond, setLogsPerSecond] = useState(0);
  const [connectionStartTime, setConnectionStartTime] = useState<Date | null>(null);
  const [toasts, setToasts] = useState<Array<{id: number; message: string; type: 'success' | 'error' | 'info' | 'warning'}>>([]);
  const toastIdRef = useRef(0);
  const [wrapLines, setWrapLines] = useState(false);
  const parentRef = useRef<HTMLDivElement>(null);
  const autoScrollEnabled = useRef(autoScroll);
  const eventSourcesRef = useRef<Map<string, EventSource>>(new Map());
  const lastLogCountRef = useRef(0);

  // Generate unique key for selection
  const getSelectionKey = (selection: ContainerSelection) => `${selection.server}-${selection.container}`;

  // Load saved views from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem('mergedLogViewer-savedViews');
    if (stored) {
      try {
        setSavedViews(JSON.parse(stored));
      } catch (e) {
        console.error('Failed to load saved views:', e);
      }
    }
  }, []);

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
      serverFilter,
      timestampMode,
    };

    const updated = [...savedViews.filter(v => v.name !== newView.name), newView];
    setSavedViews(updated);
    localStorage.setItem('mergedLogViewer-savedViews', JSON.stringify(updated));
    setViewName('');
    setShowSaveDialog(false);
    showToast(`View "${newView.name}" saved`, 'success');
  };

  // Load a saved view
  const loadView = (view: typeof savedViews[0]) => {
    setSearchTerm(view.searchTerm);
    setLevelFilter(view.levelFilter);
    setServerFilter(view.serverFilter);
    setTimestampMode(view.timestampMode);
    setShowCriticalOnly(false);
    setShowSaveDialog(false);
    showToast(`View "${view.name}" loaded`, 'info');
  };

  // Delete a saved view
  const deleteView = (name: string) => {
    const updated = savedViews.filter(v => v.name !== name);
    setSavedViews(updated);
    localStorage.setItem('mergedLogViewer-savedViews', JSON.stringify(updated));
    showToast(`View "${name}" deleted`, 'info');
  };

  // Copy line content to clipboard
  const copyLineContent = (log: MergedLogLine) => {
    const content = stripAnsi(log.content);
    navigator.clipboard.writeText(content);
    showToast('Line content copied', 'success');
  };

  // Copy full line with timestamp and server
  const copyFullLine = (log: MergedLogLine) => {
    const timestamp = formatFullTimestamp(log.timestamp);
    const content = stripAnsi(log.content);
    const fullLine = `[${log.server}] [${timestamp}] ${content}`;
    navigator.clipboard.writeText(fullLine);
    showToast('Line copied with timestamp', 'success');
  };

  // Show toast notification
  const showToast = (message: string, type: 'success' | 'error' | 'info' | 'warning') => {
    const id = toastIdRef.current++;
    setToasts((prev) => [...prev, { id, message, type }]);

    setTimeout(() => {
      setToasts((prev) => prev.filter((toast) => toast.id !== id));
    }, 3000);
  };

  // Download logs as text file
  const downloadLogs = () => {
    const logText = filteredLogs
      .map((log) => {
        const timestamp = formatFullTimestamp(log.timestamp);
        const content = stripAnsi(log.content);
        return `[${log.server}] [${timestamp}] ${log.container}: ${content}`;
      })
      .join('\n');

    const blob = new Blob([logText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;

    const now = new Date();
    const timestamp = now.toISOString().replace(/[:.]/g, '-').slice(0, 19);
    link.download = `merged-logs-${timestamp}.log`;

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
    } else if (input.match(/^\d{1,2}:\d{2}(:\d{2})?$/)) {
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

      if (diffSeconds > 0) {
        setError(`Closest match: ${diffSeconds}s ${foundTime > targetTime! ? 'after' : 'before'} target`);
        setTimeout(() => setError(null), 3000);
      }

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
      if (index > lastIndex) {
        parts.push(<span key={`text-${lastIndex}`}>{text.slice(lastIndex, index)}</span>);
      }

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

    if (lastIndex < text.length) {
      parts.push(<span key={`text-${lastIndex}`}>{text.slice(lastIndex)}</span>);
    }

    return <>{parts}</>;
  };

  // Critical patterns list
  const criticalPatterns = ['error', 'timeout', 'failed', 'exception', 'fatal', 'critical'];

  // Filter logs based on search, level, and server
  const filteredLogs = logs.filter((log) => {
    const content = stripAnsi(log.content).toLowerCase();

    // Critical-only filter
    if (showCriticalOnly) {
      return criticalPatterns.some(pattern => content.includes(pattern));
    }

    // Server filter
    if (serverFilter !== 'all' && log.server !== serverFilter) {
      return false;
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

  // Count critical patterns
  const patternCounts = filteredLogs.reduce((acc, log) => {
    const content = stripAnsi(log.content).toLowerCase();
    criticalPatterns.forEach(pattern => {
      if (content.includes(pattern)) {
        acc[pattern] = (acc[pattern] || 0) + 1;
      }
    });
    return acc;
  }, {} as Record<string, number>);

  const totalCritical = filteredLogs.filter(log => {
    const content = stripAnsi(log.content).toLowerCase();
    return criticalPatterns.some(pattern => content.includes(pattern));
  }).length;

  const [isPending, startTransition] = useTransition();

  // Virtual scrolling
  const virtualizer = useVirtualizer({
    count: filteredLogs.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => (wrapLines ? 80 : 24),
    overscan: 10,
  });

  // Connect to multiple SSE streams
  useEffect(() => {
    // Don't connect if paused or no selections
    if (isPaused || selections.length === 0) {
      // Clean up all connections
      eventSourcesRef.current.forEach((_, key) => {
        connectionQueueManager.releaseConnection(key);
      });
      eventSourcesRef.current.clear();
      setConnectionStatus(new Map());
      setQueuePositions(new Map());
      return;
    }

    const connectToStream = async (selection: ContainerSelection, index: number) => {
      const selectionKey = getSelectionKey(selection);

      try {
        // Check if already connected
        if (eventSourcesRef.current.has(selectionKey)) {
          return;
        }

        // Show queued status if needed
        const status = connectionQueueManager.getStatus();
        if (status.active >= status.capacity) {
          setConnectionStatus(prev => new Map(prev).set(selectionKey, 'queued'));
          setQueuePositions(prev => new Map(prev).set(selectionKey, status.queued + 1));
        }

        // Request connection through queue manager with staggered delay
        const delay = index * 100; // 100ms stagger
        await new Promise(resolve => setTimeout(resolve, delay));

        const eventSource = await connectionQueueManager.requestConnection(
          selectionKey,
          `/api/logs/stream?container=${selection.container}&server=${selection.server}&tail=1000`
        );

        eventSourcesRef.current.set(selectionKey, eventSource);
        setQueuePositions(prev => {
          const updated = new Map(prev);
          updated.delete(selectionKey);
          return updated;
        });

        eventSource.onopen = () => {
          setConnectionStatus(prev => new Map(prev).set(selectionKey, 'connected'));
          if (!connectionStartTime) {
            setConnectionStartTime(new Date());
          }
        };

        eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);

            if (data.error) {
              setError(data.error);
              return;
            }

            const { level } = detectLogLevel(data.content);

            const logLine: MergedLogLine = {
              timestamp: data.timestamp,
              content: data.content,
              container: data.container,
              server: data.server,
              level,
              selectionKey,
            };

            // Insert and sort by timestamp
            setLogs((prev) => {
              const updated = [...prev, logLine];
              updated.sort((a, b) =>
                new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
              );
              return updated;
            });

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
          setConnectionStatus(prev => new Map(prev).set(selectionKey, 'disconnected'));
          setError(`Connection lost for ${selection.container} (${selection.server})`);
        };
      } catch (err) {
        setConnectionStatus(prev => new Map(prev).set(selectionKey, 'disconnected'));
        setError(err instanceof Error ? err.message : 'Failed to connect');
      }
    };

    // Connect to all selected streams
    selections.forEach((selection, index) => {
      connectToStream(selection, index);
    });

    // Cleanup on unmount or when selections change
    return () => {
      const currentKeys = new Set(selections.map(getSelectionKey));

      // Release connections that are no longer selected
      eventSourcesRef.current.forEach((_, key) => {
        if (!currentKeys.has(key)) {
          connectionQueueManager.releaseConnection(key);
          eventSourcesRef.current.delete(key);
        }
      });
    };
  }, [selections, isPaused, connectionStartTime]);

  // Get server badge color
  const getServerBadgeColor = (server: 'prod1' | 'prod2') => {
    return server === 'prod1'
      ? 'bg-blue-600 text-white border-blue-500'
      : 'bg-green-600 text-white border-green-500';
  };

  // Get server border color
  const getServerBorderColor = (server: 'prod1' | 'prod2') => {
    return server === 'prod1' ? 'border-l-blue-500' : 'border-l-green-500';
  };

  // Count connections by status
  const connectedCount = Array.from(connectionStatus.values()).filter(s => s === 'connected').length;
  const queuedCount = Array.from(connectionStatus.values()).filter(s => s === 'queued').length;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-700 bg-gray-800">
        <div className="flex items-center space-x-4">
          <h3 className="font-mono text-sm font-bold text-white">
            Merged Logs
            <span className="ml-2 text-xs text-gray-400">
              ({selections.length} container{selections.length !== 1 ? 's' : ''})
            </span>
          </h3>
          <div className="flex items-center space-x-2">
            <div
              className={`w-2 h-2 rounded-full ${
                connectedCount > 0
                  ? 'bg-green-500'
                  : queuedCount > 0
                  ? 'bg-yellow-500 animate-pulse'
                  : 'bg-red-500'
              }`}
            />
            <span className="text-xs text-gray-400">
              {connectedCount > 0
                ? `${connectedCount}/${selections.length} connected`
                : queuedCount > 0
                ? `${queuedCount} queued`
                : 'Disconnected'}
            </span>
          </div>
          {connectedCount > 0 && !isPaused && (
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
          <button
            onClick={() => setIsPaused(!isPaused)}
            className="px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded border border-gray-600"
            title={isPaused ? 'Resume streaming' : 'Pause streaming'}
          >
            {isPaused ? '▶️ Resume' : '⏸️ Pause'}
          </button>
          <button
            onClick={downloadLogs}
            className="px-3 py-1 text-xs bg-green-700 hover:bg-green-600 text-white rounded border border-green-600"
            title="Download logs as text file"
          >
            💾 Download
          </button>
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
          {/* Server Filter Buttons */}
          <div className="flex items-center space-x-1">
            {(['all', 'prod1', 'prod2'] as const).map((server) => (
              <button
                key={server}
                onClick={() => setServerFilter(server)}
                className={`px-2 py-1 text-xs rounded border transition-colors ${
                  serverFilter === server
                    ? server === 'prod1'
                      ? 'bg-blue-600 border-blue-500 text-white font-bold'
                      : server === 'prod2'
                      ? 'bg-green-600 border-green-500 text-white font-bold'
                      : 'bg-purple-600 border-purple-500 text-white font-bold'
                    : 'bg-gray-800 border-gray-600 text-gray-400 hover:bg-gray-700 hover:border-gray-500'
                }`}
                title={`Show ${server === 'all' ? 'all servers' : server + ' logs only'}`}
              >
                {server === 'all' ? 'All Servers' : server}
              </button>
            ))}
          </div>

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

          {/* Search */}
          <input
            type="text"
            placeholder="Search logs..."
            value={optimisticSearch}
            onChange={(e) => {
              const value = e.target.value;
              setOptimisticSearch(value);
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

      {/* Save View Dialog */}
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
                serverFilter,
                timestampMode,
              };

              const updated = [...savedViews.filter(v => v.name !== newView.name), newView];
              setSavedViews(updated);
              localStorage.setItem('mergedLogViewer-savedViews', JSON.stringify(updated));
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
                      ({view.serverFilter}, {view.levelFilter}, {view.timestampMode}{view.searchTerm ? `, "${view.searchTerm}"` : ''})
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
            <div className="bg-black bg-opacity-30 p-3 rounded border border-purple-600">
              <div className="text-xs text-purple-300 mb-1">Throughput</div>
              <div className="text-2xl font-bold text-white">{logsPerSecond}</div>
              <div className="text-xs text-purple-400">logs/sec</div>
            </div>

            <div className="bg-black bg-opacity-30 p-3 rounded border border-purple-600">
              <div className="text-xs text-purple-300 mb-1">Total Logs</div>
              <div className="text-2xl font-bold text-white">{logs.length.toLocaleString()}</div>
              <div className="text-xs text-purple-400">lines</div>
            </div>

            <div className="bg-black bg-opacity-30 p-3 rounded border border-purple-600">
              <div className="text-xs text-purple-300 mb-1">Filtered</div>
              <div className="text-2xl font-bold text-white">{filteredLogs.length.toLocaleString()}</div>
              <div className="text-xs text-purple-400">
                {logs.length > 0 ? `${Math.round((filteredLogs.length / logs.length) * 100)}%` : '0%'}
              </div>
            </div>

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
                {connectedCount > 0 ? 'connected' : 'disconnected'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* No selections message */}
      {selections.length === 0 && (
        <div className="flex-1 flex items-center justify-center bg-gray-900 text-gray-400">
          <div className="text-center">
            <div className="text-4xl mb-4">📭</div>
            <div className="text-lg">No containers selected</div>
            <div className="text-sm mt-2">Select containers to view merged logs</div>
          </div>
        </div>
      )}

      {/* Log content */}
      {selections.length > 0 && (
        <div
          ref={parentRef}
          className={`flex-1 overflow-auto ${theme === 'dark' ? 'bg-black' : 'bg-gray-50'}`}
          style={{ contain: wrapLines ? 'none' : 'strict' }}
        >
          {wrapLines ? (
            // Wrap mode: Disable virtualization
            <div className="w-full">
              {filteredLogs.map((log, index) => {
                const segments = parseAnsi(log.content);
                const bgColor = log.level ? getLogLevelBgColor(log.level) : '';
                const isHighlighted = highlightedIndex === index;
                const serverBorderColor = getServerBorderColor(log.server as 'prod1' | 'prod2');

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
                      paddingTop: '4px',
                      paddingBottom: '4px',
                    }}
                    className={`px-4 font-mono text-xs border-l-4 ${serverBorderColor} ${
                      theme === 'dark'
                        ? 'text-gray-300 hover:bg-gray-900'
                        : 'text-gray-800 hover:bg-gray-200'
                    }`}
                  >
                    <span
                      className={`mr-2 cursor-pointer select-none ${
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
                      className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold mr-2 ${getServerBadgeColor(log.server as 'prod1' | 'prod2')}`}
                    >
                      {log.server}
                    </span>
                    <span
                      className={theme === 'dark' ? 'text-gray-500 mr-2' : 'text-gray-500 mr-2'}
                      title={formatFullTimestamp(log.timestamp)}
                    >
                      [{formatTimestamp(log.timestamp, timestampMode)}]
                    </span>
                    <span className="text-gray-400 mr-2">{log.container}:</span>
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
            // Truncate mode: Use virtual scrolling
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
                const serverBorderColor = getServerBorderColor(log.server as 'prod1' | 'prod2');

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
                    }}
                    className={`px-4 font-mono text-xs border-l-4 ${serverBorderColor} ${
                      theme === 'dark'
                        ? 'text-gray-300 hover:bg-gray-900'
                        : 'text-gray-800 hover:bg-gray-200'
                    }`}
                  >
                    <span
                      className={`mr-2 cursor-pointer select-none ${
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
                      className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold mr-2 ${getServerBadgeColor(log.server as 'prod1' | 'prod2')}`}
                    >
                      {log.server}
                    </span>
                    <span
                      className={theme === 'dark' ? 'text-gray-500 mr-2' : 'text-gray-500 mr-2'}
                      title={formatFullTimestamp(log.timestamp)}
                    >
                      [{formatTimestamp(log.timestamp, timestampMode)}]
                    </span>
                    <span className="text-gray-400 mr-2">{log.container}:</span>
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
      )}

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
