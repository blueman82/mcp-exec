import type { LogLine } from '@/types';
import type {
  SearchFilters,
  SearchMatch,
  SearchMode,
  SearchOptimizerOptions,
  SearchPreferences,
  SearchProgressEvent,
  SearchResult,
  SearchResultPage,
  SearchResultPagination,
} from '@/types/search';

interface SearchExecutionInputs {
  logs: LogLine[];
  query: string;
  filters: SearchFilters;
  preferences: SearchPreferences;
  searchMode: SearchMode;
  maxResults: number;
}

interface SearchExecutionMetrics {
  executionTime: number;
  logsProcessed: number;
  matchesFound: number;
  chunkCount: number;
  chunkSize: number;
}

const DEFAULT_CHUNK_SIZE = 500;
const DEFAULT_PAGE_SIZE = 200;
const MAX_RESULTS_LIMIT = 10_000;
const CONTEXT_RADIUS = 50;

function now(): number {
  if (typeof performance !== 'undefined' && typeof performance.now === 'function') {
    return performance.now();
  }
  return Date.now();
}

function normalizeTime(value?: Date | string | number | null): number | undefined {
  if (!value) {
    return undefined;
  }
  const time = value instanceof Date ? value.getTime() : new Date(value).getTime();
  return Number.isFinite(time) ? time : undefined;
}

function passesFilters(log: LogLine, filters: SearchFilters): boolean {
  if (filters.logLevels?.length && (!log.level || !filters.logLevels.includes(log.level))) {
    return false;
  }

  if (filters.servers?.length && (!log.server || !filters.servers.includes(log.server as any))) {
    return false;
  }

  if (filters.containers?.length && (!log.container || !filters.containers.includes(log.container))) {
    return false;
  }

  if (filters.timeRange) {
    const logTime = new Date(log.timestamp).getTime();
    const startTime = normalizeTime(filters.timeRange.start);
    const endTime = normalizeTime(filters.timeRange.end);

    if (startTime !== undefined && logTime < startTime) {
      return false;
    }

    if (endTime !== undefined && logTime >= endTime) {
      return false;
    }
  }

  if (filters.customFilters) {
    for (const predicate of filters.customFilters) {
      try {
        if (!predicate(log)) {
          return false;
        }
      } catch (error) {
        console.error('[SearchOptimizer] custom filter error:', error);
        return false;
      }
    }
  }

  return true;
}

function calculateScore(content: string, query: string, matchIndex: number): number {
  if (matchIndex < 0) {
    return 0;
  }

  let score = 100 - matchIndex * 0.1;

  if (query) {
    try {
      const escaped = query.replace(/[.*+?^$()|[\]\\]/g, '\\$&');
      if (new RegExp(`\\b${escaped}\\b`, 'i').test(content)) {
        score += 50;
      }
    } catch (error) {
      // ignore invalid regex construction and keep base score
    }

    const occurrences = (content.toLowerCase().match(new RegExp(query.toLowerCase(), 'g')) || []).length;
    score += occurrences * 10;
  }

  return Math.max(0, score);
}

function extractContext(log: LogLine, matchStart: number, matchLength: number): string {
  const rawContent = typeof log.content === 'string' ? log.content : '';

  if (!rawContent) {
    return '';
  }

  const start = Math.max(0, matchStart - CONTEXT_RADIUS);
  const end = Math.min(rawContent.length, matchStart + matchLength + CONTEXT_RADIUS);

  let context = rawContent.slice(start, end);

  if (start > 0) {
    context = `...${context}`;
  }

  if (end < rawContent.length) {
    context = `${context}...`;
  }

  return context;
}

function paginate(matches: SearchMatch[], pageSize: number): { pages: SearchResultPage[]; pagination: SearchResultPagination } {
  if (pageSize <= 0) {
    return {
      pages: [],
      pagination: {
        pageSize: matches.length,
        currentPage: 0,
        totalPages: matches.length > 0 ? 1 : 0,
      },
    };
  }

  const pages: SearchResultPage[] = [];

  for (let offset = 0; offset < matches.length; offset += pageSize) {
    const slice = matches.slice(offset, offset + pageSize);
    pages.push({
      index: pages.length,
      matches: slice,
      hasMore: offset + pageSize < matches.length,
    });
  }

  return {
    pages,
    pagination: {
      pageSize,
      currentPage: 0,
      totalPages: pages.length,
    },
  };
}

