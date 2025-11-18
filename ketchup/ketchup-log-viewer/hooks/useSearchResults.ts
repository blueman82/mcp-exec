/**
 * Custom hook for managing search results, grouping, and highlighting
 * Integrates with search highlighter and grouper for advanced functionality
 */

import { useState, useCallback, useEffect, useMemo } from 'react';
import type { SearchResult } from '@/types/search';
import type { SearchHighlighter, HighlightNavigation } from '@/lib/search-highlighter';
import type { SearchGrouper, GroupedSearchResults } from '@/lib/search-grouper';

export interface UseSearchResultsReturn {
  searchResults: SearchResult | null;
  selectedMatchId: string | null;
  expandedResults: Set<string>;
  groupedResults: GroupedSearchResults | null;
  highlightNavigation: HighlightNavigation;
  handleSearchResults: (results: SearchResult | null) => void;
  setSelectedMatchId: (id: string | null) => void;
  toggleResultExpansion: (id: string) => void;
  navigateToNextHighlight: () => void;
  navigateToPreviousHighlight: () => void;
  updateGrouping: (groupBy: any) => void;
  updateSorting: (sortBy: any, direction?: 'asc' | 'desc') => void;
  applyHighlights: (container: HTMLElement) => void;
}

export interface UseSearchResultsOptions {
  searchHighlighter: SearchHighlighter;
  searchGrouper: SearchGrouper;
  contextContainerRef: React.RefObject<HTMLElement | null>;
  onAnnounce?: (message: string) => void;
}

export function useSearchResults(options: UseSearchResultsOptions): UseSearchResultsReturn {
  const { searchHighlighter, searchGrouper, contextContainerRef, onAnnounce } = options;

  const [searchResults, setSearchResults] = useState<SearchResult | null>(null);
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null);
  const [expandedResults, setExpandedResults] = useState<Set<string>>(new Set());
  const [groupedResults, setGroupedResults] = useState<GroupedSearchResults | null>(null);
  const [highlightNavigation, setHighlightNavigation] = useState<HighlightNavigation>({
    total: 0,
    current: 0,
    highlightIds: [],
  });

  const handleSearchResults = useCallback(
    (results: SearchResult | null) => {
      setSearchResults(results);
      setSelectedMatchId(null);
      setExpandedResults(new Set());

      if (results) {
        // Group and sort results
        const grouped = searchGrouper.processSearchResult(results);
        setGroupedResults(grouped);

        // Process highlights
        searchHighlighter.processSearchResults(results);
        const navigation = searchHighlighter.getNavigationState();
        setHighlightNavigation(navigation);

        // Apply highlights if context container is available
        if (contextContainerRef.current) {
          searchHighlighter.applyHighlights(contextContainerRef.current);
        }

        // Announce results
        const message = `Found ${results.totalMatches} search result${
          results.totalMatches !== 1 ? 's' : ''
        } across ${grouped.groups.size} group${grouped.groups.size !== 1 ? 's' : ''}`;
        onAnnounce?.(message);
      } else {
        setGroupedResults(null);
        setHighlightNavigation({ total: 0, current: 0, highlightIds: [] });
        searchHighlighter.clearHighlights();
        onAnnounce?.('Search cleared');
      }
    },
    [searchGrouper, searchHighlighter, contextContainerRef, onAnnounce]
  );

  const toggleResultExpansion = useCallback((id: string) => {
    setExpandedResults((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(id)) {
        newSet.delete(id);
      } else {
        newSet.add(id);
      }
      return newSet;
    });
  }, []);

  const navigateToNextHighlight = useCallback(() => {
    searchHighlighter.navigateToNext();
    const navigation = searchHighlighter.getNavigationState();
    setHighlightNavigation(navigation);
    onAnnounce?.(`Highlight ${navigation.current + 1} of ${navigation.total}`);
  }, [searchHighlighter, onAnnounce]);

  const navigateToPreviousHighlight = useCallback(() => {
    searchHighlighter.navigateToPrevious();
    const navigation = searchHighlighter.getNavigationState();
    setHighlightNavigation(navigation);
    onAnnounce?.(`Highlight ${navigation.current + 1} of ${navigation.total}`);
  }, [searchHighlighter, onAnnounce]);

  const updateGrouping = useCallback(
    (groupBy: any) => {
      searchGrouper.updateGroupingConfig({ groupBy });
      if (searchResults) {
        const grouped = searchGrouper.processSearchResult(searchResults);
        setGroupedResults(grouped);
      }
    },
    [searchGrouper, searchResults]
  );

  const updateSorting = useCallback(
    (sortBy: any, direction: 'asc' | 'desc' = 'desc') => {
      searchGrouper.updateSortingConfig({ sortBy, direction });
      if (searchResults) {
        const grouped = searchGrouper.processSearchResult(searchResults);
        setGroupedResults(grouped);
      }
    },
    [searchGrouper, searchResults]
  );

  const applyHighlights = useCallback(
    (container: HTMLElement) => {
      if (searchResults) {
        searchHighlighter.applyHighlights(container);
      }
    },
    [searchHighlighter, searchResults]
  );

  return {
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
  };
}
