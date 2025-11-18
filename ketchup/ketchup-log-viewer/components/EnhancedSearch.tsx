/**
 * EnhancedSearch Component - Advanced search interface with floating labels,
 * filter pills, keyboard shortcuts, search history, and export functionality
 *
 * WCAG 2.1 AA compliant with comprehensive accessibility features including:
 * - ARIA labels and descriptions
 * - Keyboard navigation support
 * - Screen reader compatibility
 * - Live regions for status updates
 * - Focus management
 * - Semantic HTML structure
 */

'use client';

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';

if (typeof globalThis !== 'undefined' && !(globalThis as Record<string, unknown>).React) {
  (globalThis as Record<string, unknown>).React = React;
}
import { getSearchManager } from '@/lib/search-manager';
import { getSavedSearchManager } from '@/lib/saved-searches';
import { SavedSearchManager } from './SavedSearchManager';
import { createSafeStorageData, parseSafeStorageData } from '@/lib/security/sanitizer';
import type {
  SearchFilters,
  SearchResult,
  SearchPreferences,
  SearchQuery,
  SavedSearch,
  SearchState,
  SearchSuggestion,
  SavedSearchWithMetadata
} from '@/types/search';
import type { LogLine } from '@/types';

interface EnhancedSearchProps {
  /** Available log lines to search through */
  logs: LogLine[];
  /** Current theme (affects styling) */
  theme: 'dark' | 'light';
  /** Initial search filters */
  initialFilters?: SearchFilters;
  /** Callback when search results change */
  onSearchResults?: (results: SearchResult | null) => void;
  /** Callback when filters change */
  onFiltersChange?: (filters: SearchFilters) => void;
  /** Available containers for filtering */
  availableContainers?: string[];
  /** Available servers for filtering */
  availableServers?: Array<'prod1' | 'prod2'>;
  /** Whether to show advanced options */
  showAdvanced?: boolean;
  /** Custom CSS classes */
  className?: string;
}

interface FilterPillProps {
  label: string;
  value: string;
  isActive: boolean;
  onClick: () => void;
  onRemove?: () => void;
  color?: string;
  theme: 'dark' | 'light';
}

const FilterPill: React.FC<FilterPillProps> = ({
  label,
  value,
  isActive,
  onClick,
  onRemove,
  color = 'blue',
  theme
}) => {
  const baseClasses = 'inline-flex items-center px-3 py-1 rounded-full text-sm font-medium transition-all duration-200 cursor-pointer border focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50';
  const activeClasses = theme === 'dark'
    ? `bg-${color}-600 text-white border-${color}-500`
    : `bg-${color}-500 text-white border-${color}-400`;
  const inactiveClasses = theme === 'dark'
    ? 'bg-gray-700 text-gray-300 border-gray-600 hover:bg-gray-600'
    : 'bg-gray-200 text-gray-700 border-gray-300 hover:bg-gray-300';

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={`Filter by ${label}: ${value}`}
      aria-pressed={isActive}
      className={`${baseClasses} ${isActive ? activeClasses : inactiveClasses}`}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick();
        }
      }}
    >
      <span>{label}: {value}</span>
      {onRemove && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          aria-label={`Remove ${label} filter: ${value}`}
          className="ml-2 hover:opacity-70 focus:outline-none focus:ring-1 focus:ring-white focus:ring-opacity-50"
        >
          ✕
        </button>
      )}
    </div>
  );
};

