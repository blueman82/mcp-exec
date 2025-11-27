import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { ServerPool, ConnectionError, PoolExhaustedError } from '../src/pool/index.js';
import type { MCPConnection } from '../src/types/index.js';
import { ConnectionState } from '../src/types/index.js';

function createMockConnection(serverId: string): MCPConnection {
  return {
    serverId,
    state: ConnectionState.Disconnected,
    connect: vi.fn().mockResolvedValue(undefined),
    disconnect: vi.fn().mockResolvedValue(undefined),
    isConnected: vi.fn().mockReturnValue(true),
    getTools: vi.fn().mockResolvedValue([]),
  };
}

type ConnectionFactory = (serverId: string) => Promise<MCPConnection>;

describe('ServerPool', () => {
  let mockFactory: ConnectionFactory;
  let pool: ServerPool;

  beforeEach(() => {
    vi.useFakeTimers();
    mockFactory = vi.fn().mockImplementation((serverId: string) =>
      Promise.resolve(createMockConnection(serverId))
    );
    pool = new ServerPool(mockFactory, { maxConnections: 3, idleTimeoutMs: 300000 });
  });

  afterEach(async () => {
    await pool.shutdown();
    vi.useRealTimers();
  });

  test('getConnection returns new connection for unknown server', async () => {
    const conn = await pool.getConnection('server-a');

    expect(conn.serverId).toBe('server-a');
    expect(mockFactory).toHaveBeenCalledWith('server-a');
    expect(conn.connect).toHaveBeenCalled();
  });

  test('getConnection returns cached connection', async () => {
    const conn1 = await pool.getConnection('server-a');
    const conn2 = await pool.getConnection('server-a');

    expect(conn1).toBe(conn2);
    expect(mockFactory).toHaveBeenCalledTimes(1);
  });

  test('releaseConnection marks for cleanup', async () => {
    const conn = await pool.getConnection('server-a');
    pool.releaseConnection('server-a');

    vi.advanceTimersByTime(300001);
    await pool.runCleanup();

    expect(conn.disconnect).toHaveBeenCalled();
    expect(pool.getActiveCount()).toBe(0);
  });

  test('idle cleanup removes stale connections', async () => {
    const conn = await pool.getConnection('server-a');
    pool.releaseConnection('server-a');

    vi.advanceTimersByTime(300001);
    await pool.runCleanup();

    expect(conn.disconnect).toHaveBeenCalled();

    const conn2 = await pool.getConnection('server-a');
    expect(mockFactory).toHaveBeenCalledTimes(2);
    expect(conn2).not.toBe(conn);
  });

  test('respects max connection limit', async () => {
    await pool.getConnection('server-a');
    await pool.getConnection('server-b');
    await pool.getConnection('server-c');

    await expect(pool.getConnection('server-d')).rejects.toThrow(PoolExhaustedError);
  });

  test('LRU eviction when at max connections with released connections', async () => {
    await pool.getConnection('server-a');
    pool.releaseConnection('server-a');

    vi.advanceTimersByTime(1000);

    await pool.getConnection('server-b');
    pool.releaseConnection('server-b');

    vi.advanceTimersByTime(1000);

    await pool.getConnection('server-c');
    pool.releaseConnection('server-c');

    vi.advanceTimersByTime(1000);

    const conn = await pool.getConnection('server-d');

    expect(conn.serverId).toBe('server-d');
    expect(pool.getActiveCount()).toBe(3);
  });

  test('connection factory failure throws ConnectionError', async () => {
    const failingFactory = vi.fn().mockRejectedValue(new Error('spawn failed'));
    const failPool = new ServerPool(failingFactory, { maxConnections: 3, idleTimeoutMs: 300000 });

    await expect(failPool.getConnection('server-a')).rejects.toThrow(ConnectionError);
    await failPool.shutdown();
  });
});
