/**
 * ResultsList Component
 * Displays grouped and sorted search results with expandable context
 */

'use client';

import React from 'react';
import type { SearchResult, SearchMatch } from '@/types/search';
import type { GroupedSearchResults } from '@/lib/search-grouper';
import type { LogLine } from '@/types';

interface ResultItem {
  id: string;
  match: SearchMatch;
  context: LogLine[];
  isExpanded: boolean;
}

interface ResultsListProps {
  resultItems: ResultItem[];
  groupedResults: GroupedSearchResults | null;
  searchResults: SearchResult | null;
  selectedMatchId: string | null;
  isLoading: boolean;
  theme: 'dark' | 'light';
  onResultSelect: (matchId: string) => void;
  onToggleExpansion: (id: string) => void;
}

const ResultsList: React.FC<ResultsListProps> = ({
  resultItems,
  groupedResults,
  searchResults,
  selectedMatchId,
  isLoading,
  theme,
  onResultSelect,
  onToggleExpansion,
}) => {
  const themeClasses = {
    panel: theme === 'dark' ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200',
    header: theme === 'dark' ? 'bg-gray-900 border-gray-700' : 'bg-gray-50 border-gray-200',
    text: theme === 'dark' ? 'text-gray-200' : 'text-gray-800',
    subtext: theme === 'dark' ? 'text-gray-400' : 'text-gray-600',
    resultItem:
      theme === 'dark'
        ? 'hover:bg-gray-700 border-gray-700'
        : 'hover:bg-gray-50 border-gray-200',
    selected:
      theme === 'dark' ? 'bg-blue-900/30 border-blue-500/50' : 'bg-blue-50 border-blue-300',
  };

  const getServerBadgeColor = (server: 'prod1' | 'prod2') => {
    return server === 'prod1'
      ? 'bg-blue-500/20 text-blue-400 border-blue-500/40'
      : 'bg-green-500/20 text-green-400 border-green-500/40';
  };

  const getLogLevelColor = (level: string) => {
    switch (level.toLowerCase()) {
      case 'error':
        return 'text-red-500';
      case 'warn':
        return 'text-yellow-500';
      case 'info':
        return 'text-blue-500';
      case 'debug':
        return 'text-gray-500';
      default:
        return 'text-gray-400';
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (groupedResults?.groups.size === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className={`${themeClasses.subtext}`}>
          {searchResults ? 'No results found' : 'Enter a search query to see results'}
        </p>
      </div>
    );
  }

  if (!groupedResults) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className={`${themeClasses.subtext}`}>No search results available</p>
      </div>
    );
  }

  return (
    <div className="p-2">
      {Array.from(groupedResults.groups.entries()).map(([groupKey, groupInfo]) => {
        const itemsInGroup = groupedResults.groupedMatches.get(groupKey) || [];
        const groupResultItems = itemsInGroup
          .map((match) => {
            const globalIndex = resultItems.findIndex((item) => item.match === match);
            return resultItems[globalIndex];
          })
          .filter(Boolean);

        return (
          <div key={groupKey} className="mb-4">
            {/* Group Header */}
            <div
              className={`flex items-center gap-2 px-3 py-2 mb-2 rounded ${themeClasses.header}`}
            >
              <div
                className={`px-2 py-1 rounded text-xs font-bold border ${
                  groupInfo.metadata?.servers?.[0]
                    ? getServerBadgeColor(groupInfo.metadata.servers[0])
                    : getServerBadgeColor('prod1')
                }`}
              >
                {groupInfo.metadata?.servers?.[0] || 'Unknown'}
              </div>
              <span className={`font-mono text-sm ${themeClasses.text}`}>{groupInfo.name}</span>
              <span className={`text-xs ${themeClasses.subtext}`}>({groupInfo.count} matches)</span>
              {groupInfo.metadata?.maxScore && (
                <span className={`text-xs ${themeClasses.subtext}`}>
                  Max Score: {groupInfo.metadata.maxScore.toFixed(1)}
                </span>
              )}
            </div>

            {/* Result Items */}
            {groupResultItems.map(
              (item) =>
                item && (
                  <div
                    key={item.id}
                    id={`result-${item.id}`}
                    className={`mb-2 p-3 rounded border cursor-pointer transition-colors ${
                      selectedMatchId === item.id ? themeClasses.selected : themeClasses.resultItem
                    }`}
                    onClick={() => onResultSelect(item.id)}
                  >
                    {/* Result Header */}
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-xs ${getLogLevelColor(item.match.log.level || 'info')}`}
                        >
                          {(item.match.log.level || 'info').toUpperCase()}
                        </span>
                        <span className={`text-xs ${themeClasses.subtext}`}>
                          Index {item.match.lineIndex + 1}
                        </span>
                        <span className={`text-xs ${themeClasses.subtext}`}>
                          Score: {item.match.score.toFixed(2)}
                        </span>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onToggleExpansion(item.id);
                        }}
                        className={`px-2 py-1 text-xs rounded border ${themeClasses.resultItem}`}
                      >
                        {item.isExpanded ? '−' : '+'}
                      </button>
                    </div>

                    {/* Match Preview */}
                    <div className={`text-sm ${themeClasses.text} font-mono mb-1`}>
                      {item.match.log.content.substring(0, 100)}
                      {item.match.log.content.length > 100 && '...'}
                    </div>

                    {/* Timestamp */}
                    <div className={`text-xs ${themeClasses.subtext}`}>
                      {new Date(item.match.log.timestamp).toLocaleString()}
                    </div>

                    {/* Expanded Context */}
                    {item.isExpanded && (
                      <div className={`mt-2 p-2 rounded ${themeClasses.header}`}>
                        <div className={`text-xs ${themeClasses.subtext} mb-1`}>Context:</div>
                        {item.context.map((log, idx) => (
                          <div
                            key={idx}
                            className={`text-xs font-mono mb-1 ${
                              log.timestamp === item.match.log.timestamp &&
                              log.content === item.match.log.content
                                ? 'bg-blue-500/20 px-1 rounded'
                                : ''
                            }`}
                          >
                            <span className={`${getLogLevelColor(log.level || 'info')}`}>
                              {(log.level || 'info').toUpperCase()}
                            </span>{' '}
                            {log.content}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )
            )}
          </div>
        );
      })}
    </div>
  );
};

export default ResultsList;
