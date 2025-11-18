/**
 * Search Types - Comprehensive TypeScript interfaces for enhanced search functionality
 */

import type { LogLine } from './index';

/**
 * Search modes supported by the search manager
 */
export type SearchMode = 'text' | 'regex' | 'fuzzy' | 'semantic';

/**
 * Available log levels for filtering
 */
export type LogLevel = 'error' | 'warn' | 'info' | 'debug' | 'trace' | 'none';

/**
 * Server identifiers
 */
export type ServerType = 'prod1' | 'prod2';

/**
 * Search query with metadata
 */
export interface SearchQuery {
  id: string;
  query: string;
  filters: SearchFilters;
  timestamp: Date;
  resultCount: number;
  executionTime: number;
}

/**
 * Search filters configuration
 */
export interface SearchFilters {
  /** Log levels to include in search */
  logLevels?: LogLevel[];
  /** Servers to search across */
  servers?: ServerType[];
  /** Specific containers to search */
  containers?: string[];
  /** Time range for filtering logs */
  timeRange?: {
    start?: Date;
    end?: Date;
  };
  /** Maximum number of results to return */
  maxResults?: number;
  /** Minimum score threshold for matches */
  minScore?: number;
  /** Whether to include archived logs */
  includeArchived?: boolean;
  /** Custom filter predicates */
  customFilters?: Array<(log: LogLine) => boolean>;
}

/**
 * Individual search match result
 */
export interface SearchMatch {
  /** Index of the matched line in the original log array */
  lineIndex: number;
  /** The complete log entry that matched */
  log: LogLine;
  /** Start position of the match within the log content */
  matchStart: number;
  /** End position of the match within the log content */
  matchEnd: number;
  /** Relevance score (higher = more relevant) */
  score: number;
  /** Context around the match for preview */
  context: string;
  /** Match groups for regex searches */
  groups?: string[];
  /** Named capture groups for regex searches */
  namedGroups?: Record<string, string>;
}

export interface SearchResultPagination {
  pageSize: number;
  currentPage: number;
  totalPages: number;
}

export interface SearchResultPage {
  index: number;
  matches: SearchMatch[];
  hasMore: boolean;
}

export interface SearchProgressSnapshot {
  completion: number;
  chunksProcessed: number;
  totalChunks: number;
  estimatedRemainingMs: number;
}

export type SearchProgressEvent =
  | {
      type: 'start';
      processedLogs: number;
      totalLogs: number;
      matchesFound: number;
      chunkIndex: number;
      totalChunks: number;
    }
  | {
      type: 'chunk';
      processedLogs: number;
      totalLogs: number;
      matchesFound: number;
      chunkIndex: number;
      totalChunks: number;
      partialResult: SearchResult;
      page?: SearchResultPage;
    }
  | {
      type: 'complete' | 'cancelled';
      processedLogs: number;
      totalLogs: number;
      matchesFound: number;
      chunkIndex: number;
      totalChunks: number;
      partialResult: SearchResult;
    }
  | {
      type: 'error';
      processedLogs: number;
      totalLogs: number;
      matchesFound: number;
      chunkIndex: number;
      totalChunks: number;
      errorMessage: string;
    };

export interface SearchOptimizerOptions {
  chunkSize?: number;
  pageSize?: number;
  forceMainThread?: boolean;
  abortSignal?: AbortSignal;
  onProgress?: (event: SearchProgressEvent) => void;
}

/**
 * Complete search result set
 */
export interface SearchResult {
  /** The original query that was executed */
  query: string;
  /** Array of matching log entries */
  matches: SearchMatch[];
  /** Total number of matches found */
  totalMatches: number;
  /** Time taken to execute the search in milliseconds */
  executionTime: number;
  /** Filters that were applied during search */
  filters: SearchFilters;
  /** Search mode that was used */
  searchMode: SearchMode;
  /** Whether there are more results beyond the current page */
  hasMore: boolean;
  /** Search suggestions based on the query */
  suggestions?: string[];
  /** Search performance metrics */
  metrics?: {
    /** Number of logs processed */
    logsProcessed: number;
    /** Cache hit status */
    fromCache: boolean;
    /** Number of filter applications */
    filterApplications: number;
    /** Number of processed chunks */
    chunkCount?: number;
    /** Chunk size used */
    chunkSize?: number;
  };
  /** Pagination information */
  pagination?: SearchResultPagination;
  /** Precomputed pages */
  pages?: SearchResultPage[];
  /** Whether this result is partial */
  isPartial?: boolean;
  /** Progress snapshot at time of capture */
  progress?: SearchProgressSnapshot;
}

