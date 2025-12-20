/**
 * Unit tests for port cleanup and dynamic port allocation
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { MCPBridge } from '../src/bridge/server.js';
import { isPortInUse } from '../src/bridge/port-cleanup.js';
import type { ServerPool } from '@justanothermldude/meta-mcp-core';

function createMockPool(): ServerPool {
  return {
    getConnection: vi.fn().mockResolvedValue({
      client: {
        callTool: vi.fn().mockResolvedValue({
          content: [{ type: 'text', text: 'Tool result' }],
          isError: false,
        }),
      },
    }),
    releaseConnection: vi.fn(),
    shutdown: vi.fn().mockResolvedValue(undefined),
    getActiveCount: vi.fn().mockReturnValue(0),
    runCleanup: vi.fn().mockResolvedValue(undefined),
  } as unknown as ServerPool;
}

describe('Dynamic Port Allocation', () => {
  let bridge1: MCPBridge;
  let bridge2: MCPBridge;
  let mockPool: ServerPool;

  beforeEach(() => {
    mockPool = createMockPool();
  });

  afterEach(async () => {
    if (bridge1?.isRunning()) await bridge1.stop();
    if (bridge2?.isRunning()) await bridge2.stop();
  });

  it('should use preferred port when available', async () => {
    const preferredPort = 3200;
    bridge1 = new MCPBridge(mockPool, { port: preferredPort });

    await bridge1.start();

    expect(bridge1.getPort()).toBe(preferredPort);
  });

  it('should allocate different port when preferred is in use', async () => {
    const preferredPort = 3201;

    // Start first bridge on preferred port
    bridge1 = new MCPBridge(mockPool, { port: preferredPort });
    await bridge1.start();
    expect(bridge1.getPort()).toBe(preferredPort);

    // Start second bridge - should get different port
    bridge2 = new MCPBridge(mockPool, { port: preferredPort });
    await bridge2.start();

    expect(bridge2.getPort()).not.toBe(preferredPort);
    expect(bridge2.isRunning()).toBe(true);
  });

  it('should allow multiple bridges to run simultaneously', async () => {
    bridge1 = new MCPBridge(mockPool, { port: 3202 });
    bridge2 = new MCPBridge(mockPool, { port: 3203 });

    await bridge1.start();
    await bridge2.start();

    expect(bridge1.isRunning()).toBe(true);
    expect(bridge2.isRunning()).toBe(true);
    expect(bridge1.getPort()).not.toBe(bridge2.getPort());
  });

  it('should report actual port after start', async () => {
    bridge1 = new MCPBridge(mockPool, { port: 3204 });
    
    // Before start, getPort returns preferred port
    const beforePort = bridge1.getPort();
    
    await bridge1.start();
    
    // After start, getPort returns actual allocated port
    const afterPort = bridge1.getPort();
    
    expect(afterPort).toBe(3204);
    expect(bridge1.isRunning()).toBe(true);
  });
});

describe('isPortInUse', () => {
  let bridge: MCPBridge;
  let mockPool: ServerPool;

  beforeEach(() => {
    mockPool = createMockPool();
  });

  afterEach(async () => {
    if (bridge?.isRunning()) await bridge.stop();
  });

  it('should return false for unused port', () => {
    const unusedPort = 39999;
    expect(isPortInUse(unusedPort)).toBe(false);
  });

  it('should return true for port in use', async () => {
    const testPort = 3210;
    bridge = new MCPBridge(mockPool, { port: testPort });
    await bridge.start();

    expect(isPortInUse(testPort)).toBe(true);
  });

  it('should return false after bridge stops', async () => {
    const testPort = 3211;
    bridge = new MCPBridge(mockPool, { port: testPort });
    await bridge.start();
    expect(isPortInUse(testPort)).toBe(true);

    await bridge.stop();
    // Small delay for port release
    await new Promise((r) => setTimeout(r, 50));
    expect(isPortInUse(testPort)).toBe(false);
  });
});
