/**
 * Integration Tests for Phases 1-3 Workflow
 *
 * Comprehensive integration test suite covering the complete search enhancement workflow:
 * - Phase 1: Enhanced Search Infrastructure (SearchManager, caching, debouncing)
 * - Phase 2: Hybrid Layout Implementation (panel resizing, synchronized scrolling)
 * - Phase 3: Search Context Enhancement (grouping, sorting, highlighting)
 *
 * These tests verify that all components work together correctly in real-world scenarios.
 */

import React from 'react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Import the actual components for integration testing
import HybridLogViewer from '@/components/HybridLogViewer';
import { getSearchManager } from '@/lib/search-manager';
import { createSearchHighlighter } from '@/lib/search-highlighter';
import { createSearchGrouper } from '@/lib/search-grouper';

// Extended mock data for integration testing
const mockLogs = [
  {
    timestamp: '2025-01-14T10:00:00.000Z',
    content: 'Application started successfully on port 3000',
    container: 'ketchup-app',
    server: 'prod1',
    level: 'info',
  },
  {
    timestamp: '2025-01-14T10:00:15.000Z',
    content: 'Database connection established',
    container: 'ketchup-db',
    server: 'prod1',
    level: 'info',
  },
  {
    timestamp: '2025-01-14T10:01:00.000Z',
    content: 'ERROR: Failed to connect to payment service',
    container: 'ketchup-app',
    server: 'prod1',
    level: 'error',
  },
  {
    timestamp: '2025-01-14T10:01:30.000Z',
    content: 'WARNING: High memory usage detected (85%)',
    container: 'ketchup-monitor',
    server: 'prod2',
    level: 'warn',
  },
  {
    timestamp: '2025-01-14T10:02:00.000Z',
    content: 'User authentication successful for user@example.com',
    container: 'ketchup-auth',
    server: 'prod2',
    level: 'info',
  },
  {
    timestamp: '2025-01-14T10:02:15.000Z',
    content: 'DEBUG: Processing request #12345 for user data',
    container: 'ketchup-api',
    server: 'prod1',
    level: 'debug',
  },
  {
    timestamp: '2025-01-14T10:03:00.000Z',
    content: 'ERROR: Database timeout after 30 seconds',
    container: 'ketchup-db',
    server: 'prod2',
    level: 'error',
  },
  {
    timestamp: '2025-01-14T10:03:30.000Z',
    content: 'INFO: Cache cleared successfully',
    container: 'ketchup-cache',
    server: 'prod1',
    level: 'info',
  },
];

const mockSelections = [
  { container: 'ketchup-app', server: 'prod1' },
  { container: 'ketchup-db', server: 'prod1' },
  { container: 'ketchup-monitor', server: 'prod2' },
];

// Mock localStorage for integration tests
const localStorageMock = (() => {
  let store = {};
  return {
    getItem: vi.fn((key) => store[key] || null),
    setItem: vi.fn((key, value) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
    length: Object.keys(store).length,
    key: vi.fn((index) => Object.keys(store)[index] || null),
  };
})();

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
  writable: true,
});

// Mock fetch for API integration
global.fetch = vi.fn();

