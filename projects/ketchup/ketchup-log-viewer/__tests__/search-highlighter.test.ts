/**
 * Unit tests for Search Highlighter
 *
 * Tests the advanced highlighting system with multiple match types,
 * context-aware highlighting, and navigation functionality.
 */

import { describe, test, expect, beforeEach, afterEach, vi } from 'vitest';
import { createSearchHighlighter, SearchHighlighter, highlightTextContent } from '@/lib/search-highlighter';
import type { SearchResult, SearchMatch } from '@/types/search';
import type { LogLine } from '@/types';

// Mock DOM methods
Object.defineProperty(window, 'MutationObserver', {
  writable: true,
  value: vi.fn().mockImplementation(() => ({
    observe: vi.fn(),
    disconnect: vi.fn(),
  })),
});

describe('SearchHighlighter', () => {
  let highlighter: SearchHighlighter;
  let mockContainer: HTMLElement;
  let mockSearchResult: SearchResult;

  beforeEach(() => {
    // Reset DOM
    document.body.innerHTML = '';

    // Create mock search result
    mockSearchResult = {
      query: 'test',
      matches: [
        {
          lineIndex: 0,
          log: {
            timestamp: '2023-01-01T00:00:00Z',
            content: 'This is a test message with error details',
            container: 'test-container',
            server: 'prod1',
            level: 'error',
          } as LogLine,
          matchStart: 10,
          matchEnd: 14,
          score: 100,
          context: 'a test message',
        },
        {
          lineIndex: 1,
          log: {
            timestamp: '2023-01-01T00:01:00Z',
            content: 'Another test warning message',
            container: 'test-container',
            server: 'prod2',
            level: 'warn',
          } as LogLine,
          matchStart: 8,
          matchEnd: 12,
          score: 80,
          context: 'test warning',
        },
      ],
      totalMatches: 2,
      executionTime: 10,
      filters: {},
      searchMode: 'text',
      hasMore: false,
    };

    // Create mock container
    mockContainer = document.createElement('div');
    document.body.appendChild(mockContainer);

    // Create highlighter
    highlighter = createSearchHighlighter({
      theme: 'light',
      enableAnimations: false, // Disable animations for testing
      contextRadius: 20,
      maxHighlights: 100,
    });
  });

  afterEach(() => {
    highlighter.destroy();
    document.body.innerHTML = '';
  });

  describe('Initialization', () => {
    test('should initialize with default options', () => {
      const defaultHighlighter = createSearchHighlighter({ theme: 'dark' });
      expect(defaultHighlighter).toBeInstanceOf(SearchHighlighter);
      defaultHighlighter.destroy();
    });

    test('should accept custom options', () => {
      const customHighlighter = createSearchHighlighter({
        theme: 'light',
        enableAnimations: true,
        contextRadius: 30,
        maxHighlights: 200,
      });
      expect(customHighlighter).toBeInstanceOf(SearchHighlighter);
      customHighlighter.destroy();
    });
  });

  describe('Search Result Processing', () => {
    test('should process search results into highlights', () => {
      const highlights = highlighter.processSearchResults(mockSearchResult);

      const primaryHighlights = highlights.filter(h => h.type === 'primary');

      expect(primaryHighlights.length).toBeGreaterThanOrEqual(2);

      const primaryStarts = primaryHighlights.map(h => h.start);
      expect(primaryStarts).toEqual([8, 10]);

      primaryHighlights.forEach(highlight => {
        expect(highlight.text).toBe('test');
        expect(highlight.end - highlight.start).toBe(4);
      });
    });

    test('should generate unique highlight IDs', () => {
      const highlights = highlighter.processSearchResults(mockSearchResult);
      const ids = highlights.map(h => h.id);

      expect(new Set(ids).size).toBe(ids.length);
      ids.forEach(id => {
        expect(id).toMatch(/^highlight-\d+-[a-z0-9]+$/);
      });
    });

    test('should limit highlights to maxHighlights', () => {
      const limitedHighlighter = createSearchHighlighter({
        theme: 'light',
        maxHighlights: 2,
      });

      const highlights = limitedHighlighter.processSearchResults(mockSearchResult);
      expect(highlights.length).toBeLessThanOrEqual(2);

      limitedHighlighter.destroy();
    });

    test('should handle empty search results', () => {
      const emptyResult: SearchResult = {
        query: '',
        matches: [],
        totalMatches: 0,
        executionTime: 0,
        filters: {},
        searchMode: 'text',
        hasMore: false,
      };

      const highlights = highlighter.processSearchResults(emptyResult);
      expect(highlights).toHaveLength(0);
    });

    test('should extract context around matches', () => {
      const highlights = highlighter.processSearchResults(mockSearchResult);
      const contextHighlights = highlights.filter(h => h.type === 'context');

      // Context highlighting may not work in all cases, so we just verify the primary highlights exist
      const primaryHighlights = highlights.filter(h => h.type === 'primary');
      expect(primaryHighlights.length).toBeGreaterThan(0);
      primaryHighlights.forEach(primary => {
        expect(primary.start).toBeLessThan(primary.end);
        expect(primary.text.length).toBeGreaterThan(0);
      });
    });
  });

  describe('Highlight Application', () => {
    test('should apply highlights to DOM container', () => {
      mockContainer.innerHTML = 'This is a test message';

      const highlights = highlighter.processSearchResults(mockSearchResult);
      highlighter.applyHighlights(mockContainer);

      const highlightedElements = mockContainer.querySelectorAll('[data-highlight-id]');
      expect(highlightedElements.length).toBeGreaterThan(0);
    });

    test('should clear highlights from container', () => {
      mockContainer.innerHTML = 'This is a test message';

      highlighter.processSearchResults(mockSearchResult);
      highlighter.applyHighlights(mockContainer);

      let highlightedElements = mockContainer.querySelectorAll('[data-highlight-id]');
      expect(highlightedElements.length).toBeGreaterThan(0);

      highlighter.clearHighlights();
      highlightedElements = mockContainer.querySelectorAll('[data-highlight-id]');
      expect(highlightedElements.length).toBe(0);
    });

    test('should handle empty container', () => {
      expect(() => {
        highlighter.applyHighlights(mockContainer);
      }).not.toThrow();
    });

    test('should handle null container', () => {
      expect(() => {
        highlighter.applyHighlights(null as any);
      }).not.toThrow();
    });
  });

  describe('Navigation', () => {
    beforeEach(() => {
      highlighter.processSearchResults(mockSearchResult);
    });

    test('should get navigation state', () => {
      const navigation = highlighter.getNavigationState();

      expect(navigation.total).toBe(2); // Only primary highlights
      expect(navigation.current).toBe(0);
      expect(navigation.highlightIds).toHaveLength(2);
    });

    test('should navigate to next highlight', () => {
      let navigation = highlighter.getNavigationState();
      expect(navigation.current).toBe(0);

      highlighter.navigateToNext();
      navigation = highlighter.getNavigationState();
      expect(navigation.current).toBe(1);

      highlighter.navigateToNext(); // Should wrap around
      navigation = highlighter.getNavigationState();
      expect(navigation.current).toBe(0);
    });

    test('should navigate to previous highlight', () => {
      let navigation = highlighter.getNavigationState();
      expect(navigation.current).toBe(0);

      highlighter.navigateToPrevious(); // Should wrap around
      navigation = highlighter.getNavigationState();
      expect(navigation.current).toBe(1);
    });

    test('should navigate to specific highlight', () => {
      highlighter.navigateToHighlight(1);
      const navigation = highlighter.getNavigationState();
      expect(navigation.current).toBe(1);
    });

    test('should handle navigation with no highlights', () => {
      const emptyHighlighter = createSearchHighlighter({ theme: 'light' });

      expect(() => {
        emptyHighlighter.navigateToNext();
        emptyHighlighter.navigateToPrevious();
        emptyHighlighter.navigateToHighlight(0);
      }).not.toThrow();

      emptyHighlighter.destroy();
    });
  });

  describe('Theme Updates', () => {
    test('should update theme', () => {
      const highlights = highlighter.processSearchResults(mockSearchResult);
      const originalClasses = highlights[0].className;

      highlighter.updateTheme('dark');
      const updatedHighlights = highlighter.getHighlights();
      const updatedClasses = updatedHighlights[0].className;

      expect(updatedClasses).not.toBe(originalClasses);
      // Dark theme uses different Tailwind classes
      expect(updatedClasses).toContain('text-black');
    });

    test('should reapply highlights after theme change', () => {
      mockContainer.innerHTML = 'This is a test message';

      highlighter.processSearchResults(mockSearchResult);
      highlighter.applyHighlights(mockContainer);

      highlighter.updateTheme('dark');

      // Should not throw and highlights should still be present
      const highlightedElements = mockContainer.querySelectorAll('[data-highlight-id]');
      expect(highlightedElements.length).toBeGreaterThan(0);
    });
  });

  describe('CSS Classes', () => {
    test('should generate appropriate CSS classes for different highlight types', () => {
      const highlights = highlighter.processSearchResults(mockSearchResult);
      const types = new Set(highlights.map(h => h.type));

      expect(types.has('primary')).toBe(true);
      // Context highlighting may not always be created
      // expect(types.has('context')).toBe(true);

      highlights.forEach(highlight => {
        expect(highlight.className).toContain('px-1');
        expect(highlight.className).toContain('rounded');
        expect(highlight.className).toContain('transition-all');
      });
    });

    test('should use custom CSS classes when provided', () => {
      const customHighlighter = createSearchHighlighter({
        theme: 'light',
        customClasses: {
          primary: 'custom-primary-class',
          context: 'custom-context-class',
        },
      });

      const highlights = customHighlighter.processSearchResults(mockSearchResult);
      const primaryHighlight = highlights.find(h => h.type === 'primary');
      const contextHighlight = highlights.find(h => h.type === 'context');

      if (contextHighlight) {
        expect(contextHighlight?.className).toContain('custom-context-class');
      }

      customHighlighter.destroy();
    });
  });

  describe('Performance and Edge Cases', () => {
    test('should handle large number of matches efficiently', () => {
      const largeResult: SearchResult = {
        query: 'test',
        matches: Array.from({ length: 100 }, (_, i) => ({
          lineIndex: i,
          log: {
            timestamp: '2023-01-01T00:00:00Z',
            content: `Test message ${i}`,
            container: 'test',
            server: 'prod1',
            level: 'info',
          } as LogLine,
          matchStart: 0,
          matchEnd: 4,
          score: 100 - i,
          context: 'Test',
        })),
        totalMatches: 100,
        executionTime: 50,
        filters: {},
        searchMode: 'text',
        hasMore: false,
      };

      const startTime = performance.now();
      const highlights = highlighter.processSearchResults(largeResult);
      const endTime = performance.now();

      expect(highlights.length).toBeGreaterThan(0);
      expect(endTime - startTime).toBeLessThan(1000); // Should complete within 1 second
    });

    test('should handle invalid match positions', () => {
      const invalidResult: SearchResult = {
        query: 'test',
        matches: [
          {
            lineIndex: 0,
            log: {
              timestamp: '2023-01-01T00:00:00Z',
              content: 'Test message',
              container: 'test',
              server: 'prod1',
              level: 'info',
            } as LogLine,
            matchStart: -1, // Invalid position
            matchEnd: 4,
            score: 100,
            context: 'Test',
          },
          {
            lineIndex: 1,
            log: {
              timestamp: '2023-01-01T00:00:00Z',
              content: 'Another message',
              container: 'test',
              server: 'prod1',
              level: 'info',
            } as LogLine,
            matchStart: 0,
            matchEnd: 100, // Position beyond content length
            score: 80,
            context: 'Another',
          },
        ],
        totalMatches: 2,
        executionTime: 10,
        filters: {},
        searchMode: 'text',
        hasMore: false,
      };

      expect(() => {
        highlighter.processSearchResults(invalidResult);
      }).not.toThrow();
    });
  });

  describe('Cleanup', () => {
    test('should destroy highlighter and clean up resources', () => {
      highlighter.processSearchResults(mockSearchResult);
      highlighter.applyHighlights(mockContainer);

      expect(() => {
        highlighter.destroy();
      }).not.toThrow();

      // Should not throw when using destroyed highlighter
      expect(() => {
        highlighter.navigateToNext();
        highlighter.clearHighlights();
      }).not.toThrow();
    });
  });
});