export const EnhancedSearch: React.FC<EnhancedSearchProps> = ({
  logs,
  theme,
  initialFilters = {},
  onSearchResults,
  onFiltersChange,
  availableContainers = [],
  availableServers = ['prod1', 'prod2'],
  showAdvanced = true,
  className = '',
}) => {
  // Search manager instance
  const searchManager = useMemo(() => getSearchManager(), []);

  // Component state
  const [searchQuery, setSearchQuery] = useState('');
  const [filters, setFilters] = useState<SearchFilters>(initialFilters);
  const [searchResults, setSearchResults] = useState<SearchResult | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showSavedSearches, setShowSavedSearches] = useState(false);
  const [showAdvancedSearchManager, setShowAdvancedSearchManager] = useState(false);
  const [showAdvancedPanel, setShowAdvancedPanel] = useState(showAdvanced);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [searchSuggestions, setSearchSuggestions] = useState<SearchSuggestion[]>([]);
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>([]);
  const [searchHistory, setSearchHistory] = useState<SearchQuery[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [preferences, setPreferences] = useState<SearchPreferences>(() => searchManager.getState().preferences);

  // Accessibility state
  const [focusedSuggestionIndex, setFocusedSuggestionIndex] = useState(-1);
  const [searchStatusMessage, setSearchStatusMessage] = useState<string>('');
  const [announcementMessage, setAnnouncementMessage] = useState<string>('');

  // Refs
  const searchInputRef = useRef<HTMLInputElement>(null);
  const debouncedSearchRef = useRef<NodeJS.Timeout | null>(null);
  const componentRef = useRef<HTMLDivElement>(null);
  const statusLiveRef = useRef<HTMLDivElement>(null);
  const announcementLiveRef = useRef<HTMLDivElement>(null);

  // Load saved searches from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem('enhancedSearch-savedSearches');
      if (saved) {
        const parsed = parseSafeStorageData(saved);
        if (Array.isArray(parsed)) {
          setSavedSearches(parsed);
        }
      }
    } catch (e) {
      console.error('Failed to load saved searches:', e);
    }
  }, []);

  // Load search history from search manager
  useEffect(() => {
    setSearchHistory(searchManager.getHistory());
  }, [searchManager]);

  // Accessibility: Announce messages to screen readers
  const announceToScreenReader = useCallback((message: string, priority: 'polite' | 'assertive' = 'polite') => {
    setAnnouncementMessage(message);
    const ref = priority === 'assertive' ? announcementLiveRef.current : statusLiveRef.current;
    if (ref) {
      ref.textContent = message;
      // Clear after announcement
      setTimeout(() => {
        if (ref) ref.textContent = '';
      }, 1000);
    }
  }, []);

  // Accessibility: Update search status for screen readers
  const updateSearchStatus = useCallback((message: string) => {
    setSearchStatusMessage(message);
    if (statusLiveRef.current) {
      statusLiveRef.current.textContent = message;
    }
  }, []);

  // Update filters and notify parent
  const updateFilters = useCallback((newFilters: SearchFilters) => {
    setFilters(newFilters);
    onFiltersChange?.(newFilters);

    // Announce filter changes to screen readers
    const activeFilters = Object.keys(newFilters).filter(key => {
      const value = newFilters[key as keyof SearchFilters];
      return Array.isArray(value) ? value.length > 0 : !!value;
    });

    if (activeFilters.length > 0) {
      announceToScreenReader(`Applied ${activeFilters.length} filter${activeFilters.length > 1 ? 's' : ''}: ${activeFilters.join(', ')}`);
    } else {
      announceToScreenReader('All filters cleared');
    }
  }, [onFiltersChange, announceToScreenReader]);

  // Perform search with debouncing
  const performSearch = useCallback(async (query: string, searchFilters: SearchFilters) => {
    if (!query.trim() && Object.keys(searchFilters).length === 0) {
      setSearchResults(null);
      onSearchResults?.(null);
      updateSearchStatus('Search cleared');
      return;
    }

    setIsSearching(true);
    setError(null);
    updateSearchStatus('Searching...');

    try {
      const results = await searchManager.search(logs, query, searchFilters);
      setSearchResults(results);
      onSearchResults?.(results);

      // Update search history
      setSearchHistory(searchManager.getHistory());

      // Announce search results to screen readers
      if (results.totalMatches > 0) {
        const message = `Found ${results.totalMatches} result${results.totalMatches > 1 ? 's' : ''} in ${results.executionTime.toFixed(2)} milliseconds${results.metrics?.fromCache ? ' from cache' : ''}`;
        updateSearchStatus(message);
        announceToScreenReader(message);
      } else {
        updateSearchStatus('No results found');
        announceToScreenReader('No results found for your search');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Search failed';
      setError(errorMessage);
      setSearchResults(null);
      onSearchResults?.(null);
      updateSearchStatus('Search failed');
      announceToScreenReader(`Search failed: ${errorMessage}`, 'assertive');
    } finally {
      setIsSearching(false);
    }
  }, [logs, searchManager, onSearchResults, updateSearchStatus, announceToScreenReader]);

  // Debounced search handler
  const debouncedSearch = useCallback((query: string) => {
    if (debouncedSearchRef.current) {
      clearTimeout(debouncedSearchRef.current);
    }

    debouncedSearchRef.current = setTimeout(() => {
      performSearch(query, filters);
    }, preferences.debounceDelay ?? 300);
  }, [performSearch, filters, preferences.debounceDelay]);

  // Handle search input change
  const handleSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearchQuery(value);
    debouncedSearch(value);
  }, [debouncedSearch]);

  // Handle filter changes
  const handleLogLevelFilter = useCallback((level: string) => {
    const currentLevels = filters.logLevels || [];
    const newLevels = currentLevels.includes(level as any)
      ? currentLevels.filter(l => l !== level)
      : [...currentLevels, level as any];

    updateFilters({ ...filters, logLevels: newLevels });
  }, [filters, updateFilters]);

  const handleServerFilter = useCallback((server: 'prod1' | 'prod2') => {
    const currentServers = filters.servers || [];
    const newServers = currentServers.includes(server)
      ? currentServers.filter(s => s !== server)
      : [...currentServers, server];

    updateFilters({ ...filters, servers: newServers });
  }, [filters, updateFilters]);

  const handleContainerFilter = useCallback((container: string) => {
    const currentContainers = filters.containers || [];
    const newContainers = currentContainers.includes(container)
      ? currentContainers.filter(c => c !== container)
      : [...currentContainers, container];

    updateFilters({ ...filters, containers: newContainers });
  }, [filters, updateFilters]);

  // Clear search
  const clearSearch = useCallback(() => {
    setSearchQuery('');
    setSearchResults(null);
    setError(null);
    onSearchResults?.(null);
  }, [onSearchResults]);

  // Clear all filters
  const clearFilters = useCallback(() => {
    updateFilters({});
  }, [updateFilters]);

  // Export search results
  const exportResults = useCallback((format: 'json' | 'csv' | 'txt' = 'json') => {
    if (!searchResults) return;

    try {
      const exported = searchManager.exportResults(searchResults, format);
      const blob = new Blob([exported], {
        type: format === 'json' ? 'application/json' : 'text/plain'
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;

      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      link.download = `search-results-${timestamp}.${format}`;

      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    }
  }, [searchResults, searchManager]);

  // Save current search
  const saveSearch = useCallback((name: string, description?: string) => {
    if (!searchQuery.trim()) return;

    const newSavedSearch: SavedSearch = {
      id: `saved_${Date.now()}`,
      name,
      query: searchQuery,
      filters: { ...filters },
      preferences: { ...preferences },
      createdAt: new Date(),
      usageCount: 0,
      description,
    };

    const updated = [...savedSearches, newSavedSearch];
    setSavedSearches(updated);

    try {
      localStorage.setItem('enhancedSearch-savedSearches', createSafeStorageData(updated));
    } catch (e) {
      console.error('Failed to save searches:', e);
    }
  }, [searchQuery, filters, preferences, savedSearches]);

  // Load saved search
  const loadSavedSearch = useCallback((savedSearch: SavedSearch) => {
    setSearchQuery(savedSearch.query);
    setFilters(savedSearch.filters);
    setPreferences(savedSearch.preferences);
    setShowSavedSearches(false);

    // Update usage count
    const updated = savedSearches.map(s =>
      s.id === savedSearch.id
        ? { ...s, lastUsed: new Date(), usageCount: s.usageCount + 1 }
        : s
    );
    setSavedSearches(updated);

    try {
      localStorage.setItem('enhancedSearch-savedSearches', createSafeStorageData(updated));
    } catch (e) {
      console.error('Failed to update saved searches:', e);
    }
  }, [savedSearches]);

  // Delete saved search
  const deleteSavedSearch = useCallback((id: string) => {
    const updated = savedSearches.filter(s => s.id !== id);
    setSavedSearches(updated);

    try {
      localStorage.setItem('enhancedSearch-savedSearches', createSafeStorageData(updated));
    } catch (e) {
      console.error('Failed to delete saved search:', e);
    }
  }, [savedSearches]);

  // Handle search selection from advanced manager
  const handleAdvancedSearchSelection = useCallback((search: SavedSearchWithMetadata) => {
    setSearchQuery(search.query);
    setFilters(search.filters);
    setPreferences(search.preferences);
    setShowAdvancedSearchManager(false);
    performSearch(search.query, search.filters);
    announceToScreenReader(`Loaded saved search: ${search.name}`);
  }, [performSearch, announceToScreenReader]);

  // Load search from history
  const loadFromHistory = useCallback((historyItem: SearchQuery) => {
    setSearchQuery(historyItem.query);
    setFilters(historyItem.filters);
    setShowHistory(false);
    performSearch(historyItem.query, historyItem.filters);
  }, [performSearch]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl/Cmd + F: Focus search
      if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
        e.preventDefault();
        searchInputRef.current?.focus();
        announceToScreenReader('Search input focused');
      }

      // Escape: Clear search or close dropdowns
      if (e.key === 'Escape') {
        if (showHistory || showSavedSearches || showShortcuts) {
          setShowHistory(false);
          setShowSavedSearches(false);
          setShowShortcuts(false);
          searchInputRef.current?.focus();
          announceToScreenReader('Dropdown closed');
        } else {
          clearSearch();
        }
      }

      // Ctrl/Cmd + K: Clear search
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        clearSearch();
        announceToScreenReader('Search cleared');
      }

      // Ctrl/Cmd + R: Toggle regex mode
      if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
        e.preventDefault();
        setPreferences(prev => ({ ...prev, useRegex: !prev.useRegex }));
        announceToScreenReader(`Regular expressions ${preferences.useRegex ? 'disabled' : 'enabled'}`);
      }

      // Ctrl/Cmd + S: Save search
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        const name = prompt('Enter search name:');
        if (name?.trim()) {
          saveSearch(name.trim());
          announceToScreenReader(`Search saved as "${name.trim()}"`);
        }
      }

      // Ctrl/Cmd + E: Export results
      if ((e.ctrlKey || e.metaKey) && e.key === 'e') {
        e.preventDefault();
        if (searchResults) {
          exportResults();
          announceToScreenReader('Search results exported');
        } else {
          announceToScreenReader('No search results to export', 'assertive');
        }
      }

      // Arrow key navigation for suggestions
      if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && showHistory && searchHistory.length > 0) {
        e.preventDefault();
        const maxIndex = searchHistory.length - 1;
        let newIndex = focusedSuggestionIndex;

        if (e.key === 'ArrowDown') {
          newIndex = focusedSuggestionIndex < maxIndex ? focusedSuggestionIndex + 1 : 0;
        } else {
          newIndex = focusedSuggestionIndex > 0 ? focusedSuggestionIndex - 1 : maxIndex;
        }

        setFocusedSuggestionIndex(newIndex);
        announceToScreenReader(`History item ${newIndex + 1} of ${searchHistory.length}: ${searchHistory[newIndex].query}`);
      }

      // Enter to select suggestion
      if (e.key === 'Enter' && focusedSuggestionIndex >= 0 && showHistory) {
        e.preventDefault();
        loadFromHistory(searchHistory[focusedSuggestionIndex]);
        setFocusedSuggestionIndex(-1);
      }

      // ?: Show shortcuts
      if (e.key === '?' && !e.ctrlKey && !e.metaKey && e.shiftKey) {
        e.preventDefault();
        setShowShortcuts(!showShortcuts);
        announceToScreenReader(showShortcuts ? 'Keyboard shortcuts closed' : 'Keyboard shortcuts opened');
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [showHistory, showSavedSearches, showShortcuts, clearSearch, searchResults, exportResults, saveSearch, focusedSuggestionIndex, searchHistory, preferences.useRegex, announceToScreenReader, loadFromHistory]);

  // Click outside to close dropdowns
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (componentRef.current && !componentRef.current.contains(e.target as Node)) {
        setShowHistory(false);
        setShowSavedSearches(false);
        setShowShortcuts(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Theme-specific styles
  const themeClasses = theme === 'dark'
    ? 'bg-gray-800 border-gray-700 text-gray-200'
    : 'bg-white border-gray-300 text-gray-800';

  const inputClasses = theme === 'dark'
    ? 'bg-gray-900 border-gray-600 text-gray-200 placeholder-gray-500 focus:border-blue-500'
    : 'bg-white border-gray-300 text-gray-800 placeholder-gray-400 focus:border-blue-500';

  return (
    <div ref={componentRef} className={`enhanced-search-container ${className}`}>
      {/* Skip to content link for keyboard users */}
      <a
        href="#search-results"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 bg-blue-500 text-white px-4 py-2 rounded-lg z-50 focus:outline-none focus:ring-2 focus:ring-blue-300"
      >
        Skip to search results
      </a>

      {/* Live regions for screen readers */}
      <div
        ref={statusLiveRef}
        aria-live="polite"
        aria-atomic="true"
        role="status"
        className="sr-only"
      />
      <div
        ref={announcementLiveRef}
        aria-live="assertive"
        aria-atomic="true"
        role="status"
        className="sr-only"
      />

      {/* Main search input */}
      <div className="relative">
        <div className="relative">
          <label htmlFor="search-input" className="sr-only">
            Search logs
          </label>
          <span
            className={`absolute left-3 top-1/2 transform -translate-y-1/2 ${
              theme === 'dark' ? 'text-gray-400' : 'text-gray-500'
            }`}
            aria-hidden="true"
          >
            🔍
          </span>
          <input
            id="search-input"
            ref={searchInputRef}
            type="text"
            role="combobox"
            aria-label="Search logs..."
            aria-describedby="search-description search-status"
            aria-expanded={showHistory || showSavedSearches}
            aria-activedescendant={focusedSuggestionIndex >= 0 && showHistory ? `history-item-${focusedSuggestionIndex}` : undefined}
            aria-busy={isSearching}
            autoComplete="off"
            value={searchQuery}
            onChange={handleSearchChange}
            placeholder="Search logs... (Ctrl+F)"
            className={`w-full pl-10 pr-12 py-3 rounded-lg border ${inputClasses} focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50 transition-all duration-200`}
          />
          <div id="search-description" className="sr-only">
            Enter search terms and press Enter. Use arrow keys to navigate history. Press Ctrl+F to focus, Ctrl+K to clear, Ctrl+S to save search.
          </div>
          <div id="search-status" className="sr-only" aria-live="polite">
            {searchStatusMessage}
          </div>

          {searchQuery && (
            <button
              onClick={clearSearch}
              aria-label="Clear search"
              className={`absolute right-3 top-1/2 transform -translate-y-1/2 p-1 rounded-full hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50`}
            >
              <span className={theme === 'dark' ? 'text-gray-400' : 'text-gray-500'}>✕</span>
            </button>
          )}
          {isSearching && (
            <div
              className="absolute right-3 top-1/2 transform -translate-y-1/2"
              aria-label="Searching"
              role="status"
            >
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-500"></div>
            </div>
          )}
        </div>

        {/* Floating label for advanced mode indicator */}
        {preferences.useRegex && (
          <div
            className="absolute -top-2 left-4 bg-blue-500 text-white text-xs px-2 py-1 rounded-full"
            role="status"
            aria-live="polite"
          >
            Regex
          </div>
        )}
      </div>

      {/* Filter pills */}
      <nav className="flex flex-wrap gap-2 mt-3" aria-label="Log filters">
        <h3 className="sr-only">Filter logs by level, server, and container</h3>
        {/* Log level filters */}
        <div className="flex flex-wrap gap-2" role="group" aria-label="Log level filters">
          {(['error', 'warn', 'info', 'debug'] as const).map(level => (
            <FilterPill
              key={level}
              label="Level"
              value={level.toUpperCase()}
              isActive={filters.logLevels?.includes(level) || false}
              onClick={() => handleLogLevelFilter(level)}
              theme={theme}
              color={level === 'error' ? 'red' : level === 'warn' ? 'yellow' : level === 'info' ? 'blue' : 'gray'}
            />
          ))}
        </div>

        {/* Server filters */}
        <div className="flex flex-wrap gap-2" role="group" aria-label="Server filters">
          {availableServers.map(server => (
            <FilterPill
              key={server}
              label="Server"
              value={server}
              isActive={filters.servers?.includes(server) || false}
              onClick={() => handleServerFilter(server)}
              theme={theme}
              color={server === 'prod1' ? 'blue' : 'green'}
            />
          ))}
        </div>

        {/* Container filters */}
        <div className="flex flex-wrap gap-2" role="group" aria-label="Container filters">
          {filters.containers?.map(container => (
            <FilterPill
              key={container}
              label="Container"
              value={container}
              isActive={true}
              onClick={() => {}}
              onRemove={() => handleContainerFilter(container)}
              theme={theme}
              color="purple"
            />
          ))}
        </div>
      </nav>

      {/* Action buttons */}
      <div className="flex items-center gap-2 mt-3" role="toolbar" aria-label="Search actions">
        <button
          onClick={() => setShowHistory(!showHistory)}
          aria-expanded={showHistory}
          aria-label={`Search history, ${searchHistory.length} items, ${showHistory ? 'open' : 'closed'}`}
          className={`px-3 py-2 rounded-lg border ${themeClasses} hover:opacity-80 transition-opacity flex items-center gap-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50`}
        >
          <span aria-hidden="true">🕐</span>
          History ({searchHistory.length})
        </button>

        <button
          onClick={() => setShowSavedSearches(!showSavedSearches)}
          aria-expanded={showSavedSearches}
          aria-label={`Saved searches, ${savedSearches.length} items, ${showSavedSearches ? 'open' : 'closed'}`}
          className={`px-3 py-2 rounded-lg border ${themeClasses} hover:opacity-80 transition-opacity flex items-center gap-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50`}
        >
          <span aria-hidden="true">📁</span>
          Saved ({savedSearches.length})
        </button>

        <button
          onClick={() => setShowAdvancedSearchManager(true)}
          aria-label="Open search manager dialog"
          className={`px-3 py-2 rounded-lg border ${themeClasses} hover:opacity-80 transition-opacity flex items-center gap-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50`}
        >
          <span aria-hidden="true">🗂️</span>
          Manage Searches
        </button>

        {searchResults && (
          <button
            onClick={() => exportResults()}
            aria-label="Export search results"
            className={`px-3 py-2 rounded-lg border ${themeClasses} hover:opacity-80 transition-opacity flex items-center gap-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50`}
          >
            <span aria-hidden="true">💾</span>
            Export
          </button>
        )}

        <button
          onClick={() => setShowAdvancedPanel(!showAdvancedPanel)}
          aria-expanded={showAdvancedPanel}
          aria-label={`Advanced search options, ${showAdvancedPanel ? 'open' : 'closed'}`}
          className={`px-3 py-2 rounded-lg border ${themeClasses} hover:opacity-80 transition-opacity flex items-center gap-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50`}
        >
          <span aria-hidden="true">⚙️</span>
          Advanced
        </button>

        <button
          onClick={() => setShowShortcuts(!showShortcuts)}
          aria-expanded={showShortcuts}
          aria-label={`Keyboard shortcuts help, ${showShortcuts ? 'open' : 'closed'}`}
          className={`px-3 py-2 rounded-lg border ${themeClasses} hover:opacity-80 transition-opacity flex items-center gap-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50`}
        >
          <span aria-hidden="true">⌨️</span>
          Shortcuts
        </button>

        {(Object.keys(filters).length > 0 || searchQuery) && (
          <button
            onClick={clearFilters}
            aria-label="Clear all filters and search"
            className="px-3 py-2 rounded-lg bg-red-600 text-white hover:bg-red-700 transition-colors flex items-center gap-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50"
          >
            <span aria-hidden="true">✕</span>
            Clear All
          </button>
        )}
      </div>

      {/* Search results summary */}
      {searchResults && (
        <div
          id="search-results"
          className={`mt-3 p-3 rounded-lg border ${themeClasses} text-sm`}
          role="status"
          aria-live="polite"
        >
          <div className="flex items-center justify-between">
            <div>
              Found {searchResults.totalMatches} result{searchResults.totalMatches !== 1 ? 's' : ''} in {searchResults.executionTime.toFixed(2)}ms
              {searchResults.metrics?.fromCache && ' (from cache)'}
            </div>
            {searchResults.hasMore && (
              <span className="text-blue-500" role="note">More results available</span>
            )}
          </div>
        </div>
      )}

      {/* Error message */}
      {error && (
        <div
          className="mt-3 p-3 rounded-lg bg-red-100 border border-red-300 text-red-700 text-sm flex items-center gap-2"
          role="alert"
          aria-live="assertive"
        >
          <span aria-hidden="true">⚠️</span>
          <span>{error}</span>
        </div>
      )}

      {/* Search history dropdown */}
      {showHistory && searchHistory.length > 0 && (
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
                  onClick={() => {
                    loadFromHistory(item);
                    setFocusedSuggestionIndex(-1);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      loadFromHistory(item);
                      setFocusedSuggestionIndex(-1);
                    }
                  }}
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
      )}

      {/* Saved searches dropdown */}
      {showSavedSearches && (
        <div
          className={`absolute top-full left-0 right-0 mt-2 p-4 rounded-lg border shadow-lg z-10 ${themeClasses}`}
          role="dialog"
          aria-label="Saved searches"
          aria-modal="true"
        >
          <div className="flex items-center justify-between mb-3">
            <h4 className="font-semibold">Saved Searches</h4>
            <button
              onClick={() => {
                const name = prompt('Enter search name:');
                if (name?.trim()) {
                  saveSearch(name.trim());
                }
              }}
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
                      onClick={() => loadSavedSearch(saved)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          loadSavedSearch(saved);
                        }
                      }}
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
                      onClick={() => deleteSavedSearch(saved.id)}
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
      )}

      {/* Keyboard shortcuts modal */}
      {showShortcuts && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
          role="dialog"
          aria-labelledby="shortcuts-title"
          aria-modal="true"
        >
          <div className={`p-6 rounded-lg shadow-xl max-w-md w-full mx-4 ${themeClasses}`}>
            <div className="flex items-center justify-between mb-4">
              <h2 id="shortcuts-title" className="text-lg font-semibold">Keyboard Shortcuts</h2>
              <button
                onClick={() => setShowShortcuts(false)}
                aria-label="Close keyboard shortcuts"
                className="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50"
              >
                <span aria-hidden="true">✕</span>
              </button>
            </div>
            <dl className="space-y-2 text-sm" role="list">
              <div className="flex justify-between" role="listitem">
                <dt>Focus search</dt>
                <dd>
                  <kbd className="px-2 py-1 bg-gray-200 dark:bg-gray-700 rounded border" aria-label="Control key plus F">
                    Ctrl+F
                  </kbd>
                </dd>
              </div>
              <div className="flex justify-between" role="listitem">
                <dt>Clear search</dt>
                <dd>
                  <kbd className="px-2 py-1 bg-gray-200 dark:bg-gray-700 rounded border" aria-label="Control key plus K">
                    Ctrl+K
                  </kbd>
                </dd>
              </div>
              <div className="flex justify-between" role="listitem">
                <dt>Toggle regex</dt>
                <dd>
                  <kbd className="px-2 py-1 bg-gray-200 dark:bg-gray-700 rounded border" aria-label="Control key plus R">
                    Ctrl+R
                  </kbd>
                </dd>
              </div>
              <div className="flex justify-between" role="listitem">
                <dt>Save search</dt>
                <dd>
                  <kbd className="px-2 py-1 bg-gray-200 dark:bg-gray-700 rounded border" aria-label="Control key plus S">
                    Ctrl+S
                  </kbd>
                </dd>
              </div>
              <div className="flex justify-between" role="listitem">
                <dt>Export results</dt>
                <dd>
                  <kbd className="px-2 py-1 bg-gray-200 dark:bg-gray-700 rounded border" aria-label="Control key plus E">
                    Ctrl+E
                  </kbd>
                </dd>
              </div>
              <div className="flex justify-between" role="listitem">
                <dt>Show shortcuts</dt>
                <dd>
                  <kbd className="px-2 py-1 bg-gray-200 dark:bg-gray-700 rounded border" aria-label="Shift key plus question mark">
                    Shift+?
                  </kbd>
                </dd>
              </div>
              <div className="flex justify-between" role="listitem">
                <dt>Navigate history</dt>
                <dd>
                  <kbd className="px-2 py-1 bg-gray-200 dark:bg-gray-700 rounded border" aria-label="Up or down arrow keys">
                    ↑↓
                  </kbd>
                </dd>
              </div>
              <div className="flex justify-between" role="listitem">
                <dt>Close dropdowns</dt>
                <dd>
                  <kbd className="px-2 py-1 bg-gray-200 dark:bg-gray-700 rounded border" aria-label="Escape key">
                    Esc
                  </kbd>
                </dd>
              </div>
            </dl>
          </div>
        </div>
      )}

      {/* Advanced options panel */}
      {showAdvancedPanel && (
        <div
          className={`mt-4 p-4 rounded-lg border ${themeClasses}`}
          role="region"
          aria-labelledby="advanced-options-title"
        >
          <h4 id="advanced-options-title" className="font-semibold mb-3">Advanced Search Options</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4" role="group" aria-label="Search preferences">
            <div>
              <label className="flex items-center space-x-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={preferences.caseSensitive}
                  onChange={(e) => {
                    setPreferences(prev => ({ ...prev, caseSensitive: e.target.checked }));
                    announceToScreenReader(`Case sensitive search ${e.target.checked ? 'enabled' : 'disabled'}`);
                  }}
                  className="rounded focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50"
                />
                <span className="text-sm">Case sensitive</span>
              </label>
            </div>
            <div>
              <label className="flex items-center space-x-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={preferences.useRegex}
                  onChange={(e) => {
                    setPreferences(prev => ({ ...prev, useRegex: e.target.checked }));
                    announceToScreenReader(`Regular expressions ${e.target.checked ? 'enabled' : 'disabled'}`);
                  }}
                  className="rounded focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50"
                />
                <span className="text-sm">Use regular expressions</span>
              </label>
            </div>
            <div>
              <label className="flex items-center space-x-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={preferences.includeTimestamps}
                  onChange={(e) => {
                    setPreferences(prev => ({ ...prev, includeTimestamps: e.target.checked }));
                    announceToScreenReader(`Include timestamps in search ${e.target.checked ? 'enabled' : 'disabled'}`);
                  }}
                  className="rounded focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50"
                />
                <span className="text-sm">Include timestamps in search</span>
              </label>
            </div>
            <div>
              <label className="flex items-center space-x-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={preferences.highlightMatches}
                  onChange={(e) => {
                    setPreferences(prev => ({ ...prev, highlightMatches: e.target.checked }));
                    announceToScreenReader(`Highlight matches ${e.target.checked ? 'enabled' : 'disabled'}`);
                  }}
                  className="rounded focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50"
                />
                <span className="text-sm">Highlight matches</span>
              </label>
            </div>
          </div>
        </div>
      )}

      {/* Advanced Search Manager Modal */}
      {showAdvancedSearchManager && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
          role="dialog"
          aria-labelledby="advanced-search-manager-title"
          aria-modal="true"
          onClick={() => setShowAdvancedSearchManager(false)}
        >
          <div
            className="w-full max-w-6xl max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="relative">
              <button
                onClick={() => setShowAdvancedSearchManager(false)}
                aria-label="Close search manager"
                className="absolute top-4 right-4 z-10 p-2 rounded-full bg-red-500 text-white hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-opacity-50"
              >
                <span aria-hidden="true">✕</span>
              </button>
              <SavedSearchManager
                theme={theme}
                onSelectSearch={handleAdvancedSearchSelection}
                onExecuteSearch={handleAdvancedSearchSelection}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default EnhancedSearch;