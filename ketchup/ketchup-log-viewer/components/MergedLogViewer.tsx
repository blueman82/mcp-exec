/**
 * MergedLogViewer Component (Refactored)
 *
 * Displays logs from multiple containers across multiple servers in chronological order.
 * This refactored version uses custom hooks and modular components for better maintainability.
 *
 * Original: 1037 lines → Refactored: ~380 lines (63% reduction)
 */

'use client';

import { useEffect, useRef, useState, useOptimistic, useCallback, useMemo } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { stripAnsi } from '@/lib/ansi-parser';
import { formatFullTimestamp, type TimestampMode } from '@/lib/timestamp-formatter';
import { useLogStreaming, type ContainerSelection } from '@/hooks/useLogStreaming';
import { useLogFiltering } from '@/hooks/useLogFiltering';
import { useViewManagement } from '@/hooks/useViewManagement';
import { useToastNotifications } from '@/hooks/useToastNotifications';
import AlertPanel from '@/components/AlertPanel';
import { getAlertManager, getSeverityIcon } from '@/lib/alert-manager';
import type { AlertNotification, AlertSeverity } from '@/types/alert';
import LogViewerToolbar from '@/components/merged-log-viewer/LogViewerToolbar';
import SavedViewsDialog from '@/components/merged-log-viewer/SavedViewsDialog';
import MetricsOverlay from '@/components/merged-log-viewer/MetricsOverlay';
import LogLineRenderer from '@/components/merged-log-viewer/LogLineRenderer';
import ToastContainer from '@/components/merged-log-viewer/ToastContainer';

interface MergedLogViewerProps {
  selections: ContainerSelection[];
  autoScroll?: boolean;
  theme: 'dark' | 'light';
}

