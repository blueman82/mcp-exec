'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { getAlertManager } from '@/lib/alert-manager';
import type {
  AlertActionType,
  AlertManagerState,
  AlertNotification,
  AlertPattern,
  AlertSeverity,
} from '@/types/alert';
import AlertPatternForm from './alert/AlertPatternForm';
import AlertPatternList from './alert/AlertPatternList';
import ActiveAlertsList from './alert/ActiveAlertsList';
import AlertHistoryList from './alert/AlertHistoryList';
import type {
  ActionOption,
  AlertPanelStyles,
  FormState,
  SeverityOption,
  ThemeMode,
  Server,
} from './alert/panelTypes';

interface AlertPanelProps {
  theme: ThemeMode;
  containers: string[];
  servers: Server[];
  onClose?: () => void;
}

const themeStyles: Record<ThemeMode, AlertPanelStyles> = {
  light: {
    panel: 'bg-white text-gray-800 border border-gray-200 shadow-xl',
    section: 'border border-gray-200 bg-gray-50',
    header: 'text-gray-900',
    subtext: 'text-gray-600',
    input: 'bg-white border border-gray-300 text-gray-900 focus:ring-2 focus:ring-blue-500',
    badge: 'bg-gray-200 text-gray-700',
  },
  dark: {
    panel: 'bg-gray-900 text-gray-100 border border-gray-700 shadow-2xl',
    section: 'border border-gray-700 bg-gray-800',
    header: 'text-white',
    subtext: 'text-gray-400',
    input: 'bg-gray-900 border border-gray-700 text-gray-100 focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500',
    badge: 'bg-gray-700 text-gray-200',
  },
};

const severityOptions: SeverityOption[] = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'critical', label: 'Critical' },
];

const actionOptions: ActionOption[] = [
  { value: 'toast', label: 'Toast' },
  { value: 'browser-notification', label: 'Browser notification' },
  { value: 'sound', label: 'Sound' },
];

type PatternInput = Omit<AlertPattern, 'id' | 'createdAt' | 'updatedAt'> & { id?: string };

function createInitialForm(servers: Server[]): FormState {
  return {
    name: '',
    expression: '',
    description: '',
    severity: 'high',
    cooldownMinutes: 5,
    containers: [],
    servers,
    actions: {
      toast: true,
      'browser-notification': false,
      sound: false,
    },
    caseSensitive: false,
  };
}

function patternToForm(pattern: AlertPattern, fallbackServers: Server[]): FormState {
  return {
    name: pattern.name,
    expression: pattern.expression,
    description: pattern.description ?? '',
    severity: pattern.severity,
    cooldownMinutes: pattern.cooldownMinutes,
    containers: [...pattern.containers],
    servers: pattern.servers.length > 0 ? [...pattern.servers] : fallbackServers,
    actions: {
      toast: pattern.actions.some((action) => action.type === 'toast'),
      'browser-notification': pattern.actions.some((action) => action.type === 'browser-notification'),
      sound: pattern.actions.some((action) => action.type === 'sound'),
    },
    caseSensitive: !pattern.flags.includes('i'),
  };
}

function formToPatternInput(form: FormState) {
  const flags = form.caseSensitive ? 'g' : 'gi';
  const selectedActions = (Object.keys(form.actions) as AlertActionType[])
    .filter((action) => form.actions[action])
    .map((type) => ({ type }));

  return {
    name: form.name.trim(),
    expression: form.expression.trim(),
    description: form.description.trim() || undefined,
    severity: form.severity as AlertSeverity,
    cooldownMinutes: Math.max(0, Math.min(1440, form.cooldownMinutes || 0)),
    containers: form.containers,
    servers: form.servers,
    actions: selectedActions.length > 0 ? selectedActions : [{ type: 'toast' as const }],
    flags,
  } satisfies Omit<PatternInput, 'enabled'>;
}

