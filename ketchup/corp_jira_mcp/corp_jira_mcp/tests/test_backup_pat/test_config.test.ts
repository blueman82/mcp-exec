import { describe, it, expect } from '@jest/globals';
import {
  isValidPatFormat,
  isBackupPatExpired,
  isBackupPatValid,
  shouldUseBackupPat,
} from '../../common/pat-validation.js';

describe('BackupPATConfig', () => {
  it('should parse backup PAT expiry as Date object', () => {
    const expiryString = '2026-03-15T10:30:00Z';
    const expiryDate = new Date(expiryString);

    expect(expiryDate).toEqual(new Date('2026-03-15T10:30:00Z'));
    expect(expiryDate instanceof Date).toBe(true);
  });

  it('should handle Date parsing for backup PAT created timestamp', () => {
    const createdString = '2026-01-15T10:30:00Z';
    const createdDate = new Date(createdString);

    expect(createdDate).toEqual(new Date('2026-01-15T10:30:00Z'));
  });

  it('should construct valid JiraConfig interface with backup PAT fields', () => {
    const mockConfig = {
      apiBaseUrl: 'https://jira.corp.adobe.com/rest/api/2',
      logFile: '/app/logs/jira-api.log',
      auth: {
        email: 'test@adobe.com',
        token: 'base-token',
        pat: 'primary-token-abc123',
        patExpiry: new Date('2026-02-15T10:30:00Z'),
        usePat: false,
        backupPat: 'backup-token-xyz789',
        backupPatExpiry: new Date('2026-03-15T10:30:00Z'),
        useBackupPat: false,
        backupPatCreatedAt: new Date('2026-01-15T10:30:00Z'),
      },
      defaultProject: undefined,
      maxResults: 50,
      timeout: 30000,
      strictSSL: true,
      useIpaas: false,
    };

    // Validate structure
    expect(mockConfig.auth.pat).toBe('primary-token-abc123');
    expect(mockConfig.auth.backupPat).toBe('backup-token-xyz789');
    expect(mockConfig.auth.patExpiry instanceof Date).toBe(true);
    expect(mockConfig.auth.backupPatExpiry instanceof Date).toBe(true);
    expect(mockConfig.auth.useBackupPat).toBe(false);
    expect(mockConfig.auth.backupPatCreatedAt instanceof Date).toBe(true);
  });

  it('should support optional backup PAT fields', () => {
    const configWithoutBackup: any = {
      apiBaseUrl: 'https://jira.corp.adobe.com/rest/api/2',
      logFile: '/app/logs/jira-api.log',
      auth: {
        email: 'test@adobe.com',
        token: 'base-token',
        pat: 'primary-token-abc123',
        patExpiry: new Date('2026-02-15T10:30:00Z'),
        usePat: true,
        // No backup PAT fields
      },
      maxResults: 50,
      timeout: 30000,
      strictSSL: true,
      useIpaas: false,
    };

    // Validate that config can be created without backup PAT
    expect(configWithoutBackup.auth.pat).toBe('primary-token-abc123');
    expect(configWithoutBackup.auth.backupPat).toBeUndefined();
    expect(configWithoutBackup.auth.useBackupPat).toBeUndefined();
  });

  it('should validate Date expiry field types', () => {
    const patExpiry = new Date('2026-02-15T10:30:00Z');
    const backupPatExpiry = new Date('2026-03-15T10:30:00Z');
    const backupPatCreatedAt = new Date('2026-01-15T10:30:00Z');

    expect(patExpiry.getFullYear()).toBe(2026);
    expect(patExpiry.getMonth()).toBe(1); // February is month 1
    expect(patExpiry.getDate()).toBe(15);

    expect(backupPatExpiry.getFullYear()).toBe(2026);
    expect(backupPatExpiry.getMonth()).toBe(2); // March is month 2
    expect(backupPatExpiry.getDate()).toBe(15);

    expect(backupPatCreatedAt.getFullYear()).toBe(2026);
    expect(backupPatCreatedAt.getMonth()).toBe(0); // January is month 0
    expect(backupPatCreatedAt.getDate()).toBe(15);
  });

  it('should handle empty backup PAT gracefully', () => {
    const emptyBackupConfig = {
      apiBaseUrl: 'https://jira.corp.adobe.com/rest/api/2',
      logFile: '/app/logs/jira-api.log',
      auth: {
        email: 'test@adobe.com',
        token: 'base-token',
        pat: 'primary-token-abc123',
        backupPat: '', // Empty backup PAT
        useBackupPat: false, // Not using backup
      },
      maxResults: 50,
      timeout: 30000,
      strictSSL: true,
      useIpaas: false,
    };

    // Empty backup PAT is allowed
    expect(emptyBackupConfig.auth.backupPat).toBe('');
    expect(emptyBackupConfig.auth.useBackupPat).toBe(false);
  });

  it('should support all backup PAT metadata fields together', () => {
    const fullBackupConfig = {
      auth: {
        email: 'test@adobe.com',
        token: 'base-token',
        pat: 'primary-token-abc123',
        patExpiry: new Date('2026-02-15T10:30:00Z'),
        usePat: true,
        backupPat: 'backup-token-xyz789',
        backupPatExpiry: new Date('2026-03-15T10:30:00Z'),
        useBackupPat: false,
        backupPatCreatedAt: new Date('2026-01-15T10:30:00Z'),
      },
    };

    // All fields should be accessible
    expect(fullBackupConfig.auth.backupPat).toBeDefined();
    expect(fullBackupConfig.auth.backupPatExpiry).toBeDefined();
    expect(fullBackupConfig.auth.useBackupPat).toBeDefined();
    expect(fullBackupConfig.auth.backupPatCreatedAt).toBeDefined();

    // Values should be correct
    expect(fullBackupConfig.auth.backupPat).toBe('backup-token-xyz789');
    expect(fullBackupConfig.auth.useBackupPat).toBe(false);
  });
});

