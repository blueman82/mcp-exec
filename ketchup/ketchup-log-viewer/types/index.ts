/**
 * TypeScript type definitions for Ketchup Log Viewer
 */

export interface Server {
  id: 'prod1' | 'prod2';
  host: string;
  displayName: string;
}

export interface Container {
  name: string;
  image: string;
  status: string;
  uptime: string;
  server: 'prod1' | 'prod2';
  ports?: string;
}

export interface LogLine {
  timestamp: string;
  content: string;
  container: string;
  server: string;
  level?: 'error' | 'warn' | 'info' | 'debug' | 'trace' | 'none';
}

export interface SSHConnection {
  id: string;
  server: string;
  status: 'connecting' | 'awaiting_okta' | 'connected' | 'failed';
  timestamp: number;
}

export interface LogStreamParams {
  container: string;
  server: 'prod1' | 'prod2';
  tail?: number;
  follow?: boolean;
}

export interface OktaAuthState {
  isWaiting: boolean;
  server: string | null;
  timeoutSeconds: number;
}