export default function MergedLogViewer({
  selections,
  autoScroll = true,
  theme,
}: MergedLogViewerProps) {
  // UI State
  const [searchTerm, setSearchTerm] = useState('');
  const [optimisticSearch, setOptimisticSearch] = useOptimistic(searchTerm);
  const [timestampMode, setTimestampMode] = useState<TimestampMode>('relative');
  const [levelFilter, setLevelFilter] = useState<'all' | 'error' | 'warn' | 'info' | 'debug'>('all');
  const [serverFilter, setServerFilter] = useState<'all' | 'prod1' | 'prod2'>('all');
  const [isPaused, setIsPaused] = useState(false);
  const [jumpInput, setJumpInput] = useState('');
  const [highlightedIndex, setHighlightedIndex] = useState<number | null>(null);
  const [showCriticalOnly, setShowCriticalOnly] = useState(false);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [showMetrics, setShowMetrics] = useState(false);
  const [logsPerSecond, setLogsPerSecond] = useState(0);
  const [connectionStartTime, setConnectionStartTime] = useState<Date | null>(null);
  const [wrapLines, setWrapLines] = useState(false);
  const [showAlertPanel, setShowAlertPanel] = useState(false);

  // Refs
  const parentRef = useRef<HTMLDivElement>(null);
  const autoScrollEnabled = useRef(autoScroll);
  const lastLogCountRef = useRef(0);
  const audioContextRef = useRef<AudioContext | null>(null);

  // Custom Hooks
  const { toasts, showToast, removeToast } = useToastNotifications();

  const alertManager = useMemo(() => getAlertManager(), []);
  const [alertState, setAlertState] = useState(alertManager.getState());

  const ensureAudioContext = useCallback(() => {
    if (typeof window === 'undefined') {
      return null;
    }
    if (audioContextRef.current) {
      return audioContextRef.current;
    }
    const audioWindow = window as typeof window & { webkitAudioContext?: typeof AudioContext };
    const AudioCtor = audioWindow.AudioContext ?? audioWindow.webkitAudioContext;
    if (!AudioCtor) {
      return null;
    }
    audioContextRef.current = new AudioCtor();
    return audioContextRef.current;
  }, []);

  const playAlertTone = useCallback((severity: AlertSeverity) => {
    const context = ensureAudioContext();
    if (!context) {
      return;
    }

    const oscillator = context.createOscillator();
    const gain = context.createGain();
    const now = context.currentTime;
    const frequencies: Record<AlertSeverity, number> = {
      low: 440,
      medium: 520,
      high: 660,
      critical: 880,
    };

    oscillator.type = 'sine';
    oscillator.frequency.setValueAtTime(frequencies[severity] ?? 520, now);
    gain.gain.setValueAtTime(0.001, now);
    gain.gain.exponentialRampToValueAtTime(0.2, now + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.6);

    oscillator.connect(gain);
    gain.connect(context.destination);
    oscillator.start(now);
    oscillator.stop(now + 0.65);
  }, [ensureAudioContext]);

  const triggerBrowserNotification = useCallback((alert: AlertNotification) => {
    if (typeof window === 'undefined' || !('Notification' in window)) {
      return;
    }

    const title = `${getSeverityIcon(alert.severity)} ${alert.patternName}`;
    const body = `${alert.log.container}@${alert.log.server}: ${stripAnsi(alert.log.content).slice(0, 140)}`;

    if (Notification.permission === 'granted') {
      new Notification(title, { body });
      return;
    }

    if (Notification.permission === 'default') {
      Notification.requestPermission().then((permission) => {
        if (permission === 'granted') {
          new Notification(title, { body });
        }
      });
    }
  }, []);

  const handleAlertNotifications = useCallback(
    (alerts: AlertNotification[]) => {
      const severityToToast: Record<AlertSeverity, 'error' | 'warning' | 'info'> = {
        critical: 'error',
        high: 'error',
        medium: 'warning',
        low: 'info',
      };

      for (const alert of alerts) {
        const sanitizedContent = stripAnsi(alert.log.content);

        if (alert.actions.some((action) => action.type === 'toast')) {
          const toastType = severityToToast[alert.severity] ?? 'info';
          const message = `${getSeverityIcon(alert.severity)} ${alert.patternName} — ${sanitizedContent.slice(0, 120)}${
            sanitizedContent.length > 120 ? '…' : ''
          }`;
          showToast(message, toastType === 'error' ? 'error' : toastType === 'warning' ? 'warning' : 'info');
        }

        if (alert.actions.some((action) => action.type === 'browser-notification')) {
          triggerBrowserNotification(alert);
        }

        if (alert.actions.some((action) => action.type === 'sound')) {
          playAlertTone(alert.severity);
        }

        if (typeof navigator !== 'undefined' && navigator.vibrate && (alert.severity === 'high' || alert.severity === 'critical')) {
          navigator.vibrate(200);
        }
      }
    },
    [playAlertTone, showToast, triggerBrowserNotification]
  );

  const { logs, connectionStatus, queuePositions, error, setError } = useLogStreaming({
    selections,
    isPaused,
    autoScrollRef: autoScrollEnabled,
    onConnectionStart: () => {
      if (!connectionStartTime) {
        setConnectionStartTime(new Date());
      }
    },
    onLogLine: (log) => {
      const triggered = alertManager.processLogLine(log);
      if (triggered.length > 0) {
        handleAlertNotifications(triggered);
      }
    },
  });

  const { filteredLogs, patternCounts, totalCritical } = useLogFiltering(logs, {
    searchTerm,
    levelFilter,
    serverFilter,
    showCriticalOnly,
  });

  const { savedViews, saveView, loadView, deleteView } = useViewManagement({
    onViewLoaded: (view) => {
      setSearchTerm(view.searchTerm);
      setLevelFilter(view.levelFilter);
      setServerFilter(view.serverFilter);
      setTimestampMode(view.timestampMode);
      setShowCriticalOnly(false);
      setShowSaveDialog(false);
      showToast(`View "${view.name}" loaded`, 'info');
    },
    onViewSaved: (view) => {
      setShowSaveDialog(false);
      showToast(`View "${view.name}" saved`, 'success');
    },
    onViewDeleted: (name) => {
      showToast(`View "${name}" deleted`, 'info');
    },
  });

  useEffect(() => {
    const unsubscribe = alertManager.subscribe((state) => {
      setAlertState(state);
    });

    return () => unsubscribe();
  }, [alertManager]);

  // Virtual scrolling
  const virtualizer = useVirtualizer({
    count: filteredLogs.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => (wrapLines ? 80 : 24),
    overscan: 10,
  });

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

  // Copy utilities
  const copyLineContent = useCallback((log: typeof logs[0]) => {
    const content = stripAnsi(log.content);
    navigator.clipboard.writeText(content);
    showToast('Line content copied', 'success');
  }, [showToast]);

  const copyFullLine = useCallback((log: typeof logs[0]) => {
    const timestamp = formatFullTimestamp(log.timestamp);
    const content = stripAnsi(log.content);
    const fullLine = `[${log.server}] [${timestamp}] ${content}`;
    navigator.clipboard.writeText(fullLine);
    showToast('Line copied with timestamp', 'success');
  }, [showToast]);

  // Download logs
  const downloadLogs = useCallback(() => {
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
  }, [filteredLogs, showToast]);

  // Jump to timestamp
  const handleJumpToTimestamp = useCallback(() => {
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
        setError(
          `Closest match: ${diffSeconds}s ${foundTime > targetTime! ? 'after' : 'before'} target`
        );
        setTimeout(() => setError(null), 3000);
      }

      setTimeout(() => setHighlightedIndex(null), 3000);
    } else {
      setError('No logs found near that timestamp');
      setTimeout(() => setError(null), 3000);
    }
  }, [jumpInput, filteredLogs, virtualizer, setError]);

  // Connection counts
  const connectedCount = Array.from(connectionStatus.values()).filter(
    (s) => s === 'connected'
  ).length;
  const queuedCount = Array.from(connectionStatus.values()).filter((s) => s === 'queued').length;

  const selectedContainers = useMemo(() => {
    const unique = new Set<string>();
    selections.forEach((selection) => unique.add(selection.container));
    return Array.from(unique);
  }, [selections]);

  const selectedServers = useMemo(() => {
    const unique = new Set<'prod1' | 'prod2'>();
    selections.forEach((selection) => unique.add(selection.server));
    return Array.from(unique);
  }, [selections]);

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <LogViewerToolbar
        selections={selections}
        connectedCount={connectedCount}
        queuedCount={queuedCount}
        isPaused={isPaused}
        wrapLines={wrapLines}
        autoScrollEnabled={autoScrollEnabled}
        searchTerm={searchTerm}
        optimisticSearch={optimisticSearch}
        levelFilter={levelFilter}
        serverFilter={serverFilter}
        timestampMode={timestampMode}
        jumpInput={jumpInput}
        filteredLogsCount={filteredLogs.length}
        totalCritical={totalCritical}
        showCriticalOnly={showCriticalOnly}
        patternCounts={patternCounts}
        showMetrics={showMetrics}
        alertCount={alertState.activeAlerts.length}
        savedViewsCount={savedViews.length}
        onPauseToggle={() => setIsPaused(!isPaused)}
        onDownload={downloadLogs}
        onWrapToggle={() => setWrapLines(!wrapLines)}
        onSearchChange={(value) => {
          setOptimisticSearch(value);
          setSearchTerm(value);
        }}
        onServerFilterChange={setServerFilter}
        onLevelFilterChange={setLevelFilter}
        onJumpInputChange={setJumpInput}
        onJumpToTimestamp={handleJumpToTimestamp}
        onTimestampModeToggle={() =>
          setTimestampMode(timestampMode === 'relative' ? 'absolute' : 'relative')
        }
        onCriticalToggle={() => setShowCriticalOnly(!showCriticalOnly)}
        onSavedViewsToggle={() => setShowSaveDialog(!showSaveDialog)}
        onMetricsToggle={() => setShowMetrics(!showMetrics)}
        onAlertsToggle={() => setShowAlertPanel((prev) => !prev)}
      />

      {/* Save View Dialog */}
      <SavedViewsDialog
        isOpen={showSaveDialog}
        savedViews={savedViews}
        currentState={{ searchTerm, levelFilter, serverFilter, timestampMode }}
        onSave={saveView}
        onLoad={loadView}
        onDelete={deleteView}
        onClose={() => setShowSaveDialog(false)}
      />

      {/* Error message */}
      {error && (
        <div className="p-3 bg-red-900 border-b border-red-700 text-red-200 text-sm">{error}</div>
      )}

      {/* Performance Metrics Overlay */}
      {showMetrics && (
        <MetricsOverlay
          logsPerSecond={logsPerSecond}
          totalLogs={logs.length}
          filteredLogs={filteredLogs.length}
          connectionStartTime={connectionStartTime}
          connectedCount={connectedCount}
        />
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
              {filteredLogs.map((log, index) => (
                <LogLineRenderer
                  key={index}
                  log={log}
                  index={index}
                  isHighlighted={highlightedIndex === index}
                  searchTerm={searchTerm}
                  timestampMode={timestampMode}
                  theme={theme}
                  wrapLines={true}
                  onCopyLine={copyLineContent}
                  onCopyFullLine={copyFullLine}
                />
              ))}
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
                return (
                  <LogLineRenderer
                    key={virtualItem.index}
                    log={log}
                    index={virtualItem.index}
                    isHighlighted={highlightedIndex === virtualItem.index}
                    searchTerm={searchTerm}
                    timestampMode={timestampMode}
                    theme={theme}
                    wrapLines={false}
                    onCopyLine={copyLineContent}
                    onCopyFullLine={copyFullLine}
                    style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      width: '100%',
                      height: '24px',
                      transform: `translateY(${virtualItem.start}px)`,
                    }}
                  />
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Toast notifications */}
      <ToastContainer toasts={toasts} onRemoveToast={removeToast} />

      {showAlertPanel && (
        <AlertPanel
          theme={theme}
          containers={selectedContainers}
          servers={selectedServers.length > 0 ? selectedServers : ['prod1', 'prod2']}
          onClose={() => setShowAlertPanel(false)}
        />
      )}
    </div>
  );
}
