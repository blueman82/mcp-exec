import React from 'react';
import { getSeverityIcon } from '@/lib/alert-manager';
import type { ActionOption, AlertPanelStyles, FormState, SeverityOption, Server } from './panelTypes';
import type { AlertActionType } from '@/types/alert';

interface AlertPatternFormProps {
  styles: AlertPanelStyles;
  form: FormState;
  containers: string[];
  servers: Server[];
  severityOptions: SeverityOption[];
  actionOptions: ActionOption[];
  isEditing: boolean;
  error: string | null;
  success: string | null;
  onChange: (field: keyof FormState, value: unknown) => void;
  onToggleContainer: (container: string) => void;
  onToggleServer: (server: Server) => void;
  onToggleAction: (action: AlertActionType) => void;
  onSubmit: () => void;
  onCancel: () => void;
}

const AlertPatternForm: React.FC<AlertPatternFormProps> = ({
  styles,
  form,
  containers,
  servers,
  severityOptions,
  actionOptions,
  isEditing,
  error,
  success,
  onChange,
  onToggleContainer,
  onToggleServer,
  onToggleAction,
  onSubmit,
  onCancel,
}) => {
  return (
    <section aria-label="Alert pattern form" className={`rounded-lg p-4 space-y-4 ${styles.section}`}>
      <header>
        <h3 className={`text-sm font-semibold uppercase tracking-wide ${styles.header}`}>
          {isEditing ? 'Edit alert pattern' : 'Create alert pattern'}
        </h3>
        <p className={`text-xs ${styles.subtext}`}>
          Alerts trigger when new log lines match the configured pattern.
        </p>
      </header>

      {error && <div className="text-sm text-red-300 bg-red-900/40 border border-red-600 rounded px-3 py-2">{error}</div>}
      {success && <div className="text-sm text-green-200 bg-green-900/30 border border-green-600 rounded px-3 py-2">{success}</div>}

      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
      >
        <div className="space-y-1">
          <label className="text-xs font-semibold uppercase tracking-wide" htmlFor="alert-name">
            Name
          </label>
          <input
            id="alert-name"
            className={`w-full rounded px-3 py-2 text-sm ${styles.input}`}
            placeholder="e.g. Critical errors in metadata service"
            value={form.name}
            onChange={(event) => onChange('name', event.target.value)}
            required
          />
        </div>

        <div className="space-y-1">
          <label className="text-xs font-semibold uppercase tracking-wide" htmlFor="alert-pattern">
            Pattern (regex)
          </label>
          <input
            id="alert-pattern"
            className={`w-full rounded px-3 py-2 text-sm ${styles.input}`}
            placeholder="e.g. (error|fatal|panic)"
            value={form.expression}
            onChange={(event) => onChange('expression', event.target.value)}
            required
          />
          <label className="flex items-center justify-between text-xs text-gray-400">
            <span className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={form.caseSensitive}
                onChange={(event) => onChange('caseSensitive', event.target.checked)}
              />
              Case sensitive
            </span>
            <span>Standard JavaScript regex.</span>
          </label>
        </div>

        <div className="space-y-1">
          <label className="text-xs font-semibold uppercase tracking-wide" htmlFor="alert-description">
            Description
          </label>
          <textarea
            id="alert-description"
            className={`w-full rounded px-3 py-2 text-sm h-20 resize-none ${styles.input}`}
            placeholder="Optional summary for teammates"
            value={form.description}
            onChange={(event) => onChange('description', event.target.value)}
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <span className="text-xs font-semibold uppercase tracking-wide">Severity</span>
            <div className="grid grid-cols-2 gap-2">
              {severityOptions.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className={`px-2 py-2 text-xs rounded border flex items-center justify-center gap-2 transition-colors ${
                    form.severity === option.value
                      ? 'bg-red-600 border-red-500 text-white'
                      : 'border-dashed border-gray-600 text-gray-300'
                  }`}
                  onClick={() => onChange('severity', option.value)}
                >
                  <span>{getSeverityIcon(option.value)}</span>
                  <span>{option.label}</span>
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-semibold uppercase tracking-wide" htmlFor="alert-cooldown">
              Cooldown (minutes)
            </label>
            <input
              id="alert-cooldown"
              type="number"
              min={0}
              max={1440}
              className={`w-full rounded px-3 py-2 text-sm ${styles.input}`}
              value={form.cooldownMinutes}
              onChange={(event) => onChange('cooldownMinutes', Number(event.target.value))}
            />
            <p className={`text-xs ${styles.subtext}`}>Prevents duplicate alerts for the same pattern.</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <span className="text-xs font-semibold uppercase tracking-wide">Containers</span>
            <div className="flex flex-wrap gap-2">
              {containers.length === 0 && <span className={`text-xs ${styles.subtext}`}>None available</span>}
              {containers.map((container) => (
                <label key={container} className="flex items-center gap-2 text-xs">
                  <input
                    type="checkbox"
                    checked={form.containers.includes(container)}
                    onChange={() => onToggleContainer(container)}
                  />
                  <span>{container}</span>
                </label>
              ))}
            </div>
            <p className={`text-xs ${styles.subtext}`}>Leave empty to match every container.</p>
          </div>
          <div className="space-y-2">
            <span className="text-xs font-semibold uppercase tracking-wide">Servers</span>
            <div className="flex flex-wrap gap-2">
              {servers.map((server) => (
                <label key={server} className="flex items-center gap-2 text-xs">
                  <input
                    type="checkbox"
                    checked={form.servers.includes(server)}
                    onChange={() => onToggleServer(server)}
                  />
                  <span>{server}</span>
                </label>
              ))}
            </div>
            <p className={`text-xs ${styles.subtext}`}>Keep at least one server selected.</p>
          </div>
        </div>

        <div className="space-y-2">
          <span className="text-xs font-semibold uppercase tracking-wide">Alert actions</span>
          <div className="flex flex-wrap gap-2">
            {actionOptions.map((option) => (
              <label key={option.value} className="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={form.actions[option.value]}
                  onChange={() => onToggleAction(option.value)}
                />
                <span>{option.label}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="flex items-center justify-between pt-2">
          <button type="submit" className="px-3 py-2 text-sm font-medium rounded bg-cyan-600 text-white hover:bg-cyan-500">
            {isEditing ? 'Save changes' : 'Create Alert'}
          </button>
          {isEditing && (
            <button
              type="button"
              onClick={onCancel}
              className="px-3 py-2 text-sm rounded border border-gray-600 text-gray-200 hover:bg-gray-700"
            >
              Cancel
            </button>
          )}
        </div>
      </form>
    </section>
  );
};

export default AlertPatternForm;
