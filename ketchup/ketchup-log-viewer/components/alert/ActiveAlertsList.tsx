import React from 'react';
import { getSeverityIcon } from '@/lib/alert-manager';
import type { AlertNotification } from '@/types/alert';
import type { AlertPanelStyles } from './panelTypes';

interface ActiveAlertsListProps {
  styles: AlertPanelStyles;
  alerts: AlertNotification[];
  onAcknowledge: (alert: AlertNotification) => void;
  onClearAcknowledged: () => void;
}

const ActiveAlertsList: React.FC<ActiveAlertsListProps> = ({ styles, alerts, onAcknowledge, onClearAcknowledged }) => (
  <section aria-label="Active alerts" className={`rounded-lg p-4 space-y-3 ${styles.section}`}>
    <header className="flex items-center justify-between">
      <h3 className={`text-sm font-semibold uppercase tracking-wide ${styles.header}`}>
        Active Alerts ({alerts.length})
      </h3>
      <button type="button" onClick={onClearAcknowledged} className="text-xs underline">
        Clear acknowledged
      </button>
    </header>

    {alerts.length === 0 ? (
      <p className={`text-xs ${styles.subtext}`}>No alerts are active right now.</p>
    ) : (
      <div className="space-y-2">
        {alerts.map((alert) => (
          <article
            key={alert.id}
            className={`rounded border px-3 py-3 space-y-2 ${
              alert.severity === 'critical'
                ? 'border-red-600'
                : alert.severity === 'high'
                ? 'border-orange-500'
                : 'border-yellow-500'
            }`}
          >
            <header className="flex items-start justify-between gap-3">
              <div>
                <h4 className="text-sm font-semibold flex items-center gap-2">
                  <span>{getSeverityIcon(alert.severity)}</span>
                  <span>{alert.patternName}</span>
                </h4>
                <p className="text-xs text-red-200">
                  {new Date(alert.timestamp).toLocaleString()} — {alert.log.container} @ {alert.log.server}
                </p>
              </div>
              <button
                type="button"
                onClick={() => onAcknowledge(alert)}
                className="px-2 py-1 text-xs rounded border border-red-400 text-red-100 hover:bg-red-700"
              >
                Acknowledge
              </button>
            </header>
            <pre className="text-xs bg-black/40 text-red-100 rounded px-2 py-2 overflow-x-auto">{alert.log.content}</pre>
            <p className="text-xs text-red-200">Matches: {alert.matches.join(', ')}</p>
          </article>
        ))}
      </div>
    )}
  </section>
);

export default ActiveAlertsList;
