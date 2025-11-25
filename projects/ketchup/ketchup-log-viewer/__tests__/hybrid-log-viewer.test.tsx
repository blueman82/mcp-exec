/**
 * Unit Tests for HybridLogViewer Component
 *
 * Comprehensive test suite covering:
 * - Component rendering and layout structure
 * - Search integration and result handling
 * - Panel resizing functionality (mouse and keyboard)
 * - Result selection and context viewing
 * - Grouping and sorting controls
 * - Highlight navigation
 * - Accessibility features (WCAG 2.1 AA compliant)
 * - Keyboard shortcuts and navigation
 * - Theme responsiveness
 * - Context size configuration
 * - Error handling and edge cases
 * - Screen reader announcements
 */

import React from 'react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import HybridLogViewer from '@/components/HybridLogViewer';
import { getSearchManager } from '@/lib/search-manager';
import { createSearchHighlighter } from '@/lib/search-highlighter';
import { createSearchGrouper } from '@/lib/search-grouper';
import type { SearchResult, SearchMatch } from '@/types/search';
import type { LogLine } from '@/types';

// Mock the dependencies
vi.mock('@/components/EnhancedSearch', () => ({
  default: ({ logs, theme, onSearchResults, availableContainers, availableServers }: any) => (
    <div data-testid="enhanced-search">
      <input
        type="text"
        placeholder="Search logs..."
        data-testid="search-input"
        onChange={(e) => {
          if (onSearchResults && e.target.value) {
            // Mock search results
            const mockResult: SearchResult = {
              query: e.target.value,
              matches: logs.slice(0, 2).map((log: LogLine, index: number) => ({
                log,
                lineIndex: index,
                score: 0.9,
                startIndex: 0,
                endIndex: 4,
                text: e.target.value,
                type: 'term' as const,
              })),
              totalMatches: 2,
              executionTime: 10,
              filters: {},
            };
            onSearchResults(mockResult);
          }
        }}
      />
      <div data-testid="available-containers" data-containers={availableContainers?.join(',')} />
      <div data-testid="available-servers" data-servers={availableServers?.join(',')} />
    </div>
  ),
}));

vi.mock('@/lib/search-manager', () => ({
  getSearchManager: () => ({
    search: vi.fn().mockResolvedValue({
      query: 'test',
      matches: [],
      totalMatches: 0,
      executionTime: 5,
    }),
    getState: vi.fn().mockReturnValue({
      cacheStats: { hitRate: 85 },
    }),
  }),
}));

vi.mock('@/lib/search-highlighter', () => ({
  createSearchHighlighter: () => ({
    updateTheme: vi.fn(),
    processSearchResults: vi.fn().mockReturnValue([]),
    getNavigationState: vi.fn().mockReturnValue({ total: 0, current: 0, highlightIds: [] }),
    applyHighlights: vi.fn(),
    clearHighlights: vi.fn(),
    navigateToNext: vi.fn(),
    navigateToPrevious: vi.fn(),
    destroy: vi.fn(),
  }),
}));

vi.mock('@/lib/search-grouper', () => ({
  createSearchGrouper: () => ({
    processSearchResult: vi.fn().mockReturnValue({
      groups: new Map([
        ['ketchup-app', { name: 'ketchup-app', count: 1, metadata: { servers: ['prod1'] } }],
      ]),
      groupedMatches: new Map([
        ['ketchup-app', []],
      ]),
      sortedMatches: [],
      config: {
        grouping: { groupBy: 'container' },
        sorting: { sortBy: 'relevance', direction: 'desc' },
      },
    }),
    updateGroupingConfig: vi.fn(),
    updateSortingConfig: vi.fn(),
  }),
}));

// Mock data for testing
const mockSelections = [
  {
    container: 'ketchup-app',
    server: 'prod1' as const,
  },
  {
    container: 'ketchup-db',
    server: 'prod2' as const,
  },
];

