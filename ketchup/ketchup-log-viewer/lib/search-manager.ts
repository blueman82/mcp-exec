import type { LogLine } from '@/types';
import type {
  SearchFilters,
  SearchMode,
  SearchOptimizerOptions,
  SearchPreferences,
  SearchProgressEvent,
  SearchQuery,
  SearchResult,
  SearchState,
} from '@/types/search';
import { getSearchOptimizer } from '@/lib/search-optimizer';
import { getMemoryManager } from '@/lib/memory-manager';
import { sanitizeText, validateRegexPattern as validateRegexPatternDeprecated } from '@/lib/security/sanitizer';
import { InputValidator } from '@/lib/input-validator';
import { checkRateLimit, RATE_LIMITS } from '@/lib/rate-limiter';

export interface SearchManagerOptions {
  maxCacheSize?: number;
  maxQueryLength?: number;
  maxRegexComplexity?: number;
}

interface CacheEntry {
  query: string;
  filters: SearchFilters;
  timestamp: number;
  result: SearchResult;
}

const SECURITY_LIMITS = {
  MAX_QUERY_LENGTH: 1000,
  MAX_REGEX_COMPLEXITY: 1000,
  MAX_CACHE_SIZE: 100,
  MAX_SEARCH_RESULTS: 10_000,
  HISTORY_LIMIT: 50,
} as const;

const CACHE_RESOURCE_ID = 'search-cache';
const HISTORY_STORAGE_KEY = 'enhancedSearch-history';

type ClientOrOptions = string | SearchOptimizerOptions | undefined;

function cloneResult<T>(value: T): T {
  if (typeof structuredClone === 'function') {
    return structuredClone(value);
  }

  return JSON.parse(JSON.stringify(value));
}

export class SearchManager {
  private static instance: SearchManager | null = null;

  private readonly cache = new Map<string, CacheEntry>();
  private readonly preferences: SearchPreferences;
  private readonly options: Required<SearchManagerOptions>;
  private readonly optimizer = getSearchOptimizer();
  private readonly memoryManager = getMemoryManager();

  private searchHistory: SearchQuery[] = [];
  private historyLoaded = false;

  private totalCacheHits = 0;
  private totalCacheMisses = 0;
  private activeSearches = new Map<string, AbortController>();

  private constructor(options: SearchManagerOptions = {}) {
    this.options = {
      maxCacheSize: options.maxCacheSize ?? SECURITY_LIMITS.MAX_CACHE_SIZE,
      maxQueryLength: options.maxQueryLength ?? SECURITY_LIMITS.MAX_QUERY_LENGTH,
      maxRegexComplexity: options.maxRegexComplexity ?? SECURITY_LIMITS.MAX_REGEX_COMPLEXITY,
    };

    this.preferences = {
      mode: 'text',
      caseSensitive: false,
      useRegex: false,
      includeTimestamps: false,
      maxResults: SECURITY_LIMITS.MAX_SEARCH_RESULTS,
      highlightMatches: true,
    };

    this.memoryManager.registerResource(CACHE_RESOURCE_ID, () => this.cache.size, {
      limit: this.options.maxCacheSize,
      onLimitExceeded: () => this.enforceCacheLimit(),
    });
  }

  static getInstance(options?: SearchManagerOptions): SearchManager {
    if (!SearchManager.instance) {
      SearchManager.instance = new SearchManager(options);
    }
    return SearchManager.instance;
  }

  public updatePreferences(preferences: Partial<SearchPreferences>): void {
    Object.assign(this.preferences, preferences);
    this.clearCache();
  }

  public getState(): SearchState {
    return {
      isSearching: this.activeSearches.size > 0,
      currentQuery: '',
      recentQueries: this.getHistory().slice(0, 10),
      preferences: { ...this.preferences },
      activeFilters: {},
      cacheStats: {
        size: this.cache.size,
        maxSize: this.options.maxCacheSize,
        hitRate: this.calculateCacheHitRate(),
        totalHits: this.totalCacheHits,
        totalMisses: this.totalCacheMisses,
      },
    };
  }