/**
 * Search preferences and configuration
 */
export interface SearchPreferences {
  /** Default search mode */
  mode: SearchMode;
  /** Whether searches should be case sensitive */
  caseSensitive: boolean;
  /** Whether to interpret queries as regular expressions */
  useRegex: boolean;
  /** Whether to include timestamps in search scope */
  includeTimestamps: boolean;
  /** Maximum number of results to return by default */
  maxResults: number;
  /** Whether to highlight matches in results */
  highlightMatches: boolean;
  /** Debounce delay for search input in milliseconds */
  debounceDelay?: number;
  /** Whether to enable search suggestions */
  enableSuggestions?: boolean;
  /** Preferred export format */
  exportFormat?: 'json' | 'csv' | 'txt';
  /** Custom search shortcuts */
  shortcuts?: SearchShortcuts;
}

/**
 * Keyboard shortcuts configuration
 */
export interface SearchShortcuts {
  /** Shortcut to focus search input */
  focusSearch: string;
  /** Shortcut to clear search */
  clearSearch: string;
  /** Shortcut to toggle regex mode */
  toggleRegex: string;
  /** Shortcut to toggle case sensitivity */
  toggleCaseSensitive: string;
  /** Shortcut to export results */
  exportResults: string;
}

/**
 * Current search state
 */
export interface SearchState {
  /** Whether a search is currently in progress */
  isSearching: boolean;
  /** The currently active search query */
  currentQuery: string;
  /** Recent search queries */
  recentQueries: SearchQuery[];
  /** Current search preferences */
  preferences: SearchPreferences;
  /** Cache performance statistics */
  cacheStats: SearchCacheStats;
  /** Active filters */
  activeFilters: SearchFilters;
  /** Search errors */
  error?: string;
}

/**
 * Cache performance statistics
 */
export interface SearchCacheStats {
  /** Current number of cached entries */
  size: number;
  /** Maximum cache size */
  maxSize: number;
  /** Cache hit rate percentage */
  hitRate: number;
  /** Total cache hits */
  totalHits: number;
  /** Total cache misses */
  totalMisses: number;
}

/**
 * Saved search configuration
 */
export interface SavedSearch {
  /** Unique identifier */
  id: string;
  /** Human-readable name */
  name: string;
  /** Search query */
  query: string;
  /** Search filters */
  filters: SearchFilters;
  /** Search preferences used */
  preferences: SearchPreferences;
  /** When this search was created */
  createdAt: Date;
  /** When this search was last used */
  lastUsed?: Date;
  /** Number of times this search has been used */
  usageCount: number;
  /** Optional description */
  description?: string;
  /** Tags for categorization */
  tags?: string[];
  /** Whether this search is shared with other users */
  isShared?: boolean;
}

/**
 * Search suggestion entry
 */
export interface SearchSuggestion {
  /** Suggested query text */
  text: string;
  /** Type of suggestion */
  type: 'history' | 'completion' | 'correction' | 'related';
  /** Relevance score */
  score: number;
  /** Additional metadata */
  metadata?: {
    /** How many results this suggestion typically returns */
    estimatedResults?: number;
    /** How often this suggestion has been used */
    usageCount?: number;
    /** When this suggestion was last used */
    lastUsed?: Date;
  };
}

/**
 * Search analytics data
 */
