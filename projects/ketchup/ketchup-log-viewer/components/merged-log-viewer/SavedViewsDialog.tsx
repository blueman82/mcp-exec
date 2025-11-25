/**
 * SavedViewsDialog Component
 * Provides UI for saving, loading, and deleting custom log viewer views
 */

'use client';

import React, { useState } from 'react';
import type { SavedView } from '@/hooks/useViewManagement';

interface SavedViewsDialogProps {
  isOpen: boolean;
  savedViews: SavedView[];
  onSave: (view: SavedView) => void;
  onLoad: (view: SavedView) => void;
  onDelete: (name: string) => void;
  onClose: () => void;
  currentState: Omit<SavedView, 'name'>;
}

const SavedViewsDialog: React.FC<SavedViewsDialogProps> = ({
  isOpen,
  savedViews,
  onSave,
  onLoad,
  onDelete,
  onClose,
  currentState,
}) => {
  const [viewName, setViewName] = useState('');

  if (!isOpen) return null;

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!viewName.trim()) return;

    onSave({
      name: viewName.trim(),
      ...currentState,
    });
    setViewName('');
  };

  return (
    <div className="p-3 bg-gray-800 border-b border-gray-700">
      <form onSubmit={handleSave} className="flex items-center space-x-2 mb-2">
        <input
          type="text"
          placeholder="View name..."
          value={viewName}
          onChange={(e) => setViewName(e.target.value)}
          className="flex-1 px-3 py-1 text-sm bg-gray-900 border border-gray-600 rounded text-gray-300 focus:outline-none focus:border-blue-500"
          autoFocus
        />
        <button
          type="submit"
          disabled={!viewName.trim()}
          className="px-3 py-1 text-xs bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded"
        >
          Save Current
        </button>
        <button
          type="button"
          onClick={onClose}
          className="px-3 py-1 text-xs bg-gray-600 hover:bg-gray-700 text-white rounded"
        >
          Close
        </button>
      </form>

      {savedViews.length > 0 && (
        <div className="space-y-1">
          <div className="text-xs text-gray-400 mb-1">Saved Views:</div>
          {savedViews.map((view) => (
            <div
              key={view.name}
              className="flex items-center justify-between p-2 bg-gray-900 rounded"
            >
              <button
                onClick={() => onLoad(view)}
                className="flex-1 text-left text-sm text-gray-300 hover:text-white"
              >
                <span className="font-bold">{view.name}</span>
                <span className="text-xs text-gray-500 ml-2">
                  ({view.serverFilter}, {view.levelFilter}, {view.timestampMode}
                  {view.searchTerm ? `, "${view.searchTerm}"` : ''})
                </span>
              </button>
              <button
                onClick={() => onDelete(view.name)}
                className="ml-2 px-2 py-1 text-xs bg-red-600 hover:bg-red-700 text-white rounded"
                title="Delete view"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default SavedViewsDialog;