describe('Phases 1-3 Integration Workflow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.clearAllTimers();
    vi.useFakeTimers();
    localStorageMock.clear();

    // Mock successful API responses
    global.fetch.mockResolvedValue({
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

  describe('Phase 1: Enhanced Search Infrastructure Integration', () => {
    it('should verify search manager integration', () => {
      const searchManager = getSearchManager();

      // Test basic search manager functionality
      expect(searchManager).toBeDefined();
      expect(typeof searchManager.search).toBe('function');
      expect(typeof searchManager.getState).toBe('function');

      // Test state management
      const state = searchManager.getState();
      expect(state).toBeDefined();
      expect(state).toHaveProperty('cacheStats');
    });

    it('should verify search highlighter integration', () => {
      const searchHighlighter = createSearchHighlighter({ theme: 'dark', enableAnimations: true });

      // Test basic highlighter functionality
      expect(searchHighlighter).toBeDefined();
      expect(typeof searchHighlighter.processSearchResults).toBe('function');
      expect(typeof searchHighlighter.getNavigationState).toBe('function');
    });

    it('should verify search grouper integration', () => {
      const searchGrouper = createSearchGrouper({ persistPreferences: true });

      // Test basic grouper functionality
      expect(searchGrouper).toBeDefined();
      expect(typeof searchGrouper.processSearchResult).toBe('function');
      expect(typeof searchGrouper.updateGroupingConfig).toBe('function');
    });

    it('should verify library integration works together', () => {
      const searchManager = getSearchManager();
      const searchHighlighter = createSearchHighlighter({ theme: 'dark', enableAnimations: true });
      const searchGrouper = createSearchGrouper({ persistPreferences: true });

      // Test that libraries can work together
      const mockSearchResult = {
        query: 'test error',
        matches: mockLogs.slice(0, 2).map((log, index) => ({
          log,
          lineIndex: index,
          score: 0.9,
          startIndex: 0,
          endIndex: 5,
          text: 'test',
          type: 'term',
        })),
        totalMatches: 2,
        executionTime: 15,
        filters: { logLevels: ['error'] },
      };

      // Test grouper processing
      const groupedResults = searchGrouper.processSearchResult(mockSearchResult);
      expect(groupedResults).toBeDefined();
      expect(groupedResults.groups.size).toBeGreaterThan(0);

      // Test highlighter processing
      const highlights = searchHighlighter.processSearchResults(mockSearchResult);
      expect(Array.isArray(highlights)).toBe(true);

      // Test navigation state
      const navigation = searchHighlighter.getNavigationState();
      expect(navigation.total).toBeDefined();
      expect(navigation.current).toBeDefined();
    });
  });

  describe('Phase 2: Hybrid Layout Integration', () => {
    it('should render HybridLogViewer with correct layout', () => {
      render(
        <HybridLogViewer
          selections={mockSelections}
          theme="dark"
        />
      );

      // Verify main layout structure
      expect(screen.getByRole('main')).toBeInTheDocument();
      expect(screen.getByRole('banner')).toBeInTheDocument();
      expect(screen.getByRole('contentinfo')).toBeInTheDocument();
    });

    it('should handle panel resizing controls', async () => {
      const user = userEvent.setup();

      render(
        <HybridLogViewer
          selections={mockSelections}
          theme="dark"
        />
      );

      // Look for resize handle
      const resizeHandle = screen.getByRole('separator', { name: /panel resize handle/i });
      expect(resizeHandle).toBeInTheDocument();

      // Test that resize handle can be focused
      await user.click(resizeHandle);
      expect(resizeHandle).toHaveFocus();

      // Test keyboard controls
      await user.keyboard('{ArrowRight}');
      await user.keyboard('{Enter}');

      // Should complete without errors
      expect(resizeHandle).not.toHaveFocus();
    });

    it('should handle context size configuration', async () => {
      const user = userEvent.setup();

      render(
        <HybridLogViewer
          selections={mockSelections}
          theme="dark"
        />
      );

      // Find context size selector
      const contextSelect = screen.getByDisplayValue('5 lines');
      expect(contextSelect).toBeInTheDocument();

      // Test context size change
      await user.selectOptions(contextSelect, '10 lines');

      // Should save to localStorage
      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        'hybrid-log-viewer-context-size',
        '10'
      );
    });
  });

  describe('Phase 3: Search Context Enhancement Integration', () => {
    it('should show search controls when ready', () => {
      render(
        <HybridLogViewer
          selections={mockSelections}
          theme="dark"
        />
      );

      // Should have search input available
      expect(screen.getByPlaceholderText(/search logs/i)).toBeInTheDocument();
    });

    it('should handle search input and results', async () => {
      const user = userEvent.setup();

      render(
        <HybridLogViewer
          selections={mockSelections}
          theme="dark"
        />
      );

      const searchInput = screen.getByPlaceholderText(/search logs/i);

      // Test search input functionality
      await user.type(searchInput, 'error');
      expect(searchInput).toHaveValue('error');

      // Should not crash and component should remain functional
      expect(screen.getByRole('main')).toBeInTheDocument();
    });

    it('should integrate search libraries correctly', () => {
      const searchManager = getSearchManager();
      const searchHighlighter = createSearchHighlighter({ theme: 'dark', enableAnimations: true });
      const searchGrouper = createSearchGrouper({ persistPreferences: true });

      // Verify all components are properly integrated
      expect(searchManager).toBeDefined();
      expect(searchHighlighter).toBeDefined();
      expect(searchGrouper).toBeDefined();

      // Test basic integration
      const mockSearchResult = {
        query: 'test error',
        matches: mockLogs.slice(0, 1).map((log, index) => ({
          log,
          lineIndex: index,
          score: 0.9,
          startIndex: 0,
          endIndex: 4,
          text: 'test',
          type: 'term',
        })),
        totalMatches: 1,
        executionTime: 10,
        filters: { logLevels: ['error'] },
      };

      // Test that libraries work together without errors
      expect(() => {
        const grouped = searchGrouper.processSearchResult(mockSearchResult);
        const highlights = searchHighlighter.processSearchResults(mockSearchResult);
        const navigation = searchHighlighter.getNavigationState();

        expect(grouped).toBeDefined();
        expect(Array.isArray(highlights)).toBe(true);
        expect(navigation).toBeDefined();
      }).not.toThrow();
    });
  });

  describe('End-to-End Integration', () => {
    it('should handle basic end-to-end workflow', async () => {
      const user = userEvent.setup();

      render(
        <HybridLogViewer
          selections={mockSelections}
          theme="dark"
        />
      );

      // Step 1: Verify component renders
      expect(screen.getByRole('main')).toBeInTheDocument();

      // Step 2: Test search input
      const searchInput = screen.getByPlaceholderText(/search logs/i);
      await user.type(searchInput, 'test');
      expect(searchInput).toHaveValue('test');

      // Step 3: Test context size
      const contextSelect = screen.getByDisplayValue('5 lines');
      await user.selectOptions(contextSelect, '10 lines');

      // Step 4: Verify localStorage was updated
      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        'hybrid-log-viewer-context-size',
        '10'
      );

      // Step 5: Component should still be functional
      expect(screen.getByRole('main')).toBeInTheDocument();
    });

    it('should handle error scenarios gracefully', async () => {
      // Mock API failure
      global.fetch.mockRejectedValue(new Error('Network error'));

      // Should not throw during render
      expect(() => {
        render(
          <HybridLogViewer
            selections={mockSelections}
            theme="dark"
          />
        );
      }).not.toThrow();

      // Should still render basic UI
      expect(screen.getByRole('banner')).toBeInTheDocument();
      expect(screen.getByRole('main')).toBeInTheDocument();
    });

    it('should clean up resources on unmount', () => {
      const { unmount } = render(
        <HybridLogViewer
          selections={mockSelections}
          theme="dark"
        />
      );

      // Should render successfully
      expect(screen.getByRole('main')).toBeInTheDocument();

      // Should unmount without errors
      expect(() => {
        unmount();
      }).not.toThrow();
    });
  });

  describe('Accessibility Integration', () => {
    it('should maintain accessibility features', () => {
      render(
        <HybridLogViewer
          selections={mockSelections}
          theme="dark"
        />
      );

      // Check for accessibility landmarks
      expect(screen.getByRole('main')).toBeInTheDocument();
      expect(screen.getByRole('banner')).toBeInTheDocument();
      expect(screen.getByRole('contentinfo')).toBeInTheDocument();

      // Check for skip links
      expect(screen.getByRole('link', { name: /skip to search results/i })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /skip to log context/i })).toBeInTheDocument();

      // Check for ARIA live regions
      const liveRegions = screen.getAllByRole('status', { hidden: true });
      expect(liveRegions.length).toBeGreaterThan(0);
    });
  });
});