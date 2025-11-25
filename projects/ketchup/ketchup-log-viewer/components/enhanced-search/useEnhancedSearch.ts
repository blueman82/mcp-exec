/**
 * Enhanced Search Hook
 *
 * Core search functionality and state management for the EnhancedSearch component.
 * Handles search operations, rate limiting, filtering, and search history.
 */

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { getSearchManager } from '@/lib/search-manager';
import { getClientIdentifier, checkRateLimit, RATE_LIMITS } from '@/lib/rate-limiter';
import { sanitizeText, sanitizeFilters } from '@/lib/security/sanitizer';
import type {
  SearchFilters,
  SearchResult,
  SearchPreferences,
  SearchQuery,
  SavedSearch,
  SearchState,
} from '@/types/search';
import type { LogLine } from '@/types';

interface UseEnhancedSearchProps {
  logs: LogLine[];
  initialFilters?: SearchFilters;
  onSearchResults?: (results: SearchResult | null) => void;
  onFiltersChange?: (filters: SearchFilters) => void;
  availableContainers?: string[];
  availableServers?: Array<'prod1' | 'prod2'>;
}

export function useEnhancedSearch({
  logs,
  initialFilters = {},
  onSearchResults,
  onFiltersChange,
  availableContainers = [],
  availableServers = ['prod1', 'prod2'],
}: UseEnhancedSearchProps) {
  // Search manager instance
  const searchManager = useMemo(() => getSearchManager(), []);

  // Component state
  const [searchQuery, setSearchQuery] = useState('');
  const [filters, setFilters] = useState<SearchFilters>(initialFilters);
  const [searchResults, setSearchResults] = useState<SearchResult | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preferences, setPreferences] = useState<SearchPreferences>(() => searchManager.getState().preferences);
  const [searchHistory, setSearchHistory] = useState<SearchQuery[]>([]);
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>([]);

  // Refs
  const debouncedSearchRef = useRef<NodeJS.Timeout | null>(null);

  // Load search history from search manager
  useEffect(() => {
    setSearchHistory(searchManager.getHistory());
  }, [searchManager]);

  // Generate client identifier for rate limiting
  const clientIdentifier = useMemo(() => {
    if (typeof window !== 'undefined') {
      // Create a simple client identifier from browser characteristics
      const userAgent = navigator.userAgent;
      const timestamp = Date.now();
      return Buffer.from(`${userAgent}-${timestamp}`).toString('base64').substring(0, 32);
    }
    return 'unknown-client';
  }, []);

  // Load saved searches from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem('enhancedSearch-savedSearches');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) {
          setSavedSearches(parsed);
        }
      }
    } catch (e) {
      console.error('Failed to load saved searches:', e);
    }
  }, []);

  // Update search manager preferences
  useEffect(() => {
    searchManager.updatePreferences(preferences);
  }, [searchManager, preferences]);

  // Perform search with rate limiting and sanitization
  const performSearch = useCallback(async (query: string, searchFilters: SearchFilters) => {
    if (!query.trim() && Object.keys(searchFilters).length === 0) {
      setSearchResults(null);
      onSearchResults?.(null);
      return;
    }

    setIsSearching(true);
    setError(null);

    try {
      // Apply rate limiting
      const rateLimitResult = checkRateLimit(clientIdentifier, RATE_LIMITS.SEARCH);
      if (!rateLimitResult.allowed) {
        throw new Error(`Search rate limit exceeded. Please wait ${rateLimitResult.retryAfter || 60} seconds before trying again.`);
      }

      // Sanitize inputs
      const sanitizedQuery = sanitizeText(query, 1000);
      const sanitizedFilters = sanitizeFilters(searchFilters);

      // Perform search with client identifier for tracking
      const results = await searchManager.search(logs, sanitizedQuery, sanitizedFilters, clientIdentifier);

      setSearchResults(results);
      onSearchResults?.(results);

      // Update search history
      setSearchHistory(searchManager.getHistory());

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Search failed';
      setError(errorMessage);
      setSearchResults(null);
      onSearchResults?.(null);
    } finally {
      setIsSearching(false);
    }
  }, [logs, searchManager, onSearchResults, clientIdentifier]);

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
  const handleSearchChange = useCallback((value: string) => {
    setSearchQuery(value);
    debouncedSearch(value);
  }, [debouncedSearch]);

  // Update filters and notify parent
  const updateFilters = useCallback((newFilters: SearchFilters) => {
    setFilters(newFilters);
    onFiltersChange?.(newFilters);
  }, [onFiltersChange]);

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

  // Save current search
  const saveSearch = useCallback((name: string, description?: string) => {
    if (!searchQuery.trim()) return;

    const newSavedSearch: SavedSearch = {
      id: `saved_${Date.now()}`,
      name: sanitizeText(name, 100),
      query: sanitizeText(searchQuery, 1000),
      filters: { ...filters },
      preferences: { ...preferences },
      createdAt: new Date(),
      usageCount: 0,
      description: description ? sanitizeText(description, 500) : undefined,
    };

    const updated = [...savedSearches, newSavedSearch];
    setSavedSearches(updated);

    try {
      localStorage.setItem('enhancedSearch-savedSearches', JSON.stringify(updated));
    } catch (e) {
      console.error('Failed to save searches:', e);
    }
  }, [searchQuery, filters, preferences, savedSearches]);

  // Load saved search
  const loadSavedSearch = useCallback((savedSearch: SavedSearch) => {
    setSearchQuery(savedSearch.query);
    setFilters(savedSearch.filters);
    setPreferences(savedSearch.preferences);

    // Update usage count
    const updated = savedSearches.map(s =>
      s.id === savedSearch.id
        ? { ...s, lastUsed: new Date(), usageCount: s.usageCount + 1 }
        : s
    );
    setSavedSearches(updated);

    try {
      localStorage.setItem('enhancedSearch-savedSearches', JSON.stringify(updated));
    } catch (e) {
      console.error('Failed to update saved searches:', e);
    }
  }, [savedSearches]);

  // Delete saved search
  const deleteSavedSearch = useCallback((id: string) => {
    const updated = savedSearches.filter(s => s.id !== id);
    setSavedSearches(updated);

    try {
      localStorage.setItem('enhancedSearch-savedSearches', JSON.stringify(updated));
    } catch (e) {
      console.error('Failed to delete saved search:', e);
    }
  }, [savedSearches]);

  // Load search from history
  const loadFromHistory = useCallback((historyItem: SearchQuery) => {
    setSearchQuery(historyItem.query);
    setFilters(historyItem.filters);
    performSearch(historyItem.query, historyItem.filters);
  }, [performSearch]);

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

  // Clear all searches
  const clearAllSearches = useCallback(() => {
    clearSearch();
    clearFilters();
  }, [clearSearch, clearFilters]);

  // Get search state
  const searchState = useMemo(() => searchManager.getState(), [searchManager]);

  return {
    // State
    searchQuery,
    setSearchQuery: handleSearchChange,
    filters,
    searchResults,
    isSearching,
    error,
    preferences,
    setPreferences,
    searchHistory,
    savedSearches,
    searchState,

    // Actions
    handleLogLevelFilter,
    handleServerFilter,
    handleContainerFilter,
    clearSearch,
    clearFilters,
    clearAllSearches,
    saveSearch,
    loadSavedSearch,
    deleteSavedSearch,
    loadFromHistory,
    exportResults,

    // Available options
    availableContainers,
    availableServers,
  };
}