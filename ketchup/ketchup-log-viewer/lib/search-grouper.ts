/**
 * Search Grouper - Result grouping and sorting for better user experience
 *
 * Features:
 * - Multiple grouping options (container, server, log level, time, relevance)
 * - Multiple sorting options (relevance, time, level, alphabetical)
 * - User preference persistence
 * - Performance optimized for large datasets
 * - TypeScript strict mode compliance
 */

import type { SearchResult, SearchMatch, LogLevel, ServerType } from '@/types/search';
import type { LogLine } from '@/types';

/**
 * Grouping options for search results
 */
export type GroupingOption =
  | 'container'
  | 'server'
  | 'logLevel'
  | 'time'
  | 'relevance'
  | 'none';

/**
 * Sorting options for search results
 */
export type SortingOption =
  | 'relevance'
  | 'mostRecent'
  | 'leastRecent'
  | 'logLevelPriority'
  | 'alphabetical'
  | 'score';

/**
 * Time grouping granularity
 */
export type TimeGrouping = 'minute' | 'hour' | 'day' | 'week' | 'month';

/**
 * Grouping configuration
 */
export interface GroupingConfig {
  /** Grouping option */
  groupBy: GroupingOption;
  /** Time grouping granularity (when groupBy is 'time') */
  timeGrouping?: TimeGrouping;
  /** Whether to sort groups */
  sortGroups?: boolean;
  /** Maximum number of groups to prevent performance issues */
  maxGroups?: number;
}

/**
 * Sorting configuration
 */
export interface SortingConfig {
  /** Primary sorting option */
  sortBy: SortingOption;
  /** Secondary sorting option */
  thenBy?: SortingOption;
  /** Sort direction */
  direction: 'asc' | 'desc';
  /** Whether to sort within groups */
  sortWithinGroups?: boolean;
}

/**
 * User preferences for grouping and sorting
 */
export interface GroupingPreferences {
  /** Default grouping configuration */
  grouping: GroupingConfig;
  /** Default sorting configuration */
  sorting: SortingConfig;
  /** Whether to remember preferences */
  persistPreferences?: boolean;
}

/**
 * Group information
 */
export interface GroupInfo {
  /** Unique group identifier */
  id: string;
  /** Human-readable group name */
  name: string;
  /** Group type */
  type: GroupingOption;
  /** Group value */
  value: string;
  /** Number of items in this group */
  count: number;
  /** Group metadata */
  metadata?: {
    /** Highest score in group */
    maxScore?: number;
    /** Average score in group */
    avgScore?: number;
    /** Time range of group */
    timeRange?: {
      start: Date;
      end: Date;
    };
    /** Log levels present in group */
    logLevels?: LogLevel[];
    /** Servers present in group */
    servers?: ServerType[];
  };
}

/**
 * Grouped search results
 */
export interface GroupedSearchResults {
  /** Original search result */
  originalResult: SearchResult;
  /** Groups */
  groups: Map<string, GroupInfo>;
  /** Grouped matches */
  groupedMatches: Map<string, SearchMatch[]>;
  /** Flattened sorted matches */
  sortedMatches: SearchMatch[];
  /** Configuration used */
  config: {
    grouping: GroupingConfig;
    sorting: SortingConfig;
  };
}

/**
 * Search Grouper Class
 */
export class SearchGrouper {
  private preferences: GroupingPreferences;
  private readonly PREFERENCES_KEY = 'search-grouper-preferences';

  constructor(preferences?: Partial<GroupingPreferences>) {
    this.preferences = {
      grouping: {
        groupBy: 'container',
        maxGroups: 100,
        sortGroups: true,
      },
      sorting: {
        sortBy: 'relevance',
        direction: 'desc',
        sortWithinGroups: true,
      },
      persistPreferences: true,
      ...preferences,
    };

    this.loadPreferences();
  }

  /**
   * Load user preferences from localStorage
   */
  private loadPreferences(): void {
    if (!this.preferences.persistPreferences) return;

    try {
      const saved = localStorage.getItem(this.PREFERENCES_KEY);
      if (saved) {
        const savedPrefs = JSON.parse(saved);
        this.preferences = { ...this.preferences, ...savedPrefs };
      }
    } catch (error) {
      console.warn('Failed to load grouping preferences:', error);
    }
  }

