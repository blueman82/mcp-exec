// PAT validation utilities for backup PAT management

export function isValidPatFormat(pat: string): boolean {
  if (!pat || typeof pat !== 'string') {
    return false;
  }
  // PAT should be non-empty string, typically alphanumeric with hyphens and underscores
  return /^[a-zA-Z0-9_\-]+$/.test(pat) && pat.length > 0;
}

export function isBackupPatExpired(expiryDate?: Date): boolean {
  if (!expiryDate || !(expiryDate instanceof Date)) {
    return false;
  }
  return expiryDate < new Date();
}

export function isBackupPatValid(backupPat?: string): boolean {
  if (!backupPat) {
    return false;
  }
  return isValidPatFormat(backupPat);
}

export interface JiraConfigAuth {
  email: string;
  token: string;
  pat?: string;
  patExpiry?: Date;
  usePat?: boolean;
  backupPat?: string;
  backupPatExpiry?: Date;
  useBackupPat?: boolean;
  backupPatCreatedAt?: Date;
  imsToken?: string;
  apiKey?: string;
  username?: string;
  password?: string;
}

export interface JiraConfigForValidation {
  auth: JiraConfigAuth;
  [key: string]: any;
}

export function shouldUseBackupPat(config: JiraConfigForValidation): boolean {
  // Use backup PAT if:
  // 1. useBackupPat flag is true AND
  // 2. backupPat is valid AND
  // 3. backupPatExpiry is in the future (or not set, meaning no expiry)
  if (!config.auth.useBackupPat) {
    return false;
  }
  if (!isBackupPatValid(config.auth.backupPat)) {
    return false;
  }
  if (config.auth.backupPatExpiry && isBackupPatExpired(config.auth.backupPatExpiry)) {
    return false;
  }
  return true;
}
