import type { AlertActionType, AlertSeverity } from '@/types/alert';

export type ThemeMode = 'light' | 'dark';
export type Server = 'prod1' | 'prod2';

export interface AlertPanelStyles {
  panel: string;
  section: string;
  header: string;
  subtext: string;
  input: string;
  badge: string;
}

export interface FormState {
  name: string;
  expression: string;
  description: string;
  severity: AlertSeverity;
  cooldownMinutes: number;
  containers: string[];
  servers: Server[];
  actions: Record<AlertActionType, boolean>;
  caseSensitive: boolean;
}

export interface SeverityOption {
  value: AlertSeverity;
  label: string;
}

export interface ActionOption {
  value: AlertActionType;
  label: string;
}