  /**
   * Save user preferences to localStorage
   */
  private savePreferences(): void {
    if (!this.preferences.persistPreferences) return;

    try {
      localStorage.setItem(this.PREFERENCES_KEY, JSON.stringify(this.preferences));
    } catch (error) {
      console.warn('Failed to save grouping preferences:', error);
    }
  }

  /**
   * Generate group key for a match based on grouping configuration
   */
  private generateGroupKey(match: SearchMatch, groupBy: GroupingOption): string {
    const log = match.log;

    switch (groupBy) {
      case 'container':
        return log.container || 'unknown';

      case 'server':
        return log.server || 'unknown';

      case 'logLevel':
        return log.level || 'none';

      case 'time':
        return this.getTimeGroupKey(new Date(log.timestamp), this.preferences.grouping.timeGrouping);

      case 'relevance':
        return this.getRelevanceGroupKey(match.score);

      case 'none':
        return 'all';

      default:
        return 'unknown';
    }
  }

  /**
   * Generate time-based group key
   */
  private getTimeGroupKey(date: Date, granularity?: TimeGrouping): string {
    const g = granularity || 'hour';

    switch (g) {
      case 'minute':
        return date.toISOString().slice(0, 16); // YYYY-MM-DDTHH:MM
      case 'hour':
        return date.toISOString().slice(0, 13); // YYYY-MM-DDTHH
      case 'day':
        return date.toISOString().slice(0, 10); // YYYY-MM-DD
      case 'week':
        const weekStart = new Date(date);
        weekStart.setDate(date.getDate() - date.getDay());
        return weekStart.toISOString().slice(0, 10);
      case 'month':
        return date.toISOString().slice(0, 7); // YYYY-MM
      default:
        return date.toISOString().slice(0, 13);
    }
  }

  /**
   * Generate relevance-based group key
   */
  private getRelevanceGroupKey(score: number): string {
    if (score >= 150) return 'very-high';
    if (score >= 100) return 'high';
    if (score >= 50) return 'medium';
    if (score >= 25) return 'low';
    return 'very-low';
  }

  /**
   * Create group information
   */
  private createGroupInfo(
    id: string,
    matches: SearchMatch[],
    groupBy: GroupingOption
  ): GroupInfo {
    const name = this.getGroupDisplayName(id, groupBy);
    const count = matches.length;

    // Calculate group metadata
    const scores = matches.map(m => m.score);
    const maxScore = Math.max(...scores);
    const avgScore = scores.reduce((sum, score) => sum + score, 0) / scores.length;

    // Get time range
    const timestamps = matches.map(m => new Date(m.log.timestamp));
    const minTime = new Date(Math.min(...timestamps.map(t => t.getTime())));
    const maxTime = new Date(Math.max(...timestamps.map(t => t.getTime())));

    // Get unique log levels and servers
    const logLevels = [...new Set(matches.map(m => m.log.level).filter(Boolean))] as LogLevel[];
    const servers = [...new Set(matches.map(m => m.log.server).filter(Boolean))] as ServerType[];

    return {
      id,
      name,
      type: groupBy,
      value: id,
      count,
      metadata: {
        maxScore,
        avgScore: Math.round(avgScore * 100) / 100,
        timeRange: { start: minTime, end: maxTime },
        logLevels,
        servers,
      },
    };
  }

  /**
   * Get human-readable group display name
   */
  private getGroupDisplayName(groupId: string, groupBy: GroupingOption): string {
    switch (groupBy) {
      case 'container':
        return groupId.replace('ketchup-', '').replace(/-/g, ' ');
      case 'server':
        return groupId.toUpperCase();
      case 'logLevel':
        return groupId.toUpperCase();
      case 'time':
        return this.formatTimeGroupName(groupId);
      case 'relevance':
        return groupId.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
      case 'none':
        return 'All Results';
      default:
        return groupId;
    }
  }