export interface SearchAnalytics {
  /** Total searches performed */
  totalSearches: number;
  /** Average search execution time */
  avgExecutionTime: number;
  /** Most common search queries */
  popularQueries: Array<{
    query: string;
    count: number;
  }>;
  /** Search success rate (percentage of searches with results) */
  successRate: number;
  /** Cache performance metrics */
  cachePerformance: SearchCacheStats;
  /** Search usage over time */
  usageOverTime: Array<{
    timestamp: Date;
    searchCount: number;
  }>;
  /** Most used filters */
  popularFilters: Array<{
    filter: keyof SearchFilters;
    value: string;
    count: number;
  }>;
}

/**
 * Search export options
 */
export interface SearchExportOptions {
  /** Export format */
  format: 'json' | 'csv' | 'txt' | 'html';
  /** Whether to include metadata */
  includeMetadata: boolean;
  /** Whether to include highlights */
  includeHighlights: boolean;
  /** Maximum number of results to export */
  maxResults?: number;
  /** Custom template for formatting */
  template?: string;
  /** Whether to compress the export */
  compress?: boolean;
}

/**
 * Search validation result
 */
export interface SearchValidationResult {
  /** Whether the query is valid */
  isValid: boolean;
  /** Validation error message if invalid */
  error?: string;
  /** Validation warnings */
  warnings?: string[];
  /** Suggestions for improving the query */
  suggestions?: string[];
  /** Estimated complexity */
  complexity?: {
    score: number;
    factors: string[];
  };
}

/**
 * Search performance metrics
 */
export interface SearchPerformanceMetrics {
  /** Time taken for search execution in milliseconds */
  executionTime: number;
  /** Number of logs processed */
  logsProcessed: number;
  /** Number of matches found */
  matchesFound: number;
  /** Cache hit status */
  fromCache: boolean;
  /** Memory usage during search */
  memoryUsage?: {
    used: number;
    peak: number;
  };
  /** Time taken for each search phase */
  phaseTimings?: {
    filtering: number;
    matching: number;
    scoring: number;
    sorting: number;
  };
}

/**
 * Search configuration options
 */
export interface SearchConfig {
  /** Maximum query length */
  maxQueryLength: number;
  /** Maximum regex complexity */
  maxRegexComplexity: number;
  /** Cache configuration */
  cache: {
    maxSize: number;
    ttl: number; // Time to live in milliseconds
  };
  /** Debounce configuration */
  debounce: {
    delay: number;
    maxWait: number;
  };
  /** Performance limits */
  limits: {
    maxResults: number;
    maxExecutionTime: number; // In milliseconds
  };
  /** Feature flags */
  features: {
    enableFuzzySearch: boolean;
    enableSemanticSearch: boolean;
    enableSuggestions: boolean;
    enableAnalytics: boolean;
  };
}

/**
 * Advanced search operators
 */
export interface SearchOperators {
  /** Exact phrase search */
  phrase: (query: string) => string;
  /** Exclude terms */
  exclude: (term: string) => string;
  /** Field-specific search */
  field: (field: string, value: string) => string;
  /** Wildcard search */
  wildcard: (pattern: string) => string;
  /** Proximity search */
  proximity: (term1: string, term2: string, distance: number) => string;
  /** Boolean operators */
  boolean: {
    and: (queries: string[]) => string;
    or: (queries: string[]) => string;
    not: (query: string) => string;
  };
}

/**
 * Search context for React components
 */
export interface SearchContextType {
  /** Search manager instance */
  searchManager: any; // SearchManager type would cause circular dependency
  /** Current search state */
  state: SearchState;
  /** Update search preferences */
  updatePreferences: (preferences: Partial<SearchPreferences>) => void;
  /** Execute search */
  search: (logs: LogLine[], query: string, filters?: SearchFilters) => Promise<SearchResult>;
  /** Clear search */
  clearSearch: () => void;
  /** Get search history */
  getHistory: () => SearchQuery[];
  /** Save search */
  saveSearch: (name: string, description?: string) => void;
  /** Load saved search */
  loadSavedSearch: (id: string) => void;
  /** Delete saved search */
  deleteSavedSearch: (id: string) => void;
  /** Export search results */
  exportResults: (results: SearchResult, format?: string) => string;
}

/**
 * Event types for search operations
 */
