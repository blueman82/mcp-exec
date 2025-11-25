/**
 * ContextPanel Component
 * Displays full log context for a selected search result with surrounding lines
 */

'use client';

import React from 'react';
import type { SearchResult, SearchMatch } from '@/types/search';
import type { LogLine } from '@/types';

interface ResultItem {
  id: string;
  match: SearchMatch;
  context: LogLine[];
  isExpanded: boolean;
}

interface ContextPanelProps {
  resultItems: ResultItem[];
  selectedMatchId: string | null;
  searchResults: SearchResult | null;
  theme: 'dark' | 'light';
}

const ContextPanel: React.FC<ContextPanelProps> = ({
  resultItems,
  selectedMatchId,
  searchResults,
  theme,
}) => {
  const themeClasses = {
    header: theme === 'dark' ? 'bg-gray-900 border-gray-700' : 'bg-gray-50 border-gray-200',
    text: theme === 'dark' ? 'text-gray-200' : 'text-gray-800',
    subtext: theme === 'dark' ? 'text-gray-400' : 'text-gray-600',
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

  if (!selectedMatchId) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className={`${themeClasses.subtext}`}>
          {searchResults ? 'Select a result to view context' : 'Search for logs to see context'}
        </p>
      </div>
    );
  }

  return (
    <div className="p-4">
      {resultItems
        .filter((item) => item.id === selectedMatchId)
        .map((item) => (
          <div key={item.id}>
            {/* Match Header */}
            <div className={`mb-4 p-3 rounded border ${themeClasses.selected}`}>
              <div className="flex items-center gap-2 mb-2">
                <span className={`text-xs ${getLogLevelColor(item.match.log.level || 'info')}`}>
                  {(item.match.log.level || 'info').toUpperCase()}
                </span>
                <span className={`text-xs ${themeClasses.subtext}`}>
                  Index {item.match.lineIndex + 1}
                </span>
                <div
                  className={`px-2 py-1 rounded text-xs font-bold border ${getServerBadgeColor(
                    item.match.log.server as 'prod1' | 'prod2'
                  )}`}
                >
                  {item.match.log.server}
                </div>
                <span className={`font-mono text-sm ${themeClasses.text}`}>
                  {item.match.log.container.replace('ketchup-', '')}
                </span>
              </div>
              <div className={`text-sm ${themeClasses.text} font-mono`}>
                {item.match.log.content}
              </div>
              <div className={`text-xs ${themeClasses.subtext} mt-1`}>
                {new Date(item.match.log.timestamp).toLocaleString()}
              </div>
            </div>

            {/* Full Context */}
            <div className={`p-3 rounded border ${themeClasses.header}`}>
              <div className={`text-sm ${themeClasses.subtext} mb-3`}>Surrounding Context:</div>
              {item.context.map((log, idx) => (
                <div
                  key={idx}
                  id={`context-${item.id}`}
                  className={`mb-2 p-2 rounded ${
                    log.timestamp === item.match.log.timestamp &&
                    log.content === item.match.log.content
                      ? 'bg-blue-500/20 border border-blue-500/30'
                      : ''
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <span className={`text-xs ${themeClasses.subtext} font-mono`}>
                      {idx + 1}
                    </span>
                    <span
                      className={`text-xs ${getLogLevelColor(
                        log.level || 'info'
                      )} min-w-[50px]`}
                    >
                      {(log.level || 'info').toUpperCase()}
                    </span>
                    <div className="flex-1">
                      <div className={`text-sm ${themeClasses.text} font-mono`}>
                        {log.content}
                      </div>
                      <div className={`text-xs ${themeClasses.subtext} mt-1`}>
                        {new Date(log.timestamp).toLocaleString()}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
    </div>
  );
};

export default ContextPanel;
