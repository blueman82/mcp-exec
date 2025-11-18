import React from 'react';
import { getSeverityIcon } from '@/lib/alert-manager';
import type { AlertNotification } from '@/types/alert';
import type { AlertPanelStyles } from './panelTypes';

interface AlertHistoryListProps {
  styles: AlertPanelStyles;
  alerts: AlertNotification[];
}

const AlertHistoryList: React.FC<AlertHistoryListProps> = ({ styles, alerts }) => (
  <section aria-label="Alert history" className={`rounded-lg p-4 space-y-3 ${styles.section}`}>
    <h3 className={`text-sm font-semibold uppercase tracking-wide ${styles.header}`}>Recent Alerts</h3>

    {alerts.length === 0 ? (
      <p className={`text-xs ${styles.subtext}`}>No alerts recorded yet.</p>
    ) : (
      <ul className="space-y-2 text-xs">
        {alerts.slice(0, 10).map((alert) => (
          <li
            key={alert.id}
            className="flex justify-between items-start gap-3 border border-gray-600 rounded px-3 py-2"
          >
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span>{getSeverityIcon(alert.severity)}</span>
                <span>{alert.patternName}</span>
                {alert.acknowledged && <span className="text-[11px] text-green-300">ack</span>}
              </div>
              <div className={`text-[11px] ${styles.subtext}`}>
                {new Date(alert.timestamp).toLocaleString()} — {alert.log.container} @ {alert.log.server}
              </div>
            </div>
            <div className={`text-[11px] ${styles.subtext} text-right`}>{alert.matches[0]}</div>
          </li>
        ))}
      </ul>
    )}
  </section>
);

export default AlertHistoryList;