export interface SearchEvents {
  /** Search started */
  searchStarted: { query: string; filters: SearchFilters };
  /** Search completed */
  searchCompleted: { result: SearchResult; fromCache: boolean };
  /** Search failed */
  searchFailed: { query: string; error: string };
  /** Search cancelled */
  searchCancelled: { query: string };
  /** Preferences updated */
  preferencesUpdated: { preferences: SearchPreferences };
  /** Cache cleared */
  cacheCleared: {};
}

/**
 * Type guards for search types
 */
export function isValidSearchMode(value: string): value is SearchMode {
  return ['text', 'regex', 'fuzzy', 'semantic'].includes(value);
}

export function isValidLogLevel(value: string): value is LogLevel {
  return ['error', 'warn', 'info', 'debug', 'trace', 'none'].includes(value);
}

export function isValidServerType(value: string): value is ServerType {
  return ['prod1', 'prod2'].includes(value);
}

/**
 * Search folder for organizing saved searches
 */
export interface SearchFolder {
  /** Unique identifier */
  id: string;
  /** Folder name */
  name: string;
  /** Parent folder ID (null for root folders) */
  parentId: string | null;
  /** Folder color for visual identification */
  color?: string;
  /** Folder icon */
  icon?: string;
  /** When this folder was created */
  createdAt: Date;
  /** When this folder was last modified */
  modifiedAt: Date;
  /** Number of searches in this folder */
  searchCount: number;
  /** Whether this folder is expanded in UI */
  isExpanded?: boolean;
}

/**
 * Saved search with extended metadata
 */
export interface SavedSearchWithMetadata extends SavedSearch {
  /** Folder ID this search belongs to */
  folderId?: string;
  /** Color for visual identification */
  color?: string;
  /** Whether this search is marked as favorite */
  isFavorite: boolean;
  /** Search execution statistics */
  stats?: {
    /** Average execution time in milliseconds */
    avgExecutionTime: number;
    /** Average number of results */
    avgResultCount: number;
    /** Last result count */
    lastResultCount?: number;
  };
}

/**
 * Saved search collection for export/import
 */
export interface SavedSearchCollection {
  /** Collection version for compatibility */
  version: string;
  /** When this collection was exported */
  exportedAt: Date;
  /** Folders in this collection */
  folders: SearchFolder[];
  /** Saved searches in this collection */
  searches: SavedSearchWithMetadata[];
  /** Collection metadata */
  metadata?: {
    /** Collection name */
    name?: string;
    /** Collection description */
    description?: string;
    /** User who created this collection */
    author?: string;
  };
}

/**
 * Saved search statistics
 */
export interface SavedSearchStats {
  /** Total number of saved searches */
  totalSearches: number;
  /** Total number of folders */
  totalFolders: number;
  /** Total number of tags used */
  totalTags: number;
  /** Most used saved search */
  mostUsed?: {
    search: SavedSearchWithMetadata;
    usageCount: number;
  };
  /** Recently used searches */
  recentlyUsed: SavedSearchWithMetadata[];
  /** Favorite searches */
  favorites: SavedSearchWithMetadata[];
  /** Total usage count across all searches */
  totalUsageCount: number;
  /** Storage usage in bytes */
  storageUsage: number;
}

/**
 * Saved search manager state
 */
export interface SavedSearchManagerState {
  /** All folders */
  folders: SearchFolder[];
  /** All saved searches */
  searches: SavedSearchWithMetadata[];
  /** Currently selected folder ID */
  selectedFolderId: string | null;
  /** Currently selected search ID */
  selectedSearchId: string | null;
  /** Search filter for filtering saved searches */
  searchFilter: string;
  /** Tag filter for filtering by tags */
  tagFilter: string[];
  /** Sort order */
  sortBy: 'name' | 'lastUsed' | 'usageCount' | 'createdAt';
  /** Sort direction */
  sortDirection: 'asc' | 'desc';
  /** View mode */
  viewMode: 'list' | 'grid' | 'tree';
}

/**
 * Utility types for search operations
 */
export type SearchFilterKey = keyof SearchFilters;
export type SearchEventName = keyof SearchEvents;
export type SearchExportFormat = SearchExportOptions['format'];
export type SearchSuggestionType = SearchSuggestion['type'];