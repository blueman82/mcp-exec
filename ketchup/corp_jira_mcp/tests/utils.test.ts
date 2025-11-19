import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';

const originalEnv = process.env;

describe('buildJiraAuthHeaders', () => {
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

  it('should return Bearer token when usePat=true', async () => {
    process.env.JIRA_USE_PAT_AUTH = 'true';
    process.env.JIRA_PAT = 'my_pat_token_12345';
    const { buildJiraAuthHeaders } = await import('../dist/corp_jira_mcp/common/utils.js');
    const { config } = await import('../dist/corp_jira_mcp/common/config.js');

    const headers = buildJiraAuthHeaders(config);

    expect(headers.Authorization).toBe('Bearer my_pat_token_12345');
    expect(headers['Content-Type']).toBe('application/json');
    expect(headers['Accept']).toBe('application/json');
  });

  it('should return iPaaS headers when useIpaas=true', async () => {
    process.env.USE_IPAAS = 'true';
    process.env.JIRA_API_KEY = 'test_api_key';
    process.env.JIRA_IMS_TOKEN = 'test_ims_token';
    delete process.env.JIRA_EMAIL;
    delete process.env.JIRA_PERSONAL_ACCESS_TOKEN;

    const { buildJiraAuthHeaders } = await import('../dist/corp_jira_mcp/common/utils.js');
    const { config } = await import('../dist/corp_jira_mcp/common/config.js');

    const headers = buildJiraAuthHeaders(config);

    expect(headers.Authorization).toBe('test_ims_token');
    expect(headers.Api_key).toBe('test_api_key');
    expect(headers['Content-Type']).toBe('application/json');
    expect(headers['Accept']).toBe('application/json');
  });

  it('should return Basic Auth when both usePat and useIpaas are false', async () => {
    process.env.JIRA_USE_PAT_AUTH = 'false';
    process.env.USE_IPAAS = 'false';
    process.env.JIRA_EMAIL = 'user@adobe.com';
    process.env.JIRA_PERSONAL_ACCESS_TOKEN = 'direct_token';

    const { buildJiraAuthHeaders } = await import('../dist/corp_jira_mcp/common/utils.js');
    const { config } = await import('../dist/corp_jira_mcp/common/config.js');

    const headers = buildJiraAuthHeaders(config);

    const expectedAuth = `Basic ${Buffer.from('user@adobe.com:direct_token').toString('base64')}`;
    expect(headers.Authorization).toBe(expectedAuth);
    expect(headers['Content-Type']).toBe('application/json');
    expect(headers['Accept']).toBe('application/json');
  });

  it('should throw error when PAT is required but missing', async () => {
    process.env.JIRA_USE_PAT_AUTH = 'true';
    delete process.env.JIRA_PAT;

    const { buildJiraAuthHeaders } = await import('../dist/corp_jira_mcp/common/utils.js');
    const { config } = await import('../dist/corp_jira_mcp/common/config.js');

    expect(() => buildJiraAuthHeaders(config)).toThrow('PAT authentication is enabled but no PAT token is configured');
  });

  it('should throw error when iPaaS requires API key but missing', async () => {
    process.env.USE_IPAAS = 'true';
    delete process.env.JIRA_API_KEY;
    process.env.JIRA_IMS_TOKEN = 'test_ims_token';
    delete process.env.JIRA_EMAIL;
    delete process.env.JIRA_PERSONAL_ACCESS_TOKEN;

    // Config creation will throw since API key is required in iPaaS mode
    expect(async () => {
      await import('../dist/corp_jira_mcp/common/config.js');
    }).rejects.toThrow('JIRA_API_KEY environment variable is required when using iPaaS');
  });

  it('should throw error when basic auth requires email but missing', async () => {
    process.env.JIRA_USE_PAT_AUTH = 'false';
    process.env.USE_IPAAS = 'false';
    delete process.env.JIRA_EMAIL;
    process.env.JIRA_PERSONAL_ACCESS_TOKEN = 'token';

    // Config creation will throw since email is required for basic auth
    expect(async () => {
      await import('../dist/corp_jira_mcp/common/config.js');
    }).rejects.toThrow();
  });

  it('should include Content-Type header in all auth methods', async () => {
    process.env.JIRA_USE_PAT_AUTH = 'true';
    process.env.JIRA_PAT = 'my_pat_token';

    const { buildJiraAuthHeaders } = await import('../dist/corp_jira_mcp/common/utils.js');
    const { config } = await import('../dist/corp_jira_mcp/common/config.js');

    const headers = buildJiraAuthHeaders(config);

    expect(headers['Content-Type']).toBe('application/json');
    expect(headers['Accept']).toBe('application/json');
  });

  it('should prioritize usePat over basic auth when both are available', async () => {
    process.env.JIRA_USE_PAT_AUTH = 'true';
    process.env.JIRA_PAT = 'pat_token_12345';
    process.env.JIRA_EMAIL = 'user@adobe.com';
    process.env.JIRA_PERSONAL_ACCESS_TOKEN = 'basic_auth_token';

    const { buildJiraAuthHeaders } = await import('../dist/corp_jira_mcp/common/utils.js');
    const { config } = await import('../dist/corp_jira_mcp/common/config.js');

    const headers = buildJiraAuthHeaders(config);

    // Should use PAT, not basic auth
    expect(headers.Authorization).toBe('Bearer pat_token_12345');
  });

  it('should prioritize useIpaas over other methods', async () => {
    process.env.USE_IPAAS = 'true';
    process.env.JIRA_API_KEY = 'test_api_key';
    process.env.JIRA_IMS_TOKEN = 'test_ims_token';
    process.env.JIRA_USE_PAT_AUTH = 'true';
    process.env.JIRA_PAT = 'pat_token';
    delete process.env.JIRA_EMAIL;
    delete process.env.JIRA_PERSONAL_ACCESS_TOKEN;

    const { buildJiraAuthHeaders } = await import('../dist/corp_jira_mcp/common/utils.js');
    const { config } = await import('../dist/corp_jira_mcp/common/config.js');

    const headers = buildJiraAuthHeaders(config);

    // Should use iPaaS headers, not PAT
    expect(headers.Authorization).toBe('test_ims_token');
    expect(headers.Api_key).toBe('test_api_key');
  });

  it('should include optional iPaaS fields when provided', async () => {
    process.env.USE_IPAAS = 'true';
    process.env.JIRA_API_KEY = 'test_api_key';
    process.env.JIRA_IMS_TOKEN = 'test_ims_token';
    process.env.JIRA_USERNAME = 'optional_user';
    process.env.JIRA_PASSWORD = 'optional_pass';
    delete process.env.JIRA_EMAIL;
    delete process.env.JIRA_PERSONAL_ACCESS_TOKEN;

    const { buildJiraAuthHeaders } = await import('../dist/corp_jira_mcp/common/utils.js');
    const { config } = await import('../dist/corp_jira_mcp/common/config.js');

    const headers = buildJiraAuthHeaders(config);

    expect(headers.Authorization).toBe('test_ims_token');
    expect(headers.Api_key).toBe('test_api_key');
    expect(headers.Username).toBe('optional_user');
    expect(headers.Password).toBe('optional_pass');
  });

  it('should not include undefined optional headers', async () => {
    process.env.USE_IPAAS = 'true';
    process.env.JIRA_API_KEY = 'test_api_key';
    process.env.JIRA_IMS_TOKEN = 'test_ims_token';
    delete process.env.JIRA_USERNAME;
    delete process.env.JIRA_PASSWORD;
    delete process.env.JIRA_EMAIL;
    delete process.env.JIRA_PERSONAL_ACCESS_TOKEN;

    const { buildJiraAuthHeaders } = await import('../dist/corp_jira_mcp/common/utils.js');
    const { config } = await import('../dist/corp_jira_mcp/common/config.js');

    const headers = buildJiraAuthHeaders(config);

    expect(headers.Username).toBeUndefined();
    expect(headers.Password).toBeUndefined();
  });
});
