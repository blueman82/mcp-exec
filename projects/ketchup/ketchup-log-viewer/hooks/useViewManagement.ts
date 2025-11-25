/**
 * Custom hook for managing saved log viewer views
 * Handles saving, loading, and deleting view configurations with localStorage persistence
 */

import { useState, useEffect, useCallback } from 'react';
import type { TimestampMode } from '@/lib/timestamp-formatter';

export interface SavedView {
  name: string;
  searchTerm: string;
  levelFilter: 'all' | 'error' | 'warn' | 'info' | 'debug';
  serverFilter: 'all' | 'prod1' | 'prod2';
  timestampMode: TimestampMode;
}

export interface UseViewManagementReturn {
  savedViews: SavedView[];
  saveView: (view: SavedView) => void;
  loadView: (view: SavedView) => void;
  deleteView: (name: string) => void;
}

export interface UseViewManagementOptions {
  storageKey?: string;
  onViewLoaded?: (view: SavedView) => void;
  onViewSaved?: (view: SavedView) => void;
  onViewDeleted?: (name: string) => void;
}

export function useViewManagement(
  options: UseViewManagementOptions = {}
): UseViewManagementReturn {
  const {
    storageKey = 'mergedLogViewer-savedViews',
    onViewLoaded,
    onViewSaved,
    onViewDeleted,
  } = options;

  const [savedViews, setSavedViews] = useState<SavedView[]>([]);

  // Load saved views from localStorage on mount
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const stored = localStorage.getItem(storageKey);
    if (stored) {
      try {
        setSavedViews(JSON.parse(stored));
      } catch (e) {
        console.error('Failed to load saved views:', e);
      }
    }
  }, [storageKey]);

  const saveView = useCallback(
    (view: SavedView) => {
      const updated = [...savedViews.filter((v) => v.name !== view.name), view];
      setSavedViews(updated);

      if (typeof window !== 'undefined') {
        localStorage.setItem(storageKey, JSON.stringify(updated));
      }

      onViewSaved?.(view);
    },
    [savedViews, storageKey, onViewSaved]
  );

  const loadView = useCallback(
    (view: SavedView) => {
      onViewLoaded?.(view);
    },
    [onViewLoaded]
  );

  const deleteView = useCallback(
    (name: string) => {
      const updated = savedViews.filter((v) => v.name !== name);
      setSavedViews(updated);

      if (typeof window !== 'undefined') {
        localStorage.setItem(storageKey, JSON.stringify(updated));
      }

      onViewDeleted?.(name);
    },
    [savedViews, storageKey, onViewDeleted]
  );

  return {
    savedViews,
    saveView,
    loadView,
    deleteView,
  };
}