function buildProgressSnapshot(totalLogs: number, logsProcessed: number, chunksProcessed: number, chunkSize: number, elapsedMs: number) {
  const totalChunks = Math.ceil(totalLogs / chunkSize) || 1;
  const ratio = totalLogs === 0 ? 1 : Math.min(1, logsProcessed / totalLogs);
  const estimatedRemainingMs = ratio > 0 && ratio < 1 ? Math.max(0, (elapsedMs / ratio) - elapsedMs) : 0;

  return {
    completion: Math.round(ratio * 100),
    chunksProcessed,
    totalChunks,
    estimatedRemainingMs,
  };
}

function createMatchFromText(
  log: LogLine,
  index: number,
  content: string,
  normalizedQuery: string,
  originalQuery: string,
  chunkStartIndex: number
): SearchMatch | null {
  if (!normalizedQuery) {
    return {
      lineIndex: chunkStartIndex + index,
      log,
      matchStart: 0,
      matchEnd: 0,
      score: 100,
      context: extractContext(log, 0, 0),
    };
  }

  const matchIndex = content.indexOf(normalizedQuery);
  if (matchIndex === -1) {
    return null;
  }

  return {
    lineIndex: chunkStartIndex + index,
    log,
    matchStart: matchIndex,
    matchEnd: matchIndex + originalQuery.length,
    score: calculateScore(content, normalizedQuery, matchIndex),
    context: extractContext(log, matchIndex, originalQuery.length),
  };
}

function createMatchFromRegex(
  log: LogLine,
  index: number,
  regex: RegExp,
  content: string,
  chunkStartIndex: number
): SearchMatch | null {
  regex.lastIndex = 0;
  const match = regex.exec(content);
  if (!match) {
    return null;
  }

  return {
    lineIndex: chunkStartIndex + index,
    log,
    matchStart: match.index,
    matchEnd: match.index + match[0].length,
    score: calculateScore(content, match[0], match.index),
    context: extractContext(log, match.index, match[0].length),
    groups: match.slice(1),
    namedGroups: match.groups ?? undefined,
  };
}

function processChunk(
  chunk: LogLine[],
  offset: number,
  inputs: SearchExecutionInputs,
  normalizedQuery: string,
  originalQuery: string,
  regex: RegExp | null,
  maxResultsRemaining: number
): SearchMatch[] {
  const matches: SearchMatch[] = [];

  for (let index = 0; index < chunk.length; index += 1) {
    if (matches.length >= maxResultsRemaining) {
      break;
    }

    const log = chunk[index];
    if (!log.content || !passesFilters(log, inputs.filters)) {
      continue;
    }

    const sourceContent = inputs.preferences.includeTimestamps
      ? `${log.timestamp || ''} ${log.content}`
      : log.content;

    const content = inputs.preferences.caseSensitive ? sourceContent : sourceContent.toLowerCase();

    let match: SearchMatch | null = null;

    if (inputs.searchMode === 'regex' && regex) {
      match = createMatchFromRegex(log, index, regex, content, offset);
    } else {
      match = createMatchFromText(log, index, content, normalizedQuery, originalQuery, offset);
    }

    if (match) {
      matches.push(match);
    }
  }

  return matches;
}

function buildResult(
  inputs: SearchExecutionInputs,
  matches: SearchMatch[],
  logsProcessed: number,
  chunkCount: number,
  chunkSize: number,
  pageSize: number,
  processedAllLogs: boolean,
  executionTime: number,
  isPartial: boolean,
  elapsedMs: number,
  maxResults: number
): { result: SearchResult; pages: SearchResultPage[] } {
  const limitedMatches = matches.slice(0, maxResults);
  const { pages, pagination } = paginate(limitedMatches, pageSize);
  const progress = buildProgressSnapshot(inputs.logs.length, logsProcessed, chunkCount, chunkSize, elapsedMs);
  const hasMore = !processedAllLogs || matches.length > limitedMatches.length;

  const result: SearchResult = {
    query: inputs.query,
    matches: limitedMatches,
    totalMatches: limitedMatches.length,
    executionTime,
    filters: inputs.filters,
    searchMode: inputs.searchMode,
    hasMore,
    metrics: {
      logsProcessed,
      fromCache: false,
      filterApplications: logsProcessed,
      chunkCount,
      chunkSize,
    },
    pagination,
    pages,
    isPartial,
    progress,
  };

  return { result, pages };
}

export interface SearchOptimizerResult {
  result: SearchResult;
  pages: SearchResultPage[];
  metrics: SearchExecutionMetrics;
}