const AlertPanel: React.FC<AlertPanelProps> = ({ theme, containers, servers, onClose }) => {
  const styles = themeStyles[theme];
  const alertManager = useMemo(() => getAlertManager(), []);
  const [state, setState] = useState<AlertManagerState>(alertManager.getState());
  const [formState, setFormState] = useState<FormState>(() => createInitialForm(servers));
  const [editingId, setEditingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    const unsubscribe = alertManager.subscribe((nextState) => setState(nextState));
    return () => unsubscribe();
  }, [alertManager]);

  useEffect(() => {
    setFormState((prev) => {
      const nextContainers = prev.containers.filter((container) => containers.includes(container));
      const nextServers = prev.servers.filter((server) => servers.includes(server));
      return {
        ...prev,
        containers: nextContainers,
        servers: nextServers.length > 0 ? nextServers : servers,
      };
    });
  }, [containers, servers]);

  useEffect(() => {
    if (!success) {
      return;
    }
    const timeout = window.setTimeout(() => setSuccess(null), 3000);
    return () => window.clearTimeout(timeout);
  }, [success]);

  const handleChange = useCallback((field: keyof FormState, value: unknown) => {
    setFormState((prev) => ({ ...prev, [field]: value }));
  }, []);

  const handleToggleContainer = useCallback((container: string) => {
    setFormState((prev) => {
      const exists = prev.containers.includes(container);
      return {
        ...prev,
        containers: exists ? prev.containers.filter((item) => item !== container) : [...prev.containers, container],
      };
    });
  }, []);

  const handleToggleServer = useCallback((server: Server) => {
    setFormState((prev) => {
      const exists = prev.servers.includes(server);
      const updated = exists ? prev.servers.filter((item) => item !== server) : [...prev.servers, server];
      return {
        ...prev,
        servers: updated.length === 0 ? servers : updated,
      };
    });
  }, [servers]);

  const handleToggleAction = useCallback((action: AlertActionType) => {
    setFormState((prev) => ({
      ...prev,
      actions: {
        ...prev.actions,
        [action]: !prev.actions[action],
      },
    }));
  }, []);

  const resetForm = useCallback(() => {
    setFormState(createInitialForm(servers));
    setEditingId(null);
    setError(null);
  }, [servers]);

  const handleSubmit = useCallback(() => {
    setError(null);
    setSuccess(null);

    if (!formState.name.trim()) {
      setError('Alert name is required');
      return;
    }

    if (!formState.expression.trim()) {
      setError('Pattern expression is required');
      return;
    }

    try {
      const input = formToPatternInput(formState);
      if (editingId) {
        alertManager.updatePattern(editingId, input);
        setSuccess('Alert pattern updated');
      } else {
        alertManager.addPattern({ ...input, enabled: true });
        setSuccess('Alert pattern created');
      }
      resetForm();
    } catch (errorOrUnknown) {
      const message = errorOrUnknown instanceof Error ? errorOrUnknown.message : 'Failed to save alert pattern';
      setError(message);
    }
  }, [alertManager, editingId, formState, resetForm]);

  const handleEdit = useCallback(
    (pattern: AlertPattern) => {
      setEditingId(pattern.id);
      setError(null);
      setSuccess(null);
      setFormState(patternToForm(pattern, servers));
    },
    [servers]
  );

  const handleToggle = useCallback((pattern: AlertPattern) => {
    alertManager.togglePattern(pattern.id);
  }, [alertManager]);

  const handleDelete = useCallback((pattern: AlertPattern) => {
    alertManager.removePattern(pattern.id);
    if (editingId === pattern.id) {
      resetForm();
    }
  }, [alertManager, editingId, resetForm]);

  const handleAcknowledge = useCallback((alert: AlertNotification) => {
    alertManager.acknowledgeAlert(alert.id);
  }, [alertManager]);

  const handleClearAcknowledged = useCallback(() => {
    alertManager.clearAcknowledgedAlerts();
  }, [alertManager]);

  return (
    <aside
      aria-label="Alert management panel"
      className={`fixed top-16 right-6 w-[420px] max-h-[calc(100vh-120px)] overflow-y-auto rounded-xl p-4 space-y-4 z-40 ${styles.panel}`}
    >
      <header className="flex items-center justify-between">
        <div>
          <h2 className={`text-lg font-semibold ${styles.header}`}>Alerting</h2>
          <p className={`text-sm ${styles.subtext}`}>
            Create patterns, view live alerts, and review recent history.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-xs px-2 py-1 rounded-full ${styles.badge}`}>
            Active: {state.activeAlerts.length}
          </span>
          <span className={`text-xs px-2 py-1 rounded-full ${styles.badge}`}>
            Total: {state.stats.totalAlerts}
          </span>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="px-2 py-1 text-xs rounded border border-gray-600 text-gray-200 hover:bg-gray-700"
            >
              Close
            </button>
          )}
        </div>
      </header>

      <AlertPatternForm
        styles={styles}
        form={formState}
        containers={containers}
        servers={servers}
        severityOptions={severityOptions}
        actionOptions={actionOptions}
        isEditing={Boolean(editingId)}
        error={error}
        success={success}
        onChange={handleChange}
        onToggleContainer={handleToggleContainer}
        onToggleServer={handleToggleServer}
        onToggleAction={handleToggleAction}
        onSubmit={handleSubmit}
        onCancel={resetForm}
      />

      <AlertPatternList
        styles={styles}
        patterns={state.patterns}
        onEdit={handleEdit}
        onToggle={handleToggle}
        onDelete={handleDelete}
      />

      <ActiveAlertsList
        styles={styles}
        alerts={state.activeAlerts}
        onAcknowledge={handleAcknowledge}
        onClearAcknowledged={handleClearAcknowledged}
      />

      <AlertHistoryList styles={styles} alerts={state.alertHistory} />
    </aside>
  );
};

export default AlertPanel;
