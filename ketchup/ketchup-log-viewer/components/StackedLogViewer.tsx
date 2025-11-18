/**
 * StackedLogViewer Component
 * Displays logs from multiple containers in stacked sections with maximize/minimize controls
 */

'use client';

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import LogViewer from '@/components/LogViewer';
import AlertPanel from '@/components/AlertPanel';
import { getAlertManager } from '@/lib/alert-manager';

interface ContainerSelection {
  container: string;
  server: 'prod1' | 'prod2';
}

interface StackedLogViewerProps {
  selections: ContainerSelection[];
  theme: 'dark' | 'light';
}

interface SectionState {
  selectionKey: string;
  isMinimized: boolean;
  height: number; // percentage
}

export default function StackedLogViewer({
  selections,
  theme,
}: StackedLogViewerProps) {
  const [maximizedKey, setMaximizedKey] = useState<string | null>(null);
  const [sectionStates, setSectionStates] = useState<Map<string, SectionState>>(new Map());
  const [resizing, setResizing] = useState<{ key: string; startY: number; startHeight: number } | null>(null);
  const [showAlertPanel, setShowAlertPanel] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const alertManager = useMemo(() => getAlertManager(), []);

  // Generate unique key for selection
  const getSelectionKey = (selection: ContainerSelection) => `${selection.server}-${selection.container}`;

  // Initialize section states when selections change
  useEffect(() => {
    setSectionStates((prevStates) => {
      const newStates = new Map<string, SectionState>();
      const defaultHeight = 100 / selections.length; // Equal height distribution

      selections.forEach((selection) => {
        const key = getSelectionKey(selection);
        const existing = prevStates.get(key);

        if (existing) {
          newStates.set(key, existing);
        } else {
          newStates.set(key, {
            selectionKey: key,
            isMinimized: false,
            height: defaultHeight,
          });
        }
      });

      return newStates;
    });
  }, [selections]);

  // Handle maximize/restore
  const toggleMaximize = useCallback((key: string) => {
    setMaximizedKey((prev) => (prev === key ? null : key));
  }, []);

  // Handle minimize
  const toggleMinimize = useCallback((key: string) => {
    setSectionStates((prev) => {
      const newStates = new Map(prev);
      const state = newStates.get(key);
      if (state) {
        newStates.set(key, {
          ...state,
          isMinimized: !state.isMinimized,
        });
      }
      return newStates;
    });
  }, []);

  // Handle close (remove from selections)
  const handleClose = useCallback((selection: ContainerSelection) => {
    // This would need to be passed up to parent to actually remove
    // For now, just minimize it
    toggleMinimize(getSelectionKey(selection));
  }, [toggleMinimize]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Escape to restore from maximized
      if (e.key === 'Escape' && maximizedKey) {
        setMaximizedKey(null);
        e.preventDefault();
      }

      // Ctrl+M to toggle maximize for first visible container
      if (e.ctrlKey && e.key === 'm') {
        const firstKey = selections.length > 0 ? getSelectionKey(selections[0]) : null;
        if (firstKey) {
          toggleMaximize(firstKey);
        }
        e.preventDefault();
      }

      // Ctrl+1/2/3 to maximize specific container
      if (e.ctrlKey && /^[1-9]$/.test(e.key)) {
        const index = parseInt(e.key) - 1;
        if (index < selections.length) {
          const key = getSelectionKey(selections[index]);
          toggleMaximize(key);
        }
        e.preventDefault();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [maximizedKey, selections, toggleMaximize]);

  // Handle mouse resize start
  const handleResizeStart = (key: string, e: React.MouseEvent) => {
    const state = sectionStates.get(key);
    if (state) {
      setResizing({
        key,
        startY: e.clientY,
        startHeight: state.height,
      });
      e.preventDefault();
    }
  };

  // Handle mouse move during resize
  useEffect(() => {
    if (!resizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;

      const containerHeight = containerRef.current.offsetHeight;
      const deltaY = e.clientY - resizing.startY;
      const deltaPercent = (deltaY / containerHeight) * 100;
      const newHeight = Math.max(5, Math.min(95, resizing.startHeight + deltaPercent));

      setSectionStates((prev) => {
        const newStates = new Map(prev);
        const state = newStates.get(resizing.key);
        if (state) {
          newStates.set(resizing.key, {
            ...state,
            height: newHeight,
          });
        }
        return newStates;
      });
    };

    const handleMouseUp = () => {
      setResizing(null);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [resizing]);

  // Server badge colors
  const getServerBadgeColor = (server: 'prod1' | 'prod2') => {
    return server === 'prod1'
      ? 'bg-blue-500/20 text-blue-400 border-blue-500/40'
      : 'bg-green-500/20 text-green-400 border-green-500/40';
  };

  if (selections.length === 0) {
    return (
      <div className={`flex items-center justify-center h-full ${theme === 'dark' ? 'text-gray-500' : 'text-gray-400'}`}>
        <div className="text-center">
          <p className="text-lg">No containers selected</p>
          <p className="mt-2 text-sm">Select containers to view logs</p>
        </div>
      </div>
    );
  }

  const selectedContainers = selections.map(s => s.container);
  const selectedServers = Array.from(new Set(selections.map(s => s.server))) as ('prod1' | 'prod2')[];

  return (
    <div ref={containerRef} className="h-full flex flex-col">
      {/* Alert Toggle Button */}
      <div className={`flex justify-end px-4 py-2 border-b ${
        theme === 'dark' ? 'bg-gray-800 border-gray-700' : 'bg-gray-100 border-gray-200'
      }`}>
        <button
          onClick={() => setShowAlertPanel(!showAlertPanel)}
          className={`px-3 py-1 text-xs rounded border ${
            theme === 'dark'
              ? 'bg-gray-700 hover:bg-gray-600 text-gray-300 border-gray-600'
              : 'bg-white hover:bg-gray-50 text-gray-700 border-gray-300'
          }`}
          title="Toggle alerts"
        >
          🔔 Alerts
        </button>
      </div>

      {selections.map((selection, index) => {
        const key = getSelectionKey(selection);
        const state = sectionStates.get(key);
        const isMaximized = maximizedKey === key;
        const isMinimized = state?.isMinimized || false;
        const isHidden = maximizedKey && maximizedKey !== key;

        if (isHidden) return null;

        const height = isMaximized ? '100%' : isMinimized ? 'auto' : `${state?.height || 33}%`;

        return (
          <div
            key={key}
            className={`flex flex-col ${isMinimized ? '' : 'min-h-0'}`}
            style={{
              height,
              transition: resizing ? 'none' : 'height 0.3s ease',
            }}
          >
            {/* Header */}
            <div className={`flex items-center justify-between px-4 py-2 border-b ${
              theme === 'dark' ? 'bg-gray-800 border-gray-700' : 'bg-gray-100 border-gray-200'
            }`}>
              <div className="flex items-center gap-3">
                {/* Server Badge */}
                <div className={`px-2 py-1 rounded text-xs font-bold border ${getServerBadgeColor(selection.server)}`}>
                  {selection.server}
                </div>
                {/* Container Name */}
                <span className={`font-mono text-sm font-bold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                  {selection.container.replace('ketchup-', '')}
                </span>
              </div>

              {/* Controls */}
              <div className="flex items-center gap-2">
                {/* Maximize/Restore Button */}
                <button
                  onClick={() => toggleMaximize(key)}
                  className={`px-2 py-1 text-xs rounded border transition-colors ${
                    theme === 'dark'
                      ? 'bg-gray-700 hover:bg-gray-600 text-gray-300 border-gray-600'
                      : 'bg-white hover:bg-gray-50 text-gray-700 border-gray-300'
                  }`}
                  title={isMaximized ? 'Restore (Escape)' : 'Maximize (Ctrl+M)'}
                >
                  {isMaximized ? '▼' : '▢'}
                </button>

                {/* Minimize Button */}
                <button
                  onClick={() => toggleMinimize(key)}
                  className={`px-2 py-1 text-xs rounded border transition-colors ${
                    theme === 'dark'
                      ? 'bg-gray-700 hover:bg-gray-600 text-gray-300 border-gray-600'
                      : 'bg-white hover:bg-gray-50 text-gray-700 border-gray-300'
                  }`}
                  title={isMinimized ? 'Expand' : 'Minimize'}
                >
                  {isMinimized ? '▲' : '─'}
                </button>

                {/* Close Button */}
                <button
                  onClick={() => handleClose(selection)}
                  className={`px-2 py-1 text-xs rounded border transition-colors ${
                    theme === 'dark'
                      ? 'bg-red-700 hover:bg-red-600 text-red-200 border-red-600'
                      : 'bg-red-50 hover:bg-red-100 text-red-700 border-red-300'
                  }`}
                  title="Close"
                >
                  ×
                </button>
              </div>
            </div>

            {/* Content Area */}
            {!isMinimized && (
              <div className="flex-1 min-h-0">
                <LogViewer
                  container={selection.container}
                  server={selection.server}
                  autoScroll={true}
                  theme={theme}
                />
              </div>
            )}

            {/* Resizable Divider */}
            {!isMaximized && !isMinimized && index < selections.length - 1 && (
              <div
                className={`h-1 cursor-ns-resize ${
                  theme === 'dark' ? 'bg-gray-700 hover:bg-cyan-500' : 'bg-gray-300 hover:bg-blue-500'
                } transition-colors`}
                onMouseDown={(e) => handleResizeStart(key, e)}
                title="Drag to resize"
              />
            )}
          </div>
        );
      })}

      {/* Keyboard shortcuts hint */}
      {selections.length > 0 && (
        <div className={`absolute bottom-4 right-4 px-3 py-2 rounded-lg text-xs ${
          theme === 'dark' ? 'bg-gray-800 text-gray-400 border border-gray-700' : 'bg-white text-gray-600 border border-gray-300'
        } opacity-0 hover:opacity-100 transition-opacity`}>
          <div>💡 Shortcuts:</div>
          <div>Ctrl+M: Toggle maximize</div>
          <div>Escape: Restore</div>
          <div>Ctrl+1/2/3: Jump to container</div>
        </div>
      )}

      {/* Alert Panel Modal */}
      {showAlertPanel && (
        <AlertPanel
          theme={theme}
          containers={selectedContainers}
          servers={selectedServers}
          onClose={() => setShowAlertPanel(false)}
        />
      )}
    </div>
  );
}
