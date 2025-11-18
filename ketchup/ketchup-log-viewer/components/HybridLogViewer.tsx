/**
 * HybridLogViewer Component (Refactored)
 *
 * Displays search results alongside full log context in a resizable two-panel layout.
 * Features synchronized scrolling, virtual scrolling, and result highlighting.
 *
 * WCAG 2.1 AA compliant with comprehensive accessibility features.
 *
 * This is a refactored version that uses extracted custom hooks and components
 * to reduce complexity and improve maintainability.
 */

'use client';

import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import EnhancedSearch from '@/components/EnhancedSearch';
import AlertPanel from '@/components/AlertPanel';
import { getSearchManager } from '@/lib/search-manager';
import { createSearchHighlighter } from '@/lib/search-highlighter';
import { createSearchGrouper } from '@/lib/search-grouper';
import { getAlertManager } from '@/lib/alert-manager';
import SearchControls from '@/components/hybrid-log-viewer/SearchControls';
import ResultsList from '@/components/hybrid-log-viewer/ResultsList';
import ContextPanel from '@/components/hybrid-log-viewer/ContextPanel';
import { useAccessibility } from '@/hooks/useAccessibility';
import { usePanelResize } from '@/hooks/usePanelResize';
import { useSearchResults } from '@/hooks/useSearchResults';
import type { LogLine } from '@/types';

interface ContainerSelection {
  container: string;
  server: 'prod1' | 'prod2';
}

interface HybridLogViewerProps {
  selections: ContainerSelection[];
  theme: 'dark' | 'light';
}

