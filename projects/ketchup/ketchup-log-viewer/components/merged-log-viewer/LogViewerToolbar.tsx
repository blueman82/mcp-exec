/**
 * LogViewerToolbar Component
 * Main toolbar with filters, search, controls, and metrics for MergedLogViewer
 */

'use client';

import React, { useTransition } from 'react';
import type { TimestampMode } from '@/lib/timestamp-formatter';

interface LogViewerToolbarProps {
  // Connection state
  selections: Array<{ container: string; server: 'prod1' | 'prod2' }>;
  connectedCount: number;
  queuedCount: number;

  // Control state
  isPaused: boolean;
  wrapLines: boolean;
  autoScrollEnabled: React.MutableRefObject<boolean>;

  // Filter state
  searchTerm: string;
  optimisticSearch: string;
  levelFilter: 'all' | 'error' | 'warn' | 'info' | 'debug';
  serverFilter: 'all' | 'prod1' | 'prod2';
  timestampMode: TimestampMode;

  // Jump to timestamp
  jumpInput: string;

  // Metrics
  filteredLogsCount: number;
  totalCritical: number;
  showCriticalOnly: boolean;
  patternCounts: Record<string, number>;
  showMetrics: boolean;
  alertCount: number;
  savedViewsCount: number;

  // Callbacks
  onPauseToggle: () => void;
  onDownload: () => void;
  onWrapToggle: () => void;
  onSearchChange: (value: string) => void;
  onServerFilterChange: (filter: 'all' | 'prod1' | 'prod2') => void;
  onLevelFilterChange: (filter: 'all' | 'error' | 'warn' | 'info' | 'debug') => void;
  onJumpInputChange: (value: string) => void;
  onJumpToTimestamp: () => void;
  onTimestampModeToggle: () => void;
  onCriticalToggle: () => void;
  onSavedViewsToggle: () => void;
  onMetricsToggle: () => void;
  onAlertsToggle: () => void;
}

const LogViewerToolbar: React.FC<LogViewerToolbarProps> = ({
  selections,
  connectedCount,
  queuedCount,
  isPaused,
  wrapLines,
  autoScrollEnabled,
  searchTerm,
  optimisticSearch,
  levelFilter,
  serverFilter,
  timestampMode,
  jumpInput,
  filteredLogsCount,
  totalCritical,
  showCriticalOnly,
  patternCounts,
  showMetrics,
  alertCount,
  savedViewsCount,
  onPauseToggle,
  onDownload,
  onWrapToggle,
  onSearchChange,
  onServerFilterChange,
  onLevelFilterChange,
  onJumpInputChange,
  onJumpToTimestamp,
  onTimestampModeToggle,
  onCriticalToggle,
  onSavedViewsToggle,
  onMetricsToggle,
  onAlertsToggle,
}) => {
  const [isPending, startTransition] = useTransition();

  return (
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
          onClick={onPauseToggle}
          className="px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded border border-gray-600"
          title={isPaused ? 'Resume streaming' : 'Pause streaming'}
        >
          {isPaused ? '▶️ Resume' : '⏸️ Pause'}
        </button>
        <button
          onClick={onDownload}
          className="px-3 py-1 text-xs bg-green-700 hover:bg-green-600 text-white rounded border border-green-600"
          title="Download logs as text file"
        >
          💾 Download
        </button>
        <button
          onClick={onWrapToggle}
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
              onClick={() => onServerFilterChange(server)}
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
              onClick={() => onLevelFilterChange(level)}
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
            startTransition(() => {
              onSearchChange(value);
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
            onChange={(e) => onJumpInputChange(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && onJumpToTimestamp()}
            className="px-3 py-1 text-sm bg-gray-900 border border-gray-600 rounded text-gray-300 focus:outline-none focus:border-purple-500 w-36"
          />
          <button
            onClick={onJumpToTimestamp}
            className="px-2 py-1 text-xs bg-purple-700 hover:bg-purple-600 text-white rounded border border-purple-600"
            title="Jump to timestamp"
          >
            🎯
          </button>
        </div>

        {/* Timestamp toggle */}
        <button
          onClick={onTimestampModeToggle}
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
        <span className="text-xs text-gray-500">{filteredLogsCount} lines</span>

        {/* Pattern alerts badge */}
        {totalCritical > 0 && (
          <button
            onClick={onCriticalToggle}
            className={`flex items-center space-x-1 px-2 py-1 rounded border transition-colors ${
              showCriticalOnly
                ? 'bg-red-700 border-red-600 ring-2 ring-red-400'
                : 'bg-red-600 border-red-500 hover:bg-red-700'
            }`}
            title={`${
              showCriticalOnly ? 'Click to show all logs' : 'Click to filter critical patterns only'
            }\n\nCritical patterns found:\n${Object.entries(patternCounts)
              .map(([pattern, count]) => `${pattern}: ${count}`)
              .join('\n')}`}
          >
            <span className="text-xs font-bold text-white">⚠️ {totalCritical}</span>
          </button>
        )}

        {/* Saved Views Button */}
        <button
          onClick={onSavedViewsToggle}
          className="px-3 py-1 text-xs bg-blue-700 hover:bg-blue-600 text-white rounded border border-blue-600"
          title="Save/Load Views"
        >
          💾 Views {savedViewsCount > 0 && `(${savedViewsCount})`}
        </button>

        <button
          onClick={onAlertsToggle}
          className={`px-3 py-1 text-xs rounded border transition-colors flex items-center space-x-2 ${
            alertCount > 0
              ? 'bg-red-700 border-red-600 text-white animate-pulse'
              : 'bg-gray-700 border-gray-600 text-gray-300 hover:bg-gray-600'
          }`}
          title={
            alertCount > 0
              ? `View active alerts (${alertCount})`
              : 'Configure alert patterns'
          }
        >
          <span>🛎️ Alerts</span>
          {alertCount > 0 && <span className="text-xs font-bold">{alertCount}</span>}
        </button>

        {/* Performance Metrics Toggle */}
        <button
          onClick={onMetricsToggle}
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
  );
};

export default LogViewerToolbar;
