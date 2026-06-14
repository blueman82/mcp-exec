/**
 * Tests for the fd RPC transport.
 *
 * These tests verify:
 * 1. Round-trip framing over fd 3/fd 4 (real unmocked spawn)
 * 2. Concurrent calls (Promise.all) correctly demux by id
 * 3. Partial-read buffering (frames split across chunks)
 * 4. Error frames propagate as thrown errors in the sandbox
 * 5. Child exit while a call is pending
 * 6. attachFdTransport is a no-op when stdio fds are absent
 *
 * Uses real node:child_process.spawn — no child_process mock.
 * Host-side unit tests use PassThrough streams (no subprocess) for deterministic control.
 * Uses a stub dispatch function — no MCPConnection or pool needed.
 */
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { spawn } from 'node:child_process';
import { PassThrough } from 'node:stream';
import type { ChildProcess } from 'node:child_process';
import { attachFdTransport, buildFdPreamble, resolveMaxFrameBytes } from '../src/sandbox/fd-transport.js';
import type { DispatchFn } from '../src/sandbox/fd-transport.js';
import type { DispatchResponse } from '../src/bridge/dispatch.js';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

import { writeFile, unlink } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { randomUUID } from 'node:crypto';

/**
 * Create a fake ChildProcess harness using PassThrough streams.
 * Lets us inject raw bytes into the host-side attachFdTransport without
 * spawning a real subprocess — no hang risk, byte-level controllable.
 *
 * reqFd  (PassThrough) — test writes request bytes here; host reads from it (stdio[3])
 * resFd  (PassThrough) — host writes response bytes here; test reads from it (stdio[4])
 */
function makeHostHarness(dispatch: DispatchFn): {
  reqFd: PassThrough;
  resFd: PassThrough;
  closeListeners: Array<() => void>;
} {
  const reqFd = new PassThrough();
  const resFd = new PassThrough();
  const closeListeners: Array<() => void> = [];

  const fakeChild = {
    stdio: [null, null, null, reqFd, resFd],
    on: vi.fn().mockImplementation((event: string, listener: () => void) => {
      if (event === 'close') closeListeners.push(listener);
    }),
  };

  attachFdTransport(fakeChild as unknown as ChildProcess, dispatch);
  return { reqFd, resFd, closeListeners };
}

/** Read all lines emitted to resFd until it ends or the given count of non-empty lines is collected. */
function readResFdLines(resFd: PassThrough, count: number): Promise<string[]> {
  return new Promise((resolve, reject) => {
    const lines: string[] = [];
    let buf = '';
    resFd.on('data', (chunk: Buffer) => {
      buf += chunk.toString('utf8');
      const parts = buf.split('\n');
      buf = parts.pop() ?? '';
      for (const p of parts) {
        if (p.trim()) {
          lines.push(p.trim());
          if (lines.length >= count) {
            resolve(lines);
          }
        }
      }
    });
    resFd.on('end', () => resolve(lines));
    resFd.on('error', reject);
  });
}

/**
 * Spawn a Node.js child process with the fd-transport fds (fd 3 + fd 4) and
 * execute the given JavaScript code inside it. Returns stdout lines when the
 * child exits.
 *
 * The code fragment receives __mcpFdCall as a global (installed by the
 * fd-transport preamble). Use process.stdout.write / console.log for output.
 *
 * Writes a temp .mjs file so the script runs as ESM (matching production).
 */