  public getHistory(): SearchQuery[] {
    this.ensureHistoryLoaded();
    return this.searchHistory.map(entry => ({ ...entry }));
  }

  public clearHistory(): void {
    this.ensureHistoryLoaded();
    this.searchHistory = [];
    this.persistHistory();
  }

  public clearCache(): void {
    this.cache.clear();
    this.memoryManager.updateResourceUsage(CACHE_RESOURCE_ID, this.cache.size);
  }

  public getCacheStats() {
    return {
      size: this.cache.size,
      maxSize: this.options.maxCacheSize,
      entries: Array.from(this.cache.entries()).map(([key, entry]) => ({
        key,
        timestamp: entry.timestamp,
        query: entry.query,
        resultCount: entry.result.totalMatches,
      })),
    };
  }

  public exportResults(results: SearchResult, format: 'json' | 'csv' | 'txt' = 'json'): string {
    switch (format) {
      case 'json':
        return JSON.stringify(results, null, 2);
      case 'csv': {
        const headers = ['timestamp', 'content', 'container', 'server', 'level', 'matchScore'];
        const rows = results.matches.map(match => [
          match.log.timestamp,
          `"${match.log.content.replace(/"/g, '""')}"`,
          match.log.container,
          match.log.server,
          match.log.level ?? '',
          match.score.toString(),
        ]);
        return [headers, ...rows].map(row => row.join(',')).join('\n');
      }
      case 'txt':
        return results.matches
          .map(match => {
            const timestamp = new Date(match.log.timestamp).toISOString();
            return `[${timestamp}] [${match.log.server}] [${match.log.container}] ${match.log.content}`;
          })
          .join('\n');
      default:
        throw new Error(`Unsupported export format: ${format}`);
    }
  }

  public getCacheHitRate(): number {
    return this.calculateCacheHitRate();
  }

  public cancelAllSearches(): void {
    for (const controller of this.activeSearches.values()) {
      controller.abort();
    }
    this.activeSearches.clear();
  }

  public destroy(): void {
    this.cancelAllSearches();
    this.clearCache();
    this.clearHistory();
    this.memoryManager.unregisterResource(CACHE_RESOURCE_ID);
    SearchManager.instance = null;
  }