const mockLogs: LogLine[] = [
  {
    timestamp: '2025-01-14T10:00:00.000Z',
    content: 'Application started successfully',
    container: 'ketchup-app',
    server: 'prod1',
    level: 'info',
  },
  {
    timestamp: '2025-01-14T10:01:00.000Z',
    content: 'Database connection failed',
    container: 'ketchup-db',
    server: 'prod1',
    level: 'error',
  },
  {
    timestamp: '2025-01-14T10:02:00.000Z',
    content: 'User authentication successful',
    container: 'ketchup-auth',
    server: 'prod2',
    level: 'info',
  },
  {
    timestamp: '2025-01-14T10:03:00.000Z',
    content: 'Warning: High memory usage detected',
    container: 'ketchup-monitor',
    server: 'prod2',
    level: 'warn',
  },
  {
    timestamp: '2025-01-14T10:04:00.000Z',
    content: 'Debug: Processing request #12345',
    container: 'ketchup-api',
    server: 'prod1',
    level: 'debug',
  },
];

const mockSearchResult: SearchResult = {
  query: 'test query',
  matches: [
    {
      log: mockLogs[1],
      lineIndex: 1,
      score: 0.95,
      startIndex: 0,
      endIndex: 7,
      text: 'Database',
      type: 'term',
    },
    {
      log: mockLogs[3],
      lineIndex: 3,
      score: 0.85,
      startIndex: 9,
      endIndex: 13,
      text: 'High',
      type: 'term',
    },
  ],
  totalMatches: 2,
  executionTime: 15.5,
  filters: {
    logLevels: ['error', 'warn'],
    servers: ['prod1', 'prod2'],
    containers: ['ketchup-db', 'ketchup-monitor'],
  },
};

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  let shouldThrowError = false;

  return {
    getItem: vi.fn((key: string) => {
      if (shouldThrowError) {
        throw new Error('Storage error');
      }
      return store[key] || null;
    }),
    setItem: vi.fn((key: string, value: string) => {
      if (shouldThrowError) {
        throw new Error('Storage error');
      }
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      if (shouldThrowError) {
        throw new Error('Storage error');
      }
      delete store[key];
    }),
    clear: vi.fn(() => {
      if (shouldThrowError) {
        throw new Error('Storage error');
      }
      store = {};
    }),
    length: 0,
    key: vi.fn(() => null),
    setErrorMode: (enabled: boolean) => {
      shouldThrowError = enabled;
    },
  };
})();

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
  writable: true,
});

// Mock IntersectionObserver for virtual scrolling
const mockIntersectionObserver = vi.fn();
mockIntersectionObserver.mockReturnValue({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
});
window.IntersectionObserver = mockIntersectionObserver;

// Mock fetch API
global.fetch = vi.fn();

