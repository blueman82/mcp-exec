/**
 * TDD GREEN PHASE: Tests for constructIpaasHeaders function with PAT support
 *
 * These tests define the expected behavior for PAT authentication through iPaaS.
 * Implementation is now COMPLETE - all tests should PASS.
 *
 * Implementation: constructIpaasHeaders(imsToken, apiKey, pat?, username?, password?)
 * - PAT sent via x-authorization: Bearer {token} header
 * - Username/Password fallback preserved for backward compatibility
 */

import { describe, it, expect, beforeAll } from '@jest/globals';

// Set minimal environment before any imports to avoid config errors
process.env.JIRA_API_BASE_URL = 'https://test.atlassian.net/rest/api/3';
process.env.JIRA_EMAIL = 'test@adobe.com';
process.env.JIRA_PERSONAL_ACCESS_TOKEN = 'base_token';
process.env.USE_IPAAS = 'false'; // Disable iPaaS to avoid config validation

let constructIpaasHeaders: (
  imsToken: string,
  apiKey: string,
  username?: string,
  password?: string
) => Record<string, string>;

beforeAll(async () => {
  const utilsModule = await import('../dist/common/utils.js');
  constructIpaasHeaders = utilsModule.constructIpaasHeaders;
});

describe('constructIpaasHeaders with PAT - TDD GREEN PHASE', () => {
  /**
   * TDD GREEN PHASE - Implementation Complete
   *
   * Manual verification confirmed PAT authentication works through iPaaS using:
   * Headers:
   *   Authorization: {IMS_TOKEN}
   *   x-authorization: Bearer {PAT_TOKEN}
   *   Api_key: {IPAAS_API_KEY}
   *
   * Implementation (COMPLETE):
   * - PAT accepted as 3rd parameter (optional)
   * - When PAT is provided: x-authorization header set, NO Username/Password
   * - When PAT is not provided: falls back to Username/Password if available
   * - All tests should now PASS
   */

  it('should include x-authorization Bearer header when PAT is provided', () => {
    // When PAT is provided as 3rd parameter, x-authorization header should be set

    const headers = constructIpaasHeaders(
      'test-ims-token',
      'test-api-key',
      'test-pat-token-12345' // PAT parameter
    );

    // Verify x-authorization header is correctly set
    expect(headers['x-authorization']).toBe('Bearer test-pat-token-12345');
    expect(headers['Authorization']).toBe('test-ims-token');
    expect(headers['Api_key']).toBe('test-api-key');
    expect(headers['Content-Type']).toBe('application/json');
  });

  it('should NOT include Username header when PAT is provided', () => {
    // PAT takes precedence - no Username/Password headers should be set

    const headers = constructIpaasHeaders(
      'test-ims-token',
      'test-api-key',
      'test-pat-token'  // PAT parameter
    );

    // Verify no Username/Password when PAT is used
    expect(headers['Username']).toBeUndefined();
    expect(headers['Password']).toBeUndefined();
  });

  it('should NOT include x-authorization header when PAT is not provided', () => {
    // x-authorization should only be present when PAT is provided

    const headers = constructIpaasHeaders(
      'test-ims-token',
      'test-api-key'
      // No PAT, username, or password
    );

    // Verify x-authorization is not present without PAT
    expect(headers['x-authorization']).toBeUndefined();
    expect(headers['Authorization']).toBe('test-ims-token');
    expect(headers['Api_key']).toBe('test-api-key');
  });

  it('should format x-authorization with Bearer prefix correctly', () => {
    // PAT should be formatted as "Bearer {token}"

    const headers = constructIpaasHeaders(
      'test-ims-token',
      'test-api-key',
      'my-super-secret-pat-abc123xyz'
    );

    // Verify correct Bearer prefix formatting
    expect(headers['x-authorization']).toBe('Bearer my-super-secret-pat-abc123xyz');
    expect(headers['x-authorization']).toContain('Bearer ');
  });

  it('should use Username/Password headers when PAT is not provided but username/password are', () => {
    // Fallback to Username/Password when no PAT provided (backward compatibility)

    const headers = constructIpaasHeaders(
      'test-ims-token',
      'test-api-key',
      undefined,        // No PAT - use undefined explicitly
      'test-user',      // username (fallback)
      'test-password'   // password (fallback)
    );

    // Verify Username/Password fallback behavior
    expect(headers['Username']).toBe('test-user');
    expect(headers['Password']).toBe('test-password');
    expect(headers['x-authorization']).toBeUndefined();
  });

  it('should NOT include Username/Password when both PAT and credentials are provided', () => {
    // PAT takes absolute precedence over Username/Password

    // Function signature: constructIpaasHeaders(imsToken, apiKey, pat?, username?, password?)
    // When PAT is provided, username/password parameters are ignored

    const headers = constructIpaasHeaders(
      'test-ims-token',
      'test-api-key',
      'test-pat-token',   // PAT (3rd param) - takes precedence
      'test-user',        // username (4th param) - ignored when PAT exists
      'test-password'     // password (5th param) - ignored when PAT exists
    );

    // Verify PAT takes precedence - no Username/Password
    expect(headers['x-authorization']).toBe('Bearer test-pat-token');
    expect(headers['Username']).toBeUndefined();
    expect(headers['Password']).toBeUndefined();
  });
});
