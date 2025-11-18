/**
 * SearchHistoryDropdown Component
 *
 * Dropdown component displaying search history with keyboard navigation
 * and accessibility features.
 */

import React from 'react';
import type { SearchQuery } from '@/types/search';

interface SearchHistoryDropdownProps {
  searchHistory: SearchQuery[];
  showHistory: boolean;
  focusedSuggestionIndex: number;
  onHistoryItemClick: (item: SearchQuery, index: number) => void;
  onFocusSuggestionIndexChange: (index: number) => void;
  theme: 'dark' | 'light';
}

const SearchHistoryDropdown: React.FC<SearchHistoryDropdownProps> = ({
  searchHistory,
  showHistory,
  focusedSuggestionIndex,
  onHistoryItemClick,
  onFocusSuggestionIndexChange,
  theme
}) => {
  if (!showHistory || searchHistory.length === 0) {
    return null;
  }

  const themeClasses = theme === 'dark'
    ? 'bg-gray-800 border-gray-700 text-gray-200'
    : 'bg-white border-gray-300 text-gray-800';

  const handleKeyDown = (e: React.KeyboardEvent, item: SearchQuery, index: number) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      onHistoryItemClick(item, index);
    }
  };

  const handleClick = (item: SearchQuery, index: number) => {
    onHistoryItemClick(item, index);
    onFocusSuggestionIndexChange(-1);
  };

  return (
    <div
      className={`absolute top-full left-0 right-0 mt-2 p-4 rounded-lg border shadow-lg z-10 ${themeClasses}`}
      role="listbox"
      aria-label="Search history"
    >
      <h4 className="font-semibold mb-3">Recent Searches</h4>
      <ul className="space-y-2 max-h-60 overflow-y-auto" role="presentation">
        {searchHistory.slice(0, 10).map((item, index) => (
          <li key={item.id} role="presentation">
            <div
              id={`history-item-${index}`}
              role="option"
              aria-selected={focusedSuggestionIndex === index}
              tabIndex={focusedSuggestionIndex === index ? 0 : -1}
              onClick={() => handleClick(item, index)}
              onKeyDown={(e) => handleKeyDown(e, item, index)}
              className={`p-2 rounded cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50 ${
                focusedSuggestionIndex === index ? 'ring-2 ring-blue-500 ring-opacity-50' : ''
              } ${theme === 'dark' ? 'hover:bg-gray-700' : 'hover:bg-gray-100'}`}
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-sm">{item.query}</span>
                <span className="text-xs text-gray-500">
                  {item.resultCount} result{item.resultCount !== 1 ? 's' : ''}
                </span>
              </div>
              <div className="text-xs text-gray-400 mt-1">
                {new Date(item.timestamp).toLocaleString()}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default SearchHistoryDropdown;