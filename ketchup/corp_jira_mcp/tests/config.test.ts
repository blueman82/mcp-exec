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
    const { config } = await import('../dist/corp_jira_mcp/common/config.js');
    expect(config.auth.pat).toBe('test_pat_token_12345');
  });

  it('should load backup PAT from environment variable', async () => {
    process.env.JIRA_BACKUP_PAT = 'backup_pat_67890';
    const { config } = await import('../corp_jira_mcp/common/config.js');
    expect(config.auth.backupPat).toBe('backup_pat_67890');
  });

  it('should default usePat to false when JIRA_USE_PAT_AUTH not set', async () => {
    delete process.env.JIRA_USE_PAT_AUTH;
    const { config } = await import('../corp_jira_mcp/common/config.js');
    expect(config.auth.usePat).toBe(false);
  });

  it('should enable usePat when JIRA_USE_PAT_AUTH is true', async () => {
    process.env.JIRA_USE_PAT_AUTH = 'true';
    const { config } = await import('../corp_jira_mcp/common/config.js');
    expect(config.auth.usePat).toBe(true);
  });

  it('should not enable usePat for truthy non-true values', async () => {
    process.env.JIRA_USE_PAT_AUTH = '1';
    const { config } = await import('../corp_jira_mcp/common/config.js');
    expect(config.auth.usePat).toBe(false);
  });

  it('should maintain backward compatibility with username/password', async () => {
    process.env.JIRA_USERNAME = 'testuser';
    process.env.JIRA_PASSWORD = 'testpass';
    const { config } = await import('../corp_jira_mcp/common/config.js');
    expect(config.auth.username).toBe('testuser');
    expect(config.auth.password).toBe('testpass');
  });

  it('should default PAT to empty string when not set', async () => {
    delete process.env.JIRA_PAT;
    const { config } = await import('../corp_jira_mcp/common/config.js');
    expect(config.auth.pat).toBe('');
  });

  it('should default backup PAT to empty string when not set', async () => {
    delete process.env.JIRA_BACKUP_PAT;
    const { config } = await import('../corp_jira_mcp/common/config.js');
    expect(config.auth.backupPat).toBe('');
  });
});
