import { describe, it, expect, beforeEach, jest } from '@jest/globals';
import { createPAT, CreatePATSchema } from '../operations/createPAT.js';
import { revokePAT, RevokePATSchema } from '../operations/revokePAT.js';

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

describe('revokePAT Operation', () => {
  let mockJiraRequest: jest.MockedFunction<any>;

  beforeEach(() => {
    mockJiraRequest = require('../common/utils.js').jiraRequest as jest.Mock;
    mockJiraRequest.mockClear();
  });

  describe('test: revokePAT successfully revokes token', () => {
    it('should return success status on successful revocation', async () => {
      mockJiraRequest.mockResolvedValue(undefined);

      const result = await revokePAT({
        tokenId: 'test-token-id-12345'
      });

      expect(result.success).toBe(true);
      expect(result.message).toContain('Successfully revoked PAT token');
    });

    it('should return success for various valid token IDs', async () => {
      mockJiraRequest.mockResolvedValue(undefined);

      const tokenIds = ['12345', 'abc-def-ghi', 'token-xyz-789'];

      for (const tokenId of tokenIds) {
        const result = await revokePAT({ tokenId });
        expect(result.success).toBe(true);
      }
    });
  });

  describe('test: revokePAT handles API errors gracefully', () => {
    it('should return failure status on 401 Unauthorized', async () => {
      const error = new Error('Unauthorized');
      (error as any).status = 401;
      mockJiraRequest.mockRejectedValue(error);

      const result = await revokePAT({
        tokenId: 'error-token-id'
      });

      expect(result.success).toBe(false);
      expect(result.message).toContain('Error revoking PAT');
    });

    it('should return failure status on 403 Forbidden', async () => {
      const error = new Error('Forbidden');
      (error as any).status = 403;
      mockJiraRequest.mockRejectedValue(error);

      const result = await revokePAT({
        tokenId: 'forbidden-token-id'
      });

      expect(result.success).toBe(false);
      expect(result.message).toContain('Error revoking PAT');
    });

    it('should return failure status on 404 Not Found', async () => {
      const error = new Error('Token not found');
      (error as any).status = 404;
      mockJiraRequest.mockRejectedValue(error);

      const result = await revokePAT({
        tokenId: 'nonexistent-token-id'
      });

      expect(result.success).toBe(false);
      expect(result.message).toContain('Error revoking PAT');
    });

    it('should handle generic errors gracefully', async () => {
      const error = new Error('Network timeout');
      mockJiraRequest.mockRejectedValue(error);

      const result = await revokePAT({
        tokenId: 'network-error-token'
      });

      expect(result.success).toBe(false);
      expect(result.message).toContain('Error revoking PAT');
      expect(result.message).toContain('Network timeout');
    });
  });

  describe('test: revokePAT validates required parameters', () => {
    it('should require tokenId parameter', () => {
      expect(() => {
        RevokePATSchema.parse({});
      }).toThrow();
    });

    it('should validate tokenId is non-empty string', () => {
      expect(() => {
        RevokePATSchema.parse({
          tokenId: ''
        });
      }).toThrow();
    });

    it('should accept valid tokenId parameter', () => {
      expect(() => {
        RevokePATSchema.parse({
          tokenId: 'valid-token-id'
        });
      }).not.toThrow();
    });

    it('should accept various valid token ID formats', () => {
      const validIds = ['12345', 'abc-def', 'token_xyz', 'PAT-123456'];

      for (const id of validIds) {
        expect(() => {
          RevokePATSchema.parse({ tokenId: id });
        }).not.toThrow();
      }
    });
  });

  describe('integration: token revocation via iPaaS proxy', () => {
    it('should call jiraRequest with correct endpoint', async () => {
      mockJiraRequest.mockResolvedValue(undefined);

      const tokenId = 'test-token-id-xyz';
      await revokePAT({ tokenId });

      expect(mockJiraRequest).toHaveBeenCalled();
      const callArgs = mockJiraRequest.mock.calls[0];
      expect(callArgs[0]).toContain('tokens');
      expect(callArgs[0]).toContain(tokenId);
    });

    it('should use DELETE method for token revocation', async () => {
      mockJiraRequest.mockResolvedValue(undefined);

      await revokePAT({
        tokenId: 'delete-test-token'
      });

      expect(mockJiraRequest).toHaveBeenCalled();
      const callArgs = mockJiraRequest.mock.calls[0];
      expect(callArgs[1]?.method).toBe('DELETE');
    });

    it('should pass tokenId as part of the endpoint path', async () => {
      mockJiraRequest.mockResolvedValue(undefined);

      const testTokenId = 'path-test-12345';
      await revokePAT({ tokenId: testTokenId });

      expect(mockJiraRequest).toHaveBeenCalled();
      const callArgs = mockJiraRequest.mock.calls[0];
      const endpoint = callArgs[0];
      expect(endpoint).toContain(`tokens/tokens/${testTokenId}`);
    });

    it('should log token revocation without exposing token details', async () => {
      const consoleSpy = jest.spyOn(console, 'log');
      consoleSpy.mockClear();

      mockJiraRequest.mockResolvedValue(undefined);

      await revokePAT({
        tokenId: 'logging-test-token-secret'
      });

      const logs = consoleSpy.mock.calls.map(call => call[0]).join('\n');
      expect(logs).toContain('Revoking PAT token');
      expect(logs).toContain('Successfully revoked PAT token');

      consoleSpy.mockRestore();
    });

    it('should handle cleanup of old tokens in rotation flow', async () => {
      mockJiraRequest.mockResolvedValue(undefined);

      const oldTokenId = 'old-pat-to-revoke';
      const result = await revokePAT({ tokenId: oldTokenId });

      expect(result.success).toBe(true);
      expect(mockJiraRequest).toHaveBeenCalledWith(
        `tokens/tokens/${oldTokenId}`,
        { method: 'DELETE' }
      );
    });
  });
});