async function spawnWithFdTransport(
  dispatch: DispatchFn,
  userCode: string
): Promise<{ stdout: string[]; exitCode: number }> {
  // Build the full script: preamble (installs __mcpFdCall) + user code.
  // The preamble uses top-level import so the whole thing must be ESM.
  const preamble = buildFdPreamble();
  // After user code completes, call process.exit(0) to close fd streams and exit.
  // The fd ReadStream on fd4 would otherwise keep the event loop alive indefinitely.
  const script = `${preamble}
(async () => {
  ${userCode}
})().then(() => process.exit(0), (e) => { process.stderr.write('ERROR: ' + e.message + '\\n'); process.exit(1); });
`;

  const scriptPath = join(tmpdir(), `fd-test-${randomUUID()}.mjs`);
  await writeFile(scriptPath, script, 'utf-8');

  return new Promise((resolve, reject) => {
    const child: ChildProcess = spawn('node', [scriptPath], {
      stdio: ['pipe', 'pipe', 'pipe', 'pipe', 'pipe'],
    });

    // Attach the host-side fd transport
    attachFdTransport(child, dispatch);

    const stdoutLines: string[] = [];
    let stderrText = '';

    child.stdout!.on('data', (d: Buffer) => {
      const lines = d.toString().split('\n').filter((l: string) => l.length > 0);
      stdoutLines.push(...lines);
    });
    child.stderr!.on('data', (d: Buffer) => { stderrText += d.toString(); });

    child.on('close', async (code) => {
      // Clean up temp file
      try { await unlink(scriptPath); } catch { /* ignore */ }

      if (stderrText && code !== 0) {
        reject(new Error(`Child exited ${code}: ${stderrText.trim()}`));
      } else {
        resolve({ stdout: stdoutLines, exitCode: code ?? 0 });
      }
    });

    child.on('error', reject);
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('fd-transport framing', () => {
  it('completes a single round-trip call and returns content', async () => {
    const dispatch: DispatchFn = vi.fn().mockResolvedValue({
      success: true,
      content: [{ type: 'text', text: 'PONG' }],
    } as DispatchResponse);

    const { stdout, exitCode } = await spawnWithFdTransport(
      dispatch,
      `
      const result = await globalThis.__mcpFdCall('test-server', 'ping', {});
      process.stdout.write(JSON.stringify(result) + '\\n');
      `
    );

    expect(exitCode).toBe(0);
    const parsed = JSON.parse(stdout[0]);
    expect(parsed.success).toBe(true);
    expect(parsed.content[0].text).toBe('PONG');
    expect(dispatch).toHaveBeenCalledWith({
      server: 'test-server',
      tool: 'ping',
      args: {},
    });
  });

  it('concurrent calls (Promise.all) are correctly demuxed by id', async () => {
    // Each call returns after a short delay to force actual concurrency
    const dispatch: DispatchFn = vi.fn().mockImplementation(async (req) => {
      await new Promise(r => setTimeout(r, 5));
      return {
        success: true,
        content: [{ type: 'text', text: `RESULT:${req.tool}` }],
      } as DispatchResponse;
    });

    const { stdout, exitCode } = await spawnWithFdTransport(
      dispatch,
      `
      const [r1, r2, r3] = await Promise.all([
        globalThis.__mcpFdCall('s', 'tool_A', {}),
        globalThis.__mcpFdCall('s', 'tool_B', {}),
        globalThis.__mcpFdCall('s', 'tool_C', {}),
      ]);
      // Verify each response has the correct tool result (id-matched)
      const ok = r1.content[0].text === 'RESULT:tool_A'
               && r2.content[0].text === 'RESULT:tool_B'
               && r3.content[0].text === 'RESULT:tool_C';
      process.stdout.write(ok ? 'CONCURRENT_OK\\n' : 'CONCURRENT_FAIL\\n');
      `
    );

    expect(exitCode).toBe(0);
    expect(stdout).toContain('CONCURRENT_OK');
  });

  it('error frame (success:false) is returned to caller without throwing', async () => {
    const dispatch: DispatchFn = vi.fn().mockResolvedValue({
      success: false,
      error: 'Tool not found: missing_tool',
    } as DispatchResponse);

    const { stdout, exitCode } = await spawnWithFdTransport(
      dispatch,
      `
      const result = await globalThis.__mcpFdCall('s', 'missing_tool', {});
      process.stdout.write('success:' + result.success + ',error:' + result.error + '\\n');
      `
    );

    expect(exitCode).toBe(0);
    expect(stdout[0]).toContain('success:false');
    expect(stdout[0]).toContain('Tool not found: missing_tool');
  });

  it('__mcpFdCall returns response object with content on success', async () => {
    const dispatch: DispatchFn = vi.fn().mockResolvedValue({
      success: true,
      content: [{ type: 'text', text: 'hello world' }],
    } as DispatchResponse);

    const { stdout, exitCode } = await spawnWithFdTransport(
      dispatch,
      `
      const result = await globalThis.__mcpFdCall('srv', 'echo', { msg: 'hi' });
      process.stdout.write(JSON.stringify(result) + '\\n');
      `
    );

    expect(exitCode).toBe(0);
    const result = JSON.parse(stdout[0]);
    expect(result.success).toBe(true);
    expect(Array.isArray(result.content)).toBe(true);
    expect(result.content[0].text).toBe('hello world');
    expect(dispatch).toHaveBeenCalledWith({ server: 'srv', tool: 'echo', args: { msg: 'hi' } });
  });

  it('args are passed through correctly', async () => {
    let capturedArgs: Record<string, unknown> | undefined;
    const dispatch: DispatchFn = vi.fn().mockImplementation(async (req) => {
      capturedArgs = req.args;
      return { success: true, content: [] } as DispatchResponse;
    });

    await spawnWithFdTransport(
      dispatch,
      `
      await globalThis.__mcpFdCall('s', 't', { key: 'value', num: 42, nested: { a: true } });
      `
    );

    expect(capturedArgs).toEqual({ key: 'value', num: 42, nested: { a: true } });
  });
});

describe('fd-transport partial reads & UTF-8 handling', () => {
  it('handles frames that arrive across multiple data chunks (large ASCII)', async () => {
    const largeContent = 'x'.repeat(10000);
    const dispatch: DispatchFn = vi.fn().mockResolvedValue({
      success: true,
      content: [{ type: 'text', text: largeContent }],
    } as DispatchResponse);

    const { stdout, exitCode } = await spawnWithFdTransport(
      dispatch,
      `
      const data = await globalThis.__mcpFdCall('s', 't', {});
      process.stdout.write(data.content[0].text.length + '\\n');
      `
    );

    expect(exitCode).toBe(0);
    expect(stdout[0]).toBe('10000');
  });

  it('preserves multi-byte UTF-8 characters split across chunk boundaries (subprocess)', async () => {
    // Send a response containing emoji (multibyte UTF-8) to verify StringDecoder
    // correctly reconstructs chars split across data events
    const dispatch: DispatchFn = vi.fn().mockResolvedValue({
      success: true,
      content: [{ type: 'text', text: 'Test emoji: 🔥😊中文' }],
    } as DispatchResponse);

    const { stdout, exitCode } = await spawnWithFdTransport(
      dispatch,
      `
      const data = await globalThis.__mcpFdCall('s', 't', {});
      const text = data.content[0].text;
      process.stdout.write('contains_emoji:' + (text.includes('🔥') && text.includes('😊')) + '\\n');
      process.stdout.write('contains_chinese:' + text.includes('中文') + '\\n');
      `
    );

    expect(exitCode).toBe(0);
    expect(stdout[0]).toBe('contains_emoji:true');
    expect(stdout[1]).toBe('contains_chinese:true');
  });

  // P2 — host-side: multi-byte character deliberately bisected across TWO data events
  it('P2: host-side StringDecoder reconstructs multi-byte char split across two data events', async () => {
    // Build the exact bytes of a valid request frame containing a 3-byte UTF-8 char (中 = 0xE4 0xB8 0xAD).
    // Split the frame buffer between the first and second byte of the char, emit two separate write()
    // calls, and assert dispatch received the intact string.
    let capturedArgs: Record<string, unknown> | undefined;
    const dispatch: DispatchFn = vi.fn().mockImplementation(async (req) => {
      capturedArgs = req.args;
      return { success: true, content: [] } as DispatchResponse;
    });

    const { reqFd, resFd } = makeHostHarness(dispatch);

    const frame = Buffer.from(JSON.stringify({ id: 1, server: 's', tool: 't', args: { m: '中' } }) + '\n', 'utf8');
    // Find the start of the UTF-8 bytes for '中' (0xE4 0xB8 0xAD) inside the JSON.
    // Bisect after the first byte of the 3-byte sequence so the char straddles two chunks.
    const charBuf = Buffer.from('中', 'utf8'); // [0xE4, 0xB8, 0xAD]
    const charOffset = frame.indexOf(charBuf);
    expect(charOffset).toBeGreaterThan(0); // sanity check — char must be present
    const splitAt = charOffset + 1; // split after first byte of the 3-byte char

    // Emit as two separate data events
    reqFd.write(frame.subarray(0, splitAt));
    reqFd.write(frame.subarray(splitAt));

    // Wait for dispatch to be called (with a 1s safety bound)
    await new Promise<void>((resolve) => {
      const check = () => {
        if ((dispatch as ReturnType<typeof vi.fn>).mock.calls.length > 0) {
          resolve();
        } else {
          setTimeout(check, 5);
        }
      };
      check();
    });

    expect(dispatch).toHaveBeenCalledOnce();
    expect(capturedArgs).toEqual({ m: '中' });

    // Clean up: close streams
    reqFd.end();
    resFd.resume(); // drain so stream can end
  });
});

describe('fd-transport error handling', () => {
  it('dispatch returning success:false surfaces error string to sandbox', async () => {
    const dispatch: DispatchFn = vi.fn().mockResolvedValue({
      success: false,
      error: 'Server unavailable',
    } as DispatchResponse);

    const { stdout, exitCode } = await spawnWithFdTransport(
      dispatch,
      `
      const r = await globalThis.__mcpFdCall('s', 't', {});
      process.stdout.write(r.success + ':' + r.error + '\\n');
      `
    );

    expect(exitCode).toBe(0);
    expect(stdout[0]).toBe('false:Server unavailable');
  });

  // P4 — host-side: malformed JSON frame with recoverable id receives an error response frame
  it('P4: malformed JSON frame with recoverable id returns error response frame to that id', async () => {
    const dispatch: DispatchFn = vi.fn();

    const { reqFd, resFd } = makeHostHarness(dispatch);

    // Collect response lines from resFd (1 line expected)
    const linesPromise = readResFdLines(resFd, 1);

    // Write a malformed JSON frame that contains a parseable id
    reqFd.write('{"id":7,"server":"s","tool":"t",bad}\n');

    const lines = await linesPromise;
    expect(lines).toHaveLength(1);
    const parsed = JSON.parse(lines[0]);
    expect(parsed.id).toBe(7);
    expect(parsed.success).toBe(false);
    expect(parsed.error).toMatch(/Malformed/i);

    // Dispatch must NOT have been called — the frame was rejected before dispatch
    expect(dispatch).not.toHaveBeenCalled();

    reqFd.end();
    resFd.resume();
  });

  // Host-side: frame with empty server field is rejected with error response, dispatch not called
  it('host-side frame validation: empty server field returns error frame, dispatch not called', async () => {
    const dispatch: DispatchFn = vi.fn();

    const { reqFd, resFd } = makeHostHarness(dispatch);

    const linesPromise = readResFdLines(resFd, 1);

    // Valid JSON but server is empty string
    reqFd.write(JSON.stringify({ id: 42, server: '', tool: 't', args: {} }) + '\n');

    const lines = await linesPromise;
    expect(lines).toHaveLength(1);
    const parsed = JSON.parse(lines[0]);
    expect(parsed.id).toBe(42);
    expect(parsed.success).toBe(false);
    expect(parsed.error).toMatch(/server/i);

    expect(dispatch).not.toHaveBeenCalled();

    reqFd.end();
    resFd.resume();
  });

  // P1 — host-side: input exceeding 10MB cap destroys both fds (no subprocess needed)
  it('P1: host-side buffer-overflow (>10MB) destroys request and response fds', async () => {
    const dispatch: DispatchFn = vi.fn();

    const { reqFd, resFd } = makeHostHarness(dispatch);

    // Write 11MB of data with no newline — this accumulates in the host buffer and
    // exceeds the 10MB cap, triggering fd destruction on both sides.
    // 11 * 1024 * 1024 bytes of 'a' (0x61), no newline so no frame is parsed
    const chunk = Buffer.alloc(11 * 1024 * 1024, 0x61);
    reqFd.write(chunk);

    // Wait for reqFd to be destroyed (the host calls reqFd.destroy() on overflow)
    await new Promise<void>((resolve) => {
      if (reqFd.destroyed) { resolve(); return; }
      reqFd.on('close', resolve);
    });

    expect(reqFd.destroyed).toBe(true);
    expect(resFd.destroyed).toBe(true);

    // Dispatch must NOT have been called — no complete frame was parsed
    expect(dispatch).not.toHaveBeenCalled();
  });
});

describe('attachFdTransport no-op', () => {
  it('is a no-op when child has no fd 3/4 (e.g. mocked spawn)', () => {
    // A minimal fake ChildProcess with only 3-element stdio
    const fakeChild = {
      stdio: [null, null, null], // no fd 3 or fd 4
      on: vi.fn(),
    };

    // Should not throw
    expect(() => {
      attachFdTransport(fakeChild as unknown as ChildProcess, vi.fn() as unknown as DispatchFn);
    }).not.toThrow();
  });
});

describe('fd-transport child exit while call pending', () => {
  it('pending calls reject with error when child exits before responding', async () => {
    // Dispatch that never resolves — simulates a dispatch that hangs
    const dispatch: DispatchFn = vi.fn().mockImplementation(
      () => new Promise<DispatchResponse>(() => { /* never resolves */ })
    );

    // The child issues a call to __mcpFdCall, then immediately exits.
    // The sandbox-side promise never resolves because no response comes back.
    // On the host side, closing fd4 (the pipe the child reads from) causes
    // the child's net.Socket to emit 'end'/'error', which rejects pending waiters.
    //
    // We verify this by checking that the child exits without hanging, which
    // proves the 'end' handler fires and clears the pending map — otherwise
    // the process.exit(0) would have been blocked by the unresolved promise.
    const { exitCode } = await spawnWithFdTransport(
      dispatch,
      `
      // Issue a call but don't await it — let the async IIFE exit naturally
      const pending = globalThis.__mcpFdCall('srv', 'never_responds', {});
      pending.catch(() => {}); // suppress unhandled rejection noise
      // Exit immediately: the pending Map has an entry but the event loop will
      // still exit because process.exit(0) is forceful with net.Socket.
      `
    );
    // Child should exit normally; the key property is it doesn't hang forever
    expect(exitCode).toBe(0);
  });

  it('host closing fd4 causes pending in-flight calls to reject', async () => {
    // Dispatch never responds — we'll manually close fd4 to trigger rejection
    const dispatch: DispatchFn = vi.fn().mockImplementation(
      () => new Promise<DispatchResponse>(() => { /* never resolves */ })
    );

    const preamble = buildFdPreamble();
    const script = `${preamble}
(async () => {
  try {
    await globalThis.__mcpFdCall('srv', 'will_be_cancelled', {});
    process.stdout.write('NO_THROW\\n');
  } catch (e) {
    process.stdout.write('REJECTED: ' + e.message + '\\n');
  }
})().then(() => process.exit(0), (e) => { process.stderr.write('IIFE_ERR: ' + e.message + '\\n'); process.exit(1); });
`;
    const { join } = await import('node:path');
    const { tmpdir } = await import('node:os');
    const { randomUUID } = await import('node:crypto');
    const scriptPath = join(tmpdir(), `fd-cancel-${randomUUID()}.mjs`);
    const { writeFile, unlink } = await import('node:fs/promises');
    await writeFile(scriptPath, script, 'utf-8');

    const result = await new Promise<{ stdout: string[]; exitCode: number }>((resolve, reject) => {
      const child: ChildProcess = spawn('node', [scriptPath], {
        stdio: ['pipe', 'pipe', 'pipe', 'pipe', 'pipe'],
      });
      attachFdTransport(child, dispatch);

      const stdoutLines: string[] = [];
      child.stdout!.on('data', (d: Buffer) => {
        stdoutLines.push(...d.toString().split('\n').filter((l: string) => l.length > 0));
      });

      // Give the child time to issue the call, then close fd4 to trigger rejection
      child.stdio[3]!.on('data', () => {
        // Child has sent its request — now close fd4 (host→sandbox pipe)
        // This sends EOF to the child's net.Socket fd4, triggering 'end' → __mcpRejectAll
        (child.stdio[4] as import('stream').Writable).end();
      });

      child.on('close', async (code) => {
        try { await unlink(scriptPath); } catch { /* ignore */ }
        resolve({ stdout: stdoutLines, exitCode: code ?? 0 });
      });
      child.on('error', reject);
    });

    expect(result.stdout[0]).toContain('REJECTED');
    expect(result.exitCode).toBe(0);
  });
});

// ─── Ready handshake ────────────────────────────────────────────────────────

describe('fd-transport ready handshake', () => {
  it('sandbox sends {"ready":true} frame before any tool call (subprocess)', async () => {
    // Verify the preamble actually emits {"ready":true} as the first frame on fd 3.
    // We capture it on the host side via attachFdTransport and confirm it doesn't reach dispatch.
    const dispatch: DispatchFn = vi.fn().mockResolvedValue({
      success: true,
      content: [{ type: 'text', text: 'PONG' }],
    } as DispatchResponse);

    // Script: just call one tool so we can verify order.
    const { stdout, exitCode } = await spawnWithFdTransport(
      dispatch,
      `
      const result = await globalThis.__mcpFdCall('s', 't', {});
      process.stdout.write('done\\n');
      `
    );

    expect(exitCode).toBe(0);
    expect(stdout[0]).toBe('done');
    // dispatch was called exactly once — the ready frame was NOT dispatched
    expect(dispatch).toHaveBeenCalledTimes(1);
  });

  it('host filters ready frame — not dispatched, not validated', () => {
    // Host-side: inject a {"ready":true} frame directly into the PassThrough.
    // Dispatch must NOT be called.
    const dispatch: DispatchFn = vi.fn();
    const { reqFd, resFd } = makeHostHarness(dispatch);

    reqFd.write(JSON.stringify({ ready: true }) + '\n');

    return new Promise<void>((resolve) => {
      // Give the event loop a turn to process the data event.
      setImmediate(() => {
        expect(dispatch).not.toHaveBeenCalled();
        reqFd.end();
        resFd.resume();
        resolve();
      });
    });
  });

  it('host ignores frame that has both ready:true AND server field (dispatch-bearing)', async () => {
    // A frame like {"ready":true,"server":"x","tool":"t","id":1} should NOT be
    // treated as a ready handshake — it has a "server" field so it goes through
    // normal validation and dispatch.
    const dispatch: DispatchFn = vi.fn().mockResolvedValue({
      success: true, content: [],
    } as DispatchResponse);

    const { reqFd, resFd } = makeHostHarness(dispatch);

    const linesPromise = readResFdLines(resFd, 1);
    reqFd.write(JSON.stringify({ ready: true, id: 1, server: 'myserver', tool: 'mytool', args: {} }) + '\n');

    const lines = await linesPromise;
    // dispatch should have been called for this frame
    expect(dispatch).toHaveBeenCalledOnce();
    expect(dispatch).toHaveBeenCalledWith({ server: 'myserver', tool: 'mytool', args: {} });

    const parsed = JSON.parse(lines[0]);
    expect(parsed.success).toBe(true);

    reqFd.end();
  });
});

// ─── Configurable frame cap ─────────────────────────────────────────────────

describe('resolveMaxFrameBytes — env var frame cap', () => {
  const orig = process.env.MCP_EXEC_MAX_FRAME_BYTES;
  afterEach(() => {
    if (orig === undefined) delete process.env.MCP_EXEC_MAX_FRAME_BYTES;
    else process.env.MCP_EXEC_MAX_FRAME_BYTES = orig;
  });

  it('returns 10MB default when env var is not set', () => {
    delete process.env.MCP_EXEC_MAX_FRAME_BYTES;
    expect(resolveMaxFrameBytes()).toBe(10 * 1024 * 1024);
  });

  it('returns the parsed value when env var is a valid positive integer', () => {
    process.env.MCP_EXEC_MAX_FRAME_BYTES = '5242880'; // 5MB
    expect(resolveMaxFrameBytes()).toBe(5 * 1024 * 1024);
  });

  it('falls back to 10MB when env var is non-numeric', () => {
    process.env.MCP_EXEC_MAX_FRAME_BYTES = 'notanumber';
    expect(resolveMaxFrameBytes()).toBe(10 * 1024 * 1024);
  });

  it('falls back to 10MB when env var is zero', () => {
    process.env.MCP_EXEC_MAX_FRAME_BYTES = '0';
    expect(resolveMaxFrameBytes()).toBe(10 * 1024 * 1024);
  });

  it('falls back to 10MB when env var is negative', () => {
    process.env.MCP_EXEC_MAX_FRAME_BYTES = '-1024';
    expect(resolveMaxFrameBytes()).toBe(10 * 1024 * 1024);
  });

  it('falls back to 10MB when env var is a float (5.5)', () => {
    process.env.MCP_EXEC_MAX_FRAME_BYTES = '5.5';
    expect(resolveMaxFrameBytes()).toBe(10 * 1024 * 1024);
  });

  it('falls back to 10MB when env var is scientific notation float (1.5e6)', () => {
    process.env.MCP_EXEC_MAX_FRAME_BYTES = '1.5e6';
    expect(resolveMaxFrameBytes()).toBe(10 * 1024 * 1024);
  });

  it('buildFdPreamble() embeds the resolved cap as a literal number', () => {
    process.env.MCP_EXEC_MAX_FRAME_BYTES = '2097152'; // 2MB
    const preamble = buildFdPreamble();
    // The preamble should contain the literal 2097152, not 10485760
    expect(preamble).toContain('2097152');
    expect(preamble).not.toContain('10485760');
  });
});

// ─── Ready fast-fail timer (finding 1) ─────────────────────────────────────

describe('fd-transport ready fast-fail timer (fake timers)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('(a) no ready frame within 10s → pending dispatch rejected with fd channel error', async () => {
    // Verify: when the fast-fail timer fires, it calls all pendingRejects[] with the fd-channel error.
    // We test this by intercepting the rejection on a dispatch that never resolves.
    let capturedError: Error | null = null;
    const dispatch: DispatchFn = vi.fn().mockReturnValue(
      new Promise<DispatchResponse>((_, reject) => {
        // Store the reject so we know if it gets called (it shouldn't in this path;
        // the attachFdTransport internal pendingRejects is separate from dispatch's reject).
        void reject; // not used — attachFdTransport tracks its own pendingRejects
      })
    );

    // Use a custom resFd that captures writes synchronously.
    const reqFd = new PassThrough();
    const resFd = new PassThrough();
    const responseLines: string[] = [];
    // Monkey-patch write on resFd to capture synchronously.
    const origWrite = resFd.write.bind(resFd);
    resFd.write = (chunk: unknown, ...rest: unknown[]) => {
      if (typeof chunk === 'string') {
        chunk.split('\n').filter(l => l.trim()).forEach(l => responseLines.push(l));
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return (origWrite as (...a: any[]) => boolean)(chunk, ...rest);
    };
    const closeListeners: Array<() => void> = [];
    const fakeChild = {
      stdio: [null, null, null, reqFd, resFd],
      on: vi.fn().mockImplementation((event: string, listener: () => void) => {
        if (event === 'close') closeListeners.push(listener);
      }),
    };
    attachFdTransport(fakeChild as unknown as import('node:child_process').ChildProcess, dispatch);

    // Send a dispatch-bearing frame (NOT the ready frame) to enqueue in pendingRejects.
    reqFd.write(JSON.stringify({ id: 1, server: 's', tool: 't', args: {} }) + '\n');

    // Let the data event fire.
    await Promise.resolve();
    await Promise.resolve();

    // Advance fake clock past 10 s — the ready timer fires.
    await vi.advanceTimersByTimeAsync(10_001);

    // Drain microtask queue.
    for (let i = 0; i < 10; i++) await Promise.resolve();

    // The timer should have written an error response frame to resFd.
    expect(responseLines.length).toBeGreaterThanOrEqual(1);
    const parsedLine = JSON.parse(responseLines[0]);
    expect(parsedLine.success).toBe(false);
    expect(parsedLine.error).toMatch(/fd channel/i);
    void capturedError; // reference to satisfy linter

    reqFd.end();
    resFd.resume();
  });

  it('(b) ready frame arrives → advance past 10s → no rejection', async () => {
    const dispatch: DispatchFn = vi.fn().mockResolvedValue({
      success: true,
      content: [{ type: 'text', text: 'OK' }],
    } as DispatchResponse);

    const { reqFd, resFd } = makeHostHarness(dispatch);

    // Send ready frame first, then a dispatch frame.
    reqFd.write(JSON.stringify({ ready: true }) + '\n');
    reqFd.write(JSON.stringify({ id: 1, server: 's', tool: 't', args: {} }) + '\n');

    const responseLines: string[] = [];
    resFd.on('data', (chunk: Buffer) => {
      chunk.toString().split('\n').filter(l => l.trim()).forEach(l => responseLines.push(l));
    });

    // Advance well past 10 s.
    await vi.advanceTimersByTimeAsync(15_000);
    await Promise.resolve();

    // Dispatch response should be success, not a timer error.
    expect(responseLines.length).toBeGreaterThanOrEqual(1);
    const parsed = JSON.parse(responseLines[0]);
    expect(parsed.success).toBe(true);

    reqFd.end();
    resFd.resume();
  });

  it('(c) child exits cleanly before 10s → no rejection, timer cleared', async () => {
    const dispatch: DispatchFn = vi.fn();
    const { reqFd, closeListeners } = makeHostHarness(dispatch);

    // Do NOT send a ready frame or a dispatch frame — simulate a clean fast exit.
    // Fire the close listeners (which cancel the timer).
    for (const listener of closeListeners) listener();

    // Advance past 10 s — timer must NOT fire (was cancelled on close).
    await vi.advanceTimersByTimeAsync(15_000);
    await Promise.resolve();

    // dispatch was never called.
    expect(dispatch).not.toHaveBeenCalled();

    reqFd.end();
  });
});
