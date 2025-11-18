import type { LogLine } from '@/types';
import type {
  AlertAction,
  AlertManagerState,
  AlertNotification,
  AlertPattern,
  AlertSeverity,
} from '@/types/alert';

type AlertListener = (state: AlertManagerState) => void;

interface InternalPattern {
  pattern: AlertPattern;
  regex: RegExp;
  lastTriggeredAt?: number;
}

function createId(prefix: string): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `${prefix}-${crypto.randomUUID()}`;
  }

  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
}

function normalizeFlags(flags: string): string {
  const unique = Array.from(new Set(flags.split('').filter(Boolean)));
  const allowed = ['g', 'i', 'm', 'u', 'y'];
  const filtered = unique.filter((flag) => allowed.includes(flag));
  if (!filtered.includes('g')) {
    filtered.push('g');
  }
  return filtered.join('');
}

function isBrowser(): boolean {
  return typeof window !== 'undefined' && typeof document !== 'undefined';
}

export class AlertManager {
  private static instance: AlertManager | null = null;
  private readonly patterns = new Map<string, InternalPattern>();
  private readonly listeners = new Set<AlertListener>();
  private readonly activeAlerts = new Map<string, AlertNotification>();
  private readonly alertHistory: AlertNotification[] = [];
  private readonly dedupTimestamps = new Map<string, number>();
  private readonly STORAGE_ID = 'ketchup-alert-patterns-v1';
  private readonly historyLimit = 200;
  private readonly dedupWindowMs = 60_000;

  private constructor() {
    this.loadPersistedPatterns();
  }

  static getInstance(): AlertManager {
    if (!AlertManager.instance) {
      AlertManager.instance = new AlertManager();
    }

    return AlertManager.instance;
  }

  destroy(): void {
    this.listeners.clear();
    this.patterns.clear();
    this.activeAlerts.clear();
    this.alertHistory.length = 0;
    this.dedupTimestamps.clear();
    AlertManager.instance = null;
  }

  getState(): AlertManagerState {
    const patterns = Array.from(this.patterns.values()).map(({ pattern }) => pattern);
    const activeAlerts = Array.from(this.activeAlerts.values()).sort((a, b) =>
      a.timestamp.localeCompare(b.timestamp)
    );
    const alertHistory = [...this.alertHistory].sort((a, b) =>
      b.timestamp.localeCompare(a.timestamp)
    );
    const acknowledgedAlerts = alertHistory.filter((alert) => alert.acknowledged).length;

    return {
      patterns,
      activeAlerts,
      alertHistory,
      stats: {
        totalAlerts: alertHistory.length,
        acknowledgedAlerts,
        unacknowledgedAlerts: activeAlerts.length,
        lastTriggeredAt: alertHistory[0]?.timestamp,
      },
    };
  }

  subscribe(listener: AlertListener): () => void {
    this.listeners.add(listener);
    listener(this.getState());
    return () => {
      this.listeners.delete(listener);
    };
  }

  addPattern(pattern: Omit<AlertPattern, 'id' | 'createdAt' | 'updatedAt'> & { id?: string }): AlertPattern {
    const id = pattern.id ?? createId('alert-pattern');
    if (this.patterns.has(id)) {
      throw new Error('Pattern ID already exists');
    }

    const now = new Date().toISOString();
    const normalizedFlags = normalizeFlags(pattern.flags ?? 'gi');
    const regex = this.createRegex(pattern.expression, normalizedFlags);

    const containers = Array.from(new Set(pattern.containers ?? []));
    const servers = Array.from(new Set(pattern.servers ?? []));
    const actions: AlertAction[] = (pattern.actions?.length ?? 0) > 0 ? pattern.actions! : [{ type: 'toast' as const }];

    const alertPattern: AlertPattern = {
      ...pattern,
      id,
      flags: normalizedFlags,
      containers,
      servers,
      actions,
      createdAt: now,
      updatedAt: now,
    };

    this.patterns.set(id, { pattern: alertPattern, regex });
    this.persistPatterns();
    this.emit();

    return alertPattern;
  }

  updatePattern(id: string, updates: Partial<Omit<AlertPattern, 'id' | 'createdAt'>>): AlertPattern {
    const existing = this.patterns.get(id);
    if (!existing) {
      throw new Error('Pattern not found');
    }

    const containers = Array.from(new Set((updates.containers ?? existing.pattern.containers) ?? []));
    const servers = Array.from(new Set((updates.servers ?? existing.pattern.servers) ?? []));
    const actions: AlertAction[] = (updates.actions?.length ?? existing.pattern.actions.length) > 0
      ? (updates.actions ?? existing.pattern.actions)
      : [{ type: 'toast' as const }];

    const nextPattern: AlertPattern = {
      ...existing.pattern,
      ...updates,
      flags: normalizeFlags(updates.flags ?? existing.pattern.flags),
      containers,
      servers,
      actions,
      updatedAt: new Date().toISOString(),
    };

    const regex = this.createRegex(nextPattern.expression, nextPattern.flags);
    this.patterns.set(id, { pattern: nextPattern, regex, lastTriggeredAt: existing.lastTriggeredAt });
    this.persistPatterns();
    this.emit();

    return nextPattern;
  }

  removePattern(id: string): void {
    if (this.patterns.delete(id)) {
      this.persistPatterns();
      this.emit();
    }
  }

  togglePattern(id: string, enabled?: boolean): AlertPattern {
    const existing = this.patterns.get(id);
    if (!existing) {
      throw new Error('Pattern not found');
    }

    const nextEnabled = enabled ?? !existing.pattern.enabled;
    return this.updatePattern(id, { enabled: nextEnabled });
  }