  public async search(
    logs: LogLine[],
    query: string,
    filters: SearchFilters = {},
    clientOrOptions?: ClientOrOptions,
    executionOptions?: SearchOptimizerOptions
  ): Promise<SearchResult> {
    const clientIdentifier = typeof clientOrOptions === 'string' ? clientOrOptions : undefined;
    const runOptions: SearchOptimizerOptions = (typeof clientOrOptions === 'object' && clientOrOptions !== null)
      ? clientOrOptions
      : executionOptions ?? {};

    const sanitizedQuery = sanitizeText(query, this.options.maxQueryLength).slice(0, this.options.maxQueryLength);
    const sanitizedFilters = this.sanitizeFilters(filters);

    this.validateQuery(sanitizedQuery);

    if (clientIdentifier) {
      const rateLimitResult = checkRateLimit(clientIdentifier, RATE_LIMITS.SEARCH);
      if (!rateLimitResult.allowed) {
        throw new Error(
          `Search rate limit exceeded. Please wait ${rateLimitResult.retryAfter || 60} seconds before trying again.`
        );
      }
    }

    const cacheKey = this.generateCacheKey(sanitizedQuery, sanitizedFilters);
    const cached = this.cache.get(cacheKey);
    if (cached && Date.now() - cached.timestamp < 5 * 60 * 1000) {
      this.totalCacheHits += 1;
      const cachedResult = cloneResult(cached.result);
      if (!cachedResult.metrics) {
        cachedResult.metrics = {
          logsProcessed: 0,
          filterApplications: 0,
          fromCache: true,
        };
      } else {
        cachedResult.metrics.fromCache = true;
      }

      runOptions.onProgress?.({
        type: 'complete',
        processedLogs: cachedResult.metrics.logsProcessed ?? 0,
        totalLogs: logs.length,
        matchesFound: cachedResult.totalMatches,
        chunkIndex: cachedResult.progress?.chunksProcessed ?? 0,
        totalChunks: cachedResult.progress?.totalChunks ?? 1,
        partialResult: cachedResult,
      });

      return cachedResult;
    }

    this.totalCacheMisses += 1;

    const maxResults = Math.max(1, Math.min(
      sanitizedFilters.maxResults ?? this.preferences.maxResults,
      SECURITY_LIMITS.MAX_SEARCH_RESULTS,
    ));

    const executionInputs = {
      logs,
      query: sanitizedQuery,
      filters: sanitizedFilters,
      preferences: { ...this.preferences },
      searchMode: this.preferences.useRegex ? ('regex' as SearchMode) : ('text' as SearchMode),
      maxResults,
    };

    const searchId = this.generateSearchId();
    const controller = new AbortController();
    this.activeSearches.set(searchId, controller);

    let abortListener: (() => void) | undefined;
    if (runOptions.abortSignal) {
      if (runOptions.abortSignal.aborted) {
        controller.abort();
      } else {
        abortListener = () => controller.abort();
        runOptions.abortSignal.addEventListener('abort', abortListener, { once: true });
      }
    }

    const optimizerOptions: SearchOptimizerOptions = {
      chunkSize: runOptions.chunkSize,
      pageSize: runOptions.pageSize,
      forceMainThread: runOptions.forceMainThread,
      abortSignal: controller.signal,
      onProgress: event => this.forwardProgressEvent(runOptions, event),
    };

    try {
      const { result } = await this.optimizer.execute(executionInputs, optimizerOptions);

      if (result.metrics) {
        result.metrics.fromCache = false;
      }

      this.cache.set(cacheKey, {
        query: sanitizedQuery,
        filters: sanitizedFilters,
        timestamp: Date.now(),
        result: cloneResult(result),
      });
      this.enforceCacheLimit();

      this.addToHistory(sanitizedQuery, sanitizedFilters, result.totalMatches, result.executionTime);

      return result;
    } finally {
      if (abortListener && runOptions.abortSignal) {
        runOptions.abortSignal.removeEventListener('abort', abortListener);
      }
      if (!controller.signal.aborted) {
        controller.abort();
      }
      this.activeSearches.delete(searchId);
    }
  }

  private forwardProgressEvent(options: SearchOptimizerOptions, event: SearchProgressEvent): void {
    if (!options.onProgress) {
      return;
    }

    if (event.type === 'chunk') {
      options.onProgress({
        ...event,
        partialResult: cloneResult(event.partialResult),
        page: event.page ? cloneResult(event.page) : undefined,
      });
      return;
    }

    if (event.type === 'complete' || event.type === 'cancelled') {
      options.onProgress({
        ...event,
        partialResult: cloneResult(event.partialResult),
      });
      return;
    }

    options.onProgress(event);
  }

  private sanitizeFilters(filters: SearchFilters): SearchFilters {
    const sanitized: SearchFilters = {};

    if (filters.logLevels?.length) {
      sanitized.logLevels = filters.logLevels.filter(level => typeof level === 'string');
    }

    if (filters.servers?.length) {
      sanitized.servers = filters.servers.filter(server => typeof server === 'string');
    }

    if (filters.containers?.length) {
      sanitized.containers = filters.containers.filter(container => typeof container === 'string');
    }

    if (filters.timeRange) {
      const start = filters.timeRange.start ? new Date(filters.timeRange.start) : undefined;
      const end = filters.timeRange.end ? new Date(filters.timeRange.end) : undefined;
      sanitized.timeRange = {
        start: start && !Number.isNaN(start.getTime()) ? start : undefined,
        end: end && !Number.isNaN(end.getTime()) ? end : undefined,
      };
    }

    if (typeof filters.maxResults === 'number') {
      sanitized.maxResults = Math.max(1, Math.min(filters.maxResults, SECURITY_LIMITS.MAX_SEARCH_RESULTS));
    }

    if (typeof filters.minScore === 'number') {
      sanitized.minScore = filters.minScore;
    }

    if (typeof filters.includeArchived === 'boolean') {
      sanitized.includeArchived = filters.includeArchived;
    }

    if (filters.customFilters?.length) {
      sanitized.customFilters = [...filters.customFilters];
    }

    return sanitized;
  }

