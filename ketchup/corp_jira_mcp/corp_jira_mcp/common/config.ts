import { join, dirname, resolve } from 'path';
import { homedir } from 'os';
import { mkdirSync, existsSync } from 'fs';
import '../env.js';

// Configuration auth type definition
export interface JiraAuthConfig {
  email: string;
  token: string;
  // iPaaS specific auth fields
  imsToken?: string;
  apiKey?: string;
  username?: string;
  password?: string;
  // PAT (Personal Access Token) fields
  pat?: string;                    // Primary PAT for JIRA authentication
  patExpiry?: Date;                // When primary PAT expires
  usePat?: boolean;                // Flag to use PAT instead of token (default false)
}

// Configuration type definition
export interface JiraConfig {
  apiBaseUrl: string;
  logFile: string;
  auth: JiraAuthConfig;
  defaultProject?: string;
  maxResults?: number;
  timeout?: number;
  strictSSL?: boolean;
  useIpaas?: boolean;  // Flag to enable iPaaS mode
}

// Function to resolve path with tilde expansion
function resolvePath(path: string): string {
  if (path.startsWith('~/')) {
    return path.replace('~', homedir());
  }
  return resolve(path);
}

// Default values that can be overridden by environment variables
const defaults: JiraConfig = {
  apiBaseUrl: process.env.USE_IPAAS === 'true'
    ? "https://ipaasapi.adobe-services.com/jira/rest/api/2"
    : "https://jira.corp.adobe.com/rest/api/2",
  logFile: '/app/logs/jira-api.log',
  auth: {
    email: process.env.JIRA_EMAIL || '',
    token: process.env.JIRA_PERSONAL_ACCESS_TOKEN || '',
    imsToken: process.env.JIRA_IMS_TOKEN || '',
    apiKey: process.env.JIRA_API_KEY || '',
    username: process.env.JIRA_USERNAME || '',
    password: process.env.JIRA_PASSWORD || '',
    pat: process.env.JIRA_PAT || '',
    patExpiry: process.env.JIRA_PAT_EXPIRY ? new Date(process.env.JIRA_PAT_EXPIRY) : undefined,
    usePat: process.env.JIRA_USE_PAT_AUTH === 'true'
  },
  defaultProject: process.env.JIRA_DEFAULT_PROJECT,
  maxResults: parseInt(process.env.JIRA_MAX_RESULTS || '50', 10),
  timeout: parseInt(process.env.JIRA_TIMEOUT || '30000', 10),
  strictSSL: process.env.JIRA_STRICT_SSL !== 'false',
  useIpaas: process.env.USE_IPAAS === 'true'
};

// Create a simple internal logging function that doesn't depend on the config
// This avoids circular dependency issues since utils.ts imports config.ts
function internalLog(message: string): void {
  // Only log to stderr for critical messages
  if (message.includes('Failed to create log directory')) {
    console.error(message);
  }
}

// Ensure log directory exists
function ensureLogDirectory(logPath: string): void {
  const dir = dirname(logPath);
  internalLog(`Ensuring log directory exists: ${dir}`);
  if (!existsSync(dir)) {
    try {
      internalLog(`Creating log directory: ${dir}`);
      mkdirSync(dir, { recursive: true });
      internalLog(`Log directory created: ${dir}`);
    } catch (error) {
      console.error(`Failed to create log directory: ${dir}`, error);
    }
  }
}

// Validate and create config
function createConfig(): JiraConfig {
  const config: JiraConfig = {
    apiBaseUrl: process.env.JIRA_API_BASE_URL || defaults.apiBaseUrl,
    logFile: resolvePath(process.env.JIRA_LOG_FILE || defaults.logFile),
    auth: {
      email: process.env.JIRA_EMAIL || defaults.auth.email,
      token: process.env.JIRA_PERSONAL_ACCESS_TOKEN || defaults.auth.token,
      imsToken: process.env.JIRA_IMS_TOKEN || defaults.auth.imsToken,
      apiKey: process.env.JIRA_API_KEY || defaults.auth.apiKey,
      username: process.env.JIRA_USERNAME || defaults.auth.username,
      password: process.env.JIRA_PASSWORD || defaults.auth.password,
      pat: process.env.JIRA_PAT || defaults.auth.pat,
      patExpiry: process.env.JIRA_PAT_EXPIRY ? new Date(process.env.JIRA_PAT_EXPIRY) : defaults.auth.patExpiry,
      usePat: process.env.JIRA_USE_PAT_AUTH === 'true'
    },
    defaultProject: process.env.JIRA_DEFAULT_PROJECT || defaults.defaultProject,
    maxResults: parseInt(process.env.JIRA_MAX_RESULTS || String(defaults.maxResults), 10),
    timeout: parseInt(process.env.JIRA_TIMEOUT || String(defaults.timeout), 10),
    strictSSL: process.env.JIRA_STRICT_SSL === undefined ? defaults.strictSSL : process.env.JIRA_STRICT_SSL !== 'false',
    useIpaas: process.env.USE_IPAAS === 'true' || defaults.useIpaas
  };

  // Validate API URL
  try {
    new URL(config.apiBaseUrl);
  } catch (error) {
    console.error(`Invalid JIRA_API_BASE_URL: ${config.apiBaseUrl}`);
    config.apiBaseUrl = defaults.apiBaseUrl;
  }

  // Validate required auth fields based on mode
  if (config.useIpaas) {
    if (!config.auth.apiKey) {
      throw new Error('JIRA_API_KEY environment variable is required when using iPaaS');
    }
    // IMS token can be empty if provided via Authorization header later
  } else {
  if (!config.auth.email || !config.auth.token) {
    throw new Error('JIRA_EMAIL and JIRA_PERSONAL_ACCESS_TOKEN environment variables are required');
    }
  }

  // Ensure log directory exists
  ensureLogDirectory(config.logFile);

  return config;
}

// Re-export validation utilities from pat-validation module
export {
  isValidPatFormat,
} from './pat-validation.js';

export const config = createConfig();
