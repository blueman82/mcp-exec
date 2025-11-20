import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';

const originalEnv = process.env;

describe('PAT fallback logic', () => {
  beforeEach(() => {
    jest.resetModules();
    process.env = { ...originalEnv };
    // Set required base config to avoid validation errors
    process.env.JIRA_EMAIL = 'test@adobe.com';
    process.env.JIRA_PERSONAL_ACCESS_TOKEN = 'base_token';
    process.env.USE_IPAAS = 'false';
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  it('should use primary PAT when available and not expired', async () => {
    const now = new Date();
    const futureDate = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000); // 30 days from now

    process.env.JIRA_USE_PAT_AUTH = 'true';
    process.env.JIRA_PAT = 'primary-token-12345';
    process.env.JIRA_PAT_EXPIRY = futureDate.toISOString();
    process.env.JIRA_BACKUP_PAT = 'backup-token-67890';
    process.env.JIRA_BACKUP_PAT_EXPIRY = new Date(now.getTime() + 60 * 24 * 60 * 60 * 1000).toISOString();

    const { buildJiraAuthHeaders } = await import('../dist/corp_jira_mcp/common/utils.js');
    const { config } = await import('../dist/corp_jira_mcp/common/config.js');

    const headers = buildJiraAuthHeaders(config);

    expect(headers.Authorization).toBe('Bearer primary-token-12345');
    expect(headers['Content-Type']).toBe('application/json');
  });

  it('should fall back to backup PAT when primary is expired', async () => {
    const now = new Date();
    const pastDate = new Date(now.getTime() - 1 * 24 * 60 * 60 * 1000); // 1 day ago
    const futureDate = new Date(now.getTime() + 60 * 24 * 60 * 60 * 1000); // 60 days from now

    process.env.JIRA_USE_PAT_AUTH = 'true';
    process.env.JIRA_PAT = 'expired-primary-token';
    process.env.JIRA_PAT_EXPIRY = pastDate.toISOString();
    process.env.JIRA_BACKUP_PAT = 'valid-backup-token';
    process.env.JIRA_BACKUP_PAT_EXPIRY = futureDate.toISOString();

    const { buildJiraAuthHeaders } = await import('../dist/corp_jira_mcp/common/utils.js');
    const { config } = await import('../dist/corp_jira_mcp/common/config.js');

    const headers = buildJiraAuthHeaders(config);

    expect(headers.Authorization).toBe('Bearer valid-backup-token');
  });

  it('should use backup PAT when explicitly flagged', async () => {
    const now = new Date();
    const futureDate = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000); // 30 days from now

    process.env.JIRA_USE_PAT_AUTH = 'true';
    process.env.JIRA_PAT = 'primary-token';
    process.env.JIRA_PAT_EXPIRY = futureDate.toISOString();
    process.env.JIRA_USE_BACKUP_PAT = 'true'; // Explicitly using backup
    process.env.JIRA_BACKUP_PAT = 'explicitly-used-backup-token';
    process.env.JIRA_BACKUP_PAT_EXPIRY = futureDate.toISOString();

    const { buildJiraAuthHeaders } = await import('../dist/corp_jira_mcp/common/utils.js');
    const { config } = await import('../dist/corp_jira_mcp/common/config.js');

    const headers = buildJiraAuthHeaders(config);

    expect(headers.Authorization).toBe('Bearer explicitly-used-backup-token');
  });

  it('should throw error if neither PAT available', async () => {
    process.env.JIRA_USE_PAT_AUTH = 'true';
    delete process.env.JIRA_PAT;
    delete process.env.JIRA_BACKUP_PAT;

    const { buildJiraAuthHeaders } = await import('../dist/corp_jira_mcp/common/utils.js');
    const { config } = await import('../dist/corp_jira_mcp/common/config.js');

    expect(() => buildJiraAuthHeaders(config)).toThrow(
      'No PAT available (primary and backup missing or expired)'
    );
  });

  it('should throw error when primary expired and backup missing', async () => {
    const now = new Date();
    const pastDate = new Date(now.getTime() - 1 * 24 * 60 * 60 * 1000); // 1 day ago

    process.env.JIRA_USE_PAT_AUTH = 'true';
    process.env.JIRA_PAT = 'expired-primary';
    process.env.JIRA_PAT_EXPIRY = pastDate.toISOString();
    delete process.env.JIRA_BACKUP_PAT;

    const { buildJiraAuthHeaders } = await import('../dist/corp_jira_mcp/common/utils.js');
    const { config } = await import('../dist/corp_jira_mcp/common/config.js');

    expect(() => buildJiraAuthHeaders(config)).toThrow(
      'No PAT available (primary and backup missing or expired)'
    );
  });

  it('should throw error when both PATs are expired', async () => {
    const now = new Date();
    const pastDate = new Date(now.getTime() - 1 * 24 * 60 * 60 * 1000); // 1 day ago

    process.env.JIRA_USE_PAT_AUTH = 'true';
    process.env.JIRA_PAT = 'expired-primary';
    process.env.JIRA_PAT_EXPIRY = pastDate.toISOString();
    process.env.JIRA_BACKUP_PAT = 'also-expired-backup';
    process.env.JIRA_BACKUP_PAT_EXPIRY = pastDate.toISOString();

    const { buildJiraAuthHeaders } = await import('../dist/corp_jira_mcp/common/utils.js');
    const { config } = await import('../dist/corp_jira_mcp/common/config.js');

    expect(() => buildJiraAuthHeaders(config)).toThrow(
      'No PAT available (primary and backup missing or expired)'
    );
  });

  it('should prefer backup when useBackupPat is true even if primary is valid', async () => {
    const now = new Date();
    const futureDate = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000);

    process.env.JIRA_USE_PAT_AUTH = 'true';
    process.env.JIRA_PAT = 'valid-primary-token';
    process.env.JIRA_PAT_EXPIRY = futureDate.toISOString();
    process.env.JIRA_USE_BACKUP_PAT = 'true';
    process.env.JIRA_BACKUP_PAT = 'preferred-backup-token';
    process.env.JIRA_BACKUP_PAT_EXPIRY = futureDate.toISOString();

    const { buildJiraAuthHeaders } = await import('../dist/corp_jira_mcp/common/utils.js');
    const { config } = await import('../dist/corp_jira_mcp/common/config.js');

    const headers = buildJiraAuthHeaders(config);

    expect(headers.Authorization).toBe('Bearer preferred-backup-token');
  });

  it('should fallback to backup when primary is missing', async () => {
    const now = new Date();
    const futureDate = new Date(now.getTime() + 60 * 24 * 60 * 60 * 1000);

    process.env.JIRA_USE_PAT_AUTH = 'true';
    delete process.env.JIRA_PAT; // No primary PAT
    process.env.JIRA_BACKUP_PAT = 'fallback-backup-token';
    process.env.JIRA_BACKUP_PAT_EXPIRY = futureDate.toISOString();

    const { buildJiraAuthHeaders } = await import('../dist/corp_jira_mcp/common/utils.js');
    const { config } = await import('../dist/corp_jira_mcp/common/config.js');

    const headers = buildJiraAuthHeaders(config);

    expect(headers.Authorization).toBe('Bearer fallback-backup-token');
  });

  it('should not fallback when PAT authentication is disabled', async () => {
    const now = new Date();
    const futureDate = new Date(now.getTime() + 60 * 24 * 60 * 60 * 1000);

    process.env.JIRA_USE_PAT_AUTH = 'false'; // Disabled
    process.env.JIRA_PAT = 'some-primary-pat';
    process.env.JIRA_BACKUP_PAT = 'some-backup-pat';
    process.env.JIRA_BACKUP_PAT_EXPIRY = futureDate.toISOString();

    const { buildJiraAuthHeaders } = await import('../dist/corp_jira_mcp/common/utils.js');
    const { config } = await import('../dist/corp_jira_mcp/common/config.js');

    // Should use basic auth, not PAT fallback
    const headers = buildJiraAuthHeaders(config);
    expect(headers.Authorization).toContain('Basic');
    expect(headers.Authorization).not.toContain('Bearer');
  });

  it('should include base headers even with fallback', async () => {
    const now = new Date();
    const pastDate = new Date(now.getTime() - 1 * 24 * 60 * 60 * 1000);
    const futureDate = new Date(now.getTime() + 60 * 24 * 60 * 60 * 1000);

    process.env.JIRA_USE_PAT_AUTH = 'true';
    process.env.JIRA_PAT = 'expired-primary';
    process.env.JIRA_PAT_EXPIRY = pastDate.toISOString();
    process.env.JIRA_BACKUP_PAT = 'backup-token';
    process.env.JIRA_BACKUP_PAT_EXPIRY = futureDate.toISOString();

    const { buildJiraAuthHeaders } = await import('../dist/corp_jira_mcp/common/utils.js');
    const { config } = await import('../dist/corp_jira_mcp/common/config.js');

    const headers = buildJiraAuthHeaders(config);

    expect(headers.Authorization).toBe('Bearer backup-token');
    expect(headers['Content-Type']).toBe('application/json');
    expect(headers['Accept']).toBe('application/json');
  });

  it('should not interfere with iPaaS auth priority', async () => {
    const now = new Date();
    const pastDate = new Date(now.getTime() - 1 * 24 * 60 * 60 * 1000);
    const futureDate = new Date(now.getTime() + 60 * 24 * 60 * 60 * 1000);

    process.env.USE_IPAAS = 'true';
    process.env.JIRA_API_KEY = 'ipaas_api_key';
    process.env.JIRA_IMS_TOKEN = 'ipaas_ims_token';
    process.env.JIRA_USE_PAT_AUTH = 'true';
    process.env.JIRA_PAT = 'expired-primary';
    process.env.JIRA_PAT_EXPIRY = pastDate.toISOString();
    process.env.JIRA_BACKUP_PAT = 'backup-token';
    process.env.JIRA_BACKUP_PAT_EXPIRY = futureDate.toISOString();
    delete process.env.JIRA_EMAIL;
    delete process.env.JIRA_PERSONAL_ACCESS_TOKEN;

    const { buildJiraAuthHeaders } = await import('../dist/corp_jira_mcp/common/utils.js');
    const { config } = await import('../dist/corp_jira_mcp/common/config.js');

    const headers = buildJiraAuthHeaders(config);

    // iPaaS should take priority over PAT fallback
    expect(headers.Authorization).toBe('ipaas_ims_token');
    expect(headers.Api_key).toBe('ipaas_api_key');
  });

  it('should handle edge case: backup PAT with no expiry date', async () => {
    const now = new Date();
    const futureDate = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000);

    process.env.JIRA_USE_PAT_AUTH = 'true';
    process.env.JIRA_PAT = 'expired-primary';
    process.env.JIRA_PAT_EXPIRY = new Date(now.getTime() - 1 * 24 * 60 * 60 * 1000).toISOString();
    process.env.JIRA_BACKUP_PAT = 'backup-with-no-expiry';
    delete process.env.JIRA_BACKUP_PAT_EXPIRY; // No expiry date

    const { buildJiraAuthHeaders } = await import('../dist/corp_jira_mcp/common/utils.js');
    const { config } = await import('../dist/corp_jira_mcp/common/config.js');

    const headers = buildJiraAuthHeaders(config);

    // Should use backup even with no expiry date
    expect(headers.Authorization).toBe('Bearer backup-with-no-expiry');
  });
});
