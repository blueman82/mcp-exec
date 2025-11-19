import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';

// We'll need to reload the config module after setting env vars
// Store original env vars to restore after tests
const originalEnv = process.env;

describe('Config - PAT Support', () => {
  beforeEach(() => {
    // Reset modules before each test to reload config with new env vars
    jest.resetModules();
    // Clone the original environment
    process.env = { ...originalEnv };
    // Set required base config to avoid validation errors
    process.env.JIRA_EMAIL = 'test@adobe.com';
    process.env.JIRA_PERSONAL_ACCESS_TOKEN = 'base_token';
    // Ensure iPaaS mode is disabled to avoid API key validation
    // Note: Must set to 'false' rather than delete, because dotenv.config()
    // will reload from .env file if the variable is not present
    process.env.USE_IPAAS = 'false';
  });

  afterEach(() => {
    // Restore original environment
    process.env = originalEnv;
  });

  it('should load PAT from environment variable', async () => {
    process.env.JIRA_PAT = 'test_pat_token_12345';
    const { config } = await import('../common/config.js');
    expect(config.auth.pat).toBe('test_pat_token_12345');
  });

  it('should load backup PAT from environment variable', async () => {
    process.env.JIRA_BACKUP_PAT = 'backup_pat_67890';
    const { config } = await import('../common/config.js');
    expect(config.auth.backupPat).toBe('backup_pat_67890');
  });

  it('should default usePat to false when JIRA_USE_PAT_AUTH not set', async () => {
    delete process.env.JIRA_USE_PAT_AUTH;
    const { config } = await import('../common/config.js');
    expect(config.auth.usePat).toBe(false);
  });

  it('should enable usePat when JIRA_USE_PAT_AUTH is true', async () => {
    process.env.JIRA_USE_PAT_AUTH = 'true';
    const { config } = await import('../common/config.js');
    expect(config.auth.usePat).toBe(true);
  });

  it('should not enable usePat for truthy non-true values', async () => {
    process.env.JIRA_USE_PAT_AUTH = '1';
    const { config } = await import('../common/config.js');
    expect(config.auth.usePat).toBe(false);
  });

  it('should maintain backward compatibility with username/password', async () => {
    process.env.JIRA_USERNAME = 'testuser';
    process.env.JIRA_PASSWORD = 'testpass';
    const { config } = await import('../common/config.js');
    expect(config.auth.username).toBe('testuser');
    expect(config.auth.password).toBe('testpass');
  });

  it('should default PAT to empty string when not set', async () => {
    delete process.env.JIRA_PAT;
    const { config } = await import('../common/config.js');
    expect(config.auth.pat).toBe('');
  });

  it('should default backup PAT to empty string when not set', async () => {
    delete process.env.JIRA_BACKUP_PAT;
    const { config } = await import('../common/config.js');
    expect(config.auth.backupPat).toBe('');
  });
});

describe('env-aws.ts - PAT mappings', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    jest.resetModules();
    process.env = { ...originalEnv };
    // Clear any existing PAT variables
    delete process.env.JIRA_PAT;
    delete process.env.JIRA_PAT_EXPIRY;
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  it('should load JIRA_PAT from AWS Secrets', async () => {
    // Mock AWS Secrets Manager
    const mockSecretsManager = {
      send: jest.fn().mockResolvedValue({
        SecretString: JSON.stringify({
          'ketchup_jira_pat': 'test_pat_token_12345'
        })
      })
    };

    jest.doMock('@aws-sdk/client-secrets-manager', () => ({
      SecretsManagerClient: jest.fn(() => mockSecretsManager),
      GetSecretValueCommand: jest.fn((input) => input)
    }));

    const { loadSecretsFromAWS } = await import('../env-aws.js');
    await loadSecretsFromAWS();

    expect(process.env.JIRA_PAT).toBe('test_pat_token_12345');
  });

  it('should load JIRA_PAT_EXPIRY from AWS Secrets', async () => {
    const testExpiry = '2025-12-31T23:59:59Z';
    const mockSecretsManager = {
      send: jest.fn().mockResolvedValue({
        SecretString: JSON.stringify({
          'ketchup_jira_pat_expiry': testExpiry
        })
      })
    };

    jest.doMock('@aws-sdk/client-secrets-manager', () => ({
      SecretsManagerClient: jest.fn(() => mockSecretsManager),
      GetSecretValueCommand: jest.fn((input) => input)
    }));

    const { loadSecretsFromAWS } = await import('../env-aws.js');
    await loadSecretsFromAWS();

    expect(process.env.JIRA_PAT_EXPIRY).toBe(testExpiry);
  });

  it('should handle missing PAT gracefully', async () => {
    const mockSecretsManager = {
      send: jest.fn().mockResolvedValue({
        SecretString: JSON.stringify({
          'ipaas_username': 'test@example.com'
        })
      })
    };

    jest.doMock('@aws-sdk/client-secrets-manager', () => ({
      SecretsManagerClient: jest.fn(() => mockSecretsManager),
      GetSecretValueCommand: jest.fn((input) => input)
    }));

    const { loadSecretsFromAWS } = await import('../env-aws.js');
    await loadSecretsFromAWS();

    expect(process.env.JIRA_PAT).toBeUndefined();
  });

  it('should log PAT presence without exposing value', async () => {
    const consoleSpy = jest.spyOn(console, 'error');

    const mockSecretsManager = {
      send: jest.fn().mockResolvedValue({
        SecretString: JSON.stringify({
          'ketchup_jira_pat': 'secret_token_value'
        })
      })
    };

    jest.doMock('@aws-sdk/client-secrets-manager', () => ({
      SecretsManagerClient: jest.fn(() => mockSecretsManager),
      GetSecretValueCommand: jest.fn((input) => input)
    }));

    const { loadSecretsFromAWS } = await import('../env-aws.js');
    await loadSecretsFromAWS();

    const logCalls = consoleSpy.mock.calls.map(call => call[0]).join('\n');
    expect(logCalls).toContain('[REDACTED]');
    expect(logCalls).not.toContain('secret_token_value');

    consoleSpy.mockRestore();
  });
});
