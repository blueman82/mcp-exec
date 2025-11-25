import type { LogLine } from '@/types';

export type AlertSeverity = 'low' | 'medium' | 'high' | 'critical';

export type AlertActionType = 'toast' | 'browser-notification' | 'sound';

export interface AlertAction {
  type: AlertActionType;
  payload?: Record<string, unknown>;
}

export interface AlertPattern {
  id: string;
  name: string;
  expression: string;
  flags: string;
  severity: AlertSeverity;
  description?: string;
  containers: string[];
  servers: ('prod1' | 'prod2')[];
  enabled: boolean;
  cooldownMinutes: number;
  actions: AlertAction[];
  createdAt: string;
  updatedAt: string;
}

export interface AlertNotification {
  id: string;
  patternId: string;
  patternName: string;
  severity: AlertSeverity;
  timestamp: string;
  log: LogLine;
  matches: string[];
  acknowledged: boolean;
  acknowledgedAt?: string;
  actions: AlertAction[];
  dedupKey?: string;
}

export interface AlertManagerState {
  patterns: AlertPattern[];
  activeAlerts: AlertNotification[];
  alertHistory: AlertNotification[];
  stats: {
    totalAlerts: number;
    acknowledgedAlerts: number;
    unacknowledgedAlerts: number;
    lastTriggeredAt?: string;
  };
}
