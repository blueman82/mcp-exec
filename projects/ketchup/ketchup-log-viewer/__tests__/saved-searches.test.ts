/**
 * Tests for SavedSearchManager
 *
 * This test suite covers:
 * - CRUD operations for searches and folders
 * - Usage tracking and analytics
 * - Tag management
 * - Import/export functionality
 * - Search and filtering
 * - Statistics
 */

import { SavedSearchManager } from '../lib/saved-searches';
import type {
  SavedSearchWithMetadata,
  SearchFolder,
  SearchFilters,
  SearchPreferences,
  SavedSearchCollection,
} from '../types/search';

describe('SavedSearchManager', () => {
  let manager: SavedSearchManager;

  beforeEach(() => {
    // Create a fresh instance for each test
    manager = new SavedSearchManager();
  });

  afterEach(() => {
    // Clean up after each test
    manager.clearAll();
  });

  // ========================================================================
  // SEARCH CRUD OPERATIONS
  // ========================================================================

  describe('Search CRUD Operations', () => {
    test('should create a new saved search', () => {
      const search = manager.createSearch(
        'Test Search',
        'error',
        { logLevels: ['error'] },
        {
          mode: 'text',
          caseSensitive: false,
          useRegex: false,
          includeTimestamps: true,
          maxResults: 100,
          highlightMatches: true,
        }
      );

      expect(search).toBeDefined();
      expect(search.id).toBeTruthy();
      expect(search.name).toBe('Test Search');
      expect(search.query).toBe('error');
      expect(search.usageCount).toBe(0);
      expect(search.isFavorite).toBe(false);
    });

    test('should create search with optional parameters', () => {
      const search = manager.createSearch(
        'Tagged Search',
        'warning',
        { logLevels: ['warn'] },
        {
          mode: 'text',
          caseSensitive: false,
          useRegex: false,
          includeTimestamps: true,
          maxResults: 100,
          highlightMatches: true,
        },
        {
          description: 'Find all warnings',
          tags: ['production', 'monitoring'],
          color: '#ff0000',
        }
      );

      expect(search.description).toBe('Find all warnings');
      expect(search.tags).toEqual(['production', 'monitoring']);
      expect(search.color).toBe('#ff0000');
    });

    test('should retrieve a saved search by ID', () => {
      const created = manager.createSearch(
        'Test',
        'test',
        {},
        {
          mode: 'text',
          caseSensitive: false,
          useRegex: false,
          includeTimestamps: true,
          maxResults: 100,
          highlightMatches: true,
        }
      );

      const retrieved = manager.getSearch(created.id);
      expect(retrieved).toEqual(created);
    });

    test('should return undefined for non-existent search', () => {
      const result = manager.getSearch('non-existent-id');
      expect(result).toBeUndefined();
    });

    test('should get all saved searches', () => {
      manager.createSearch('Search 1', 'query1', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });
      manager.createSearch('Search 2', 'query2', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });

      const all = manager.getAllSearches();
      expect(all).toHaveLength(2);
    });

    test('should update a saved search', () => {
      const search = manager.createSearch('Original', 'query', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });

      const updated = manager.updateSearch(search.id, {
        name: 'Updated Name',
        description: 'New description',
      });

      expect(updated).toBeDefined();
      expect(updated!.name).toBe('Updated Name');
      expect(updated!.description).toBe('New description');
    });

    test('should return null when updating non-existent search', () => {
      const result = manager.updateSearch('non-existent', { name: 'Test' });
      expect(result).toBeNull();
    });

    test('should delete a saved search', () => {
      const search = manager.createSearch('To Delete', 'query', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });

      const deleted = manager.deleteSearch(search.id);
      expect(deleted).toBe(true);
      expect(manager.getSearch(search.id)).toBeUndefined();
    });

    test('should return false when deleting non-existent search', () => {
      const result = manager.deleteSearch('non-existent');
      expect(result).toBe(false);
    });

    test('should bulk delete multiple searches', () => {
      const search1 = manager.createSearch('Search 1', 'q1', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });
      const search2 = manager.createSearch('Search 2', 'q2', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });
      const search3 = manager.createSearch('Search 3', 'q3', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });

      const count = manager.deleteSearches([search1.id, search2.id, 'non-existent']);
      expect(count).toBe(2);
      expect(manager.getAllSearches()).toHaveLength(1);
    });
  });

  // ========================================================================
  // FOLDER OPERATIONS
  // ========================================================================

  describe('Folder Operations', () => {
    test('should create a new folder', () => {
      const folder = manager.createFolder('My Folder');

      expect(folder).toBeDefined();
      expect(folder.id).toBeTruthy();
      expect(folder.name).toBe('My Folder');
      expect(folder.parentId).toBeNull();
      expect(folder.searchCount).toBe(0);
      expect(folder.isExpanded).toBe(true);
    });

    test('should create folder with parent', () => {
      const parent = manager.createFolder('Parent');
      const child = manager.createFolder('Child', { parentId: parent.id });

      expect(child.parentId).toBe(parent.id);
    });

    test('should create folder with options', () => {
      const folder = manager.createFolder('Colored Folder', {
        color: '#00ff00',
        icon: '📁',
      });

      expect(folder.color).toBe('#00ff00');
      expect(folder.icon).toBe('📁');
    });

    test('should retrieve a folder by ID', () => {
      const created = manager.createFolder('Test Folder');
      const retrieved = manager.getFolder(created.id);

      expect(retrieved).toEqual(created);
    });

    test('should get all folders', () => {
      manager.createFolder('Folder 1');
      manager.createFolder('Folder 2');

      const all = manager.getAllFolders();
      expect(all).toHaveLength(2);
    });

    test('should update a folder', () => {
      const folder = manager.createFolder('Original');
      const updated = manager.updateFolder(folder.id, {
        name: 'Updated',
        color: '#ff0000',
      });

      expect(updated).toBeDefined();
      expect(updated!.name).toBe('Updated');
      expect(updated!.color).toBe('#ff0000');
      expect(updated!.modifiedAt).toBeInstanceOf(Date);
    });

    test('should delete a folder', () => {
      const folder = manager.createFolder('To Delete');
      const deleted = manager.deleteFolder(folder.id);

      expect(deleted).toBe(true);
      expect(manager.getFolder(folder.id)).toBeUndefined();
    });

    test('should delete folder and its searches', () => {
      const folder = manager.createFolder('Folder');
      const search = manager.createSearch('Search', 'query', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      }, { folderId: folder.id });

      manager.deleteFolder(folder.id);

      expect(manager.getFolder(folder.id)).toBeUndefined();
      expect(manager.getSearch(search.id)).toBeUndefined();
    });

    test('should delete folder and move searches to another folder', () => {
      const folder1 = manager.createFolder('Folder 1');
      const folder2 = manager.createFolder('Folder 2');
      const search = manager.createSearch('Search', 'query', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      }, { folderId: folder1.id });

      manager.deleteFolder(folder1.id, folder2.id);

      expect(manager.getFolder(folder1.id)).toBeUndefined();
      const movedSearch = manager.getSearch(search.id);
      expect(movedSearch).toBeDefined();
      expect(movedSearch!.folderId).toBe(folder2.id);
    });

    test('should get searches in a folder', () => {
      const folder = manager.createFolder('Folder');
      manager.createSearch('Search 1', 'q1', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      }, { folderId: folder.id });
      manager.createSearch('Search 2', 'q2', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      }, { folderId: folder.id });
      manager.createSearch('Search 3', 'q3', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });

      const searches = manager.getSearchesInFolder(folder.id);
      expect(searches).toHaveLength(2);
    });

    test('should get root searches (no folder)', () => {
      const folder = manager.createFolder('Folder');
      manager.createSearch('Root Search', 'q1', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });
      manager.createSearch('Folder Search', 'q2', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      }, { folderId: folder.id });

      const rootSearches = manager.getSearchesInFolder(null);
      expect(rootSearches).toHaveLength(1);
    });

    test('should get child folders', () => {
      const parent = manager.createFolder('Parent');
      manager.createFolder('Child 1', { parentId: parent.id });
      manager.createFolder('Child 2', { parentId: parent.id });
      manager.createFolder('Root Folder');

      const children = manager.getChildFolders(parent.id);
      expect(children).toHaveLength(2);
    });
  });

  // ========================================================================
  // USAGE TRACKING
  // ========================================================================

  describe('Usage Tracking', () => {
    test('should record search usage', () => {
      const search = manager.createSearch('Test', 'query', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });

      manager.recordUsage(search.id, 42, 150);

      const updated = manager.getSearch(search.id);
      expect(updated!.usageCount).toBe(1);
      expect(updated!.lastUsed).toBeDefined();
      expect(updated!.stats?.avgExecutionTime).toBe(150);
      expect(updated!.stats?.avgResultCount).toBe(42);
      expect(updated!.stats?.lastResultCount).toBe(42);
    });

    test('should calculate running averages for usage stats', () => {
      const search = manager.createSearch('Test', 'query', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });

      manager.recordUsage(search.id, 100, 100);
      manager.recordUsage(search.id, 200, 200);
      manager.recordUsage(search.id, 300, 300);

      const updated = manager.getSearch(search.id);
      expect(updated!.usageCount).toBe(3);
      expect(updated!.stats?.avgExecutionTime).toBe(200);
      expect(updated!.stats?.avgResultCount).toBe(200);
      expect(updated!.stats?.lastResultCount).toBe(300);
    });

    test('should toggle favorite status', () => {
      const search = manager.createSearch('Test', 'query', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });

      let result = manager.toggleFavorite(search.id);
      expect(result).toBe(true);

      result = manager.toggleFavorite(search.id);
      expect(result).toBe(false);
    });

    test('should return null when toggling favorite for non-existent search', () => {
      const result = manager.toggleFavorite('non-existent');
      expect(result).toBeNull();
    });

    test('should get favorite searches', () => {
      const search1 = manager.createSearch('Fav 1', 'q1', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });
      const search2 = manager.createSearch('Fav 2', 'q2', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });
      const search3 = manager.createSearch('Not Fav', 'q3', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });

      manager.toggleFavorite(search1.id);
      manager.toggleFavorite(search2.id);

      const favorites = manager.getFavorites();
      expect(favorites).toHaveLength(2);
    });

    test('should get recently used searches', () => {
      const search1 = manager.createSearch('Recent 1', 'q1', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });
      const search2 = manager.createSearch('Recent 2', 'q2', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });
      const search3 = manager.createSearch('Not Used', 'q3', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });

      manager.recordUsage(search1.id);
      manager.recordUsage(search2.id);

      const recent = manager.getRecentlyUsed();
      expect(recent).toHaveLength(2);
      // Both searches should be in the recently used list
      const ids = recent.map(s => s.id);
      expect(ids).toContain(search1.id);
      expect(ids).toContain(search2.id);
    });

    test('should limit recently used searches', () => {
      for (let i = 0; i < 15; i++) {
        const search = manager.createSearch(`Search ${i}`, `query${i}`, {}, {
          mode: 'text',
          caseSensitive: false,
          useRegex: false,
          includeTimestamps: true,
          maxResults: 100,
          highlightMatches: true,
        });
        manager.recordUsage(search.id);
      }

      const recent = manager.getRecentlyUsed(5);
      expect(recent).toHaveLength(5);
    });

    test('should get most used searches', () => {
      const search1 = manager.createSearch('Popular', 'q1', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });
      const search2 = manager.createSearch('Less Popular', 'q2', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });

      manager.recordUsage(search1.id);
      manager.recordUsage(search1.id);
      manager.recordUsage(search1.id);
      manager.recordUsage(search2.id);

      const mostUsed = manager.getMostUsed();
      expect(mostUsed[0].id).toBe(search1.id);
      expect(mostUsed[0].usageCount).toBe(3);
    });
  });

  // ========================================================================
  // TAG MANAGEMENT
  // ========================================================================

  describe('Tag Management', () => {
    test('should get all unique tags', () => {
      manager.createSearch('Search 1', 'q1', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      }, { tags: ['production', 'error'] });
      manager.createSearch('Search 2', 'q2', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      }, { tags: ['development', 'error'] });

      const tags = manager.getAllTags();
      expect(tags).toHaveLength(3);
      expect(tags).toContain('production');
      expect(tags).toContain('development');
      expect(tags).toContain('error');
      expect(tags).toEqual(expect.arrayContaining(['development', 'error', 'production'])); // Sorted
    });

    test('should get searches by tags', () => {
      manager.createSearch('Prod Error', 'q1', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      }, { tags: ['production', 'error'] });
      manager.createSearch('Dev Error', 'q2', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      }, { tags: ['development', 'error'] });
      manager.createSearch('Prod Info', 'q3', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      }, { tags: ['production', 'info'] });

      const errorSearches = manager.getSearchesByTags(['error']);
      expect(errorSearches).toHaveLength(2);

      const prodSearches = manager.getSearchesByTags(['production']);
      expect(prodSearches).toHaveLength(2);
    });

    test('should add tags to a search', () => {
      const search = manager.createSearch('Test', 'query', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      }, { tags: ['initial'] });

      manager.addTags(search.id, ['new', 'tags']);

      const updated = manager.getSearch(search.id);
      expect(updated!.tags).toContain('initial');
      expect(updated!.tags).toContain('new');
      expect(updated!.tags).toContain('tags');
    });

    test('should not add duplicate tags', () => {
      const search = manager.createSearch('Test', 'query', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      }, { tags: ['tag1'] });

      manager.addTags(search.id, ['tag1', 'tag2']);

      const updated = manager.getSearch(search.id);
      expect(updated!.tags).toHaveLength(2);
    });

    test('should remove tags from a search', () => {
      const search = manager.createSearch('Test', 'query', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      }, { tags: ['tag1', 'tag2', 'tag3'] });

      manager.removeTags(search.id, ['tag2']);

      const updated = manager.getSearch(search.id);
      expect(updated!.tags).toHaveLength(2);
      expect(updated!.tags).not.toContain('tag2');
    });
  });

  // ========================================================================
  // SEARCH AND FILTER
  // ========================================================================

  describe('Search and Filter', () => {
    test('should search saved searches by name', () => {
      manager.createSearch('Error Logs', 'error', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });
      manager.createSearch('Warning Logs', 'warning', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });

      const results = manager.searchSavedSearches('error');
      expect(results).toHaveLength(1);
      expect(results[0].name).toBe('Error Logs');
    });

    test('should search by query text', () => {
      manager.createSearch('Critical Issues', 'critical AND failure', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });
      manager.createSearch('All Errors', 'error', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });

      const results = manager.searchSavedSearches('failure');
      expect(results).toHaveLength(1);
    });

    test('should search by description', () => {
      manager.createSearch('Test', 'query', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      }, { description: 'Find production errors' });

      const results = manager.searchSavedSearches('production');
      expect(results).toHaveLength(1);
    });

    test('should search by tags', () => {
      manager.createSearch('Test', 'query', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      }, { tags: ['monitoring', 'alerts'] });

      const results = manager.searchSavedSearches('monitoring');
      expect(results).toHaveLength(1);
    });

    test('should filter searches by folder', () => {
      const folder = manager.createFolder('Test Folder');
      manager.createSearch('In Folder', 'q1', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      }, { folderId: folder.id });
      manager.createSearch('Root Search', 'q2', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });

      const results = manager.filterSearches({ folderId: folder.id });
      expect(results).toHaveLength(1);
      expect(results[0].name).toBe('In Folder');
    });

    test('should filter by favorite status', () => {
      const search1 = manager.createSearch('Favorite', 'q1', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });
      manager.createSearch('Not Favorite', 'q2', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });

      manager.toggleFavorite(search1.id);

      const results = manager.filterSearches({ isFavorite: true });
      expect(results).toHaveLength(1);
    });

    test('should filter by multiple criteria', () => {
      const folder = manager.createFolder('Folder');
      const search1 = manager.createSearch('Match', 'query1', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      }, { folderId: folder.id, tags: ['prod'] });
      manager.createSearch('No Match', 'query2', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      }, { tags: ['dev'] });

      const results = manager.filterSearches({
        folderId: folder.id,
        tags: ['prod'],
      });

      expect(results).toHaveLength(1);
      expect(results[0].id).toBe(search1.id);
    });

    test('should sort searches by name ascending', () => {
      manager.createSearch('Charlie', 'q1', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });
      manager.createSearch('Alice', 'q2', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });
      manager.createSearch('Bob', 'q3', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });

      const sorted = manager.sortSearches(manager.getAllSearches(), 'name', 'asc');
      expect(sorted[0].name).toBe('Alice');
      expect(sorted[1].name).toBe('Bob');
      expect(sorted[2].name).toBe('Charlie');
    });

    test('should sort searches by usage count descending', () => {
      const s1 = manager.createSearch('Low', 'q1', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });
      const s2 = manager.createSearch('High', 'q2', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });

      manager.recordUsage(s1.id);
      manager.recordUsage(s2.id);
      manager.recordUsage(s2.id);
      manager.recordUsage(s2.id);

      const sorted = manager.sortSearches(manager.getAllSearches(), 'usageCount', 'desc');
      expect(sorted[0].name).toBe('High');
    });
  });

  // ========================================================================
  // STATISTICS
  // ========================================================================

  describe('Statistics', () => {
    test('should calculate comprehensive stats', () => {
      const folder1 = manager.createFolder('Folder 1');
      const folder2 = manager.createFolder('Folder 2');

      const s1 = manager.createSearch('Search 1', 'q1', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      }, { tags: ['tag1', 'tag2'] });
      const s2 = manager.createSearch('Search 2', 'q2', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      }, { tags: ['tag3'] });

      manager.toggleFavorite(s1.id);
      manager.recordUsage(s1.id);
      manager.recordUsage(s2.id);
      manager.recordUsage(s2.id);

      const stats = manager.getStats();
      expect(stats.totalSearches).toBe(2);
      expect(stats.totalFolders).toBe(2);
      expect(stats.totalTags).toBe(3);
      expect(stats.favorites).toHaveLength(1);
      expect(stats.recentlyUsed).toHaveLength(2);
      expect(stats.mostUsed?.search.id).toBe(s2.id);
      expect(stats.totalUsageCount).toBe(3);
      expect(stats.storageUsage).toBeGreaterThan(0);
    });

    test('should handle empty stats', () => {
      const stats = manager.getStats();
      expect(stats.totalSearches).toBe(0);
      expect(stats.totalFolders).toBe(0);
      expect(stats.totalTags).toBe(0);
      expect(stats.mostUsed).toBeUndefined();
      expect(stats.favorites).toHaveLength(0);
      expect(stats.recentlyUsed).toHaveLength(0);
    });
  });

  // ========================================================================
  // IMPORT/EXPORT
  // ========================================================================

  describe('Import/Export', () => {
    test('should export collection', () => {
      const folder = manager.createFolder('Test Folder');
      const search = manager.createSearch('Test Search', 'query', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      }, { folderId: folder.id });

      const collection = manager.exportCollection({
        name: 'My Collection',
        author: 'Test User',
      });

      expect(collection.version).toBe('1.0.0');
      expect(collection.folders).toHaveLength(1);
      expect(collection.searches).toHaveLength(1);
      expect(collection.metadata?.name).toBe('My Collection');
      expect(collection.metadata?.author).toBe('Test User');
    });

    test('should export to JSON string', () => {
      manager.createSearch('Test', 'query', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });

      const json = manager.exportToJson();
      expect(json).toBeTruthy();
      expect(() => JSON.parse(json)).not.toThrow();
    });

    test('should import collection', () => {
      const originalManager = new SavedSearchManager();
      const folder = originalManager.createFolder('Folder');
      originalManager.createSearch('Search', 'query', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      }, { folderId: folder.id });

      const collection = originalManager.exportCollection();

      const newManager = new SavedSearchManager();
      const result = newManager.importCollection(collection);

      expect(result.imported).toBe(2); // 1 folder + 1 search
      expect(result.skipped).toBe(0);
      expect(result.errors).toHaveLength(0);
      expect(newManager.getAllFolders()).toHaveLength(1);
      expect(newManager.getAllSearches()).toHaveLength(1);
    });

    test('should handle merge during import', () => {
      const folder = manager.createFolder('Existing');
      const search = manager.createSearch('Existing', 'query', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });

      const collection: SavedSearchCollection = {
        version: '1.0.0',
        exportedAt: new Date(),
        folders: [folder],
        searches: [search, {
          ...search,
          id: 'new-id',
          name: 'New Search',
        }],
      };

      const result = manager.importCollection(collection, { merge: true });
      expect(result.imported).toBe(1); // Only new search
      expect(result.skipped).toBe(2); // Existing folder and search
    });

    test('should handle overwrite during import', () => {
      const search = manager.createSearch('Original', 'query', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });

      const updatedSearch = { ...search, name: 'Updated' };
      const collection: SavedSearchCollection = {
        version: '1.0.0',
        exportedAt: new Date(),
        folders: [],
        searches: [updatedSearch],
      };

      manager.importCollection(collection, { merge: true, overwrite: true });

      const result = manager.getSearch(search.id);
      expect(result?.name).toBe('Updated');
    });

    test('should import from JSON string', () => {
      const originalManager = new SavedSearchManager();
      originalManager.createSearch('Test', 'query', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });

      const json = originalManager.exportToJson();

      const newManager = new SavedSearchManager();
      const result = newManager.importFromJson(json);

      expect(result.imported).toBeGreaterThan(0);
      expect(result.errors).toHaveLength(0);
    });

    test('should handle invalid JSON during import', () => {
      const result = manager.importFromJson('invalid json');
      expect(result.imported).toBe(0);
      expect(result.errors.length).toBeGreaterThan(0);
    });
  });

  // ========================================================================
  // STATE MANAGEMENT
  // ========================================================================

  describe('State Management', () => {
    test('should get current state', () => {
      manager.createFolder('Folder');
      manager.createSearch('Search', 'query', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });

      const state = manager.getState();
      expect(state.folders).toHaveLength(1);
      expect(state.searches).toHaveLength(1);
    });

    test('should update state', () => {
      manager.updateState({
        sortBy: 'name',
        sortDirection: 'asc',
        viewMode: 'grid',
      });

      const state = manager.getState();
      expect(state.sortBy).toBe('name');
      expect(state.sortDirection).toBe('asc');
      expect(state.viewMode).toBe('grid');
    });

    test('should clear all data', () => {
      manager.createFolder('Folder');
      manager.createSearch('Search', 'query', {}, {
        mode: 'text',
        caseSensitive: false,
        useRegex: false,
        includeTimestamps: true,
        maxResults: 100,
        highlightMatches: true,
      });

      manager.clearAll();

      expect(manager.getAllFolders()).toHaveLength(0);
      expect(manager.getAllSearches()).toHaveLength(0);
    });
  });
});
