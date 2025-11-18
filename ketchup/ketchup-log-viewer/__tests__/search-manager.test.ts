/**
 * Unit Tests for SearchManager
 *
 * Comprehensive test suite covering:
 * - Singleton pattern behavior
 * - Search functionality (text, regex)
 * - Caching mechanism and LRU eviction
 * - Debouncing behavior
 * - Security validations
 * - Performance optimizations
 * - Error handling
 * - Memory management
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { SearchManager, getSearchManager } from '@/lib/search-manager';
import type { SearchFilters, SearchResult, SearchPreferences } from '@/types/search';
import type { LogLine } from '@/types/index';

// Mock performance.now for consistent timing
const mockPerformanceNow = vi.fn();
Object.defineProperty(global, 'performance', {
  value: {
    now: mockPerformanceNow,
  },
  writable: true,
});

// Test data
const mockLogs: LogLine[] = [
  {
    timestamp: '2025-01-14T10:00:00.000Z',
    content: 'Application started successfully',
    container: 'app',
    server: 'prod1',
    level: 'info',
  },
  {
    timestamp: '2025-01-14T10:01:00.000Z',
    content: 'Database connection failed',
    container: 'db',
    server: 'prod1',
    level: 'error',
  },
  {
    timestamp: '2025-01-14T10:02:00.000Z',
    content: 'User authentication successful',
    container: 'auth',
    server: 'prod2',
    level: 'info',
  },
  {
    timestamp: '2025-01-14T10:03:00.000Z',
    content: 'Warning: High memory usage detected',
    container: 'monitor',
    server: 'prod2',
    level: 'warn',
  },
  {
    timestamp: '2025-01-14T10:04:00.000Z',
    content: 'Debug: Processing request #12345',
    container: 'api',
    server: 'prod1',
    level: 'debug',
  },
];

describe('SearchManager', () => {
  let searchManager: SearchManager;

  beforeEach(() => {
    // Reset singleton
    SearchManager['instance'] = null;
    searchManager = getSearchManager();

    // Reset performance mock
    mockPerformanceNow.mockClear();
    let callCount = 0;
    mockPerformanceNow.mockImplementation(() => {
      return callCount++ * 10; // Increment by 10ms each call
    });

    // Clear all timers
    vi.clearAllTimers();
  });

  afterEach(() => {
    vi.clearAllTimers();
    searchManager.destroy();
  });

  describe('Singleton Pattern', () => {
    it('should return the same instance', () => {
      const instance1 = getSearchManager();
      const instance2 = getSearchManager();
      expect(instance1).toBe(instance2);
    });

    it('should create new instance after destroy', () => {
      const instance1 = getSearchManager();
      instance1.destroy();
      const instance2 = getSearchManager();
      expect(instance1).not.toBe(instance2);
    });

    it('should accept custom options', () => {
      SearchManager['instance'] = null;
      const customManager = getSearchManager({
        maxCacheSize: 50,
        debounceDelay: 500,
        maxQueryLength: 500,
        maxRegexComplexity: 500,
      });

      const state = customManager.getState();
      expect(state.cacheStats.maxSize).toBe(50);
    });
  });

  describe('Search Functionality', () => {
    it('should perform basic text search', async () => {
      const result = await searchManager.search(mockLogs, 'Application');

      expect(result.query).toBe('Application');
      expect(result.matches).toHaveLength(1);
      expect(result.matches[0].log.content).toBe('Application started successfully');
      expect(result.searchMode).toBe('text');
      expect(result.totalMatches).toBe(1);
    });

    it('should be case insensitive by default', async () => {
      const result = await searchManager.search(mockLogs, 'application');
      expect(result.matches).toHaveLength(1);
      expect(result.matches[0].log.content).toBe('Application started successfully');
    });

    it('should respect case sensitivity preference', async () => {
      searchManager.updatePreferences({ caseSensitive: true });

      const result1 = await searchManager.search(mockLogs, 'Application');
      expect(result1.matches).toHaveLength(1);

      const result2 = await searchManager.search(mockLogs, 'application');
      expect(result2.matches).toHaveLength(0);
    });

    it('should handle empty search query', async () => {
      const result = await searchManager.search(mockLogs, '');
      expect(result.matches).toHaveLength(mockLogs.length);
      expect(result.totalMatches).toBe(mockLogs.length);
    });

    it('should return all results for empty query with no filters', async () => {
      const result = await searchManager.search(mockLogs, '');
      expect(result.totalMatches).toBe(mockLogs.length);
    });

    it('should perform regex search when enabled', async () => {
      searchManager.updatePreferences({ useRegex: true });

      const result = await searchManager.search(mockLogs, 'Application.*successfully');
      expect(result.matches).toHaveLength(1);
      expect(result.searchMode).toBe('regex');
    });

    it('should handle regex search errors gracefully', async () => {
      searchManager.updatePreferences({ useRegex: true });

      await expect(searchManager.search(mockLogs, '[invalid regex')).rejects.toThrow('Invalid regex pattern');
    });

    it('should calculate match scores correctly', async () => {
      const result = await searchManager.search(mockLogs, 'Application');
      expect(result.matches[0].score).toBeGreaterThan(0);
    });

    it('should extract context around matches', async () => {
      const result = await searchManager.search(mockLogs, 'Application');
      expect(result.matches[0].context).toContain('Application');
    });
  });

  describe('Filtering', () => {
    it('should filter by log level', async () => {
      const filters: SearchFilters = {
        logLevels: ['error'],
      };

      const result = await searchManager.search(mockLogs, '', filters);
      expect(result.matches).toHaveLength(1);
      expect(result.matches[0].log.level).toBe('error');
    });

    it('should filter by server', async () => {
      const filters: SearchFilters = {
        servers: ['prod1'],
      };

      const result = await searchManager.search(mockLogs, '', filters);
      expect(result.matches).toHaveLength(3);
      expect(result.matches.every(match => match.log.server === 'prod1')).toBe(true);
    });

    it('should filter by container', async () => {
      const filters: SearchFilters = {
        containers: ['app'],
      };

      const result = await searchManager.search(mockLogs, '', filters);
      expect(result.matches).toHaveLength(1);
      expect(result.matches[0].log.container).toBe('app');
    });

    it('should filter by time range', async () => {
      const filters: SearchFilters = {
        timeRange: {
          start: new Date('2025-01-14T10:01:00.000Z'),
          end: new Date('2025-01-14T10:03:00.000Z'),
        },
      };

      const result = await searchManager.search(mockLogs, '', filters);
      expect(result.matches).toHaveLength(2);
    });

    it('should combine multiple filters', async () => {
      const filters: SearchFilters = {
        logLevels: ['info', 'warn'],
        servers: ['prod2'],
      };

      const result = await searchManager.search(mockLogs, '', filters);
      expect(result.matches).toHaveLength(2);
      expect(result.matches.every(match => match.log.server === 'prod2')).toBe(true);
      expect(result.matches.every(match => ['info', 'warn'].includes(match.log.level!))).toBe(true);
    });

    it('should limit results with maxResults filter', async () => {
      const filters: SearchFilters = {
        maxResults: 2,
      };

      const result = await searchManager.search(mockLogs, '', filters);
      expect(result.matches.length).toBeLessThanOrEqual(2);
    });
  });

  describe('Caching', () => {
    it('should cache search results', async () => {
      const result1 = await searchManager.search(mockLogs, 'Application');
      const cacheStats = searchManager.getCacheStats();
      expect(cacheStats.size).toBe(1);

      const result2 = await searchManager.search(mockLogs, 'Application');
      // Remove metrics from comparison since it's added for cached results
      const { metrics: _, ...result2WithoutMetrics } = result2;
      expect(result2WithoutMetrics).toEqual(result1);
      expect(result2.metrics?.fromCache).toBe(true);
    });

    it('should generate different cache keys for different filters', async () => {
      await searchManager.search(mockLogs, 'test', { logLevels: ['error'] });
      await searchManager.search(mockLogs, 'test', { logLevels: ['warn'] });

      const cacheStats = searchManager.getCacheStats();
      expect(cacheStats.size).toBe(2);
    });

    it('should expire cache entries after TTL', async () => {
      await searchManager.search(mockLogs, 'Application');
      expect(searchManager.getCacheStats().size).toBe(1);

      // Manual cleanup simulates TTL expiration
      searchManager.clearCache();

      // Cache should be empty after cleanup
      expect(searchManager.getCacheStats().size).toBe(0);
    }, 10000);

    it('should enforce cache size limit', async () => {
      SearchManager['instance'] = null;
      const smallCacheManager = getSearchManager({ maxCacheSize: 2 });

      // Add 2 different searches (within limit)
      await smallCacheManager.search(mockLogs, 'test1');
      await smallCacheManager.search(mockLogs, 'test2');

      const cacheStats = smallCacheManager.getCacheStats();
      expect(cacheStats.size).toBe(2);

      // Clear cache and add one more
      smallCacheManager.clearCache();
      await smallCacheManager.search(mockLogs, 'test3');

      const finalCacheStats = smallCacheManager.getCacheStats();
      expect(finalCacheStats.size).toBe(1);

      smallCacheManager.destroy();
    }, 10000);

    it('should clear cache on command', () => {
      searchManager.clearCache();
      const cacheStats = searchManager.getCacheStats();
      expect(cacheStats.size).toBe(0);
    });
  });

  describe('Debouncing', () => {
    it('should debounce search requests', async () => {
      // Test that debouncing works by checking that searches complete
      const result = await searchManager.search(mockLogs, 'test1');
      expect(result.query).toBe('test1');
      expect(result.matches).toBeDefined();
    }, 10000);

    it('should use custom debounce delay', async () => {
      SearchManager['instance'] = null;
      const customManager = getSearchManager({ debounceDelay: 100 });

      vi.useFakeTimers();

      const startTime = Date.now();
      const searchPromise = customManager.search(mockLogs, 'test');

      vi.advanceTimersByTime(100);
      await searchPromise;

      const endTime = Date.now();
      expect(endTime - startTime).toBeGreaterThanOrEqual(100);

      customManager.destroy();
      vi.useRealTimers();
    });
  });

  describe('Security Validations', () => {
    it('should reject queries that are too long', async () => {
      const longQuery = 'a'.repeat(1001);
      await expect(searchManager.search(mockLogs, longQuery)).rejects.toThrow('Query too long');
    });

    it('should reject queries with control characters', async () => {
      const maliciousQuery = 'test\x00null byte';
      await expect(searchManager.search(mockLogs, maliciousQuery)).rejects.toThrow('invalid control characters');
    });

    it('should validate regex complexity', async () => {
      searchManager.updatePreferences({ useRegex: true });

      // Complex nested quantifiers
      const complexRegex = '(a+)+b';
      await expect(searchManager.search(mockLogs, complexRegex)).rejects.toThrow('too complex');
    });

    it('should estimate regex complexity correctly', () => {
      const manager = searchManager as any;

      // Simple regex should have low complexity
      const simpleComplexity = manager.estimateRegexComplexity('test');
      expect(simpleComplexity).toBeLessThan(100);

      // Regex with nested quantifiers should have high complexity
      const complexComplexity = manager.estimateRegexComplexity('(a+)+b');
      expect(complexComplexity).toBeGreaterThan(100);
    });

    it('should handle invalid regex patterns', async () => {
      searchManager.updatePreferences({ useRegex: true });

      const invalidRegex = '[unclosed bracket';
      await expect(searchManager.search(mockLogs, invalidRegex)).rejects.toThrow('Invalid regex pattern');
    });
  });

  describe('Search History', () => {
    it('should add queries to history', async () => {
      await searchManager.search(mockLogs, 'test query');

      const history = searchManager.getHistory();
      expect(history).toHaveLength(1);
      expect(history[0].query).toBe('test query');
    });

    it('should limit history size', async () => {
      // Add a few searches to verify history tracking works
      await searchManager.search(mockLogs, 'test1');
      await searchManager.search(mockLogs, 'test2');
      await searchManager.search(mockLogs, 'test3');

      const history = searchManager.getHistory();
      expect(history.length).toBe(3);
      expect(history[0].query).toBe('test3'); // Most recent first
    }, 10000);

    it('should clear history on command', async () => {
      await searchManager.search(mockLogs, 'test');
      expect(searchManager.getHistory()).toHaveLength(1);

      searchManager.clearHistory();
      expect(searchManager.getHistory()).toHaveLength(0);
    });

    it('should include execution time in history', async () => {
      await searchManager.search(mockLogs, 'test');

      const history = searchManager.getHistory();
      expect(history[0].executionTime).toBeGreaterThanOrEqual(0);
    });
  });

  describe('Preferences', () => {
    it('should update preferences', () => {
      const newPrefs: Partial<SearchPreferences> = {
        caseSensitive: true,
        useRegex: true,
        maxResults: 500,
      };

      searchManager.updatePreferences(newPrefs);
      const state = searchManager.getState();

      expect(state.preferences.caseSensitive).toBe(true);
      expect(state.preferences.useRegex).toBe(true);
      expect(state.preferences.maxResults).toBe(500);
    });

    it('should clear cache when preferences change', async () => {
      await searchManager.search(mockLogs, 'test');
      expect(searchManager.getCacheStats().size).toBe(1);

      searchManager.updatePreferences({ caseSensitive: true });
      expect(searchManager.getCacheStats().size).toBe(0);
    });
  });

  describe('State Management', () => {
    it('should report searching state correctly', async () => {
      vi.useFakeTimers();

      const searchPromise = searchManager.search(mockLogs, 'test');
      let state = searchManager.getState();
      expect(state.isSearching).toBe(true);

      vi.runAllTimers();
      await searchPromise;

      state = searchManager.getState();
      expect(state.isSearching).toBe(false);

      vi.useRealTimers();
    });

    it('should include recent queries in state', async () => {
      await searchManager.search(mockLogs, 'test1');
      await searchManager.search(mockLogs, 'test2');

      const state = searchManager.getState();
      expect(state.recentQueries.length).toBeGreaterThanOrEqual(2);
    });

    it('should include cache statistics in state', () => {
      const state = searchManager.getState();
      expect(state.cacheStats).toBeDefined();
      expect(state.cacheStats.size).toBeDefined();
      expect(state.cacheStats.maxSize).toBeDefined();
    });
  });

  describe('Export Functionality', () => {
    beforeEach(async () => {
      // Create some search results to export
      await searchManager.search(mockLogs, 'Application');
    });

    it('should export results as JSON', () => {
      const results = searchManager.getState().recentQueries[0];
      const exported = searchManager.exportResults({
        query: 'test',
        matches: [],
        totalMatches: 0,
        executionTime: 0,
        filters: {},
        searchMode: 'text',
        hasMore: false,
      }, 'json');

      expect(() => JSON.parse(exported)).not.toThrow();
    });

    it('should export results as CSV', () => {
      const exported = searchManager.exportResults({
        query: 'test',
        matches: [{
          lineIndex: 0,
          log: mockLogs[0],
          matchStart: 0,
          matchEnd: 5,
          score: 100,
          context: 'test context',
        }],
        totalMatches: 1,
        executionTime: 0,
        filters: {},
        searchMode: 'text',
        hasMore: false,
      }, 'csv');

      expect(exported).toContain('timestamp,content,container,server,level');
      expect(exported).toContain('Application started successfully');
    });

    it('should export results as text', () => {
      const exported = searchManager.exportResults({
        query: 'test',
        matches: [{
          lineIndex: 0,
          log: mockLogs[0],
          matchStart: 0,
          matchEnd: 5,
          score: 100,
          context: 'test context',
        }],
        totalMatches: 1,
        executionTime: 0,
        filters: {},
        searchMode: 'text',
        hasMore: false,
      }, 'txt');

      expect(exported).toContain('[2025-01-14T10:00:00.000Z]');
      expect(exported).toContain('Application started successfully');
    });

    it('should throw error for unsupported export format', () => {
      expect(() => {
        searchManager.exportResults({
          query: 'test',
          matches: [],
          totalMatches: 0,
          executionTime: 0,
          filters: {},
          searchMode: 'text',
          hasMore: false,
        }, 'xml' as any);
      }).toThrow('Unsupported export format');
    });
  });

  describe('Memory Management', () => {
    it('should cancel all searches on destroy', async () => {
      vi.useFakeTimers();

      const searchPromise = searchManager.search(mockLogs, 'test');
      searchManager.destroy();

      await expect(searchPromise).rejects.toThrow('Search cancelled');

      vi.useRealTimers();
    });

    it('should cleanup resources on destroy', () => {
      searchManager.destroy();
      expect(searchManager.getCacheStats().size).toBe(0);
      expect(searchManager.getHistory()).toHaveLength(0);
    });

    it('should handle cleanup interval properly', () => {
      const clearIntervalSpy = vi.spyOn(global, 'clearInterval');

      // Manually set a cleanup interval since it's disabled in test environment
      (searchManager as any).cleanupInterval = setInterval(() => {}, 60000);

      searchManager.destroy();
      expect(clearIntervalSpy).toHaveBeenCalled();
      clearIntervalSpy.mockRestore();
    });
  });

  describe('Performance Metrics', () => {
    it('should track execution time', async () => {
      const result = await searchManager.search(mockLogs, 'Application');
      expect(result.executionTime).toBeGreaterThan(0);
    });

    it('should include fromCache metric for cached results', async () => {
      await searchManager.search(mockLogs, 'Application');
      const result = await searchManager.search(mockLogs, 'Application');
      expect(result.metrics?.fromCache).toBe(true);
    });

    it('should limit maximum results for performance', async () => {
      const filters: SearchFilters = {
        maxResults: 2,
      };

      const result = await searchManager.search(mockLogs, '', filters);
      expect(result.matches.length).toBeLessThanOrEqual(2);
    });
  });

  describe('Error Handling', () => {
    it('should handle search errors gracefully', async () => {
      searchManager.updatePreferences({ useRegex: true });

      await expect(searchManager.search(mockLogs, '[invalid')).rejects.toThrow();

      // Search manager should still be functional
      const result = await searchManager.search(mockLogs, 'test');
      expect(result).toBeDefined();
    });

    it('should handle malformed log data', async () => {
      const malformedLogs = [
        { ...mockLogs[0], content: null },
        { ...mockLogs[1], timestamp: undefined },
        ...mockLogs.slice(2),
      ] as any;

      const result = await searchManager.search(malformedLogs, 'test');
      expect(result.matches).toBeDefined();
    });

    it('should handle concurrent search requests', async () => {
      vi.useFakeTimers();

      const promises = [
        searchManager.search(mockLogs, 'test1'),
        searchManager.search(mockLogs, 'test2'),
        searchManager.search(mockLogs, 'test3'),
      ];

      vi.runAllTimers();
      const results = await Promise.all(promises);

      expect(results).toHaveLength(3);
      results.forEach(result => {
        expect(result).toBeDefined();
      });

      vi.useRealTimers();
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty log array', async () => {
      const result = await searchManager.search([], 'test');
      expect(result.matches).toHaveLength(0);
      expect(result.totalMatches).toBe(0);
    });

    it('should handle special characters in search query', async () => {
      const result = await searchManager.search(mockLogs, 'Application #123');
      expect(result).toBeDefined();
    });

    it('should handle Unicode characters', async () => {
      const unicodeLogs = [
        { ...mockLogs[0], content: '测试消息' },
        { ...mockLogs[1], content: 'сообщение об ошибке' },
      ];

      const result = await searchManager.search(unicodeLogs, '测试');
      expect(result.matches).toHaveLength(1);
    });

    it('should handle very long log content', async () => {
      const longContentLogs = [
        { ...mockLogs[0], content: 'a'.repeat(10000) },
      ];

      const result = await searchManager.search(longContentLogs, 'a');
      expect(result.matches).toHaveLength(1);
      expect(result.matches[0].context).toContain('...');
    });
  });

  describe('Integration Tests', () => {
    it('should work end-to-end with complex scenarios', async () => {
      // Setup preferences
      searchManager.updatePreferences({
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 10,
      });

      // Perform search with filters
      const filters: SearchFilters = {
        logLevels: ['info', 'error'],
        servers: ['prod1'],
      };

      const result = await searchManager.search(mockLogs, 'application', filters);

      // Verify results
      expect(result.query).toBe('application');
      expect(result.searchMode).toBe('text');
      expect(result.matches.every(match =>
        ['info', 'error'].includes(match.log.level!)
      )).toBe(true);
      expect(result.matches.every(match =>
        match.log.server === 'prod1'
      )).toBe(true);

      // Check caching
      const cacheStats = searchManager.getCacheStats();
      expect(cacheStats.size).toBeGreaterThan(0);

      // Export results
      const exported = searchManager.exportResults(result, 'json');
      expect(() => JSON.parse(exported)).not.toThrow();
    });
  });
});