/**
 * Unit tests for backend-auth module
 * Tests environment variable resolution and backend auth header lookup
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { writeFileSync, unlinkSync } from 'node:fs';
import { homedir } from 'node:os';
import {
  resolveBackendAuth,
  getBackendAuthHeader,
  parseEnvFile,
  EnvVarNotFoundError,
} from '../../src/auth/index.js';
import type { ServerConfig } from '../../src/types/index.js';

describe('backend-auth', () => {
  // Store original env to restore after each test
  let originalEnv: NodeJS.ProcessEnv;

  beforeEach(() => {
    originalEnv = { ...process.env };
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  describe('resolveBackendAuth', () => {
    it('should resolve a single environment variable', () => {
      process.env.TEST_TOKEN = 'my-secret-token';

      const result = resolveBackendAuth('Bearer ${TEST_TOKEN}');

      expect(result).toBe('Bearer my-secret-token');
    });

    it('should resolve multiple environment variables', () => {
      process.env.USER = 'testuser';
      process.env.PASS = 'testpass';

      const result = resolveBackendAuth('${USER}:${PASS}');

      expect(result).toBe('testuser:testpass');
    });

    it('should return string as-is when no env vars present', () => {
      const result = resolveBackendAuth('static-value');

      expect(result).toBe('static-value');
    });

    it('should throw EnvVarNotFoundError when env var is undefined', () => {
      delete process.env.MISSING_VAR;

      expect(() => resolveBackendAuth('Bearer ${MISSING_VAR}')).toThrow(
        EnvVarNotFoundError
      );
      expect(() => resolveBackendAuth('Bearer ${MISSING_VAR}')).toThrow(
        'Environment variable not found: MISSING_VAR'
      );
    });

    it('should throw for first missing var when multiple vars are missing', () => {
      delete process.env.MISSING_ONE;
      delete process.env.MISSING_TWO;

      expect(() =>
        resolveBackendAuth('${MISSING_ONE}:${MISSING_TWO}')
      ).toThrow(EnvVarNotFoundError);
    });

    it('should handle empty string env var value', () => {
      process.env.EMPTY_VAR = '';

      const result = resolveBackendAuth('prefix-${EMPTY_VAR}-suffix');

      expect(result).toBe('prefix--suffix');
    });

    it('should handle nested-looking vars (resolves literally)', () => {
      process.env.OUTER = 'outer-value';
      process.env.INNER = 'inner-value';

      // Nested patterns like ${${INNER}} are not supported - only flat resolution
      const result = resolveBackendAuth('${OUTER}');

      expect(result).toBe('outer-value');
    });

    it('should handle complex auth header patterns', () => {
      process.env.JIRA_PAT = 'jira-personal-access-token-123';

      const result = resolveBackendAuth('Bearer ${JIRA_PAT}');

      expect(result).toBe('Bearer jira-personal-access-token-123');
    });

    it('should handle Basic auth pattern with base64', () => {
      process.env.BASIC_AUTH_CREDS = 'dXNlcjpwYXNz'; // base64 of user:pass

      const result = resolveBackendAuth('Basic ${BASIC_AUTH_CREDS}');

      expect(result).toBe('Basic dXNlcjpwYXNz');
    });
  });

  describe('getBackendAuthHeader', () => {
    it('should return resolved auth header for matching server', () => {
      process.env.JIRA_PAT = 'jira-token-abc';

      const config: ServerConfig = {
        name: 'gateway',
        command: 'node',
        backendAuth: {
          jira: 'Bearer ${JIRA_PAT}',
        },
      };

      const result = getBackendAuthHeader(config, 'jira');

      expect(result).toBe('Bearer jira-token-abc');
    });

    it('should return undefined for non-matching server name', () => {
      process.env.JIRA_PAT = 'jira-token';

      const config: ServerConfig = {
        name: 'gateway',
        command: 'node',
        backendAuth: {
          jira: 'Bearer ${JIRA_PAT}',
        },
      };

      const result = getBackendAuthHeader(config, 'confluence');

      expect(result).toBeUndefined();
    });

    it('should return undefined when backendAuth is not configured', () => {
      const config: ServerConfig = {
        name: 'simple-server',
        command: 'node',
      };

      const result = getBackendAuthHeader(config, 'jira');

      expect(result).toBeUndefined();
    });

    it('should return undefined when backendAuth is empty object', () => {
      const config: ServerConfig = {
        name: 'gateway',
        command: 'node',
        backendAuth: {},
      };

      const result = getBackendAuthHeader(config, 'jira');

      expect(result).toBeUndefined();
    });

    it('should throw EnvVarNotFoundError when auth value references missing env var', () => {
      delete process.env.MISSING_TOKEN;

      const config: ServerConfig = {
        name: 'gateway',
        command: 'node',
        backendAuth: {
          jira: 'Bearer ${MISSING_TOKEN}',
        },
      };

      expect(() => getBackendAuthHeader(config, 'jira')).toThrow(
        EnvVarNotFoundError
      );
    });

    it('should handle multiple backend auth entries', () => {
      process.env.JIRA_PAT = 'jira-token';
      process.env.CONFLUENCE_PAT = 'confluence-token';
      process.env.GITHUB_PAT = 'github-token';

      const config: ServerConfig = {
        name: 'gateway',
        command: 'node',
        backendAuth: {
          jira: 'Bearer ${JIRA_PAT}',
          confluence: 'Bearer ${CONFLUENCE_PAT}',
          github: 'token ${GITHUB_PAT}',
        },
      };

      expect(getBackendAuthHeader(config, 'jira')).toBe('Bearer jira-token');
      expect(getBackendAuthHeader(config, 'confluence')).toBe(
        'Bearer confluence-token'
      );
      expect(getBackendAuthHeader(config, 'github')).toBe('token github-token');
    });

    it('should handle static auth values (no env vars)', () => {
      const config: ServerConfig = {
        name: 'gateway',
        command: 'node',
        backendAuth: {
          'public-api': 'static-api-key-123',
        },
      };

      const result = getBackendAuthHeader(config, 'public-api');

      expect(result).toBe('static-api-key-123');
    });

    it('should handle config with URL transport', () => {
      process.env.API_KEY = 'secret-key';

      const config: ServerConfig = {
        name: 'http-gateway',
        url: 'https://api.example.com/mcp',
        backendAuth: {
          backend: 'ApiKey ${API_KEY}',
        },
      };

      const result = getBackendAuthHeader(config, 'backend');

      expect(result).toBe('ApiKey secret-key');
    });
  });

  describe('parseEnvFile inline comments', () => {
    it('strips trailing comment from double-quoted value', () => {
      const f = `${homedir()}/.test-parse-env-inline.env`;
      writeFileSync(f, 'TOKEN="abc123"  # provide via header\n');
      expect(parseEnvFile(f)).toEqual({ TOKEN: 'abc123' });
      unlinkSync(f);
    });

    it('strips trailing comment from single-quoted value', () => {
      const f = `${homedir()}/.test-parse-env-inline.env`;
      writeFileSync(f, "TOKEN='abc123'  # comment\n");
      expect(parseEnvFile(f)).toEqual({ TOKEN: 'abc123' });
      unlinkSync(f);
    });

    it('strips trailing comment from unquoted value', () => {
      const f = `${homedir()}/.test-parse-env-inline.env`;
      writeFileSync(f, 'TOKEN=abc123   # comment\n');
      expect(parseEnvFile(f)).toEqual({ TOKEN: 'abc123' });
      unlinkSync(f);
    });

    it('preserves value with no comment', () => {
      const f = `${homedir()}/.test-parse-env-inline.env`;
      writeFileSync(f, 'TOKEN="abc123"\n');
      expect(parseEnvFile(f)).toEqual({ TOKEN: 'abc123' });
      unlinkSync(f);
    });

    it('preserves empty quoted value', () => {
      const f = `${homedir()}/.test-parse-env-inline.env`;
      writeFileSync(f, 'TOKEN=""  # provide via header\n');
      expect(parseEnvFile(f)).toEqual({ TOKEN: '' });
      unlinkSync(f);
    });
  });

  describe('EnvVarNotFoundError', () => {
    it('should have correct error name', () => {
      const error = new EnvVarNotFoundError('TEST_VAR');

      expect(error.name).toBe('EnvVarNotFoundError');
    });

    it('should have descriptive error message', () => {
      const error = new EnvVarNotFoundError('MY_SECRET');

      expect(error.message).toBe('Environment variable not found: MY_SECRET');
    });

    it('should be instanceof Error', () => {
      const error = new EnvVarNotFoundError('VAR');

      expect(error).toBeInstanceOf(Error);
    });
  });
});