describe('BackupPATValidation', () => {
  it('should validate PAT format correctly', () => {
    // Valid PAT formats
    expect(isValidPatFormat('token-abc123')).toBe(true);
    expect(isValidPatFormat('token_abc123')).toBe(true);
    expect(isValidPatFormat('abc123')).toBe(true);
    expect(isValidPatFormat('token-XYZ_789')).toBe(true);

    // Invalid PAT formats
    expect(isValidPatFormat('')).toBe(false);
    expect(isValidPatFormat('token@invalid')).toBe(false);
    expect(isValidPatFormat('token with spaces')).toBe(false);
    expect(isValidPatFormat('token!@#$%')).toBe(false);
    expect(isValidPatFormat(null as any)).toBe(false);
    expect(isValidPatFormat(undefined as any)).toBe(false);
  });

  it('should detect expired backup PAT correctly', () => {
    const pastDate = new Date('2020-01-01T00:00:00Z');
    const futureDate = new Date('2030-01-01T00:00:00Z');

    // Expired PAT
    expect(isBackupPatExpired(pastDate)).toBe(true);

    // Not expired
    expect(isBackupPatExpired(futureDate)).toBe(false);

    // No expiry date
    expect(isBackupPatExpired(undefined)).toBe(false);
    expect(isBackupPatExpired(null as any)).toBe(false);
  });

  it('should validate backup PAT validity', () => {
    // Valid backup PAT
    expect(isBackupPatValid('backup-token-xyz789')).toBe(true);
    expect(isBackupPatValid('token123')).toBe(true);

    // Invalid backup PAT
    expect(isBackupPatValid('')).toBe(false);
    expect(isBackupPatValid(undefined)).toBe(false);
    expect(isBackupPatValid(null as any)).toBe(false);
    expect(isBackupPatValid('invalid@token')).toBe(false);
  });

  it('should determine when to use backup PAT', () => {
    const futureDate = new Date('2030-01-01T00:00:00Z');

    // Should use backup PAT: flag true, valid PAT, future expiry
    const validConfig = {
      apiBaseUrl: 'https://jira.corp.adobe.com/rest/api/2',
      logFile: '/app/logs/jira-api.log',
      auth: {
        email: 'test@adobe.com',
        token: 'base-token',
        backupPat: 'backup-token-xyz789',
        backupPatExpiry: futureDate,
        useBackupPat: true,
      },
      maxResults: 50,
      timeout: 30000,
      strictSSL: true,
      useIpaas: false,
    };

    expect(shouldUseBackupPat(validConfig as any)).toBe(true);

    // Should not use: flag false
    const disabledConfig = {
      ...validConfig,
      auth: { ...validConfig.auth, useBackupPat: false },
    };
    expect(shouldUseBackupPat(disabledConfig as any)).toBe(false);

    // Should not use: no backup PAT
    const noBackupConfig = {
      ...validConfig,
      auth: { ...validConfig.auth, backupPat: '' },
    };
    expect(shouldUseBackupPat(noBackupConfig as any)).toBe(false);

    // Should not use: expired backup PAT
    const expiredConfig = {
      ...validConfig,
      auth: {
        ...validConfig.auth,
        backupPatExpiry: new Date('2020-01-01T00:00:00Z'),
      },
    };
    expect(shouldUseBackupPat(expiredConfig as any)).toBe(false);
  });

  it('should handle backup PAT expiry edge cases', () => {
    // Current time
    const now = new Date();

    // Should be expired (1ms in the past)
    const expiredByOne = new Date(now.getTime() - 1);
    expect(isBackupPatExpired(expiredByOne)).toBe(true);

    // Should not be expired (1ms in the future)
    const expiresInOne = new Date(now.getTime() + 1);
    expect(isBackupPatExpired(expiresInOne)).toBe(false);
  });
});
