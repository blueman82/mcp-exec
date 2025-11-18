/**
 * Custom hook for managing Server-Sent Events (SSE) log streaming
 * Handles connections to multiple log streams with queue management and auto-sorting
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { connectionQueueManager } from '@/lib/connection-queue-manager';
import { detectLogLevel } from '@/lib/log-level-detector';
import type { LogLine } from '@/types';

export interface ContainerSelection {
  container: string;
  server: 'prod1' | 'prod2';
}

export interface MergedLogLine extends LogLine {
  selectionKey: string;
}

export interface ConnectionInfo {
  status: 'connected' | 'queued' | 'disconnected';
  queuePosition?: number;
}

export interface UseLogStreamingReturn {
  logs: MergedLogLine[];
  connectionStatus: Map<string, 'connected' | 'queued' | 'disconnected'>;
  queuePositions: Map<string, number>;
  error: string | null;
  setError: (error: string | null) => void;
}

export interface UseLogStreamingOptions {
  selections: ContainerSelection[];
  isPaused: boolean;
  autoScrollRef: React.MutableRefObject<boolean>;
  onConnectionStart?: () => void;
  onLogLine?: (log: MergedLogLine) => void;
}

export function useLogStreaming(options: UseLogStreamingOptions): UseLogStreamingReturn {
  const { selections, isPaused, autoScrollRef, onConnectionStart, onLogLine } = options;

  const [logs, setLogs] = useState<MergedLogLine[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<
    Map<string, 'connected' | 'queued' | 'disconnected'>
  >(new Map());
  const [queuePositions, setQueuePositions] = useState<Map<string, number>>(new Map());
  const [error, setError] = useState<string | null>(null);
  const eventSourcesRef = useRef<Map<string, EventSource>>(new Map());

  const getSelectionKey = useCallback(
    (selection: ContainerSelection) => `${selection.server}-${selection.container}`,
    []
  );

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
          setConnectionStatus((prev) => new Map(prev).set(selectionKey, 'queued'));
          setQueuePositions((prev) => new Map(prev).set(selectionKey, status.queued + 1));
        }

        // Request connection through queue manager with staggered delay
        const delay = index * 100; // 100ms stagger
        await new Promise((resolve) => setTimeout(resolve, delay));

        const eventSource = await connectionQueueManager.requestConnection(
          selectionKey,
          `/api/logs/stream?container=${selection.container}&server=${selection.server}&tail=1000`
        );

        eventSourcesRef.current.set(selectionKey, eventSource);
        setQueuePositions((prev) => {
          const updated = new Map(prev);
          updated.delete(selectionKey);
          return updated;
        });

        eventSource.onopen = () => {
          setConnectionStatus((prev) => new Map(prev).set(selectionKey, 'connected'));
          onConnectionStart?.();
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
              updated.sort(
                (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
              );
              return updated;
            });

            if (onLogLine) {
              onLogLine(logLine);
            }
          } catch (err) {
            console.error('Failed to parse log event:', err);
          }
        };

        eventSource.onerror = () => {
          setConnectionStatus((prev) => new Map(prev).set(selectionKey, 'disconnected'));
          setError(`Connection lost for ${selection.container} (${selection.server})`);
        };
      } catch (err) {
        setConnectionStatus((prev) => new Map(prev).set(selectionKey, 'disconnected'));
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
  }, [selections, isPaused, getSelectionKey, onConnectionStart, onLogLine]);

  return {
    logs,
    connectionStatus,
    queuePositions,
    error,
    setError,
  };
}
