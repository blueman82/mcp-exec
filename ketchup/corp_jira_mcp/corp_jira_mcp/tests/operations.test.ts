import { describe, it, expect, beforeEach, jest } from '@jest/globals';
import { createPAT, CreatePATSchema } from '../operations/createPAT.js';

// Mock the jiraRequest function
jest.mock('../common/utils.js', () => ({
  jiraRequest: jest.fn() as jest.MockedFunction<typeof jest.fn>,
  buildUrl: jest.fn(),
  verifyAuthentication: jest.fn(),
  buildJiraAuthHeaders: jest.fn(),
  setCurrentAuthToken: jest.fn()
}));

describe('createPAT Operation', () => {
  let mockJiraRequest: jest.MockedFunction<any>;

  beforeEach(() => {
    mockJiraRequest = require('../common/utils.js').jiraRequest as jest.Mock;
    mockJiraRequest.mockClear();
  });

  describe('test: createPAT returns token and expiry date', () => {
    it('should return token and expiry date from JIRA API', async () => {
      const mockResponse = {
        token: 'test_generated_pat_token_xyz789',
        expiresAt: '2025-02-17T23:59:59Z'
      };

      mockJiraRequest.mockResolvedValue(mockResponse);

      const result = await createPAT({
        tokenName: 'rotation-token-' + Date.now(),
        expiryDays: 90
      });

      expect(result.success).toBe(true);
      expect(result.data).toBeDefined();
      expect(result.data?.token).toBe('test_generated_pat_token_xyz789');
      expect(result.data?.expiresAt).toBe('2025-02-17T23:59:59Z');
    });
  });

  describe('test: createPAT formats token correctly', () => {
    it('should return token as string', async () => {
      const mockResponse = {
        token: 'abc123def456ghi789',
        expiresAt: '2025-03-20T00:00:00Z'
      };

      mockJiraRequest.mockResolvedValue(mockResponse);

      const result = await createPAT({
        tokenName: 'test-token',
        expiryDays: 90
      });

      expect(typeof result.data?.token).toBe('string');
      expect(result.data?.token).toMatch(/^[a-zA-Z0-9_-]+$/);
    });

    it('should return expiry as ISO 8601 date string', async () => {
      const mockResponse = {
        token: 'valid_token_string',
        expiresAt: '2025-04-15T14:30:45Z'
      };

      mockJiraRequest.mockResolvedValue(mockResponse);

      const result = await createPAT({
        tokenName: 'iso-date-token',
        expiryDays: 90
      });

      expect(typeof result.data?.expiresAt).toBe('string');
      // ISO 8601 format: YYYY-MM-DDTHH:mm:ssZ
      expect(result.data?.expiresAt).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/);
    });
  });

  describe('test: createPAT handles API errors gracefully', () => {
    it('should throw JiraAuthenticationError on 401 response', async () => {
      const error = new Error('Unauthorized');
      (error as any).status = 401;
      mockJiraRequest.mockRejectedValue(error);

      const result = await createPAT({
        tokenName: 'error-token',
        expiryDays: 90
      });

      expect(result.success).toBe(false);
      expect(result.message).toContain('Error creating PAT');
    });

    it('should throw JiraPermissionError on 403 response', async () => {
      const error = new Error('Forbidden');
      (error as any).status = 403;
      mockJiraRequest.mockRejectedValue(error);

      const result = await createPAT({
        tokenName: 'forbidden-token',
        expiryDays: 90
      });

      expect(result.success).toBe(false);
      expect(result.message).toContain('Error creating PAT');
    });

    it('should throw JiraResourceNotFoundError on 404 response', async () => {
      const error = new Error('Not Found');
      (error as any).status = 404;
      mockJiraRequest.mockRejectedValue(error);

      const result = await createPAT({
        tokenName: 'not-found-token',
        expiryDays: 90
      });

      expect(result.success).toBe(false);
      expect(result.message).toContain('Error creating PAT');
    });

    it('should handle generic errors gracefully', async () => {
      const error = new Error('Network timeout');
      mockJiraRequest.mockRejectedValue(error);

      const result = await createPAT({
        tokenName: 'network-error-token',
        expiryDays: 90
      });

      expect(result.success).toBe(false);
      expect(result.message).toContain('Error creating PAT');
      expect(result.message).toContain('Network timeout');
    });
  });

  describe('test: createPAT validates required parameters', () => {
    it('should require tokenName parameter', () => {
      expect(() => {
        CreatePATSchema.parse({
          expiryDays: 90
        });
      }).toThrow();
    });

    it('should require expiryDays parameter', () => {
      expect(() => {
        CreatePATSchema.parse({
          tokenName: 'test-token'
        });
      }).toThrow();
    });

    it('should validate tokenName is non-empty string', () => {
      expect(() => {
        CreatePATSchema.parse({
          tokenName: '',
          expiryDays: 90
        });
      }).toThrow();
    });

    it('should validate expiryDays is positive integer', () => {
      expect(() => {
        CreatePATSchema.parse({
          tokenName: 'test-token',
          expiryDays: -1
        });
      }).toThrow();
    });

    it('should validate expiryDays is minimum 1', () => {
      expect(() => {
        CreatePATSchema.parse({
          tokenName: 'test-token',
          expiryDays: 0
        });
      }).toThrow();
    });

    it('should accept valid parameters', () => {
      expect(() => {
        CreatePATSchema.parse({
          tokenName: 'valid-token-name',
          expiryDays: 90
        });
      }).not.toThrow();
    });

    it('should validate 90-day expiry is accepted', () => {
      expect(() => {
        CreatePATSchema.parse({
          tokenName: 'rotation-token',
          expiryDays: 90
        });
      }).not.toThrow();
    });
  });

  describe('integration: token creation via iPaaS proxy', () => {
    it('should call jiraRequest with correct endpoint', async () => {
      mockJiraRequest.mockResolvedValue({
        token: 'test_token',
        expiresAt: '2025-02-17T23:59:59Z'
      });

      await createPAT({
        tokenName: 'integration-test-token',
        expiryDays: 90
      });

      expect(mockJiraRequest).toHaveBeenCalled();
      const callArgs = mockJiraRequest.mock.calls[0];
      expect(callArgs[0]).toContain('tokens');
    });

    it('should pass tokenName and expiryDays to JIRA API', async () => {
      mockJiraRequest.mockResolvedValue({
        token: 'test_token',
        expiresAt: '2025-02-17T23:59:59Z'
      });

      const testName = 'my-token-' + Date.now();
      const testDays = 90;

      await createPAT({
        tokenName: testName,
        expiryDays: testDays
      });

      expect(mockJiraRequest).toHaveBeenCalled();
      const callArgs = mockJiraRequest.mock.calls[0];
      const body = callArgs[1]?.body;
      expect(body).toBeDefined();
      expect(body.name).toContain(testName);
      expect(body.expirationDays).toBe(testDays);
    });

    it('should use POST method for token creation', async () => {
      mockJiraRequest.mockResolvedValue({
        token: 'test_token',
        expiresAt: '2025-02-17T23:59:59Z'
      });

      await createPAT({
        tokenName: 'post-test-token',
        expiryDays: 90
      });

      expect(mockJiraRequest).toHaveBeenCalled();
      const callArgs = mockJiraRequest.mock.calls[0];
      expect(callArgs[1]?.method).toBe('POST');
    });

    it('should log token creation without exposing token value', async () => {
      const consoleSpy = jest.spyOn(console, 'log');
      consoleSpy.mockClear();

      mockJiraRequest.mockResolvedValue({
        token: 'secret_token_xyz',
        expiresAt: '2025-02-17T23:59:59Z'
      });

      await createPAT({
        tokenName: 'logging-test-token',
        expiryDays: 90
      });

      const logs = consoleSpy.mock.calls.map(call => call[0]).join('\n');
      expect(logs).toContain('Created PAT token');
      expect(logs).not.toContain('secret_token_xyz');

      consoleSpy.mockRestore();
    });
  });
});