  private validateQuery(query: string): void {
    // Guard against null/undefined queries
    if (query === null || query === undefined) {
      throw new Error('Search query cannot be null or undefined');
    }

    // Use new InputValidator for search term validation
    const searchTermResult = InputValidator.validateSearchTerm(query);
    if (!searchTermResult.valid) {
      throw new Error(searchTermResult.error || 'Invalid search term');
    }

    // Additional regex validation if regex mode is enabled
    if (this.preferences.useRegex && query.length > 0) {
      const regexResult = InputValidator.validateRegexPattern(query);
      if (!regexResult.valid) {
        throw new Error(regexResult.error || 'Invalid regex pattern');
      }
    }
  }

  // validateRegexComplexity method removed - complexity validation now handled by InputValidator.validateRegexPattern

  private generateCacheKey(query: string, filters: SearchFilters): string {
    const payload = {
      q: query,
      f: filters,
      p: {
        mode: this.preferences.mode,
        caseSensitive: this.preferences.caseSensitive,
        includeTimestamps: this.preferences.includeTimestamps,
        maxResults: this.preferences.maxResults,
      },
    };

    const json = JSON.stringify(payload);

    if (typeof Buffer !== 'undefined') {
      return Buffer.from(json).toString('base64');
    }

    if (typeof btoa === 'function') {
      return btoa(unescape(encodeURIComponent(json)));
    }

    return json;
  }

  private generateSearchId(): string {
    return `search_${Date.now()}_${Math.random().toString(36).slice(2)}`;
  }

  private enforceCacheLimit(): void {
    if (this.cache.size <= this.options.maxCacheSize) {
      this.memoryManager.updateResourceUsage(CACHE_RESOURCE_ID, this.cache.size);
      return;
    }

    const entries = Array.from(this.cache.entries()).sort((a, b) => a[1].timestamp - b[1].timestamp);
    const toRemove = entries.slice(0, this.cache.size - this.options.maxCacheSize);
    for (const [key] of toRemove) {
      this.cache.delete(key);
    }
    this.memoryManager.updateResourceUsage(CACHE_RESOURCE_ID, this.cache.size);
  }

  private calculateCacheHitRate(): number {
    const total = this.totalCacheHits + this.totalCacheMisses;
    if (total === 0) {
      return 0;
    }
    return Math.round((this.totalCacheHits / total) * 100);
  }

  private ensureHistoryLoaded(): void {
    if (this.historyLoaded) {
      return;
    }
    this.historyLoaded = true;

    if (typeof window === 'undefined' || !window.localStorage) {
      return;
    }

    try {
      const stored = window.localStorage.getItem(HISTORY_STORAGE_KEY);
      if (!stored) {
        return;
      }

      const parsed = JSON.parse(stored) as Array<Omit<SearchQuery, 'timestamp'> & { timestamp: string }>;
      this.searchHistory = parsed
        .map(item => ({
          ...item,
          timestamp: new Date(item.timestamp),
        }))
        .filter(entry => !Number.isNaN(entry.timestamp.getTime()));
    } catch (error) {
      console.error('Failed to load search history:', error);
    }
  }

  private persistHistory(): void {
    if (typeof window === 'undefined' || !window.localStorage) {
      return;
    }

    try {
      const serialisable = this.searchHistory.map(entry => ({
        ...entry,
        timestamp: entry.timestamp.toISOString(),
      }));
      window.localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(serialisable));
    } catch (error) {
      console.error('Failed to persist search history:', error);
    }
  }

  private addToHistory(query: string, filters: SearchFilters, resultCount: number, executionTime: number): void {
    this.ensureHistoryLoaded();

    const searchQuery: SearchQuery = {
      id: this.generateSearchId(),
      query,
      filters: { ...filters },
      timestamp: new Date(),
      resultCount,
      executionTime,
    };

    this.searchHistory = [searchQuery, ...this.searchHistory.filter(item => item.query !== query)].slice(
      0,
      SECURITY_LIMITS.HISTORY_LIMIT
    );

    this.persistHistory();
  }
}

export const getSearchManager = SearchManager.getInstance;
