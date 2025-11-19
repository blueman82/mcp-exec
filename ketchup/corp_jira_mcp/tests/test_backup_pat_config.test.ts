import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';
import type { JiraConfig } from '../corp_jira_mcp/common/config.js';

// Store original env vars to restore after tests
const originalEnv = process.env;

describe('BackupPATConfig', () => {
  beforeEach(() => {
    // Reset modules before each test to reload config with new env vars
    jest.resetModules();
    // Clone the original environment
    process.env = { ...originalEnv };
    // Set required base config to avoid validation errors
    process.env.JIRA_EMAIL = 'test@adobe.com';
    process.env.JIRA_PERSONAL_ACCESS_TOKEN = 'base_token';
    // Ensure iPaaS mode is disabled to avoid API key validation
    process.env.USE_IPAAS = 'false';
  });

  afterEach(() => {
    // Restore original environment
    process.env = originalEnv;
  });

  it('should load primary and backup PAT from environment', async () => {
    process.env.JIRA_PAT = 'primary-token-abc123';
    process.env.JIRA_BACKUP_PAT = 'backup-token-xyz789';
    const { config } = await import('../common/config.js');
    expect(config.auth.pat).toBe('primary-token-abc123');
    expect(config.auth.backupPat).toBe('backup-token-xyz789');
  });

  it('should parse backup PAT expiry as Date', async () => {
    process.env.JIRA_PAT = 'primary-token-abc123';
    process.env.JIRA_PAT_EXPIRY = '2026-02-15T10:30:00Z';
    process.env.JIRA_BACKUP_PAT = 'backup-token-xyz789';
    process.env.JIRA_BACKUP_PAT_EXPIRY = '2026-03-15T10:30:00Z';
    const { config } = await import('../common/config.js');
    expect(config.auth.backupPatExpiry).toEqual(
      new Date('2026-03-15T10:30:00Z')
    );
  });

  it('should have useBackupPat flag defaulting to false', async () => {
    process.env.JIRA_PAT = 'primary-token-abc123';
    process.env.JIRA_BACKUP_PAT = 'backup-token-xyz789';
    const { config } = await import('../common/config.js');
    expect(config.auth.useBackupPat).toBe(false);
  });

  it('should set useBackupPat flag when JIRA_USE_BACKUP_PAT is true', async () => {
    process.env.JIRA_PAT = 'primary-token-abc123';
    process.env.JIRA_BACKUP_PAT = 'backup-token-xyz789';
    process.env.JIRA_USE_BACKUP_PAT = 'true';
    const { config } = await import('../common/config.js');
    expect(config.auth.useBackupPat).toBe(true);
  });

  it('should handle missing backup PAT gracefully', async () => {
    process.env.JIRA_PAT = 'primary-token-abc123';
    delete process.env.JIRA_BACKUP_PAT;
    delete process.env.JIRA_BACKUP_PAT_EXPIRY;
    const { config } = await import('../common/config.js');
    expect(config.auth.backupPat).toBe('');
    expect(config.auth.backupPatExpiry).toBeUndefined();
    expect(config.auth.useBackupPat).toBe(false);
  });

  it('should handle missing backup PAT expiry', async () => {
    process.env.JIRA_PAT = 'primary-token-abc123';
    process.env.JIRA_BACKUP_PAT = 'backup-token-xyz789';
    delete process.env.JIRA_BACKUP_PAT_EXPIRY;
    const { config } = await import('../common/config.js');
    expect(config.auth.backupPat).toBe('backup-token-xyz789');
    expect(config.auth.backupPatExpiry).toBeUndefined();
  });

  it('should store backup PAT created timestamp', async () => {
    process.env.JIRA_PAT = 'primary-token-abc123';
    process.env.JIRA_BACKUP_PAT = 'backup-token-xyz789';
    process.env.JIRA_BACKUP_PAT_CREATED = '2025-11-15T10:30:00Z';
    const { config } = await import('../common/config.js');
    expect(config.auth.backupPatCreatedAt).toEqual(
      new Date('2025-11-15T10:30:00Z')
    );
  });

  it('should validate backup PAT format with isValidPatFormat', async () => {
    const { isValidPatFormat } = await import('../corp_jira_mcp/common/pat-validation.js');
    expect(isValidPatFormat('valid-token-123')).toBe(true);
    expect(isValidPatFormat('valid_token_456')).toBe(true);
    expect(isValidPatFormat('VALID-TOKEN-789')).toBe(true);
    expect(isValidPatFormat('')).toBe(false);
    expect(isValidPatFormat('invalid token with spaces')).toBe(false);
    expect(isValidPatFormat('invalid@token')).toBe(false);
  });

  it('should detect expired backup PAT with isBackupPatExpired', async () => {
    const { isBackupPatExpired } = await import('../corp_jira_mcp/common/pat-validation.js');
    const pastDate = new Date('2020-01-01T00:00:00Z');
    const futureDate = new Date('2030-01-01T00:00:00Z');
    expect(isBackupPatExpired(pastDate)).toBe(true);
    expect(isBackupPatExpired(futureDate)).toBe(false);
    expect(isBackupPatExpired(undefined)).toBe(false);
  });

  it('should validate backup PAT with isBackupPatValid', async () => {
    const { isBackupPatValid } = await import('../corp_jira_mcp/common/pat-validation.js');
    expect(isBackupPatValid('valid-backup-token-123')).toBe(true);
    expect(isBackupPatValid('valid_backup_token_456')).toBe(true);
    expect(isBackupPatValid('')).toBe(false);
    expect(isBackupPatValid(undefined)).toBe(false);
    expect(isBackupPatValid('invalid token')).toBe(false);
  });

  it('should determine when to use backup PAT with shouldUseBackupPat', async () => {
    const { shouldUseBackupPat } = await import('../corp_jira_mcp/common/pat-validation.js');

    // Should use backup when flag is true, token is valid, and not expired
    const validConfig = {
      auth: {
        useBackupPat: true,
        backupPat: 'valid-token-123',
        backupPatExpiry: new Date('2030-01-01T00:00:00Z')
      }
    };
    expect(shouldUseBackupPat(validConfig)).toBe(true);

    // Should not use if flag is false
    const flagFalseConfig = {
      auth: {
        useBackupPat: false,
        backupPat: 'valid-token-123',
        backupPatExpiry: new Date('2030-01-01T00:00:00Z')
      }
    };
    expect(shouldUseBackupPat(flagFalseConfig)).toBe(false);

    // Should not use if backup PAT is invalid
    const invalidTokenConfig = {
      auth: {
        useBackupPat: true,
        backupPat: 'invalid token with spaces',
        backupPatExpiry: new Date('2030-01-01T00:00:00Z')
      }
    };
    expect(shouldUseBackupPat(invalidTokenConfig)).toBe(false);

    // Should not use if backup PAT is expired
    const expiredConfig = {
      auth: {
        useBackupPat: true,
        backupPat: 'valid-token-123',
        backupPatExpiry: new Date('2020-01-01T00:00:00Z')
      }
    };
    expect(shouldUseBackupPat(expiredConfig)).toBe(false);

    // Should use if expiry is not set (no expiration)
    const noExpiryConfig = {
      auth: {
        useBackupPat: true,
        backupPat: 'valid-token-123'
      }
    };
    expect(shouldUseBackupPat(noExpiryConfig)).toBe(true);
  });

  it('should load config without primary PAT for fresh rotation scenario', async () => {
    // During rotation, we might have backup but not primary
    process.env.JIRA_EMAIL = 'test@adobe.com';
    process.env.JIRA_PERSONAL_ACCESS_TOKEN = 'base_token';
    process.env.USE_IPAAS = 'false';
    // Intentionally not setting JIRA_PAT for fresh rotation
    process.env.JIRA_BACKUP_PAT = 'backup-token-xyz789';
    process.env.JIRA_BACKUP_PAT_EXPIRY = '2026-03-15T10:30:00Z';
    const { config } = await import('../corp_jira_mcp/common/config.js');
    expect(config.auth.backupPat).toBe('backup-token-xyz789');
    expect(config.auth.backupPatExpiry).toEqual(
      new Date('2026-03-15T10:30:00Z')
    );
  });
});