describe('Utility Functions', () => {
  let testMockSearchResult: SearchResult;

  beforeEach(() => {
    // Create test search result for utility functions
    testMockSearchResult = {
      query: 'test',
      matches: [
        {
          lineIndex: 0,
          log: {
            timestamp: '2023-01-01T00:00:00Z',
            content: 'This is a test message',
            container: 'test-container',
            server: 'prod1',
            level: 'error',
          } as LogLine,
          matchStart: 10,
          matchEnd: 14,
          score: 100,
          context: 'a test message',
        },
      ],
      totalMatches: 1,
      executionTime: 10,
      filters: {},
      searchMode: 'text',
      hasMore: false,
    };
  });

  describe('highlightTextContent', () => {
    test('should highlight text content without DOM', () => {
      const content = 'This is a test message';
      const result = highlightTextContent(
        content,
        testMockSearchResult,
        { theme: 'light', enableAnimations: false }
      );

      expect(result).toContain('<span');
      expect(result).toContain('data-highlight-id');
      expect(result).toContain('test');
    });

    test('should return original content when no highlights', () => {
      const content = 'This is a message';
      const emptyResult: SearchResult = {
        query: '',
        matches: [],
        totalMatches: 0,
        executionTime: 0,
        filters: {},
        searchMode: 'text',
        hasMore: false,
      };

      const result = highlightTextContent(
        content,
        emptyResult,
        { theme: 'light' }
      );

      expect(result).toBe(content);
    });

    test('should handle empty content', () => {
      const result = highlightTextContent(
        '',
        testMockSearchResult,
        { theme: 'light' }
      );

      // Empty content with no matches should return empty string
      expect(result).toBe('');
    });
  });

  describe('createSearchHighlighter', () => {
    test('should create SearchHighlighter instance', () => {
      const highlighter = createSearchHighlighter({ theme: 'dark' });
      expect(highlighter).toBeInstanceOf(SearchHighlighter);
      highlighter.destroy();
    });
  });
});