  processLogLine(log: LogLine): AlertNotification[] {
    if (this.patterns.size === 0) {
      return [];
    }

    const triggeredAlerts: AlertNotification[] = [];
    const now = Date.now();

    for (const { pattern, regex, lastTriggeredAt } of this.patterns.values()) {
      if (!pattern.enabled) {
        continue;
      }

      if (pattern.servers.length > 0 && !pattern.servers.includes(log.server as 'prod1' | 'prod2')) {
        continue;
      }

      if (pattern.containers.length > 0 && !pattern.containers.includes(log.container)) {
        continue;
      }

      if (pattern.cooldownMinutes > 0 && lastTriggeredAt) {
        const elapsed = now - lastTriggeredAt;
        if (elapsed < pattern.cooldownMinutes * 60_000) {
          continue;
        }
      }

      regex.lastIndex = 0;
      const matches: string[] = [];
      let match: RegExpExecArray | null;
      let iterations = 0;

      while ((match = regex.exec(log.content)) !== null) {
        matches.push(match[0]);
        iterations += 1;
        if (!regex.global || iterations > 20) {
          break;
        }
      }

      regex.lastIndex = 0;

      if (matches.length === 0) {
        continue;
      }

      const dedupKey = `${pattern.id}:${log.timestamp}:${matches[0]}`;
      const lastTrigger = this.dedupTimestamps.get(dedupKey);
      if (lastTrigger && now - lastTrigger < this.dedupWindowMs) {
        continue;
      }

      const alert: AlertNotification = {
        id: createId('alert'),
        patternId: pattern.id,
        patternName: pattern.name,
        severity: pattern.severity,
        timestamp: new Date().toISOString(),
        log,
        matches,
        acknowledged: false,
        actions: pattern.actions,
        dedupKey,
      };
      this.activeAlerts.set(alert.id, alert);
      this.alertHistory.unshift(alert);
      if (this.alertHistory.length > this.historyLimit) {
        this.alertHistory.length = this.historyLimit;
      }

      this.dedupTimestamps.set(dedupKey, now);

      const internal = this.patterns.get(pattern.id);
      if (internal) {
        internal.lastTriggeredAt = now;
      }

      triggeredAlerts.push(alert);
    }

    if (triggeredAlerts.length > 0) {
      this.emit();
    }

    return triggeredAlerts;
  }

  acknowledgeAlert(alertId: string): void {
    const alert = this.activeAlerts.get(alertId);
    if (!alert) {
      return;
    }

    const acknowledgedAlert: AlertNotification = {
      ...alert,
      acknowledged: true,
      acknowledgedAt: new Date().toISOString(),
    };

    this.activeAlerts.delete(alertId);
    const historyIndex = this.alertHistory.findIndex((item) => item.id === alertId);
    if (historyIndex !== -1) {
      this.alertHistory[historyIndex] = acknowledgedAlert;
    } else {
      this.alertHistory.unshift(acknowledgedAlert);
    }

    this.emit();
  }

  clearAcknowledgedAlerts(): void {
    for (const alert of this.alertHistory) {
      if (alert.acknowledged) {
        this.activeAlerts.delete(alert.id);
      }
    }
    this.emit();
  }

  reset(): void {
    this.patterns.clear();
    this.activeAlerts.clear();
    this.alertHistory.length = 0;
    this.dedupTimestamps.clear();
    this.persistPatterns();
    this.emit();
  }

  private emit(): void {
    const state = this.getState();
    for (const listener of this.listeners) {
      listener(state);
    }
  }

  private createRegex(expression: string, flags: string): RegExp {
    if (!expression.trim()) {
      throw new Error('Pattern expression is required');
    }

    if (expression.length > 500) {
      throw new Error('Pattern expression too long');
    }

    const groupCount = (expression.match(/\(/g) || []).length;
    if (groupCount > 10) {
      throw new Error('Pattern has too many capture groups');
    }

    const catastrophic = /(\+|\*){4,}/;
    if (catastrophic.test(expression)) {
      throw new Error('Pattern may cause performance issues');
    }

    try {
      return new RegExp(expression, normalizeFlags(flags));
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Invalid regex pattern';
      throw new Error(message);
    }
  }

  private persistPatterns(): void {
    if (!isBrowser()) {
      return;
    }

    const payload = Array.from(this.patterns.values()).map(({ pattern }) => pattern);

    try {
      window.localStorage.setItem(this.STORAGE_ID, JSON.stringify(payload));
    } catch (error) {
      console.warn('Failed to persist alert patterns', error);
    }
  }

  private loadPersistedPatterns(): void {
    if (!isBrowser()) {
      return;
    }

    try {
      const raw = window.localStorage.getItem(this.STORAGE_ID);
      if (!raw) {
        return;
      }

      const parsed = JSON.parse(raw) as AlertPattern[];
      for (const pattern of parsed) {
        const normalizedFlags = normalizeFlags(pattern.flags);
        const regex = this.createRegex(pattern.expression, normalizedFlags);
        this.patterns.set(pattern.id, {
          pattern: { ...pattern, flags: normalizedFlags },
          regex,
        });
      }
    } catch (error) {
      console.warn('Failed to load alert patterns', error);
    }
  }
}

export function getAlertManager(): AlertManager {
  return AlertManager.getInstance();
}

export function getSeverityIcon(severity: AlertSeverity): string {
  switch (severity) {
    case 'critical':
      return '🛑';
    case 'high':
      return '⚠️';
    case 'medium':
      return '🚨';
    default:
      return '🔔';
  }
}