const HybridLogViewer: React.FC<HybridLogViewerProps> = ({ selections, theme }) => {
  // State management
  const [allLogs, setAllLogs] = useState<LogLine[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [availableContainers, setAvailableContainers] = useState<string[]>([]);
  const [focusedResultIndex, setFocusedResultIndex] = useState(-1);
  const [showGroupingControls, setShowGroupingControls] = useState(false);
  const [showHighlightControls, setShowHighlightControls] = useState(true);
  const [showAlertPanel, setShowAlertPanel] = useState(false);
  const alertManager = useMemo(() => getAlertManager(), []);

  // Context configuration with localStorage persistence
  const [contextSize, setContextSize] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('hybrid-log-viewer-context-size');
      return saved ? parseInt(saved, 10) : 5;
    }
    return 5;
  });

  // Refs
  const containerRef = useRef<HTMLDivElement>(null);
  const resultsContainerRef = useRef<HTMLDivElement>(null);
  const contextContainerRef = useRef<HTMLDivElement>(null);

  // Initialize managers
  const searchManager = useMemo(() => getSearchManager(), []);
  const searchHighlighter = useMemo(
    () => createSearchHighlighter({ theme, enableAnimations: true }),
    [theme]
  );
  const searchGrouper = useMemo(() => createSearchGrouper({ persistPreferences: true }), []);

  // Custom hooks
  const { announcementLiveRef, announceToScreenReader } = useAccessibility();

  const {
    panelDimensions,
    isResizing,
    panelResizeValue,
    resizeHandleRef,
    handleResizeStart,
    handleResizeKeyDown,
  } = usePanelResize({
    initialLeftWidth: 30,
    onResize: (dimensions) => {
      announceToScreenReader(
        `Left panel: ${dimensions.leftWidth}%, Right panel: ${dimensions.rightWidth}%`
      );
    },
    onResizeComplete: (dimensions) => {
      announceToScreenReader(
        `Panel resize complete. Left panel: ${dimensions.leftWidth}%, Right panel: ${dimensions.rightWidth}%`
      );
    },
  });

  const {
    searchResults,
    selectedMatchId,
    expandedResults,
    groupedResults,
    highlightNavigation,
    handleSearchResults,
    setSelectedMatchId,
    toggleResultExpansion,
    navigateToNextHighlight,
    navigateToPreviousHighlight,
    updateGrouping,
    updateSorting,
    applyHighlights,
  } = useSearchResults({
    searchHighlighter,
    searchGrouper,
    contextContainerRef,
    onAnnounce: announceToScreenReader,
  });

  // Save context size to localStorage
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('hybrid-log-viewer-context-size', contextSize.toString());
    }
  }, [contextSize]);

  // Update highlighter when theme changes
  useEffect(() => {
    searchHighlighter.updateTheme(theme);
  }, [theme, searchHighlighter]);

  // Cleanup highlighter on unmount
  useEffect(() => {
    return () => {
      searchHighlighter.destroy();
    };
  }, [searchHighlighter]);

  // Load logs from selected containers
  useEffect(() => {
    const loadLogs = async () => {
      setIsLoading(true);
      try {
        const logs: LogLine[] = [];
        const containers = new Set<string>();

        for (const selection of selections) {
          containers.add(selection.container);
          const containerLogs = await fetchLogsForContainer(selection.container, selection.server);
          logs.push(...containerLogs);
        }

        setAllLogs(logs);
        setAvailableContainers(Array.from(containers));
      } catch (error) {
        console.error('Failed to load logs:', error);
      } finally {
        setIsLoading(false);
      }
    };

    if (selections.length > 0) {
      loadLogs();
    }
  }, [selections]);

  // Fetch logs from API
  const fetchLogsForContainer = async (
    container: string,
    server: string
  ): Promise<LogLine[]> => {
    try {
      const params = new URLSearchParams({
        container,
        server,
        tail: '1000',
        since: '24h',
      });

      const response = await fetch(`/api/logs/fetch?${params.toString()}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Failed to fetch logs: ${response.statusText}`);
      }

      const data = await response.json();
      if (!data.success) {
        throw new Error(data.error || 'Failed to fetch logs');
      }

      return data.data || [];
    } catch (error) {
      console.error(`Failed to fetch logs for ${container} on ${server}:`, error);
      return [];
    }
  };

  // Get result items with context
  const resultItems = useMemo(() => {
    const matches = groupedResults?.sortedMatches || searchResults?.matches || [];

    return matches.map((match, index) => {
      const id = `match-${index}`;
      const startIndex = Math.max(0, match.lineIndex - contextSize);
      const endIndex = Math.min(allLogs.length - 1, match.lineIndex + contextSize);
      const context = allLogs.slice(startIndex, endIndex + 1);

      return {
        id,
        match,
        context,
        isExpanded: expandedResults.has(id),
      };
    });
  }, [groupedResults, searchResults, allLogs, expandedResults, contextSize]);

  // Handle result selection
  const handleResultSelect = useCallback(
    (matchId: string) => {
      setSelectedMatchId(matchId);

      // Scroll to match in context panel
      setTimeout(() => {
        const contextElement = document.getElementById(`context-${matchId}`);
        if (contextElement && contextContainerRef.current) {
          contextElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }, 100);

      // Re-apply highlights when context changes
      setTimeout(() => {
        if (contextContainerRef.current && searchResults) {
          applyHighlights(contextContainerRef.current);
        }
      }, 200);
    },
    [searchResults, setSelectedMatchId, applyHighlights]
  );

  // Keyboard navigation for results
  const navigateResults = useCallback(
    (direction: 'next' | 'previous') => {
      if (!resultItems.length) return;

      let newIndex = focusedResultIndex;

      if (direction === 'next') {
        newIndex = focusedResultIndex < resultItems.length - 1 ? focusedResultIndex + 1 : 0;
      } else {
        newIndex = focusedResultIndex > 0 ? focusedResultIndex - 1 : resultItems.length - 1;
      }

      setFocusedResultIndex(newIndex);
      const item = resultItems[newIndex];
      if (item) {
        handleResultSelect(item.id);
        const preview = item.match.log.content.substring(0, 100);
        announceToScreenReader(
          `Result ${newIndex + 1} of ${resultItems.length}: ${preview}${
            item.match.log.content.length > 100 ? '...' : ''
          }`
        );
      }
    },
    [resultItems, focusedResultIndex, handleResultSelect, announceToScreenReader]
  );

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'F3' && !e.shiftKey) {
        e.preventDefault();
        navigateResults('next');
      }
      if (e.key === 'F3' && e.shiftKey) {
        e.preventDefault();
        navigateResults('previous');
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [navigateResults]);

  // Theme classes
  const themeClasses = {
    panel: theme === 'dark' ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200',
    header: theme === 'dark' ? 'bg-gray-900 border-gray-700' : 'bg-gray-50 border-gray-200',
    text: theme === 'dark' ? 'text-gray-200' : 'text-gray-800',
    subtext: theme === 'dark' ? 'text-gray-400' : 'text-gray-600',
    resizeHandle:
      theme === 'dark' ? 'bg-gray-700 hover:bg-cyan-500' : 'bg-gray-300 hover:bg-blue-500',
  };

  return (
    <div ref={containerRef} className="h-full flex flex-col">
      {/* Skip links */}
      <div className="sr-only">
        <a
          href="#search-results-panel"
          className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 bg-blue-500 text-white px-4 py-2 rounded-lg z-50 focus:outline-none focus:ring-2 focus:ring-blue-300"
        >
          Skip to search results
        </a>
        <a
          href="#log-context-panel"
          className="sr-only focus:not-sr-only focus:absolute focus:top-16 focus:left-4 bg-blue-500 text-white px-4 py-2 rounded-lg z-50 focus:outline-none focus:ring-2 focus:ring-blue-300"
        >
          Skip to log context
        </a>
      </div>

      {/* Live region for announcements */}
      <div ref={announcementLiveRef} aria-live="polite" aria-atomic="true" className="sr-only" />

      {/* Search Header */}
      <header className={`p-4 border-b ${themeClasses.header}`} role="banner">
        <div className="flex items-center justify-between mb-4">
          <div className="flex-1">
            <EnhancedSearch
              logs={allLogs}
              theme={theme}
              onSearchResults={handleSearchResults}
              availableContainers={availableContainers}
              availableServers={['prod1', 'prod2']}
            />
          </div>
          <button
            onClick={() => setShowAlertPanel(!showAlertPanel)}
            className={`ml-2 px-3 py-2 text-xs rounded border ${
              theme === 'dark'
                ? 'bg-gray-700 hover:bg-gray-600 text-gray-300 border-gray-600'
                : 'bg-white hover:bg-gray-50 text-gray-700 border-gray-300'
            }`}
            title="Toggle alerts"
          >
            🔔 Alerts
          </button>
        </div>

        {searchResults && (
          <SearchControls
            groupedResults={groupedResults}
            highlightNavigation={highlightNavigation}
            contextSize={contextSize}
            showGroupingControls={showGroupingControls}
            showHighlightControls={showHighlightControls}
            theme={theme}
            onToggleGroupingControls={() => setShowGroupingControls(!showGroupingControls)}
            onToggleHighlightControls={() => setShowHighlightControls(!showHighlightControls)}
            onUpdateGrouping={updateGrouping}
            onUpdateSorting={updateSorting}
            onContextSizeChange={setContextSize}
            onNavigateNext={navigateToNextHighlight}
            onNavigatePrevious={navigateToPreviousHighlight}
            onAnnounce={announceToScreenReader}
          />
        )}
      </header>

      {/* Results Summary */}
      {searchResults && (
        <div
          className={`px-4 py-2 border-b ${themeClasses.header} ${themeClasses.text} text-sm`}
          role="status"
          aria-live="polite"
        >
          <div className="flex items-center justify-between">
            <span>
              Found {searchResults.totalMatches} result
              {searchResults.totalMatches !== 1 ? 's' : ''} in{' '}
              {searchResults.executionTime.toFixed(2)}ms
              {groupedResults && groupedResults.groups.size > 0 && (
                <span className="ml-2">
                  ({groupedResults.groups.size} group{groupedResults.groups.size !== 1 ? 's' : ''})
                </span>
              )}
            </span>
            {searchResults.metrics?.fromCache && (
              <span className="text-blue-500" role="note">
                From cache
              </span>
            )}
          </div>
        </div>
      )}

      {/* Main Panels */}
      <main className="flex-1 flex overflow-hidden" role="main">
        {/* Left Panel - Search Results */}
        <section
          id="search-results-panel"
          className={`${themeClasses.panel} border-r flex flex-col`}
          style={{ width: `${panelDimensions.leftWidth}%` }}
          aria-label="Search results panel"
        >
          <header className={`p-4 border-b ${themeClasses.header}`}>
            <h2 className={`font-semibold ${themeClasses.text}`}>
              Search Results ({searchResults?.matches.length || 0})
            </h2>
          </header>

          <div ref={resultsContainerRef} className="flex-1 overflow-y-auto">
            <ResultsList
              resultItems={resultItems}
              groupedResults={groupedResults}
              searchResults={searchResults}
              selectedMatchId={selectedMatchId}
              isLoading={isLoading}
              theme={theme}
              onResultSelect={handleResultSelect}
              onToggleExpansion={toggleResultExpansion}
            />
          </div>
        </section>

        {/* Resize Handle */}
        <div
          ref={resizeHandleRef}
          role="separator"
          aria-label="Panel resize handle"
          aria-orientation="vertical"
          aria-valuemin={20}
          aria-valuemax={80}
          aria-valuenow={panelDimensions.leftWidth}
          aria-controls="search-results-panel log-context-panel"
          tabIndex={isResizing ? 0 : -1}
          className={`w-1 cursor-ew-resize ${themeClasses.resizeHandle} transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50 ${
            isResizing ? 'ring-2 ring-blue-500' : ''
          }`}
          onMouseDown={handleResizeStart}
          onKeyDown={handleResizeKeyDown}
          title="Resize panels (Enter to start, arrow keys to adjust, Enter to confirm, Escape to cancel)"
        />

        {/* Right Panel - Full Log Context */}
        <section
          id="log-context-panel"
          className={`${themeClasses.panel} flex flex-col`}
          style={{ width: `${panelDimensions.rightWidth}%` }}
          aria-label="Full log context panel"
        >
          <header className={`p-4 border-b ${themeClasses.header}`}>
            <h2 className={`font-semibold ${themeClasses.text}`}>Full Log Context</h2>
            {selectedMatchId && (
              <div className="text-sm mt-1 opacity-70">Viewing context for selected result</div>
            )}
          </header>

          <div ref={contextContainerRef} className="flex-1 overflow-y-auto">
            <ContextPanel
              resultItems={resultItems}
              selectedMatchId={selectedMatchId}
              searchResults={searchResults}
              theme={theme}
            />
          </div>
        </section>
      </main>

      {/* Keyboard Shortcuts Hint */}
      <footer
        className={`absolute bottom-4 right-4 px-3 py-2 rounded-lg text-xs ${
          theme === 'dark'
            ? 'bg-gray-800 text-gray-400 border border-gray-700'
            : 'bg-white text-gray-600 border border-gray-300'
        } opacity-0 hover:opacity-100 transition-opacity`}
        role="contentinfo"
        aria-label="Keyboard shortcuts help"
      >
        <div className="font-semibold mb-1">Keyboard Shortcuts:</div>
        <ul className="space-y-1 text-left">
          <li>
            <kbd>F3</kbd> / <kbd>Shift+F3</kbd> - Navigate results
          </li>
          <li>
            <kbd>↑</kbd> <kbd>↓</kbd> - Resize panels (when focused)
          </li>
          <li>
            <kbd>Click</kbd> - Select result to view context
          </li>
          <li>
            <kbd>+</kbd> - Expand result context
          </li>
        </ul>
      </footer>

      {/* Alert Panel Modal - Displays pattern alerts and management */}
      {showAlertPanel && (
        <AlertPanel
          theme={theme}
          containers={availableContainers}
          servers={['prod1', 'prod2']}
          onClose={() => setShowAlertPanel(false)}
        />
      )}
    </div>
  );
};

export default HybridLogViewer;
