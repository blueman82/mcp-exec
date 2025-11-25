/**
 * Saved Search Manager - Persistent saved searches with usage tracking, folders, and analytics
 *
 * This module provides comprehensive management for saved searches including:
 * - CRUD operations for searches and folders
 * - Usage tracking and analytics
 * - Import/export functionality
 * - Tag management
 * - Search organization with folders
 */

import type {
  SavedSearch,
  SearchFolder,
  SavedSearchWithMetadata,
  SavedSearchCollection,
  SavedSearchStats,
  SavedSearchManagerState,
  SearchFilters,
  SearchPreferences,
} from '../types/search';

/**
 * Storage key for localStorage persistence
 */
const STORAGE_KEYS = {
  SEARCHES: 'ketchup-saved-searches',
  FOLDERS: 'ketchup-search-folders',
  STATE: 'ketchup-search-manager-state',
} as const;

/**
 * Default search preferences
 */
const DEFAULT_PREFERENCES: SearchPreferences = {
  mode: 'text',
  caseSensitive: false,
  useRegex: false,
  includeTimestamps: true,
  maxResults: 100,
  highlightMatches: true,
  debounceDelay: 300,
  enableSuggestions: true,
  exportFormat: 'json',
};

/**
 * SavedSearchManager - Manages saved searches, folders, and analytics
 *
 * Features:
 * - Persistent storage using localStorage
 * - Folder-based organization
 * - Tag management
 * - Usage tracking
 * - Import/export
 * - Full CRUD operations
 */
export class SavedSearchManager {
  private searches: Map<string, SavedSearchWithMetadata>;
  private folders: Map<string, SearchFolder>;
  private state: SavedSearchManagerState;
  private isTestEnvironment: boolean;

  constructor() {
    this.searches = new Map();
    this.folders = new Map();
    this.state = this.getDefaultState();
    this.isTestEnvironment = this.detectTestEnvironment();
    this.loadFromStorage();
  }

  /**
   * Detect if running in a test environment
   */
  private detectTestEnvironment(): boolean {
    // Check for common test environment indicators
    if (typeof window === 'undefined') return true;
    if (typeof process !== 'undefined' && process.env?.NODE_ENV === 'test') return true;
    if (typeof global !== 'undefined' && (global as any).test !== undefined) return true;
    return false;
  }

  /**
   * Get default state for the manager
   */
  private getDefaultState(): SavedSearchManagerState {
    return {
      folders: [],
      searches: [],
      selectedFolderId: null,
      selectedSearchId: null,
      searchFilter: '',
      tagFilter: [],
      sortBy: 'lastUsed',
      sortDirection: 'desc',
      viewMode: 'list',
    };
  }

  /**
   * Load searches and folders from localStorage
   */
  private loadFromStorage(): void {
    if (this.isTestEnvironment || typeof window === 'undefined' || typeof localStorage === 'undefined') {
      return;
    }

    try {
      // Load searches
      const searchesJson = localStorage.getItem(STORAGE_KEYS.SEARCHES);
      if (searchesJson) {
        const searches: SavedSearchWithMetadata[] = JSON.parse(searchesJson);
        searches.forEach(search => {
          // Convert date strings back to Date objects
          search.createdAt = new Date(search.createdAt);
          if (search.lastUsed) {
            search.lastUsed = new Date(search.lastUsed);
          }
          this.searches.set(search.id, search);
        });
      }

      // Load folders
      const foldersJson = localStorage.getItem(STORAGE_KEYS.FOLDERS);
      if (foldersJson) {
        const folders: SearchFolder[] = JSON.parse(foldersJson);
        folders.forEach(folder => {
          // Convert date strings back to Date objects
          folder.createdAt = new Date(folder.createdAt);
          folder.modifiedAt = new Date(folder.modifiedAt);
          this.folders.set(folder.id, folder);
        });
      }

      // Load state
      const stateJson = localStorage.getItem(STORAGE_KEYS.STATE);
      if (stateJson) {
        this.state = JSON.parse(stateJson);
      }
    } catch (error) {
      console.error('Failed to load saved searches from storage:', error);
    }
  }

