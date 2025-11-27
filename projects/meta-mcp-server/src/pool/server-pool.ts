import type { MCPConnection } from '../types/index.js';
import { ConnectionState } from '../types/index.js';

export class ConnectionError extends Error {
  constructor(message: string, public readonly cause?: Error) {
    super(message);
    this.name = 'ConnectionError';
  }
}

export class PoolExhaustedError extends Error {
  constructor(message: string = 'Connection pool exhausted') {
    super(message);
    this.name = 'PoolExhaustedError';
  }
}

export type ConnectionFactory = (serverId: string) => Promise<MCPConnection>;

export interface PoolConfig {
  maxConnections: number;
  idleTimeoutMs: number;
}

interface PoolEntry {
  connection: MCPConnection;
  lastAccessTime: number;
  inUse: boolean;
}

const DEFAULT_CONFIG: PoolConfig = {
  maxConnections: 6,
  idleTimeoutMs: 300000,
};

export class ServerPool {
  private readonly connections = new Map<string, PoolEntry>();
  private readonly factory: ConnectionFactory;
  private readonly config: PoolConfig;
  private cleanupInterval: ReturnType<typeof setInterval> | null = null;

  constructor(factory: ConnectionFactory, config: Partial<PoolConfig> = {}) {
    this.factory = factory;
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.startCleanupTimer();
  }

  async getConnection(serverId: string): Promise<MCPConnection> {
    const existing = this.connections.get(serverId);
    if (existing) {
      existing.lastAccessTime = Date.now();
      existing.inUse = true;
      return existing.connection;
    }

    if (this.connections.size >= this.config.maxConnections) {
      const evicted = this.evictLRU();
      if (!evicted) {
        throw new PoolExhaustedError();
      }
    }

    let connection: MCPConnection;
    try {
      connection = await this.factory(serverId);
      await connection.connect();
    } catch (err) {
      throw new ConnectionError(
        `Failed to create connection for ${serverId}`,
        err instanceof Error ? err : undefined
      );
    }

    this.connections.set(serverId, {
      connection,
      lastAccessTime: Date.now(),
      inUse: true,
    });

    return connection;
  }

  releaseConnection(serverId: string): void {
    const entry = this.connections.get(serverId);
    if (entry) {
      entry.inUse = false;
      entry.lastAccessTime = Date.now();
    }
  }

  async runCleanup(): Promise<void> {
    const now = Date.now();
    const toRemove: string[] = [];

    for (const [serverId, entry] of this.connections) {
      if (!entry.inUse && now - entry.lastAccessTime > this.config.idleTimeoutMs) {
        toRemove.push(serverId);
      }
    }

    for (const serverId of toRemove) {
      const entry = this.connections.get(serverId);
      if (entry) {
        await entry.connection.disconnect();
        this.connections.delete(serverId);
      }
    }
  }

  getActiveCount(): number {
    return this.connections.size;
  }

  async shutdown(): Promise<void> {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
      this.cleanupInterval = null;
    }

    for (const [, entry] of this.connections) {
      await entry.connection.disconnect();
    }
    this.connections.clear();
  }

  private evictLRU(): boolean {
    let oldest: { serverId: string; entry: PoolEntry } | null = null;

    for (const [serverId, entry] of this.connections) {
      if (!entry.inUse) {
        if (!oldest || entry.lastAccessTime < oldest.entry.lastAccessTime) {
          oldest = { serverId, entry };
        }
      }
    }

    if (oldest) {
      oldest.entry.connection.disconnect();
      this.connections.delete(oldest.serverId);
      return true;
    }

    return false;
  }

  private startCleanupTimer(): void {
    this.cleanupInterval = setInterval(() => {
      this.runCleanup();
    }, 60000);
  }
}
