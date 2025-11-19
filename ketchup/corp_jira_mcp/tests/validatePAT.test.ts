import { describe, it, expect, beforeEach, jest } from '@jest/globals';
import { validatePAT, ValidatePATSchema } from '../operations/validatePAT.js';

// Mock the jiraRequest function
jest.mock('../common/utils.js', () => ({
  jiraRequest: jest.fn() as jest.MockedFunction<typeof jest.fn>,
  buildUrl: jest.fn(),
  verifyAuthentication: jest.fn(),
  buildJiraAuthHeaders: jest.fn(),
  setCurrentAuthToken: jest.fn()
}));

describe('validatePAT Operation', () => {
  let mockJiraRequest: jest.MockedFunction<any>;

  beforeEach(() => {
    mockJiraRequest = require('../common/utils.js').jiraRequest as jest.Mock;
    mockJiraRequest.mockClear();
  });

  describe('test: validatePAT successfully validates token', () => {
    it('should return valid=true for working token', async () => {
      mockJiraRequest.mockResolvedValue({
        accountId: 'user123',
        displayName: 'Test User'
      });

      const result = await validatePAT({
        token: 'valid_test_token_xyz'
      });

      expect(result.success).toBe(true);
      expect(result.valid).toBe(true);
      expect(result.message).toContain('valid');
    });

    it('should return valid=true for various valid tokens', async () => {
      mockJiraRequest.mockResolvedValue({
        accountId: 'user456',
        displayName: 'Another User'
      });

      const validTokens = [
        'token-abc-123',
        'pat_xyz_789',
        'very_long_token_with_many_characters_that_is_valid'
      ];

      for (const token of validTokens) {
        const result = await validatePAT({ token });
        expect(result.valid).toBe(true);
        expect(result.success).toBe(true);
      }
    });
  });

  describe('test: validatePAT handles invalid tokens', () => {
    it('should return valid=false for invalid token', async () => {
      const error = new Error('Unauthorized');
      (error as any).status = 401;
      mockJiraRequest.mockRejectedValue(error);

      const result = await validatePAT({
        token: 'invalid_token'
      });

      expect(result.success).toBe(false);
      expect(result.valid).toBe(false);
      expect(result.message).toContain('Token validation failed');
    });

    it('should handle expired token gracefully', async () => {
      const error = new Error('Unauthorized: Token expired');
      (error as any).status = 401;
      mockJiraRequest.mockRejectedValue(error);

      const result = await validatePAT({
        token: 'expired_token'
      });

      expect(result.valid).toBe(false);
      expect(result.message).not.toContain('expired_token');
    });

    it('should not expose sensitive error details', async () => {
      const error = new Error('Invalid credentials provided');
      (error as any).status = 401;
      mockJiraRequest.mockRejectedValue(error);

      const result = await validatePAT({
        token: 'secret_token_xyz'
      });

      expect(result.success).toBe(false);
      expect(result.message).not.toContain('credentials');
      expect(result.message).not.toContain('secret_token');
    });

    it('should handle network errors without exposing details', async () => {
      const error = new Error('Network timeout');
      mockJiraRequest.mockRejectedValue(error);

      const result = await validatePAT({
        token: 'network_error_token'
      });

      expect(result.valid).toBe(false);
      expect(result.message).not.toContain('timeout');
    });
  });

  describe('test: validatePAT validates parameters', () => {
    it('should require token parameter', () => {
      expect(() => {
        ValidatePATSchema.parse({});
      }).toThrow();
    });

    it('should validate token is non-empty string', () => {
      expect(() => {
        ValidatePATSchema.parse({
          token: ''
        });
      }).toThrow();
    });

    it('should validate token is string', () => {
      expect(() => {
        ValidatePATSchema.parse({
          token: 123
        });
      }).toThrow();
    });

    it('should accept valid token parameter', () => {
      expect(() => {
        ValidatePATSchema.parse({
          token: 'valid-token-string'
        });
      }).not.toThrow();
    });
  });

  describe('test: validatePAT handles empty token', () => {
    it('should return invalid for empty token', async () => {
      const result = await validatePAT({
        token: '   '
      });

      expect(result.valid).toBe(false);
      expect(result.success).toBe(false);
      expect(result.message).toContain('Token validation failed');
    });
  });

  describe('integration: token validation via API', () => {
    it('should call jiraRequest with correct endpoint', async () => {
      mockJiraRequest.mockResolvedValue({
        accountId: 'test-user',
        displayName: 'Test User'
      });

      await validatePAT({
        token: 'test-token-abc'
      });

      expect(mockJiraRequest).toHaveBeenCalled();
      const callArgs = mockJiraRequest.mock.calls[0];
      expect(callArgs[0]).toContain('myself');
    });

    it('should use GET method for validation', async () => {
      mockJiraRequest.mockResolvedValue({
        accountId: 'test-user',
        displayName: 'Test User'
      });

      await validatePAT({
        token: 'test-token-abc'
      });

      expect(mockJiraRequest).toHaveBeenCalled();
      const callArgs = mockJiraRequest.mock.calls[0];
      expect(callArgs[1]?.method).toBe('GET');
    });

    it('should pass token in Authorization header', async () => {
      mockJiraRequest.mockResolvedValue({
        accountId: 'test-user',
        displayName: 'Test User'
      });

      const testToken = 'validation-test-token-xyz';
      await validatePAT({
        token: testToken
      });

      expect(mockJiraRequest).toHaveBeenCalled();
      const callArgs = mockJiraRequest.mock.calls[0];
      expect(callArgs[1]?.headers?.Authorization).toContain(`Bearer ${testToken}`);
    });

    it('should log validation attempt without exposing token', async () => {
      const consoleSpy = jest.spyOn(console, 'log');
      consoleSpy.mockClear();

      mockJiraRequest.mockResolvedValue({
        accountId: 'test-user',
        displayName: 'Test User'
      });

      await validatePAT({
        token: 'secret_token_xyz'
      });

      const logs = consoleSpy.mock.calls.map(call => call[0]).join('\n');
      expect(logs).toContain('Validating PAT token');
      expect(logs).not.toContain('secret_token_xyz');

      consoleSpy.mockRestore();
    });

    it('should support token validation in rotation flow', async () => {
      mockJiraRequest.mockResolvedValue({
        accountId: 'rotation-user',
        displayName: 'Rotation Service'
      });

      const newToken = 'newly-created-pat-token';
      const result = await validatePAT({
        token: newToken
      });

      expect(result.valid).toBe(true);
      expect(result.success).toBe(true);
      expect(mockJiraRequest).toHaveBeenCalled();
    });
  });
});
