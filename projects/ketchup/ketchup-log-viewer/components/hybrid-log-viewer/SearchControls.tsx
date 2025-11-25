/**
 * SearchControls Component
 * Provides grouping, sorting, and highlight navigation controls for search results
 */

'use client';

import React from 'react';
import type { GroupedSearchResults, GroupingOption, SortingOption } from '@/lib/search-grouper';
import type { HighlightNavigation } from '@/lib/search-highlighter';

interface SearchControlsProps {
  groupedResults: GroupedSearchResults | null;
  highlightNavigation: HighlightNavigation;
  contextSize: number;
  showGroupingControls: boolean;
  showHighlightControls: boolean;
  theme: 'dark' | 'light';
  onToggleGroupingControls: () => void;
  onToggleHighlightControls: () => void;
  onUpdateGrouping: (groupBy: GroupingOption) => void;
  onUpdateSorting: (sortBy: SortingOption, direction?: 'asc' | 'desc') => void;
  onContextSizeChange: (size: number) => void;
  onNavigateNext: () => void;
  onNavigatePrevious: () => void;
  onAnnounce?: (message: string) => void;
}

const SearchControls: React.FC<SearchControlsProps> = ({
  groupedResults,
  highlightNavigation,
  contextSize,
  showGroupingControls,
  showHighlightControls,
  theme,
  onToggleGroupingControls,
  onToggleHighlightControls,
  onUpdateGrouping,
  onUpdateSorting,
  onContextSizeChange,
  onNavigateNext,
  onNavigatePrevious,
  onAnnounce,
}) => {
  const themeClasses = {
    panel: theme === 'dark' ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200',
    text: theme === 'dark' ? 'text-gray-200' : 'text-gray-800',
    subtext: theme === 'dark' ? 'text-gray-400' : 'text-gray-600',
  };

  return (
    <nav
      className="flex flex-wrap items-center gap-3 mt-4 pt-4 border-t border-gray-200 dark:border-gray-700"
      role="navigation"
      aria-label="Search result controls"
    >
      {/* Grouping Controls */}
      <div className="flex items-center gap-2" role="group" aria-label="Grouping options">
        <button
          onClick={onToggleGroupingControls}
          aria-expanded={showGroupingControls}
          aria-label={`Grouping options, ${showGroupingControls ? 'expanded' : 'collapsed'}`}
          className={`px-3 py-2 rounded-lg border ${themeClasses.panel} hover:opacity-80 transition-opacity flex items-center gap-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50`}
        >
          <span aria-hidden="true">📊</span>
          Grouping
        </button>

        {showGroupingControls && (
          <div className="flex items-center gap-2">
            <label htmlFor="grouping-select" className="sr-only">
              Group results by
            </label>
            <select
              id="grouping-select"
              value={groupedResults?.config.grouping.groupBy || 'container'}
              onChange={(e) => {
                onUpdateGrouping(e.target.value as GroupingOption);
                onAnnounce?.(`Results grouped by ${e.target.value}`);
              }}
              className={`px-3 py-2 rounded-lg border ${themeClasses.panel} text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50`}
            >
              <option value="container">Container</option>
              <option value="server">Server</option>
              <option value="logLevel">Log Level</option>
              <option value="time">Time</option>
              <option value="relevance">Relevance</option>
              <option value="none">No Grouping</option>
            </select>
          </div>
        )}
      </div>

      {/* Sorting Controls */}
      <div className="flex items-center gap-2" role="group" aria-label="Sorting options">
        <label htmlFor="sorting-select" className="sr-only">
          Sort results by
        </label>
        <select
          id="sorting-select"
          value={groupedResults?.config.sorting.sortBy || 'relevance'}
          onChange={(e) => {
            onUpdateSorting(e.target.value as SortingOption);
            onAnnounce?.(`Results sorted by ${e.target.value}`);
          }}
          className={`px-3 py-2 rounded-lg border ${themeClasses.panel} text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50`}
        >
          <option value="relevance">Relevance</option>
          <option value="mostRecent">Most Recent</option>
          <option value="leastRecent">Least Recent</option>
          <option value="logLevelPriority">Log Level</option>
          <option value="alphabetical">Alphabetical</option>
        </select>

        <button
          onClick={() => {
            const currentDirection = groupedResults?.config.sorting.direction || 'desc';
            const newDirection = currentDirection === 'asc' ? 'desc' : 'asc';
            onUpdateSorting(
              groupedResults?.config.sorting.sortBy || 'relevance',
              newDirection
            );
            onAnnounce?.(
              `Sort order changed to ${newDirection === 'asc' ? 'ascending' : 'descending'}`
            );
          }}
          aria-label={`Sort direction: ${
            groupedResults?.config.sorting.direction === 'asc' ? 'ascending' : 'descending'
          }`}
          className={`px-3 py-2 rounded-lg border ${themeClasses.panel} hover:opacity-80 transition-opacity text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50`}
        >
          {groupedResults?.config.sorting.direction === 'asc' ? '↑' : '↓'}
        </button>
      </div>

      {/* Highlight Navigation Controls */}
      {showHighlightControls && highlightNavigation.total > 0 && (
        <div className="flex items-center gap-2" role="group" aria-label="Highlight navigation">
          <button
            onClick={onNavigatePrevious}
            aria-label="Previous highlight (Shift+F3)"
            className={`px-3 py-2 rounded-lg border ${themeClasses.panel} hover:opacity-80 transition-opacity text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50`}
          >
            ▲
          </button>
          <span className={`text-sm ${themeClasses.text}`} aria-live="polite">
            {highlightNavigation.current + 1} of {highlightNavigation.total}
          </span>
          <button
            onClick={onNavigateNext}
            aria-label="Next highlight (F3)"
            className={`px-3 py-2 rounded-lg border ${themeClasses.panel} hover:opacity-80 transition-opacity text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50`}
          >
            ▼
          </button>
        </div>
      )}

      {/* Toggle Controls */}
      <div className="flex items-center gap-2 ml-auto" role="group" aria-label="View options">
        {/* Context Size Control */}
        <div className="flex items-center gap-2">
          <label htmlFor="context-size-select" className="sr-only">
            Context size
          </label>
          <select
            id="context-size-select"
            value={contextSize}
            onChange={(e) => {
              const newSize = parseInt(e.target.value, 10);
              onContextSizeChange(newSize);
              onAnnounce?.(`Context size changed to ${newSize} lines`);
            }}
            className={`px-3 py-2 rounded-lg border ${themeClasses.panel} text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50`}
          >
            <option value={3}>3 lines</option>
            <option value={5}>5 lines</option>
            <option value={10}>10 lines</option>
            <option value={15}>15 lines</option>
            <option value={20}>20 lines</option>
          </select>
          <span className={`text-xs ${themeClasses.subtext}`}>context</span>
        </div>

        <button
          onClick={onToggleHighlightControls}
          aria-expanded={showHighlightControls}
          aria-label={`Highlight controls, ${showHighlightControls ? 'visible' : 'hidden'}`}
          className={`px-3 py-2 rounded-lg border ${themeClasses.panel} hover:opacity-80 transition-opacity text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50`}
        >
          <span aria-hidden="true">🎨</span>
          Highlights
        </button>
      </div>
    </nav>
  );
};

export default SearchControls;
