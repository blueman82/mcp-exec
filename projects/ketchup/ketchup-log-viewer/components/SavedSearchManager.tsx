/**
 * SavedSearchManager Component - UI for managing saved searches
 *
 * Features:
 * - Folder tree navigation
 * - Searchable list of saved searches
 * - Tag-based filtering
 * - Usage statistics
 * - Bulk operations (delete, export, move)
 * - Import/export functionality
 */

'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { getSavedSearchManager } from '../lib/saved-searches';
import type {
  SavedSearchWithMetadata,
  SearchFolder,
  SavedSearchStats,
  SearchFilters,
  SearchPreferences,
} from '../types/search';

interface SavedSearchManagerProps {
  /** Current theme */
  theme: 'light' | 'dark';
  /** Callback when a saved search is selected */
  onSelectSearch?: (search: SavedSearchWithMetadata) => void;
  /** Callback when a search is executed */
  onExecuteSearch?: (search: SavedSearchWithMetadata) => void;
  /** Whether the manager is in compact mode */
  compact?: boolean;
}

/**
 * SavedSearchManager - Main component for managing saved searches
 */
export function SavedSearchManager({
  theme,
  onSelectSearch,
  onExecuteSearch,
  compact = false,
}: SavedSearchManagerProps) {
  const manager = getSavedSearchManager();

  // State
  const [searches, setSearches] = useState<SavedSearchWithMetadata[]>([]);
  const [folders, setFolders] = useState<SearchFolder[]>([]);
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null);
  const [selectedSearchId, setSelectedSearchId] = useState<string | null>(null);
  const [searchFilter, setSearchFilter] = useState('');
  const [tagFilter, setTagFilter] = useState<string[]>([]);
  const [sortBy, setSortBy] = useState<'name' | 'lastUsed' | 'usageCount' | 'createdAt'>('lastUsed');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  const [viewMode, setViewMode] = useState<'list' | 'grid' | 'tree'>('list');
  const [showStats, setShowStats] = useState(false);
  const [stats, setStats] = useState<SavedSearchStats | null>(null);
  const [selectedSearches, setSelectedSearches] = useState<Set<string>>(new Set());
  const [isCreatingFolder, setIsCreatingFolder] = useState(false);
  const [isCreatingSearch, setIsCreatingSearch] = useState(false);

  // Load data
  useEffect(() => {
    loadData();
  }, []);

  const loadData = useCallback(() => {
    setSearches(manager.getAllSearches());
    setFolders(manager.getAllFolders());
    setStats(manager.getStats());
  }, [manager]);

  // Get all unique tags
  const allTags = useMemo(() => manager.getAllTags(), [manager, searches]);

  // Filter and sort searches
  const filteredSearches = useMemo(() => {
    let results = searches;

    // Apply folder filter
    if (selectedFolderId !== null) {
      results = manager.getSearchesInFolder(selectedFolderId);
    }

    // Apply text search filter
    if (searchFilter) {
      results = manager.searchSavedSearches(searchFilter);
    }

    // Apply tag filter
    if (tagFilter.length > 0) {
      results = results.filter(search =>
        search.tags?.some(tag => tagFilter.includes(tag))
      );
    }

    // Sort
    results = manager.sortSearches(results, sortBy, sortDirection);

    return results;
  }, [searches, selectedFolderId, searchFilter, tagFilter, sortBy, sortDirection, manager]);

  // Event handlers
  const handleSelectSearch = useCallback((search: SavedSearchWithMetadata) => {
    setSelectedSearchId(search.id);
    onSelectSearch?.(search);
  }, [onSelectSearch]);

  const handleExecuteSearch = useCallback((search: SavedSearchWithMetadata) => {
    manager.recordUsage(search.id);
    loadData();
    onExecuteSearch?.(search);
  }, [manager, loadData, onExecuteSearch]);

  const handleDeleteSearch = useCallback((id: string) => {
    manager.deleteSearch(id);
    loadData();
    setSelectedSearchId(null);
  }, [manager, loadData]);

  const handleToggleFavorite = useCallback((id: string) => {
    manager.toggleFavorite(id);
    loadData();
  }, [manager, loadData]);

  const handleCreateFolder = useCallback((name: string, parentId?: string | null) => {
    manager.createFolder(name, { parentId });
    loadData();
    setIsCreatingFolder(false);
  }, [manager, loadData]);

  const handleDeleteFolder = useCallback((id: string) => {
    if (confirm('Delete this folder and all its searches?')) {
      manager.deleteFolder(id);
      loadData();
      if (selectedFolderId === id) {
        setSelectedFolderId(null);
      }
    }
  }, [manager, loadData, selectedFolderId]);

  const handleBulkDelete = useCallback(() => {
    if (confirm(`Delete ${selectedSearches.size} selected searches?`)) {
      manager.deleteSearches(Array.from(selectedSearches));
      loadData();
      setSelectedSearches(new Set());
    }
  }, [manager, loadData, selectedSearches]);

  const handleExport = useCallback(() => {
    const json = manager.exportToJson({
      name: 'Ketchup Saved Searches',
      description: 'Exported saved searches',
      author: 'User',
    });

    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ketchup-saved-searches-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [manager]);

  const handleImport = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      const json = e.target?.result as string;
      const result = manager.importFromJson(json, { merge: true });

      if (result.errors.length > 0) {
        alert(`Import completed with errors:\n${result.errors.join('\n')}`);
      } else {
        alert(`Imported ${result.imported} items successfully`);
      }

      loadData();
    };
    reader.readAsText(file);
  }, [manager, loadData]);

  // Render folder tree
  const renderFolderTree = (parentId: string | null = null, depth: number = 0) => {
    const childFolders = manager.getChildFolders(parentId);

    return childFolders.map(folder => (
      <div key={folder.id} style={{ marginLeft: `${depth * 20}px` }}>
        <button
          onClick={() => setSelectedFolderId(folder.id)}
          className={`
            w-full text-left px-3 py-2 rounded-md text-sm transition-colors
            ${selectedFolderId === folder.id
              ? 'bg-blue-500 text-white'
              : theme === 'dark'
              ? 'hover:bg-gray-700'
              : 'hover:bg-gray-200'
            }
          `}
        >
          <span className="mr-2">{folder.icon || '📁'}</span>
          {folder.name}
          <span className="ml-2 text-xs opacity-60">({folder.searchCount})</span>
        </button>
        {renderFolderTree(folder.id, depth + 1)}
      </div>
    ));
  };

  const bgColor = theme === 'dark' ? 'bg-gray-900' : 'bg-white';
  const textColor = theme === 'dark' ? 'text-gray-100' : 'text-gray-900';
  const borderColor = theme === 'dark' ? 'border-gray-700' : 'border-gray-300';

  if (compact) {
    return (
      <div className={`${bgColor} ${textColor} rounded-lg shadow-lg p-4 max-h-96 overflow-y-auto`}>
        <div className="space-y-2">
          {filteredSearches.map(search => (
            <button
              key={search.id}
              onClick={() => handleExecuteSearch(search)}
              className={`
                w-full text-left p-2 rounded border ${borderColor}
                hover:bg-opacity-10 hover:bg-blue-500 transition-colors
              `}
            >
              <div className="flex items-center justify-between">
                <span className="font-medium">{search.name}</span>
                {search.isFavorite && <span>⭐</span>}
              </div>
              <div className="text-xs opacity-60 mt-1">{search.query}</div>
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className={`${bgColor} ${textColor} rounded-lg shadow-lg p-6 space-y-4`}>
      {/* Header */}
      <div className="flex items-center justify-between border-b ${borderColor} pb-4">
        <h2 className="text-2xl font-bold">Saved Searches</h2>
        <div className="flex gap-2">
          <button
            onClick={() => setShowStats(!showStats)}
            className="px-3 py-1 rounded-md bg-blue-500 text-white hover:bg-blue-600"
            title="Show Statistics"
          >
            📊
          </button>
          <button
            onClick={handleExport}
            className="px-3 py-1 rounded-md bg-green-500 text-white hover:bg-green-600"
            title="Export"
          >
            ⬇️
          </button>
          <label className="px-3 py-1 rounded-md bg-purple-500 text-white hover:bg-purple-600 cursor-pointer" title="Import">
            ⬆️
            <input
              type="file"
              accept=".json"
              onChange={handleImport}
              className="hidden"
            />
          </label>
        </div>
      </div>

      {/* Statistics */}
      {showStats && stats && (
        <div className={`grid grid-cols-4 gap-4 p-4 rounded-lg border ${borderColor}`}>
          <div>
            <div className="text-2xl font-bold">{stats.totalSearches}</div>
            <div className="text-sm opacity-60">Total Searches</div>
          </div>
          <div>
            <div className="text-2xl font-bold">{stats.totalFolders}</div>
            <div className="text-sm opacity-60">Folders</div>
          </div>
          <div>
            <div className="text-2xl font-bold">{stats.totalTags}</div>
            <div className="text-sm opacity-60">Tags</div>
          </div>
          <div>
            <div className="text-2xl font-bold">{stats.totalUsageCount}</div>
            <div className="text-sm opacity-60">Total Uses</div>
          </div>
        </div>
      )}

      {/* Main content */}
      <div className="grid grid-cols-4 gap-4">
        {/* Sidebar - Folders and filters */}
        <div className="col-span-1 space-y-4">
          {/* Folder tree */}
          <div className={`border ${borderColor} rounded-lg p-4`}>
            <h3 className="font-semibold mb-2">Folders</h3>
            <button
              onClick={() => setSelectedFolderId(null)}
              className={`
                w-full text-left px-3 py-2 rounded-md text-sm mb-2 transition-colors
                ${selectedFolderId === null
                  ? 'bg-blue-500 text-white'
                  : theme === 'dark'
                  ? 'hover:bg-gray-700'
                  : 'hover:bg-gray-200'
                }
              `}
            >
              📂 All Searches ({searches.length})
            </button>
            {renderFolderTree()}
            <button
              onClick={() => setIsCreatingFolder(true)}
              className="w-full text-left px-3 py-2 rounded-md text-sm mt-2 border border-dashed hover:bg-opacity-10 hover:bg-blue-500"
            >
              + New Folder
            </button>
          </div>

          {/* Tag filter */}
          <div className={`border ${borderColor} rounded-lg p-4`}>
            <h3 className="font-semibold mb-2">Filter by Tags</h3>
            <div className="flex flex-wrap gap-2">
              {allTags.map(tag => (
                <button
                  key={tag}
                  onClick={() => {
                    if (tagFilter.includes(tag)) {
                      setTagFilter(tagFilter.filter(t => t !== tag));
                    } else {
                      setTagFilter([...tagFilter, tag]);
                    }
                  }}
                  className={`
                    px-2 py-1 rounded-full text-xs transition-colors
                    ${tagFilter.includes(tag)
                      ? 'bg-blue-500 text-white'
                      : theme === 'dark'
                      ? 'bg-gray-700'
                      : 'bg-gray-200'
                    }
                  `}
                >
                  {tag}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Search list */}
        <div className="col-span-3 space-y-4">
          {/* Search and sort controls */}
          <div className="flex gap-2">
            <input
              type="text"
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              placeholder="Search saved searches..."
              className={`
                flex-1 px-4 py-2 rounded-md border ${borderColor}
                ${theme === 'dark' ? 'bg-gray-800' : 'bg-white'}
                focus:outline-none focus:ring-2 focus:ring-blue-500
              `}
            />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className={`px-3 py-2 rounded-md border ${borderColor} ${theme === 'dark' ? 'bg-gray-800' : 'bg-white'}`}
            >
              <option value="lastUsed">Last Used</option>
              <option value="name">Name</option>
              <option value="usageCount">Usage Count</option>
              <option value="createdAt">Created</option>
            </select>
            <button
              onClick={() => setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')}
              className="px-3 py-2 rounded-md bg-gray-500 text-white hover:bg-gray-600"
            >
              {sortDirection === 'asc' ? '↑' : '↓'}
            </button>
          </div>

          {/* Bulk actions */}
          {selectedSearches.size > 0 && (
            <div className="flex gap-2 p-2 bg-blue-500 bg-opacity-10 rounded-md">
              <span className="px-2 py-1">{selectedSearches.size} selected</span>
              <button
                onClick={handleBulkDelete}
                className="px-3 py-1 rounded-md bg-red-500 text-white hover:bg-red-600"
              >
                Delete Selected
              </button>
              <button
                onClick={() => setSelectedSearches(new Set())}
                className="px-3 py-1 rounded-md bg-gray-500 text-white hover:bg-gray-600"
              >
                Clear Selection
              </button>
            </div>
          )}

          {/* Search items */}
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {filteredSearches.map(search => (
              <div
                key={search.id}
                className={`
                  p-4 rounded-lg border ${borderColor}
                  ${selectedSearchId === search.id ? 'ring-2 ring-blue-500' : ''}
                  hover:bg-opacity-10 hover:bg-blue-500 transition-all
                `}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <input
                        type="checkbox"
                        checked={selectedSearches.has(search.id)}
                        onChange={(e) => {
                          const newSet = new Set(selectedSearches);
                          if (e.target.checked) {
                            newSet.add(search.id);
                          } else {
                            newSet.delete(search.id);
                          }
                          setSelectedSearches(newSet);
                        }}
                        className="cursor-pointer"
                      />
                      <button
                        onClick={() => handleToggleFavorite(search.id)}
                        className="text-xl"
                      >
                        {search.isFavorite ? '⭐' : '☆'}
                      </button>
                      <h4 className="font-semibold">{search.name}</h4>
                    </div>

                    <p className="text-sm opacity-75 mb-2">{search.query}</p>

                    {search.description && (
                      <p className="text-xs opacity-60 mb-2">{search.description}</p>
                    )}

                    {search.tags && search.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mb-2">
                        {search.tags.map(tag => (
                          <span
                            key={tag}
                            className={`px-2 py-0.5 rounded-full text-xs ${
                              theme === 'dark' ? 'bg-gray-700' : 'bg-gray-200'
                            }`}
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}

                    <div className="flex gap-4 text-xs opacity-60">
                      <span>Used {search.usageCount} times</span>
                      {search.lastUsed && (
                        <span>Last used: {new Date(search.lastUsed).toLocaleDateString()}</span>
                      )}
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <button
                      onClick={() => handleExecuteSearch(search)}
                      className="px-3 py-1 rounded-md bg-blue-500 text-white hover:bg-blue-600"
                    >
                      Execute
                    </button>
                    <button
                      onClick={() => handleSelectSearch(search)}
                      className="px-3 py-1 rounded-md bg-gray-500 text-white hover:bg-gray-600"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDeleteSearch(search.id)}
                      className="px-3 py-1 rounded-md bg-red-500 text-white hover:bg-red-600"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))}

            {filteredSearches.length === 0 && (
              <div className="text-center py-8 opacity-60">
                No saved searches found
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
