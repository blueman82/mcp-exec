import type { JiraConfig } from '../common/config.js';

export interface Logger {
  info(message: string): void;
  error(message: string, error?: any): void;
  warn(message: string): void;
  debug(message: string): void;
}

export interface MCPPATOperations {
  createPAT(): Promise<{ token: string; expiresAt: Date }>;
  validatePAT(token: string): Promise<{ valid: boolean }>;
}

export interface SecretsManager {
  updateSecret(secretName: string, secretValue: any): Promise<void>;
  getSecret(secretName: string): Promise<any>;
}

export class BackupPATService {
  constructor(
    private mcpPat: MCPPATOperations,
    private secrets: SecretsManager,
    private logger: Logger
  ) {}

  async createBackupPAT(): Promise<{ token: string; expiresAt: Date }> {
    try {
      this.logger.info('Creating backup PAT');

      const result = await this.mcpPat.createPAT();

      this.logger.info('Backup PAT created successfully');

      // Store in AWS Secrets
      await this.secrets.updateSecret('Ketchup_Token_Secrets', {
        ketchup_jira_pat_backup: result.token,
        ketchup_jira_backup_pat_expiry: result.expiresAt.toISOString(),
      });

      this.logger.info('Backup PAT stored in secrets');

      return result;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      this.logger.error(`Failed to create backup PAT: ${errorMessage}`, error);
      throw new Error('Failed to create backup PAT');
    }
  }

  async validateBackupPAT(token: string): Promise<boolean> {
    try {
      this.logger.info('Validating backup PAT against JIRA API');

      const result = await this.mcpPat.validatePAT(token);

      if (result.valid) {
        this.logger.info('Backup PAT validation successful');
      } else {
        this.logger.warn('Backup PAT validation failed: token is invalid');
      }

      return result.valid;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      this.logger.warn(
        `Failed to validate backup PAT: ${errorMessage}`
      );
      return false;
    }
  }

  isBackupPATExpiring(expiryDate: Date | undefined, daysThreshold: number): boolean {
    if (!expiryDate) {
      return false;
    }

    const now = new Date();
    const daysUntilExpiry =
      (expiryDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24);

    return daysUntilExpiry < daysThreshold;
  }

  async useBackupPAT(config: JiraConfig): Promise<void> {
    try {
      // Validate backup PAT exists
      if (!config.auth.backupPat) {
        throw new Error('No backup PAT available');
      }

      // Check if already using backup PAT
      if (config.auth.useBackupPat) {
        this.logger.info('Already using backup PAT, no action needed');
        return;
      }

      // Toggle useBackupPat flag
      config.auth.useBackupPat = true;

      // Update secrets
      await this.secrets.updateSecret('Ketchup_Token_Secrets', {
        ketchup_jira_use_backup_pat: 'true',
      });

      this.logger.info('Switched to backup PAT successfully');
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);

      if (errorMessage === 'No backup PAT available') {
        this.logger.error('Cannot switch to backup PAT: no backup PAT configured');
        throw error;
      }

      this.logger.error(
        `Failed to switch to backup PAT: ${errorMessage}`,
        error
      );
      throw new Error('Failed to switch to backup PAT');
    }
  }

  async rotateBackupPAT(): Promise<{ token: string; expiresAt: Date }> {
    try {
      this.logger.info('Starting backup PAT rotation');

      // Create new backup PAT
      const newBackupPAT = await this.createBackupPAT();

      // Validate the new backup PAT
      const isValid = await this.validateBackupPAT(newBackupPAT.token);

      if (!isValid) {
        this.logger.error(
          'New backup PAT failed validation during rotation'
        );
        throw new Error('New backup PAT failed validation');
      }

      this.logger.info('Backup PAT rotation completed successfully');

      return newBackupPAT;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);

      if (errorMessage === 'New backup PAT failed validation') {
        throw error;
      }

      this.logger.error(
        `Backup PAT rotation failed: ${errorMessage}`,
        error
      );
      throw new Error('Failed to rotate backup PAT');
    }
  }
}