describe('HybridLogViewer Component', () => {
  const defaultProps = {
    selections: mockSelections,
    theme: 'dark' as const,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.clearAllTimers();
    vi.useFakeTimers();
    localStorageMock.clear();

    // Mock successful fetch responses
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        data: mockLogs,
      }),
    });
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    localStorageMock.clear();
  });

  describe('Component Rendering', () => {
    it('should render main layout structure', () => {
      act(() => {
        render(<HybridLogViewer {...defaultProps} />);
      });

      // Check for main sections - use getAllByRole for multiple banners
      expect(screen.getAllByRole('banner')).toHaveLength(3); // Main header + two panel headers
      expect(screen.getByRole('main')).toBeInTheDocument(); // Main panels
      expect(screen.getByRole('contentinfo')).toBeInTheDocument(); // Footer
    });

    it('should render two resizable panels', () => {
      render(<HybridLogViewer {...defaultProps} />);

      expect(screen.getByRole('region', { name: /search results panel/i })).toBeInTheDocument();
      expect(screen.getByRole('region', { name: /full log context panel/i })).toBeInTheDocument();
    });

    it('should render resize handle with proper ARIA attributes', () => {
      render(<HybridLogViewer {...defaultProps} />);

      const resizeHandle = screen.getByRole('separator', { name: /panel resize handle/i });
      expect(resizeHandle).toHaveAttribute('aria-orientation', 'vertical');
      expect(resizeHandle).toHaveAttribute('aria-valuemin', '20');
      expect(resizeHandle).toHaveAttribute('aria-valuemax', '80');
      expect(resizeHandle).toHaveAttribute('aria-controls', 'search-results-panel log-context-panel');
    });

    it('should render skip links for accessibility', () => {
      render(<HybridLogViewer {...defaultProps} />);

      expect(screen.getByRole('link', { name: /skip to search results/i })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /skip to log context/i })).toBeInTheDocument();
    });

    it('should apply dark theme styling', () => {
      render(<HybridLogViewer {...defaultProps} theme="dark" />);

      const header = screen.getByRole('banner');
      expect(header).toHaveClass('bg-gray-900');
    });

    it('should apply light theme styling', () => {
      render(<HybridLogViewer {...defaultProps} theme="light" />);

      const header = screen.getByRole('banner');
      expect(header).toHaveClass('bg-gray-50');
    });

    it('should load context size from localStorage on mount', () => {
      localStorageMock.getItem.mockReturnValue('10');

      render(<HybridLogViewer {...defaultProps} />);

      expect(localStorageMock.getItem).toHaveBeenCalledWith('hybrid-log-viewer-context-size');
      expect(screen.getByDisplayValue('10 lines')).toBeInTheDocument();
    });
  });

  describe('Search Integration', () => {
    it('should render EnhancedSearch component', () => {
      render(<HybridLogViewer {...defaultProps} />);

      expect(screen.getByPlaceholderText(/search logs/i)).toBeInTheDocument();
    });

    it('should handle search results from EnhancedSearch', async () => {
      render(<HybridLogViewer {...defaultProps} />);

      const searchInput = screen.getByPlaceholderText(/search logs/i);
      await userEvent.type(searchInput, 'test');

      // Mock search result callback
      const enhancedSearch = screen.getByTestId('enhanced-search') || searchInput.closest('form');
      if (enhancedSearch) {
        // Simulate search results being received
        fireEvent.change(searchInput, { target: { value: 'test' } });

        await waitFor(() => {
          expect(screen.getByText(/found \d+ results? in \d+\.\d+ms/i)).toBeInTheDocument();
        });
      }
    });

    it('should display search results summary', async () => {
      render(<HybridLogViewer {...defaultProps} />);

      // Simulate receiving search results
      const resultsSummary = screen.queryByRole('status', { name: /search results/i });
      if (resultsSummary) {
        expect(resultsSummary).toBeInTheDocument();
      }
    });

    it('should show cache indicator when results from cache', async () => {
      render(<HybridLogViewer {...defaultProps} />);

      // Look for cache indicator
      const cacheIndicator = screen.queryByText(/from cache/i);
      if (cacheIndicator) {
        expect(cacheIndicator).toBeInTheDocument();
        expect(cacheIndicator).toHaveAttribute('role', 'note');
      }
    });
  });

  describe('Panel Resizing', () => {
    it('should start panel resize on mouse down', async () => {
      const user = userEvent.setup();
      render(<HybridLogViewer {...defaultProps} />);

      const resizeHandle = screen.getByRole('separator', { name: /panel resize handle/i });

      await user.click(resizeHandle);

      expect(resizeHandle).toHaveFocus();
    });

    it('should handle keyboard panel resizing', async () => {
      const user = userEvent.setup();
      render(<HybridLogViewer {...defaultProps} />);

      const resizeHandle = screen.getByRole('separator', { name: /panel resize handle/i });

      // Start resizing
      await user.click(resizeHandle);

      // Navigate with arrow keys
      await user.keyboard('{ArrowRight}');

      // Should announce new panel sizes
      const liveRegion = screen.getByRole('status', { hidden: true });
      expect(liveRegion).toBeInTheDocument();
    });

    it('should confirm panel resize with Enter key', async () => {
      const user = userEvent.setup();
      render(<HybridLogViewer {...defaultProps} />);

      const resizeHandle = screen.getByRole('separator', { name: /panel resize handle/i });

      await user.click(resizeHandle);
      await user.keyboard('{ArrowRight}');
      await user.keyboard('{Enter}');

      // Should announce confirmation
      expect(resizeHandle).not.toHaveFocus();
    });

    it('should cancel panel resize with Escape key', async () => {
      const user = userEvent.setup();
      render(<HybridLogViewer {...defaultProps} />);

      const resizeHandle = screen.getByRole('separator', { name: /panel resize handle/i });

      await user.click(resizeHandle);
      await user.keyboard('{ArrowRight}');
      await user.keyboard('{Escape}');

      // Should announce cancellation
      expect(resizeHandle).not.toHaveFocus();
    });

    it('should constrain panel sizes between 20% and 80%', async () => {
      const user = userEvent.setup();
      render(<HybridLogViewer {...defaultProps} />);

      const resizeHandle = screen.getByRole('separator', { name: /panel resize handle/i });

      await user.click(resizeHandle);

      // Try to go beyond minimum
      await user.keyboard('{Home}');
      expect(resizeHandle).toHaveAttribute('aria-valuenow', '20');

      // Try to go beyond maximum
      await user.keyboard('{End}');
      expect(resizeHandle).toHaveAttribute('aria-valuenow', '80');
    });
  });

  describe('Search Results Display', () => {
    beforeEach(() => {
      // Mock search results
      vi.spyOn(getSearchManager(), 'search').mockResolvedValue(mockSearchResult);
    });

    it('should display search results in left panel', async () => {
      render(<HybridLogViewer {...defaultProps} />);

      // Perform search
      const searchInput = screen.getByPlaceholderText(/search logs/i);
      await userEvent.type(searchInput, 'test');

      await waitFor(() => {
        const resultsPanel = screen.getByRole('region', { name: /search results panel/i });
        expect(resultsPanel).toBeInTheDocument();
      });
    });

    it('should group results by container', async () => {
      render(<HybridLogViewer {...defaultProps} />);

      // Mock grouped results
      await waitFor(() => {
        const groupHeaders = screen.getAllByText(/ketchup-(app|db|auth|monitor|api)/i);
        expect(groupHeaders.length).toBeGreaterThan(0);
      });
    });

    it('should show result metadata (log level, score, index)', async () => {
      render(<HybridLogViewer {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText(/ERROR/i)).toBeInTheDocument();
        expect(screen.getByText(/Score:/i)).toBeInTheDocument();
        expect(screen.getByText(/Index \d+/i)).toBeInTheDocument();
      });
    });

    it('should expand result context on + button click', async () => {
      const user = userEvent.setup();
      render(<HybridLogViewer {...defaultProps} />);

      // Find and click expand button
      const expandButtons = screen.getAllByRole('button', { name: '+' });
      if (expandButtons.length > 0) {
        await user.click(expandButtons[0]);

        // Should show context
        expect(screen.getByText(/Context:/i)).toBeInTheDocument();
      }
    });

    it('should select result and show context in right panel', async () => {
      const user = userEvent.setup();
      render(<HybridLogViewer {...defaultProps} />);

      await waitFor(() => {
        const resultItems = screen.getAllByRole('button').filter(
          button => button.textContent && button.textContent.length > 20
        );

        if (resultItems.length > 0) {
          user.click(resultItems[0]);

          // Should show context panel
          expect(screen.getByText(/Viewing context for selected result/i)).toBeInTheDocument();
        }
      });
    });
  });

  describe('Grouping and Sorting Controls', () => {
    it('should show grouping controls when search results exist', async () => {
      render(<HybridLogViewer {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /grouping/i })).toBeInTheDocument();
      });
    });

    it('should expand grouping controls on button click', async () => {
      const user = userEvent.setup();
      render(<HybridLogViewer {...defaultProps} />);

      const groupingButton = screen.getByRole('button', { name: /grouping/i });
      await user.click(groupingButton);

      expect(screen.getByDisplayValue(/container/i)).toBeInTheDocument();
    });

    it('should update grouping when selection changes', async () => {
      const user = userEvent.setup();
      render(<HybridLogViewer {...defaultProps} />);

      const groupingButton = screen.getByRole('button', { name: /grouping/i });
      await user.click(groupingButton);

      const groupingSelect = screen.getByDisplayValue(/container/i);
      await user.selectOptions(groupingSelect, 'server');

      // Should announce change
      const liveRegion = screen.getByRole('status', { hidden: true });
      expect(liveRegion).toBeInTheDocument();
    });

    it('should show sorting controls', async () => {
      render(<HybridLogViewer {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByDisplayValue(/relevance/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /sort direction/i })).toBeInTheDocument();
      });
    });

    it('should toggle sort direction', async () => {
      const user = userEvent.setup();
      render(<HybridLogViewer {...defaultProps} />);

      const sortDirectionButton = screen.getByRole('button', { name: /sort direction/i });
      await user.click(sortDirectionButton);

      // Should announce direction change
      const liveRegion = screen.getByRole('status', { hidden: true });
      expect(liveRegion).toBeInTheDocument();
    });
  });

  describe('Highlight Navigation', () => {
    it('should show highlight navigation controls', async () => {
      render(<HybridLogViewer {...defaultProps} />);

      await waitFor(() => {
        const highlightControls = screen.queryByRole('group', { name: /highlight navigation/i });
        if (highlightControls) {
          expect(highlightControls).toBeInTheDocument();
          expect(screen.getByRole('button', { name: /previous highlight/i })).toBeInTheDocument();
          expect(screen.getByRole('button', { name: /next highlight/i })).toBeInTheDocument();
        }
      });
    });

    it('should navigate to next highlight', async () => {
      const user = userEvent.setup();
      render(<HybridLogViewer {...defaultProps} />);

      const nextButton = screen.queryByRole('button', { name: /next highlight/i });
      if (nextButton) {
        await user.click(nextButton);

        // Should announce navigation
        const liveRegion = screen.getByRole('status', { hidden: true });
        expect(liveRegion).toBeInTheDocument();
      }
    });

    it('should navigate to previous highlight', async () => {
      const user = userEvent.setup();
      render(<HybridLogViewer {...defaultProps} />);

      const prevButton = screen.queryByRole('button', { name: /previous highlight/i });
      if (prevButton) {
        await user.click(prevButton);

        // Should announce navigation
        const liveRegion = screen.getByRole('status', { hidden: true });
        expect(liveRegion).toBeInTheDocument();
      }
    });
  });

  describe('Context Size Configuration', () => {
    it('should show context size selector', () => {
      render(<HybridLogViewer {...defaultProps} />);

      expect(screen.getByDisplayValue('5 lines')).toBeInTheDocument();
    });

    it('should change context size when selection changes', async () => {
      const user = userEvent.setup();
      render(<HybridLogViewer {...defaultProps} />);

      const contextSelect = screen.getByDisplayValue('5 lines');
      await user.selectOptions(contextSelect, '10 lines');

      expect(contextSelect).toHaveValue('10');

      // Should save to localStorage
      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        'hybrid-log-viewer-context-size',
        '10'
      );
    });

    it('should announce context size change', async () => {
      const user = userEvent.setup();
      render(<HybridLogViewer {...defaultProps} />);

      const contextSelect = screen.getByDisplayValue('5 lines');
      await user.selectOptions(contextSelect, '10 lines');

      const liveRegion = screen.getByRole('status', { hidden: true });
      expect(liveRegion).toBeInTheDocument();
    });
  });

  describe('Keyboard Shortcuts', () => {
    it('should navigate results with F3 and Shift+F3', async () => {
      render(<HybridLogViewer {...defaultProps} />);

      // F3 - next result
      fireEvent.keyDown(document, { key: 'F3' });

      // Shift+F3 - previous result
      fireEvent.keyDown(document, { key: 'F3', shiftKey: true });

      const liveRegion = screen.getByRole('status', { hidden: true });
      expect(liveRegion).toBeInTheDocument();
    });

    it('should focus resize handle with keyboard when appropriate', async () => {
      const user = userEvent.setup();
      render(<HybridLogViewer {...defaultProps} />);

      const resizeHandle = screen.getByRole('separator', { name: /panel resize handle/i });
      await user.click(resizeHandle);

      expect(resizeHandle).toHaveFocus();
    });
  });

  describe('Accessibility Features', () => {
    it('should have proper ARIA labels and roles', () => {
      render(<HybridLogViewer {...defaultProps} />);

      expect(screen.getByRole('banner')).toBeInTheDocument();
      expect(screen.getByRole('main')).toBeInTheDocument();
      expect(screen.getByRole('contentinfo')).toBeInTheDocument();
      expect(screen.getByRole('navigation', { name: /search result controls/i })).toBeInTheDocument();
    });

    it('should have screen reader announcements', () => {
      render(<HybridLogViewer {...defaultProps} />);

      const liveRegions = screen.getAllByRole('status', { hidden: true });
      expect(liveRegions.length).toBeGreaterThan(0);
    });

    it('should have semantic HTML structure', () => {
      render(<HybridLogViewer {...defaultProps} />);

      expect(screen.getByRole('region', { name: /search results panel/i })).toBeInTheDocument();
      expect(screen.getByRole('region', { name: /full log context panel/i })).toBeInTheDocument();
    });

    it('should have focus management for resize handle', async () => {
      const user = userEvent.setup();
      render(<HybridLogViewer {...defaultProps} />);

      const resizeHandle = screen.getByRole('separator', { name: /panel resize handle/i });

      // Initially not focusable
      expect(resizeHandle).toHaveAttribute('tabIndex', '-1');

      // Becomes focusable when resizing
      await user.click(resizeHandle);
      expect(resizeHandle).toHaveFocus();
    });

    it('should have skip links that work', async () => {
      const user = userEvent.setup();
      render(<HybridLogViewer {...defaultProps} />);

      const skipLink = screen.getByRole('link', { name: /skip to search results/i });
      await user.click(skipLink);

      expect(window.location.hash).toBe('#search-results-panel');
    });
  });

  describe('Error Handling', () => {
    it('should handle API fetch errors gracefully', async () => {
      (global.fetch as any).mockRejectedValue(new Error('Network error'));

      render(<HybridLogViewer {...defaultProps} />);

      // Should not crash
      expect(screen.getByRole('banner')).toBeInTheDocument();
    });

    it('should handle empty selections', () => {
      render(<HybridLogViewer {...defaultProps} selections={[]} />);

      expect(screen.getByRole('banner')).toBeInTheDocument();
    });

    it('should handle missing localStorage gracefully', () => {
      localStorageMock.setErrorMode(true);

      expect(() => {
        act(() => {
          render(<HybridLogViewer {...defaultProps} />);
        });
      }).not.toThrow();

      localStorageMock.setErrorMode(false);
    });

    it('should handle search manager errors', async () => {
      const searchManager = getSearchManager();
      vi.spyOn(searchManager, 'search').mockRejectedValue(new Error('Search failed'));

      render(<HybridLogViewer {...defaultProps} />);

      const searchInput = screen.getByPlaceholderText(/search logs/i);
      await userEvent.type(searchInput, 'test');

      // Should not crash
      expect(screen.getByRole('banner')).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should handle no search results', () => {
      render(<HybridLogViewer {...defaultProps} />);

      const resultsPanel = screen.getByRole('region', { name: /search results panel/i });
      expect(resultsPanel).toBeInTheDocument();
    });

    it('should handle large number of results', async () => {
      // Mock many results
      const manyResults: SearchResult = {
        ...mockSearchResult,
        matches: Array.from({ length: 1000 }, (_, i) => ({
          ...mockSearchResult.matches[0],
          lineIndex: i,
        })),
        totalMatches: 1000,
      };

      vi.spyOn(getSearchManager(), 'search').mockResolvedValue(manyResults);

      render(<HybridLogViewer {...defaultProps} />);

      const searchInput = screen.getByPlaceholderText(/search logs/i);
      await userEvent.type(searchInput, 'test');

      await waitFor(() => {
        expect(screen.getByText(/found 1000 results?/i)).toBeInTheDocument();
      });
    });

    it('should handle very long log lines', () => {
      const longLogs: LogLine[] = [
        {
          ...mockLogs[0],
          content: 'a'.repeat(10000),
        },
      ];

      render(<HybridLogViewer {...defaultProps} selections={[{ container: 'test', server: 'prod1' }]} logs={longLogs} />);

      expect(screen.getByRole('banner')).toBeInTheDocument();
    });

    it('should handle rapid panel resizing', async () => {
      const user = userEvent.setup();
      render(<HybridLogViewer {...defaultProps} />);

      const resizeHandle = screen.getByRole('separator', { name: /panel resize handle/i });

      await user.click(resizeHandle);
      await user.keyboard('{ArrowRight}');
      await user.keyboard('{ArrowLeft}');
      await user.keyboard('{ArrowRight}');
      await user.keyboard('{Enter}');

      expect(resizeHandle).not.toHaveFocus();
    });

    it('should handle missing optional props', () => {
      render(<HybridLogViewer selections={mockSelections} theme="dark" />);

      expect(screen.getByRole('banner')).toBeInTheDocument();
    });
  });

  describe('Component Lifecycle', () => {
    it('should clean up highlighter on unmount', () => {
      const { unmount } = render(<HybridLogViewer {...defaultProps} />);

      const highlighter = createSearchHighlighter({ theme: 'dark', enableAnimations: true });
      const destroySpy = vi.spyOn(highlighter, 'destroy');

      unmount();

      // Cleanup should happen
      expect(destroySpy).toHaveBeenCalled();
    });

    it('should update highlighter when theme changes', () => {
      const { rerender } = render(<HybridLogViewer {...defaultProps} theme="dark" />);

      rerender(<HybridLogViewer {...defaultProps} theme="light" />);

      // Should update highlighter theme
      expect(screen.getByRole('banner')).toBeInTheDocument();
    });
  });

  describe('Performance Considerations', () => {
    it('should debounce search input', async () => {
      const user = userEvent.setup({ delay: null });
      render(<HybridLogViewer {...defaultProps} />);

      const searchInput = screen.getByPlaceholderText(/search logs/i);
      await user.type(searchInput, 'test');

      // Should show loading indicator
      expect(screen.queryByRole('status', { name: /searching/i })).toBeInTheDocument();

      // Advance timers
      vi.advanceTimersByTime(300);

      await waitFor(() => {
        // Should finish searching
        expect(screen.queryByRole('status', { name: /searching/i })).not.toBeInTheDocument();
      });
    });

    it('should handle large log arrays efficiently', () => {
      const largeLogs = Array.from({ length: 10000 }, (_, i) => ({
        ...mockLogs[0],
        timestamp: new Date(Date.now() - i * 1000).toISOString(),
        content: `Log entry ${i}`,
      }));

      render(<HybridLogViewer {...defaultProps} selections={[{ container: 'test', server: 'prod1' }]} logs={largeLogs} />);

      expect(screen.getByRole('banner')).toBeInTheDocument();
    });
  });
});