  /**
   * Format time group name based on ISO string prefix
   */
  private formatTimeGroupName(groupId: string): string {
    try {
      // Handle different ISO string prefix formats
      let dateStr = groupId;
      
      // Complete incomplete ISO strings for proper Date parsing
      if (groupId.match(/^\d{4}-\d{2}-\d{2}T\d{2}$/)) {
        // Hour format: YYYY-MM-DDTHH -> YYYY-MM-DDTHH:00:00Z
        dateStr = `${groupId}:00:00Z`;
      } else if (groupId.match(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/)) {
        // Minute format: YYYY-MM-DDTHH:MM -> YYYY-MM-DDTHH:MM:00Z
        dateStr = `${groupId}:00Z`;
      } else if (groupId.match(/^\d{4}-\d{2}-\d{2}$/)) {
        // Day format: YYYY-MM-DD -> YYYY-MM-DDT00:00:00Z
        dateStr = `${groupId}T00:00:00Z`;
      } else if (groupId.match(/^\d{4}-\d{2}$/)) {
        // Month format: YYYY-MM -> YYYY-MM-01T00:00:00Z
        dateStr = `${groupId}-01T00:00:00Z`;
      } else {
        // Try to parse as-is
        dateStr = groupId;
      }

      const date = new Date(dateStr);
      
      // Check if date is valid
      if (isNaN(date.getTime())) {
        return groupId; // Fallback to raw groupId if date parsing fails
      }

      const granularity = this.preferences.grouping.timeGrouping || 'hour';
      
      // Format based on granularity
      switch (granularity) {
        case 'minute':
          return date.toLocaleString(undefined, {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
          });
        case 'hour':
          return date.toLocaleString(undefined, {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
          });
        case 'day':
          return date.toLocaleDateString(undefined, {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
          });
        case 'week':
          const endOfWeek = new Date(date);
          endOfWeek.setDate(date.getDate() + 6);
          return `${date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} - ${endOfWeek.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}`;
        case 'month':
          return date.toLocaleDateString(undefined, {
            month: 'long',
            year: 'numeric',
          });
        default:
          return date.toLocaleString();
      }
    } catch (error) {
      console.error('Error formatting time group name:', error, 'groupId:', groupId);
      return groupId; // Fallback to raw groupId on error
    }
  }

  /**
   * Sort matches based on configuration
   */
  private sortMatches(matches: SearchMatch[], config: SortingConfig): SearchMatch[] {
    const { sortBy, direction, thenBy } = config;

    const sorted = [...matches].sort((a, b) => {
      let comparison = 0;

      switch (sortBy) {
        case 'relevance':
        case 'score':
          comparison = b.score - a.score;
          break;

        case 'mostRecent':
          comparison = new Date(b.log.timestamp).getTime() - new Date(a.log.timestamp).getTime();
          break;

        case 'leastRecent':
          comparison = new Date(a.log.timestamp).getTime() - new Date(b.log.timestamp).getTime();
          break;

        case 'logLevelPriority':
          comparison = this.getLogLevelPriority(b.log.level) - this.getLogLevelPriority(a.log.level);
          break;

        case 'alphabetical':
          comparison = (a.log.content || '').localeCompare(b.log.content || '');
          break;

        default:
          comparison = 0;
      }

      // Apply direction
      if (direction === 'asc') {
        comparison = -comparison;
      }

      // Use secondary sort if primary sort results in tie
      if (comparison === 0 && thenBy && thenBy !== sortBy) {
        const secondaryConfig = { ...config, sortBy: thenBy, thenBy: undefined };
        comparison = this.sortMatches([a, b], secondaryConfig)[0] === a ? -1 : 1;
      }

      return comparison;
    });

    return sorted;
  }

  /**
   * Get priority value for log level sorting
   */
  private getLogLevelPriority(level?: LogLevel): number {
    const priorities: Record<LogLevel, number> = {
      error: 5,
      warn: 4,
      info: 3,
      debug: 2,
      trace: 1,
      none: 0,
    };

    return priorities[level || 'none'];
  }

