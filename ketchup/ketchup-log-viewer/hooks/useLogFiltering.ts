/**
 * Custom hook for filtering and searching log lines
 * Handles text search, level filtering, server filtering, and critical pattern detection
 */

import { useMemo } from 'react';
import { stripAnsi } from '@/lib/ansi-parser';
import type { LogLine } from '@/types';

export interface FilterOptions {
  searchTerm: string;
  levelFilter: 'all' | 'error' | 'warn' | 'info' | 'debug';
  serverFilter: 'all' | 'prod1' | 'prod2';
  showCriticalOnly: boolean;
}

export interface UseLogFilteringReturn<T extends LogLine = LogLine> {
  filteredLogs: T[];
  patternCounts: Record<string, number>;
  totalCritical: number;
}

const CRITICAL_PATTERNS = ['error', 'timeout', 'failed', 'exception', 'fatal', 'critical'];

export function useLogFiltering<T extends LogLine = LogLine>(
  logs: T[],
  filters: FilterOptions
): UseLogFilteringReturn<T> {
  const { searchTerm, levelFilter, serverFilter, showCriticalOnly } = filters;

  const filteredLogs = useMemo(() => {
    return logs.filter((log) => {
      const content = stripAnsi(log.content).toLowerCase();

      // Critical-only filter
      if (showCriticalOnly) {
        return CRITICAL_PATTERNS.some((pattern) => content.includes(pattern));
      }

      // Server filter
      if (serverFilter !== 'all' && log.server !== serverFilter) {
        return false;
      }

      // Search filter
      if (searchTerm && !content.includes(searchTerm.toLowerCase())) {
        return false;
      }

      // Level filter
      if (levelFilter !== 'all' && log.level !== levelFilter) {
        return false;
      }

      return true;
    });
  }, [logs, searchTerm, levelFilter, serverFilter, showCriticalOnly]);

  const patternCounts = useMemo(() => {
    return filteredLogs.reduce((acc, log) => {
      const content = stripAnsi(log.content).toLowerCase();
      CRITICAL_PATTERNS.forEach((pattern) => {
        if (content.includes(pattern)) {
          acc[pattern] = (acc[pattern] || 0) + 1;
        }
      });
      return acc;
    }, {} as Record<string, number>);
  }, [filteredLogs]);

  const totalCritical = useMemo(() => {
    return filteredLogs.filter((log) => {
      const content = stripAnsi(log.content).toLowerCase();
      return CRITICAL_PATTERNS.some((pattern) => content.includes(pattern));
    }).length;
  }, [filteredLogs]);

  return {
    filteredLogs,
    patternCounts,
    totalCritical,
  };
}
