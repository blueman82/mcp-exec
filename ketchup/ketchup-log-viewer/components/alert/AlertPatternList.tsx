import React from 'react';
import { getSeverityIcon } from '@/lib/alert-manager';
import type { AlertPattern } from '@/types/alert';
import type { AlertPanelStyles } from './panelTypes';

interface AlertPatternListProps {
  styles: AlertPanelStyles;
  patterns: AlertPattern[];
  onEdit: (pattern: AlertPattern) => void;
  onToggle: (pattern: AlertPattern) => void;
  onDelete: (pattern: AlertPattern) => void;
}

const AlertPatternList: React.FC<AlertPatternListProps> = ({ styles, patterns, onEdit, onToggle, onDelete }) => (
  <section aria-label="Configured alert patterns" className={`rounded-lg p-4 space-y-3 ${styles.section}`}>
    <header className="flex items-center justify-between">
      <h3 className={`text-sm font-semibold uppercase tracking-wide ${styles.header}`}>
        Alert Patterns ({patterns.length})
      </h3>
    </header>

    {patterns.length === 0 ? (
      <p className={`text-xs ${styles.subtext}`}>No patterns configured yet.</p>
    ) : (
      <div className="space-y-2">
        {patterns.map((pattern) => (
          <article key={pattern.id} className="rounded border border-gray-600 px-3 py-3 space-y-2">
            <header className="flex items-start justify-between gap-3">
              <div>
                <h4 className="text-sm font-semibold flex items-center gap-2">
                  <span>{getSeverityIcon(pattern.severity)}</span>
                  <span>{pattern.name}</span>
                  {!pattern.enabled && <span className="text-xs text-gray-400">(disabled)</span>}
                </h4>
                <p className={`text-xs ${styles.subtext}`}>/{pattern.expression}/</p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => onToggle(pattern)}
                  className={`px-2 py-1 text-xs rounded border ${
                    pattern.enabled
                      ? 'border-green-500 text-green-200 hover:bg-green-700'
                      : 'border-gray-500 text-gray-300 hover:bg-gray-700'
                  }`}
                >
                  {pattern.enabled ? 'Disable' : 'Enable'}
                </button>
                <button
                  type="button"
                  onClick={() => onEdit(pattern)}
                  className="px-2 py-1 text-xs rounded border border-gray-500 text-gray-200 hover:bg-gray-700"
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() => onDelete(pattern)}
                  className="px-2 py-1 text-xs rounded border border-red-500 text-red-200 hover:bg-red-700"
                >
                  Delete
                </button>
              </div>
            </header>

            {pattern.description && <p className={`text-xs ${styles.subtext}`}>{pattern.description}</p>}

            <footer className="flex flex-wrap items-center gap-3 text-xs">
              <span className={styles.badge}>Cooldown: {pattern.cooldownMinutes}m</span>
              {pattern.containers.length > 0 && <span className={styles.badge}>Containers: {pattern.containers.join(', ')}</span>}
              {pattern.servers.length > 0 && <span className={styles.badge}>Servers: {pattern.servers.join(', ')}</span>}
              <span className={styles.badge}>Actions: {pattern.actions.map((action) => action.type).join(', ')}</span>
            </footer>
          </article>
        ))}
      </div>
    )}
  </section>
);

export default AlertPatternList;