  /**
   * Sort groups based on configuration
   */
  private sortGroups(groups: Map<string, GroupInfo>): Map<string, GroupInfo> {
    const { sortBy, direction } = this.preferences.sorting;

    const sortedGroups = Array.from(groups.entries()).sort(([, a], [, b]) => {
      let comparison = 0;

      switch (sortBy) {
        case 'relevance':
        case 'score':
          comparison = (b.metadata?.maxScore || 0) - (a.metadata?.maxScore || 0);
          break;

        case 'mostRecent':
          comparison = (b.metadata?.timeRange?.start.getTime() || 0) - (a.metadata?.timeRange?.start.getTime() || 0);
          break;

        case 'leastRecent':
          comparison = (a.metadata?.timeRange?.start.getTime() || 0) - (b.metadata?.timeRange?.start.getTime() || 0);
          break;

        case 'logLevelPriority':
          const aMaxLevel = this.getHighestLogLevelPriority(a.metadata?.logLevels || []);
          const bMaxLevel = this.getHighestLogLevelPriority(b.metadata?.logLevels || []);
          comparison = bMaxLevel - aMaxLevel;
          break;

        case 'alphabetical':
          comparison = a.name.localeCompare(b.name);
          break;

        default:
          comparison = b.count - a.count; // Default: sort by count
      }

      return direction === 'asc' ? -comparison : comparison;
    });

    const sortedMap = new Map<string, GroupInfo>();
    for (const [key, group] of sortedGroups) {
      sortedMap.set(key, group);
    }

    return sortedMap;
  }

  /**
   * Get highest log level priority from an array of levels
   */
  private getHighestLogLevelPriority(levels: LogLevel[]): number {
    return Math.max(...levels.map(level => this.getLogLevelPriority(level)));
  }

  /**
   * Group and sort search results
   */
  public processSearchResult(searchResult: SearchResult): GroupedSearchResults {
    const { grouping, sorting } = this.preferences;
    const groups = new Map<string, GroupInfo>();
    const groupedMatches = new Map<string, SearchMatch[]>();

    // Group matches
    for (const match of searchResult.matches) {
      const groupKey = this.generateGroupKey(match, grouping.groupBy);

      if (!groupedMatches.has(groupKey)) {
        groupedMatches.set(groupKey, []);
      }

      groupedMatches.get(groupKey)!.push(match);

      // Enforce max groups limit
      if (groupedMatches.size > (grouping.maxGroups || 100)) {
        console.warn(`Maximum groups limit (${grouping.maxGroups}) reached`);
        break;
      }
    }

    // Create group info
    for (const [groupKey, matches] of groupedMatches.entries()) {
      const groupInfo = this.createGroupInfo(groupKey, matches, grouping.groupBy);
      groups.set(groupKey, groupInfo);

      // Sort matches within group if configured
      if (sorting.sortWithinGroups) {
        const sortedMatches = this.sortMatches(matches, sorting);
        groupedMatches.set(groupKey, sortedMatches);
      }
    }

    // Sort groups if configured
    if (grouping.sortGroups) {
      const sortedGroups = this.sortGroups(groups);
      groups.clear();
      for (const [key, group] of sortedGroups.entries()) {
        groups.set(key, group);
      }
    }

    // Create flattened sorted matches
    const sortedMatches: SearchMatch[] = [];
    for (const [, matches] of groupedMatches.entries()) {
      sortedMatches.push(...matches);
    }

    // If no grouping, just sort all matches
    if (grouping.groupBy === 'none') {
      const allSorted = this.sortMatches(searchResult.matches, sorting);
      return {
        originalResult: searchResult,
        groups: new Map(),
        groupedMatches: new Map(),
        sortedMatches: allSorted,
        config: { grouping, sorting },
      };
    }

    return {
      originalResult: searchResult,
      groups,
      groupedMatches,
      sortedMatches,
      config: { grouping, sorting },
    };
  }

  /**
   * Update grouping configuration
   */
  public updateGroupingConfig(config: Partial<GroupingConfig>): void {
    this.preferences.grouping = { ...this.preferences.grouping, ...config };
    this.savePreferences();
  }

  /**
   * Update sorting configuration
   */
  public updateSortingConfig(config: Partial<SortingConfig>): void {
    this.preferences.sorting = { ...this.preferences.sorting, ...config };
    this.savePreferences();
  }

