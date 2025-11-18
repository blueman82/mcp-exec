/**
 * SavedSearchesDropdown Component
 *
 * Dropdown component for managing saved searches with CRUD operations
 * and accessibility features.
 */

import React from 'react';
import type { SavedSearch } from '@/types/search';

interface SavedSearchesDropdownProps {
  savedSearches: SavedSearch[];
  showSavedSearches: boolean;
  onSaveCurrent: (name: string, description?: string) => void;
  onLoadSavedSearch: (savedSearch: SavedSearch) => void;
  onDeleteSavedSearch: (id: string) => void;
  theme: 'dark' | 'light';
}

const SavedSearchesDropdown: React.FC<SavedSearchesDropdownProps> = ({
  savedSearches,
  showSavedSearches,
  onSaveCurrent,
  onLoadSavedSearch,
  onDeleteSavedSearch,
  theme
}) => {
  if (!showSavedSearches) {
    return null;
  }

  const themeClasses = theme === 'dark'
    ? 'bg-gray-800 border-gray-700 text-gray-200'
    : 'bg-white border-gray-300 text-gray-800';

  const handleSaveCurrent = () => {
    const name = prompt('Enter search name:');
    if (name?.trim()) {
      onSaveCurrent(name.trim());
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent, savedSearch: SavedSearch) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      onLoadSavedSearch(savedSearch);
    }
  };

  const handleClick = (savedSearch: SavedSearch) => {
    onLoadSavedSearch(savedSearch);
  };

  return (
    <div
      className={`absolute top-full left-0 right-0 mt-2 p-4 rounded-lg border shadow-lg z-10 ${themeClasses}`}
      role="dialog"
      aria-label="Saved searches"
      aria-modal="true"
    >
      <div className="flex items-center justify-between mb-3">
        <h4 className="font-semibold">Saved Searches</h4>
        <button
          onClick={handleSaveCurrent}
          aria-label="Save current search"
          className="text-blue-500 hover:text-blue-600 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50 rounded px-2 py-1"
        >
          <span aria-hidden="true">💾</span>
          Save Current
        </button>
      </div>
      <div className="space-y-2 max-h-60 overflow-y-auto" role="list">
        {savedSearches.length === 0 ? (
          <div className="text-center text-gray-500 py-4" role="status">
            No saved searches
          </div>
        ) : (
          savedSearches.map(saved => (
            <div
              key={saved.id}
              className={`p-3 rounded border focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50 ${
                theme === 'dark' ? 'border-gray-600' : 'border-gray-200'
              }`}
              role="listitem"
            >
              <div className="flex items-center justify-between">
                <div
                  className="flex-1 cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50 rounded p-1"
                  onClick={() => handleClick(saved)}
                  onKeyDown={(e) => handleKeyDown(e, saved)}
                  tabIndex={0}
                  role="button"
                  aria-label={`Load saved search: ${saved.name}. Query: ${saved.query}`}
                >
                  <div className="font-medium">{saved.name}</div>
                  <div className="text-sm text-gray-500 font-mono">{saved.query}</div>
                  {saved.description && (
                    <div className="text-xs text-gray-400 mt-1">{saved.description}</div>
                  )}
                </div>
                <button
                  onClick={() => onDeleteSavedSearch(saved.id)}
                  aria-label={`Delete saved search: ${saved.name}`}
                  className="text-red-500 hover:text-red-600 ml-2 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-opacity-50 rounded p-1"
                >
                  <span aria-hidden="true">🗑️</span>
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default SavedSearchesDropdown;