export class SearchOptimizer {
  private static instance: SearchOptimizer | null = null;

  static getInstance(): SearchOptimizer {
    if (!SearchOptimizer.instance) {
      SearchOptimizer.instance = new SearchOptimizer();
    }
    return SearchOptimizer.instance;
  }

  async execute(inputs: SearchExecutionInputs, options: SearchOptimizerOptions = {}): Promise<SearchOptimizerResult> {
    const chunkSize = Math.max(10, options.chunkSize ?? DEFAULT_CHUNK_SIZE);
    const pageSize = Math.max(1, options.pageSize ?? DEFAULT_PAGE_SIZE);
    const maxResults = Math.max(1, Math.min(inputs.maxResults, MAX_RESULTS_LIMIT));
    const startTime = now();

    let logsProcessed = 0;
    let chunkIndex = 0;
    const matches: SearchMatch[] = [];

    const normalizedQuery = inputs.preferences.caseSensitive ? inputs.query : inputs.query.toLowerCase();

    let regex: RegExp | null = null;
    if (inputs.searchMode === 'regex' && inputs.query) {
      try {
        regex = new RegExp(inputs.query, inputs.preferences.caseSensitive ? 'g' : 'gi');
      } catch (error) {
        console.error('[SearchOptimizer] invalid regex provided, falling back to text search', error);
      }
    }

    const totalChunks = Math.ceil(inputs.logs.length / chunkSize) || 1;

    const startEvent: SearchProgressEvent = {
      type: 'start',
      processedLogs: 0,
      totalLogs: inputs.logs.length,
      matchesFound: 0,
      chunkIndex: 0,
      totalChunks,
    };
    options.onProgress?.(startEvent);

    let aborted = options.abortSignal?.aborted ?? false;

    for (let offset = 0; offset < inputs.logs.length; offset += chunkSize) {
      if (options.abortSignal?.aborted) {
        aborted = true;
        break;
      }

      const chunk = inputs.logs.slice(offset, offset + chunkSize);
      const remaining = maxResults - matches.length;
      if (remaining <= 0) {
        break;
      }

      const chunkMatches = processChunk(chunk, offset, inputs, normalizedQuery, inputs.query, regex, remaining);
      matches.push(...chunkMatches);
      logsProcessed += chunk.length;
      chunkIndex += 1;

      const elapsed = now() - startTime;
      const { result: partialResult } = buildResult(
        inputs,
        matches,
        Math.min(logsProcessed, inputs.logs.length),
        chunkIndex,
        chunkSize,
        pageSize,
        false,
        elapsed,
        true,
        elapsed,
        maxResults
      );

      const progressEvent: SearchProgressEvent = {
        type: 'chunk',
        processedLogs: Math.min(logsProcessed, inputs.logs.length),
        totalLogs: inputs.logs.length,
        matchesFound: partialResult.totalMatches,
        chunkIndex,
        totalChunks,
        partialResult,
        page: partialResult.pagination
          ? {
              index: partialResult.pagination.currentPage,
              matches: partialResult.matches,
              hasMore: partialResult.hasMore,
            }
          : undefined,
      };

      options.onProgress?.(progressEvent);
    }

    const processedAllLogs = !aborted && logsProcessed >= inputs.logs.length;
    const finalElapsed = now() - startTime;
    const { result, pages } = buildResult(
      inputs,
      matches,
      Math.min(logsProcessed, inputs.logs.length),
      chunkIndex,
      chunkSize,
      pageSize,
      processedAllLogs,
      finalElapsed,
      false,
      finalElapsed,
      maxResults
    );

    const completionEvent: SearchProgressEvent = {
      type: aborted ? 'cancelled' : 'complete',
      processedLogs: Math.min(logsProcessed, inputs.logs.length),
      totalLogs: inputs.logs.length,
      matchesFound: result.totalMatches,
      chunkIndex,
      totalChunks,
      partialResult: result,
    };
    options.onProgress?.(completionEvent);

    const metrics: SearchExecutionMetrics = {
      executionTime: finalElapsed,
      logsProcessed: Math.min(logsProcessed, inputs.logs.length),
      matchesFound: result.totalMatches,
      chunkCount: chunkIndex,
      chunkSize,
    };

    return { result, pages, metrics };
  }

  destroy(): void {
    SearchOptimizer.instance = null;
  }
}

export const getSearchOptimizer = () => SearchOptimizer.getInstance();