  /**
   * Get current preferences
   */
  public getPreferences(): GroupingPreferences {
    return { ...this.preferences };
  }

  /**
   * Set preferences
   */
  public setPreferences(preferences: Partial<GroupingPreferences>): void {
    this.preferences = { ...this.preferences, ...preferences };
    this.savePreferences();
  }

  /**
   * Reset preferences to defaults
   */
  public resetPreferences(): void {
    this.preferences = {
      grouping: {
        groupBy: 'container',
        maxGroups: 100,
        sortGroups: true,
      },
      sorting: {
        sortBy: 'relevance',
        direction: 'desc',
        sortWithinGroups: true,
      },
      persistPreferences: true,
    };
    this.savePreferences();
  }

  /**
   * Get available grouping options
   */
  public static getAvailableGroupingOptions(): Array<{
    value: GroupingOption;
    label: string;
    description: string;
  }> {
    return [
      {
        value: 'container',
        label: 'Container',
        description: 'Group results by container name',
      },
      {
        value: 'server',
        label: 'Server',
        description: 'Group results by server (prod1/prod2)',
      },
      {
        value: 'logLevel',
        label: 'Log Level',
        description: 'Group results by log level (error/warn/info/debug)',
      },
      {
        value: 'time',
        label: 'Time',
        description: 'Group results by time period',
      },
      {
        value: 'relevance',
        label: 'Relevance',
        description: 'Group results by relevance score',
      },
      {
        value: 'none',
        label: 'No Grouping',
        description: 'Show all results in a single list',
      },
    ];
  }

  /**
   * Get available sorting options
   */
  public static getAvailableSortingOptions(): Array<{
    value: SortingOption;
    label: string;
    description: string;
  }> {
    return [
      {
        value: 'relevance',
        label: 'Relevance',
        description: 'Sort by relevance score (most relevant first)',
      },
      {
        value: 'mostRecent',
        label: 'Most Recent',
        description: 'Sort by timestamp (newest first)',
      },
      {
        value: 'leastRecent',
        label: 'Least Recent',
        description: 'Sort by timestamp (oldest first)',
      },
      {
        value: 'logLevelPriority',
        label: 'Log Level Priority',
        description: 'Sort by log level importance (error → debug)',
      },
      {
        value: 'alphabetical',
        label: 'Alphabetical',
        description: 'Sort by log content alphabetically',
      },
      {
        value: 'score',
        label: 'Score',
        description: 'Sort by match score (highest first)',
      },
    ];
  }

  /**
   * Get available time grouping options
   */
  public static getAvailableTimeGroupingOptions(): Array<{
    value: TimeGrouping;
    label: string;
    description: string;
  }> {
    return [
      {
        value: 'minute',
        label: 'Minute',
        description: 'Group by minute',
      },
      {
        value: 'hour',
        label: 'Hour',
        description: 'Group by hour',
      },
      {
        value: 'day',
        label: 'Day',
        description: 'Group by day',
      },
      {
        value: 'week',
        label: 'Week',
        description: 'Group by week',
      },
      {
        value: 'month',
        label: 'Month',
        description: 'Group by month',
      },
    ];
  }
}

/**
 * Utility function to create a search grouper instance
 */
export function createSearchGrouper(preferences?: Partial<GroupingPreferences>): SearchGrouper {
  return new SearchGrouper(preferences);
}

/**
 * Utility function for one-time grouping and sorting
 */
export function groupAndSortSearchResults(
  searchResult: SearchResult,
  groupingConfig?: Partial<GroupingConfig>,
  sortingConfig?: Partial<SortingConfig>
): GroupedSearchResults {
  const grouper = new SearchGrouper({
    grouping: {
      groupBy: 'container',
      maxGroups: 100,
      sortGroups: true,
      ...groupingConfig,
    },
    sorting: {
      sortBy: 'relevance',
      direction: 'desc',
      sortWithinGroups: true,
      ...sortingConfig,
    },
    persistPreferences: false,
  });

  return grouper.processSearchResult(searchResult);
}