/**
 * SSH Command Manager using System SSH
 * Uses child_process to execute SSH commands via system OpenSSH
 * This approach leverages existing SSH config and handles Okta 2FA automatically
 */

import 'server-only';
import { spawn, ChildProcess } from 'child_process';

type ConnectionStatus = 'connecting' | 'awaiting_okta' | 'connected' | 'failed' | 'disconnected';

interface ServerConfig {
  host: string;
}

class SSHCommandManager {
  private config: Map<string, ServerConfig> = new Map();
  private connectionStatus: Map<string, { status: ConnectionStatus; error?: string }> = new Map();
  private activeProcesses: Map<string, ChildProcess> = new Map();

  constructor() {
    // Server configurations - using SSH config aliases
    this.config.set('prod1', {
      host: 'ketchup-prod1', // SSH config alias
    });

    this.config.set('prod2', {
      host: 'ketchup-prod2', // SSH config alias
    });
  }

  /**
   * Get current connection status for polling
   */
  getConnectionStatus(server: string): { status: ConnectionStatus; error?: string } {
    return this.connectionStatus.get(server) || { status: 'disconnected' };
  }

  /**
   * Test SSH connection by running a simple command
   * This initiates the Okta 2FA flow if needed
   */
  connectInBackground(server: string): void {
    const config = this.config.get(server);
    if (!config) {
      this.connectionStatus.set(server, {
        status: 'failed',
        error: `Unknown server: ${server}`,
      });
      return;
    }

    this.connectionStatus.set(server, { status: 'connecting' });

    // Test connection with a command that requires authentication
    // Disable ControlMaster to force fresh connection and trigger Okta 2FA
    const sshProcess = spawn('ssh', [
      '-o', 'ControlMaster=no',  // Force fresh connection, no multiplexing
      '-o', 'ControlPath=none',  // Don't use control sockets
      config.host,
      'whoami',  // Simple command that requires authenticated shell
    ]);

    let stdout = '';
    let stderr = '';

    sshProcess.stdout.on('data', (data: Buffer) => {
      stdout += data.toString();

      // If we get output from whoami, auth succeeded
      if (stdout.trim().length > 0) {
        this.connectionStatus.set(server, { status: 'connected' });
      }
    });

    sshProcess.stderr.on('data', (data: Buffer) => {
      stderr += data.toString();
      const msg = data.toString().toLowerCase();

      // Detect Okta 2FA prompt
      if (msg.includes('duo') || msg.includes('push') || msg.includes('passcode')) {
        this.connectionStatus.set(server, { status: 'awaiting_okta' });
      }
    });

    sshProcess.on('close', (code: number) => {
      if (code === 0 && stdout.trim().length > 0) {
        this.connectionStatus.set(server, { status: 'connected' });
      } else if (code !== 0) {
        this.connectionStatus.set(server, {
          status: 'failed',
          error: stderr || `SSH connection failed with exit code ${code}`,
        });
      }
    });

    sshProcess.on('error', (err: Error) => {
      console.error(`[SSH] ✗ Connection error:`, err.message);
      this.connectionStatus.set(server, {
        status: 'failed',
        error: err.message,
      });
    });
  }

  /**
   * Execute a command on the remote server
   */
  async executeCommand(
    server: string,
    command: string
  ): Promise<{ stdout: string; stderr: string }> {
    const config = this.config.get(server);
    if (!config) {
      throw new Error(`Unknown server: ${server}`);
    }

    return new Promise((resolve, reject) => {
      const sshProcess = spawn('ssh', [config.host, command]);

      let stdout = '';
      let stderr = '';

      sshProcess.stdout.on('data', (data: Buffer) => {
        stdout += data.toString();
      });

      sshProcess.stderr.on('data', (data: Buffer) => {
        stderr += data.toString();
      });

      sshProcess.on('close', (code: number) => {
        if (code === 0) {
          resolve({ stdout, stderr });
        } else {
          reject(new Error(`Command failed with exit code ${code}: ${stderr}`));
        }
      });

      sshProcess.on('error', (err: Error) => {
        reject(err);
      });
    });
  }

  /**
   * Stream command output (for docker logs -f)
   */
  streamCommand(
    server: string,
    command: string,
    onData: (data: string) => void,
    onError: (err: Error) => void
  ): () => void {
    const config = this.config.get(server);
    if (!config) {
      onError(new Error(`Unknown server: ${server}`));
      return () => {};
    }

    const sshProcess = spawn('ssh', [config.host, command]);
    const processId = `${server}-${Date.now()}`;
    this.activeProcesses.set(processId, sshProcess);

    sshProcess.stdout.on('data', (data: Buffer) => {
      onData(data.toString());
    });

    sshProcess.stderr.on('data', (data: Buffer) => {
      onData(data.toString());
    });

    sshProcess.on('error', (err: Error) => {
      onError(err);
    });

    sshProcess.on('close', (code: number) => {
      this.activeProcesses.delete(processId);
    });

    // Return cleanup function
    return () => {
      if (sshProcess && !sshProcess.killed) {
        sshProcess.kill();
        this.activeProcesses.delete(processId);
      }
    };
  }

  /**
   * Check if connected (not really needed with system SSH, but kept for API compatibility)
   */
  isConnected(server: string): boolean {
    const status = this.connectionStatus.get(server);
    return status?.status === 'connected';
  }

  /**
   * Disconnect (cleanup any active processes)
   */
  disconnect(server: string): void {
    this.connectionStatus.set(server, { status: 'disconnected' });

    // Kill any active processes for this server
    this.activeProcesses.forEach((process, processId) => {
      if (processId.startsWith(server)) {
        process.kill();
        this.activeProcesses.delete(processId);
      }
    });
  }

  /**
   * Disconnect all
   */
  disconnectAll(): void {
    this.config.forEach((_, server) => {
      this.disconnect(server);
    });
  }
}

// Singleton instance
export const sshCommandManager = new SSHCommandManager();
