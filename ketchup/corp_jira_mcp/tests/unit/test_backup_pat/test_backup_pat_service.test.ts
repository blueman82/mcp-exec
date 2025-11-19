import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';
import { BackupPATService } from '../../../dist/corp_jira_mcp/services/backup-pat.service.js';
import type { JiraConfig } from '../../../dist/corp_jira_mcp/common/config.js';

// Mock logger
const mockLogger = {
  info: jest.fn(),
  error: jest.fn(),
  warn: jest.fn(),
  debug: jest.fn(),
} as any;

// Mock MCP PAT operations
const mockMCPPATOperations = {
  createPAT: jest.fn(),
  validatePAT: jest.fn(),
} as any;

// Mock SecretsManager
const mockSecretsManager = {
  updateSecret: jest.fn(),
  getSecret: jest.fn(),
} as any;

describe('BackupPATService', () => {
  let service: BackupPATService;

  beforeEach(() => {
    jest.clearAllMocks();
    service = new BackupPATService(
      mockMCPPATOperations as any,
      mockSecretsManager as any,
      mockLogger as any
    );
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('createBackupPAT', () => {
    it('should create backup PAT and store in secrets', async () => {
      const mockExpiryDate = new Date(Date.now() + 90 * 24 * 60 * 60 * 1000);
      mockMCPPATOperations.createPAT.mockResolvedValueOnce({
        token: 'backup-token-123',
        expiresAt: mockExpiryDate,
      });

      const result = await service.createBackupPAT();

      expect(result.token).toBe('backup-token-123');
      expect(result.expiresAt).toEqual(mockExpiryDate);
      expect(mockMCPPATOperations.createPAT).toHaveBeenCalled();
      expect(mockSecretsManager.updateSecret).toHaveBeenCalledWith(
        'Ketchup_Token_Secrets',
        expect.objectContaining({
          ketchup_jira_pat_backup: 'backup-token-123',
        })
      );
      expect(mockLogger.info).toHaveBeenCalledWith(
        expect.stringContaining('Creating backup PAT')
      );
    });

    it('should handle backup PAT creation failure gracefully', async () => {
      const error = new Error('JIRA API rate limited');
      mockMCPPATOperations.createPAT.mockRejectedValueOnce(error);

      await expect(service.createBackupPAT()).rejects.toThrow(
        'Failed to create backup PAT'
      );

      expect(mockLogger.error).toHaveBeenCalledWith(
        expect.stringContaining('Failed to create backup PAT'),
        error
      );
    });

    it('should log audit trail for backup PAT creation', async () => {
      const mockExpiryDate = new Date(Date.now() + 90 * 24 * 60 * 60 * 1000);
      mockMCPPATOperations.createPAT.mockResolvedValueOnce({
        token: 'backup-token-456',
        expiresAt: mockExpiryDate,
      });

      await service.createBackupPAT();

      expect(mockLogger.info).toHaveBeenCalledWith(
        expect.stringContaining('Backup PAT created successfully')
      );
      expect(mockLogger.info).toHaveBeenCalledWith(
        expect.stringContaining('Backup PAT stored in secrets')
      );
    });
  });

  describe('validateBackupPAT', () => {
    it('should validate backup PAT against JIRA API', async () => {
      mockMCPPATOperations.validatePAT.mockResolvedValueOnce({ valid: true });

      const isValid = await service.validateBackupPAT('backup-token-123');

      expect(isValid).toBe(true);
      expect(mockMCPPATOperations.validatePAT).toHaveBeenCalledWith(
        'backup-token-123'
      );
    });

    it('should return false when backup PAT is invalid', async () => {
      mockMCPPATOperations.validatePAT.mockResolvedValueOnce({ valid: false });

      const isValid = await service.validateBackupPAT('invalid-token');

      expect(isValid).toBe(false);
    });

    it('should handle validation errors gracefully', async () => {
      mockMCPPATOperations.validatePAT.mockRejectedValueOnce(
        new Error('Network error')
      );

      const isValid = await service.validateBackupPAT('backup-token-123');

      expect(isValid).toBe(false);
      expect(mockLogger.warn).toHaveBeenCalledWith(
        expect.stringContaining('Failed to validate backup PAT')
      );
    });
  });

  describe('isBackupPATExpiring', () => {
    it('should detect backup PAT is expiring soon', () => {
      const soon = new Date(Date.now() + 10 * 24 * 60 * 60 * 1000); // 10 days
      const isExpiring = service.isBackupPATExpiring(soon, 14); // 14-day threshold

      expect(isExpiring).toBe(true);
    });

    it('should return false when backup PAT has plenty of time', () => {
      const future = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000); // 30 days
      const isExpiring = service.isBackupPATExpiring(future, 14); // 14-day threshold

      expect(isExpiring).toBe(false);
    });

    it('should return true when backup PAT is already expired', () => {
      const past = new Date(Date.now() - 1 * 24 * 60 * 60 * 1000); // 1 day ago
      const isExpiring = service.isBackupPATExpiring(past, 14);

      expect(isExpiring).toBe(true);
    });

    it('should handle undefined expiry date', () => {
      const isExpiring = service.isBackupPATExpiring(undefined as any, 14);

      expect(isExpiring).toBe(false);
    });
  });

  describe('useBackupPAT', () => {
    it('should toggle useBackupPat flag safely', async () => {
      const config: JiraConfig = {
        apiBaseUrl: 'https://jira.example.com/api/v2',
        logFile: '/tmp/test.log',
        auth: {
          email: 'test@example.com',
          token: 'base-token',
          pat: 'primary-token',
          backupPat: 'backup-token-123',
          useBackupPat: false,
        },
      };

      await service.useBackupPAT(config);

      expect(config.auth.useBackupPat).toBe(true);
      expect(mockSecretsManager.updateSecret).toHaveBeenCalled();
      expect(mockLogger.info).toHaveBeenCalledWith(
        expect.stringContaining('Switched to backup PAT')
      );
    });

    it('should throw error if backup PAT does not exist', async () => {
      const config: JiraConfig = {
        apiBaseUrl: 'https://jira.example.com/api/v2',
        logFile: '/tmp/test.log',
        auth: {
          email: 'test@example.com',
          token: 'base-token',
          pat: 'primary-token',
          useBackupPat: false,
        },
      };

      await expect(service.useBackupPAT(config)).rejects.toThrow(
        'No backup PAT available'
      );
    });

    it('should not update if already using backup PAT', async () => {
      const config: JiraConfig = {
        apiBaseUrl: 'https://jira.example.com/api/v2',
        logFile: '/tmp/test.log',
        auth: {
          email: 'test@example.com',
          token: 'base-token',
          pat: 'primary-token',
          backupPat: 'backup-token-123',
          useBackupPat: true,
        },
      };

      await service.useBackupPAT(config);

      expect(config.auth.useBackupPat).toBe(true);
      expect(mockLogger.info).toHaveBeenCalledWith(
        expect.stringContaining('Already using backup PAT')
      );
    });

    it('should update secrets when switching to backup PAT', async () => {
      const config: JiraConfig = {
        apiBaseUrl: 'https://jira.example.com/api/v2',
        logFile: '/tmp/test.log',
        auth: {
          email: 'test@example.com',
          token: 'base-token',
          pat: 'primary-token',
          backupPat: 'backup-token-123',
          useBackupPat: false,
        },
      };

      await service.useBackupPAT(config);

      expect(mockSecretsManager.updateSecret).toHaveBeenCalledWith(
        'Ketchup_Token_Secrets',
        expect.objectContaining({
          ketchup_jira_use_backup_pat: 'true',
        })
      );
    });
  });

  describe('rotateBackupPAT', () => {
    it('should create new backup PAT and validate it', async () => {
      const mockExpiryDate = new Date(Date.now() + 90 * 24 * 60 * 60 * 1000);
      mockMCPPATOperations.createPAT.mockResolvedValueOnce({
        token: 'new-backup-token',
        expiresAt: mockExpiryDate,
      });
      mockMCPPATOperations.validatePAT.mockResolvedValueOnce({
        valid: true,
      });

      const result = await service.rotateBackupPAT();

      expect(result.token).toBe('new-backup-token');
      expect(result.expiresAt).toEqual(mockExpiryDate);
      expect(mockMCPPATOperations.createPAT).toHaveBeenCalled();
      expect(mockMCPPATOperations.validatePAT).toHaveBeenCalledWith(
        'new-backup-token'
      );
      expect(mockLogger.info).toHaveBeenCalledWith(
        expect.stringContaining('Backup PAT rotation completed')
      );
    });

    it('should throw error if new backup PAT validation fails', async () => {
      const mockExpiryDate = new Date(Date.now() + 90 * 24 * 60 * 60 * 1000);
      mockMCPPATOperations.createPAT.mockResolvedValueOnce({
        token: 'invalid-backup-token',
        expiresAt: mockExpiryDate,
      });
      mockMCPPATOperations.validatePAT.mockResolvedValueOnce({
        valid: false,
      });

      await expect(service.rotateBackupPAT()).rejects.toThrow(
        'New backup PAT failed validation'
      );
    });
  });
});
