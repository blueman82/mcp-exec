import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { AlertManager, getAlertManager } from '@/lib/alert-manager';
import type { LogLine } from '@/types';

const localStorageMock = (() => {
  let store: Record<string, string> = {};

  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };
})();

describe('AlertManager', () => {
  let manager: AlertManager;

  beforeEach(() => {
    Object.defineProperty(window, 'localStorage', {
      value: localStorageMock,
      configurable: true,
    });
    localStorageMock.clear();
    vi.useFakeTimers();
    manager = getAlertManager();
    manager.reset();
  });

  afterEach(() => {
    manager.destroy();
    vi.useRealTimers();
  });

  const createLog = (content: string, overrides: Partial<LogLine> = {}): LogLine => ({
    timestamp: new Date().toISOString(),
    content,
    container: 'ketchup-app',
    server: 'prod1',
    level: 'error',
    ...overrides,
  });

  it('should add and trigger an alert pattern', () => {
    manager.addPattern({
      name: 'Error detector',
      expression: 'error',
      description: 'Capture error logs',
      severity: 'high',
      cooldownMinutes: 0,
      containers: [],
      servers: [],
      actions: [{ type: 'toast' }],
      flags: 'gi',
      enabled: true,
    });

    const triggered = manager.processLogLine(createLog('Critical error occurred'));
    expect(triggered).toHaveLength(1);
    expect(triggered[0].patternName).toBe('Error detector');

    const state = manager.getState();
    expect(state.activeAlerts).toHaveLength(1);
    expect(state.alertHistory).toHaveLength(1);
  });

  it('should respect cooldown period between alerts', () => {
    manager.addPattern({
      name: 'Cooldown tester',
      expression: 'timeout',
      severity: 'medium',
      description: '',
      cooldownMinutes: 1,
      containers: [],
      servers: [],
      actions: [{ type: 'toast' }],
      flags: 'gi',
      enabled: true,
    });

    const log = createLog('Request timeout');
    const first = manager.processLogLine(log);
    expect(first).toHaveLength(1);

    const second = manager.processLogLine({ ...log, timestamp: new Date().toISOString() });
    expect(second).toHaveLength(0);

    vi.advanceTimersByTime(61_000);

    const third = manager.processLogLine({ ...log, timestamp: new Date().toISOString() });
    expect(third).toHaveLength(1);
  });

  it('should deduplicate alerts within the deduplication window', () => {
    manager.addPattern({
      name: 'Dedup checker',
      expression: 'failed',
      severity: 'medium',
      description: '',
      cooldownMinutes: 0,
      containers: [],
      servers: [],
      actions: [{ type: 'toast' }],
      flags: 'gi',
      enabled: true,
    });

    const log = createLog('Job failed unexpectedly');
    const first = manager.processLogLine(log);
    expect(first).toHaveLength(1);

    const second = manager.processLogLine(log);
    expect(second).toHaveLength(0);
  });

  it('should acknowledge alerts and update history', () => {
    manager.addPattern({
      name: 'Ack tester',
      expression: 'panic',
      severity: 'critical',
      description: '',
      cooldownMinutes: 0,
      containers: [],
      servers: [],
      actions: [{ type: 'toast' }],
      flags: 'gi',
      enabled: true,
    });

    const [alert] = manager.processLogLine(createLog('Kernel panic detected'));
    expect(alert).toBeDefined();

    manager.acknowledgeAlert(alert.id);

    const state = manager.getState();
    expect(state.activeAlerts).toHaveLength(0);
    expect(state.alertHistory[0].acknowledged).toBe(true);
  });

  it('should persist patterns to localStorage and reload them', () => {
    manager.addPattern({
      name: 'Persistence test',
      expression: 'fatal',
      severity: 'high',
      description: '',
      cooldownMinutes: 5,
      containers: [],
      servers: [],
      actions: [{ type: 'toast' }],
      flags: 'gi',
      enabled: true,
    });

    expect(localStorageMock.setItem).toHaveBeenCalled();

    manager.destroy();

    const rehydratedManager = getAlertManager();
    const state = rehydratedManager.getState();
    expect(state.patterns).toHaveLength(1);
    expect(state.patterns[0].name).toBe('Persistence test');

    rehydratedManager.destroy();
  });
});