  /**
   * Save searches and folders to localStorage
   */
  private saveToStorage(): void {
    if (this.isTestEnvironment || typeof window === 'undefined' || typeof localStorage === 'undefined') {
      return;
    }

    try {
      // Save searches
      const searches = Array.from(this.searches.values());
      localStorage.setItem(STORAGE_KEYS.SEARCHES, JSON.stringify(searches));

      // Save folders
      const folders = Array.from(this.folders.values());
      localStorage.setItem(STORAGE_KEYS.FOLDERS, JSON.stringify(folders));

      // Save state
      localStorage.setItem(STORAGE_KEYS.STATE, JSON.stringify(this.state));
    } catch (error) {
      console.error('Failed to save searches to storage:', error);
    }
  }

  /**
   * Generate a unique ID
   */
  private generateId(): string {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  // ========================================================================
  // SEARCH CRUD OPERATIONS
  // ========================================================================

  /**
   * Create a new saved search
   */
  createSearch(
    name: string,
    query: string,
    filters: SearchFilters,
    preferences: SearchPreferences = DEFAULT_PREFERENCES,
    options?: {
      description?: string;
      tags?: string[];
      folderId?: string;
      color?: string;
    }
  ): SavedSearchWithMetadata {
    const search: SavedSearchWithMetadata = {
      id: this.generateId(),
      name,
      query,
      filters,
      preferences,
      createdAt: new Date(),
      usageCount: 0,
      isFavorite: false,
      description: options?.description,
      tags: options?.tags || [],
      folderId: options?.folderId,
      color: options?.color,
    };

    this.searches.set(search.id, search);
    this.saveToStorage();
    return search;
  }

  /**
   * Get a saved search by ID
   */
  getSearch(id: string): SavedSearchWithMetadata | undefined {
    return this.searches.get(id);
  }

  /**
   * Get all saved searches
   */
  getAllSearches(): SavedSearchWithMetadata[] {
    return Array.from(this.searches.values());
  }

  /**
   * Update a saved search
   */
  updateSearch(id: string, updates: Partial<SavedSearchWithMetadata>): SavedSearchWithMetadata | null {
    const search = this.searches.get(id);
    if (!search) return null;

    const updated = { ...search, ...updates };
    this.searches.set(id, updated);
    this.saveToStorage();
    return updated;
  }

  /**
   * Delete a saved search
   */
  deleteSearch(id: string): boolean {
    const deleted = this.searches.delete(id);
    if (deleted) {
      this.saveToStorage();
    }
    return deleted;
  }

  /**
   * Bulk delete saved searches
   */
  deleteSearches(ids: string[]): number {
    let count = 0;
    ids.forEach(id => {
      if (this.searches.delete(id)) {
        count++;
      }
    });
    if (count > 0) {
      this.saveToStorage();
    }
    return count;
  }

  // ========================================================================
  // FOLDER OPERATIONS
  // ========================================================================

  /**
   * Create a new folder
   */
  createFolder(
    name: string,
    options?: {
      parentId?: string | null;
      color?: string;
      icon?: string;
    }
  ): SearchFolder {
    const folder: SearchFolder = {
      id: this.generateId(),
      name,
      parentId: options?.parentId || null,
      color: options?.color,
      icon: options?.icon,
      createdAt: new Date(),
      modifiedAt: new Date(),
      searchCount: 0,
      isExpanded: true,
    };

    this.folders.set(folder.id, folder);
    this.updateFolderSearchCounts();
    this.saveToStorage();
    return folder;
  }

  /**
   * Get a folder by ID
   */
  getFolder(id: string): SearchFolder | undefined {
    return this.folders.get(id);
  }

  /**
   * Get all folders
   */
  getAllFolders(): SearchFolder[] {
    return Array.from(this.folders.values());
  }

  /**
   * Update a folder
   */
  updateFolder(id: string, updates: Partial<SearchFolder>): SearchFolder | null {
    const folder = this.folders.get(id);
    if (!folder) return null;

    const updated = {
      ...folder,
      ...updates,
      modifiedAt: new Date(),
    };
    this.folders.set(id, updated);
    this.saveToStorage();
    return updated;
  }

  /**
   * Delete a folder and optionally move its searches
   */
  deleteFolder(id: string, moveSearchesToFolderId?: string | null): boolean {
    const folder = this.folders.get(id);
    if (!folder) return false;

    // Move or remove searches in this folder
    const searchesInFolder = this.getSearchesInFolder(id);
    searchesInFolder.forEach(search => {
      if (moveSearchesToFolderId !== undefined) {
        this.updateSearch(search.id, { folderId: moveSearchesToFolderId });
      } else {
        this.deleteSearch(search.id);
      }
    });

    // Delete child folders recursively
    const childFolders = this.getChildFolders(id);
    childFolders.forEach(childFolder => {
      this.deleteFolder(childFolder.id, moveSearchesToFolderId);
    });

    const deleted = this.folders.delete(id);
    if (deleted) {
      this.updateFolderSearchCounts();
      this.saveToStorage();
    }
    return deleted;
  }

  /**
   * Get searches in a specific folder
   */
  getSearchesInFolder(folderId: string | null): SavedSearchWithMetadata[] {
    return this.getAllSearches().filter(search => {
      // Treat undefined folderId as null (root folder)
      const searchFolder = search.folderId || null;
      return searchFolder === folderId;
    });
  }

  /**
   * Get child folders of a folder
   */
  getChildFolders(parentId: string | null): SearchFolder[] {
    return this.getAllFolders().filter(folder => folder.parentId === parentId);
  }

  /**
   * Update search counts for all folders
   */
  private updateFolderSearchCounts(): void {
    this.folders.forEach(folder => {
      folder.searchCount = this.getSearchesInFolder(folder.id).length;
    });
  }

  // ========================================================================
  // USAGE TRACKING
  // ========================================================================

  /**
   * Record usage of a saved search
   */
  recordUsage(id: string, resultCount?: number, executionTime?: number): void {
    const search = this.searches.get(id);
    if (!search) return;

    search.usageCount++;
    search.lastUsed = new Date();

    // Update statistics
    if (!search.stats) {
      search.stats = {
        avgExecutionTime: executionTime || 0,
        avgResultCount: resultCount || 0,
        lastResultCount: resultCount,
      };
    } else {
      // Calculate running average
      const totalExecutions = search.usageCount;
      if (executionTime !== undefined) {
        search.stats.avgExecutionTime =
          (search.stats.avgExecutionTime * (totalExecutions - 1) + executionTime) / totalExecutions;
      }
      if (resultCount !== undefined) {
        search.stats.avgResultCount =
          (search.stats.avgResultCount * (totalExecutions - 1) + resultCount) / totalExecutions;
        search.stats.lastResultCount = resultCount;
      }
    }

    this.searches.set(id, search);
    this.saveToStorage();
  }

  /**
   * Toggle favorite status of a search
   */
  toggleFavorite(id: string): boolean | null {
    const search = this.searches.get(id);
    if (!search) return null;

    search.isFavorite = !search.isFavorite;
    this.searches.set(id, search);
    this.saveToStorage();
    return search.isFavorite;
  }

  /**
   * Get favorite searches
   */
  getFavorites(): SavedSearchWithMetadata[] {
    return this.getAllSearches().filter(search => search.isFavorite);
  }

  /**
   * Get recently used searches
   */
  getRecentlyUsed(limit: number = 10): SavedSearchWithMetadata[] {
    return this.getAllSearches()
      .filter(search => search.lastUsed)
      .sort((a, b) => {
        if (!a.lastUsed || !b.lastUsed) return 0;
        return b.lastUsed.getTime() - a.lastUsed.getTime();
      })
      .slice(0, limit);
  }

  /**
   * Get most used searches
   */
  getMostUsed(limit: number = 10): SavedSearchWithMetadata[] {
    return this.getAllSearches()
      .sort((a, b) => b.usageCount - a.usageCount)
      .slice(0, limit);
  }

  // ========================================================================
  // TAG MANAGEMENT
  // ========================================================================

  /**
   * Get all unique tags
   */
  getAllTags(): string[] {
    const tags = new Set<string>();
    this.searches.forEach(search => {
      search.tags?.forEach(tag => tags.add(tag));
    });
    return Array.from(tags).sort();
  }

  /**
   * Get searches with specific tags
   */
  getSearchesByTags(tags: string[]): SavedSearchWithMetadata[] {
    return this.getAllSearches().filter(search => {
      if (!search.tags || search.tags.length === 0) return false;
      return tags.some(tag => search.tags!.includes(tag));
    });
  }

  /**
   * Add tags to a search
   */
  addTags(id: string, tags: string[]): SavedSearchWithMetadata | null {
    const search = this.searches.get(id);
    if (!search) return null;

    const existingTags = search.tags || [];
    search.tags = Array.from(new Set([...existingTags, ...tags]));
    this.searches.set(id, search);
    this.saveToStorage();
    return search;
  }

  /**
   * Remove tags from a search
   */
  removeTags(id: string, tags: string[]): SavedSearchWithMetadata | null {
    const search = this.searches.get(id);
    if (!search) return null;

    search.tags = (search.tags || []).filter(tag => !tags.includes(tag));
    this.searches.set(id, search);
    this.saveToStorage();
    return search;
  }

  // ========================================================================
  // SEARCH AND FILTER
  // ========================================================================

  /**
   * Search saved searches by name or query
   */
  searchSavedSearches(searchTerm: string): SavedSearchWithMetadata[] {
    const term = searchTerm.toLowerCase();
    return this.getAllSearches().filter(search => {
      return (
        search.name.toLowerCase().includes(term) ||
        search.query.toLowerCase().includes(term) ||
        search.description?.toLowerCase().includes(term) ||
        search.tags?.some(tag => tag.toLowerCase().includes(term))
      );
    });
  }

  /**
   * Filter searches by multiple criteria
   */
  filterSearches(criteria: {
    folderId?: string | null;
    tags?: string[];
    isFavorite?: boolean;
    query?: string;
  }): SavedSearchWithMetadata[] {
    let results = this.getAllSearches();

    if (criteria.folderId !== undefined) {
      results = results.filter(search => search.folderId === criteria.folderId);
    }

    if (criteria.tags && criteria.tags.length > 0) {
      results = results.filter(search => {
        if (!search.tags || search.tags.length === 0) return false;
        return criteria.tags!.some(tag => search.tags!.includes(tag));
      });
    }

    if (criteria.isFavorite !== undefined) {
      results = results.filter(search => search.isFavorite === criteria.isFavorite);
    }

    if (criteria.query) {
      const term = criteria.query.toLowerCase();
      results = results.filter(search => {
        return (
          search.name.toLowerCase().includes(term) ||
          search.query.toLowerCase().includes(term) ||
          search.description?.toLowerCase().includes(term)
        );
      });
    }

    return results;
  }

  /**
   * Sort searches by specified criteria
   */
  sortSearches(
    searches: SavedSearchWithMetadata[],
    sortBy: 'name' | 'lastUsed' | 'usageCount' | 'createdAt',
    direction: 'asc' | 'desc' = 'asc'
  ): SavedSearchWithMetadata[] {
    const sorted = [...searches].sort((a, b) => {
      let comparison = 0;

      switch (sortBy) {
        case 'name':
          comparison = a.name.localeCompare(b.name);
          break;
        case 'lastUsed':
          if (!a.lastUsed && !b.lastUsed) comparison = 0;
          else if (!a.lastUsed) comparison = 1;
          else if (!b.lastUsed) comparison = -1;
          else comparison = a.lastUsed.getTime() - b.lastUsed.getTime();
          break;
        case 'usageCount':
          comparison = a.usageCount - b.usageCount;
          break;
        case 'createdAt':
          comparison = a.createdAt.getTime() - b.createdAt.getTime();
          break;
      }

      return direction === 'asc' ? comparison : -comparison;
    });

    return sorted;
  }

  // ========================================================================
  // STATISTICS
  // ========================================================================

  /**
   * Get comprehensive statistics about saved searches
   */
  getStats(): SavedSearchStats {
    const allSearches = this.getAllSearches();
    const favorites = allSearches.filter(s => s.isFavorite);
    const recentlyUsed = this.getRecentlyUsed(10);
    const mostUsed = this.getMostUsed(1);

    // Calculate storage usage (rough estimate)
    const storageUsage = new Blob([JSON.stringify({
      searches: allSearches,
      folders: this.getAllFolders(),
    })]).size;

    return {
      totalSearches: allSearches.length,
      totalFolders: this.folders.size,
      totalTags: this.getAllTags().length,
      mostUsed: mostUsed.length > 0
        ? { search: mostUsed[0], usageCount: mostUsed[0].usageCount }
        : undefined,
      recentlyUsed,
      favorites,
      totalUsageCount: allSearches.reduce((sum, s) => sum + s.usageCount, 0),
      storageUsage,
    };
  }

  // ========================================================================
  // IMPORT/EXPORT
  // ========================================================================

  /**
   * Export all saved searches and folders
   */
  exportCollection(metadata?: {
    name?: string;
    description?: string;
    author?: string;
  }): SavedSearchCollection {
    return {
      version: '1.0.0',
      exportedAt: new Date(),
      folders: this.getAllFolders(),
      searches: this.getAllSearches(),
      metadata,
    };
  }

  /**
   * Export as JSON string
   */
  exportToJson(metadata?: {
    name?: string;
    description?: string;
    author?: string;
  }): string {
    return JSON.stringify(this.exportCollection(metadata), null, 2);
  }

  /**
   * Import a collection
   */
  importCollection(collection: SavedSearchCollection, options?: {
    merge?: boolean;
    overwrite?: boolean;
  }): {
    imported: number;
    skipped: number;
    errors: string[];
  } {
    const errors: string[] = [];
    let imported = 0;
    let skipped = 0;

    const merge = options?.merge ?? true;
    const overwrite = options?.overwrite ?? false;

    try {
      // Import folders
      collection.folders.forEach(folder => {
        // Convert date strings to Date objects
        folder.createdAt = new Date(folder.createdAt);
        folder.modifiedAt = new Date(folder.modifiedAt);

        const exists = this.folders.has(folder.id);
        if (exists && !overwrite && merge) {
          skipped++;
          return;
        }

        this.folders.set(folder.id, folder);
        if (!exists) imported++;
      });

      // Import searches
      collection.searches.forEach(search => {
        // Convert date strings to Date objects
        search.createdAt = new Date(search.createdAt);
        if (search.lastUsed) {
          search.lastUsed = new Date(search.lastUsed);
        }

        const exists = this.searches.has(search.id);
        if (exists && !overwrite && merge) {
          skipped++;
          return;
        }

        this.searches.set(search.id, search);
        if (!exists) imported++;
      });

      this.updateFolderSearchCounts();
      this.saveToStorage();
    } catch (error) {
      errors.push(`Import failed: ${error instanceof Error ? error.message : String(error)}`);
    }

    return { imported, skipped, errors };
  }

  /**
   * Import from JSON string
   */
  importFromJson(json: string, options?: {
    merge?: boolean;
    overwrite?: boolean;
  }): {
    imported: number;
    skipped: number;
    errors: string[];
  } {
    try {
      const collection: SavedSearchCollection = JSON.parse(json);
      return this.importCollection(collection, options);
    } catch (error) {
      return {
        imported: 0,
        skipped: 0,
        errors: [`Failed to parse JSON: ${error instanceof Error ? error.message : String(error)}`],
      };
    }
  }

  // ========================================================================
  // STATE MANAGEMENT
  // ========================================================================

  /**
   * Get current manager state
   */
  getState(): SavedSearchManagerState {
    // Update state with current data
    this.state.folders = this.getAllFolders();
    this.state.searches = this.getAllSearches();
    return this.state;
  }

  /**
   * Update manager state
   */
  updateState(updates: Partial<SavedSearchManagerState>): void {
    this.state = { ...this.state, ...updates };
    this.saveToStorage();
  }

  /**
   * Clear all saved searches and folders
   */
  clearAll(): void {
    this.searches.clear();
    this.folders.clear();
    this.state = this.getDefaultState();
    this.saveToStorage();
  }
}

/**
 * Singleton instance
 */
let instance: SavedSearchManager | null = null;

/**
 * Get the singleton instance of SavedSearchManager
 */
export function getSavedSearchManager(): SavedSearchManager {
  if (!instance) {
    instance = new SavedSearchManager();
  }
  return instance;
}
