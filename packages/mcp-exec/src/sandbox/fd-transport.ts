/**
 * Fd RPC transport — host side.
 *
 * Layout (two unidirectional fds, both as 'pipe' in spawn stdio):
 *   fd 3  — sandbox → host   (requests + ready handshake)
 *   fd 4  — host   → sandbox (responses)
 *
 * Protocol: newline-delimited JSON frames.
 *   Ready    (sandbox→host): {"ready":true}  — sent immediately at sandbox startup
 *   Request  (sandbox→host): {"id":<int>,"server":str,"tool":str,"args":object}
 *   Response (host→sandbox): {"id":<int>,"success":bool,"content"?:unknown[],"error"?:str,"isError"?:bool}
 *
 * Ready handshake: the sandbox writes {"ready":true} on fd 3 before any tool call.
 * The host records it. A FD_READY_TIMEOUT_MS (10 s) timer is armed unconditionally
 * inside attachFdTransport at attach time. If neither a ready frame nor child exit
 * arrives within that window, any in-flight AND future dispatch calls are rejected
 * with a plain-English error naming fd survival as the likely root cause. The timer
 * is unref()'d so a child that finishes cleanly in <10 s without making any tool
 * call does NOT get a spurious rejection (child close always cancels the timer first).
 *
 * Frame size cap: both host and sandbox cap frames at MCP_EXEC_MAX_FRAME_BYTES
 * (env var, default 10MB). The sandbox value is resolved at generation time
 * (buildFdPreamble) — the sandbox never reads the env directly.
 *
 * Buffer protection: both sides accumulate frames with the same cap.
 * UTF-8 handling: both use StringDecoder to handle multi-byte chars split across chunks.
 *
 * fd directionality was verified empirically on macOS (see spike): a single 'pipe'
 * fd does NOT carry data in both directions cleanly; two separate fds are required.
 * The host reads fd 3 (child.stdio[3]) and writes fd 4 (child.stdio[4]).
 *
 * Child-side implementation uses net.Socket (not fs.createReadStream/WriteStream).
 * fs.createReadStream uses a libuv threadpool blocking read(), which prevents
 * process.exit(0) from completing; net.Socket uses poll-based I/O and exits cleanly.
 *
 * Re-pilot: run the fd-transport suite on a Linux/WSL2 box and confirm green before
 * merging any bump to @anthropic-ai/sandbox-runtime (fd survival is version-sensitive).
 */

import type { ChildProcess } from 'node:child_process';
import type { Readable, Writable } from 'node:stream';
import { StringDecoder } from 'node:string_decoder';
import type { DispatchRequest, DispatchResponse } from '../bridge/dispatch.js';

export type DispatchFn = (req: DispatchRequest) => Promise<DispatchResponse>;

/**
 * How long (ms) to wait for the sandbox ready frame before failing pending calls.
 * A 10-second window is generous for any normally-functioning sandbox; if it hasn't
 * sent the handshake by then the fd channel almost certainly didn't survive the
 * sandbox launch (bwrap seccomp, permission error, etc.).
 */
const FD_READY_TIMEOUT_MS = 10_000;

/**
 * Resolve the frame-size cap from the MCP_EXEC_MAX_FRAME_BYTES environment variable.
 * Non-numeric or ≤0 values fall back to the default (10MB).
 */
export function resolveMaxFrameBytes(): number {
  const DEFAULT = 10 * 1024 * 1024; // 10MB
  const raw = process.env.MCP_EXEC_MAX_FRAME_BYTES;
  if (!raw) return DEFAULT;
  // Require a bare integer string (digits only, optional leading minus).
  // Reject floats like '5.5' and scientific notation like '1.5e6' even when
  // Number() would evaluate them to a whole number — the env var must be an
  // unambiguous integer literal.
  if (!/^-?\d+$/.test(raw.trim())) return DEFAULT;
  const parsed = Number(raw);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : DEFAULT;
}

/**
 * Frame received from the sandbox (request from child).
 */
interface RequestFrame {
  id: number;
  server: string;
  tool: string;
  args?: Record<string, unknown>;
}

/** The ready handshake frame sent by the sandbox immediately at startup. */
type ReadyFrame = { ready: true };

/** Type-guard: true iff the parsed frame is the ready handshake ({"ready":true}, no "server" field). */
function isReadyFrame(frame: Record<string, unknown>): frame is ReadyFrame {
  return frame.ready === true && !('server' in frame);
}

/**
 * Attach the fd RPC reader/writer pair to a spawned child process.
 *
 * Reads newline-delimited JSON request frames from fd 3 (child.stdio[3]),
 * dispatches each to the provided dispatch function concurrently,
 * and writes response frames to fd 4 (child.stdio[4]).
 *
 * The first frame from the sandbox is expected to be the ready handshake
 * ({"ready":true}). A FD_READY_TIMEOUT_MS (10 s) timer is armed unconditionally
 * at attach time. If neither a ready frame nor child exit arrives within that
 * window, any in-flight AND future dispatch calls on this execution are rejected
 * with a plain-English error naming fd survival as the likely root cause. The timer
 * is unref()'d so a child that finishes cleanly in <10 s without making any tool
 * call does NOT get a spurious rejection — child close always cancels the timer first.
 *
 * @param child    - The spawned child process (must have been spawned with 5-element stdio array)
 * @param dispatch - Transport-agnostic tool dispatch function
 */
export function attachFdTransport(child: ChildProcess, dispatch: DispatchFn): void {
  // child.stdio[3] is readable by the host (child writes requests here)
  // child.stdio[4] is writable by the host (child reads responses here)
  const requestFd = child.stdio[3] as Readable | null;
  const responseFd = child.stdio[4] as Writable | null;

  if (!requestFd || !responseFd) {
    // Sandbox wasn't spawned with fd transport fds — nothing to attach.
    // This is a no-op so tests that mock spawn can still function.
    return;
  }

  const MAX_BUFFER_SIZE = resolveMaxFrameBytes();
  const decoder = new StringDecoder('utf8');
  let buffer = '';

  // Ready-handshake state
  let sandboxReady = false;
  let childExited = false;
  // When the fast-fail timer fires, all subsequent dispatch attempts are also rejected.
  let fdChannelDead = false;
  const fdDeadError = new Error(
    'sandbox fd channel never initialised — fds 3/4 may not have survived sandbox launch'
  );

  // Pending dispatch promises awaiting rejection if the fast-fail fires.
  // Each entry is the reject function for one in-flight dispatch call.
  const pendingRejects: Array<(err: Error) => void> = [];

  // Arm the 10 s ready timer unconditionally at attach time.
  // unref() ensures this timer cannot keep the host process open after a clean fast exit.
  const readyTimerHandle = setTimeout(() => {
    if (!sandboxReady && !childExited) {
      fdChannelDead = true;
      // Reject all currently-pending dispatch calls.
      for (const rejectFn of pendingRejects) {
        rejectFn(fdDeadError);
      }
      pendingRejects.length = 0;
      // Tear down both fds so no further data arrives.
      try { requestFd.destroy(); } catch { /* ignore */ }
      try { responseFd.destroy(); } catch { /* ignore */ }
    }
  }, FD_READY_TIMEOUT_MS);
  readyTimerHandle.unref();

  /** Cancel the ready timer — called when the ready frame arrives or child exits cleanly. */
  function cancelReadyTimer(): void {
    clearTimeout(readyTimerHandle);
  }

  requestFd.on('data', (chunk: Buffer) => {
    buffer += decoder.write(chunk);

    // Check for buffer overflow (untrusted input)
    if (buffer.length > MAX_BUFFER_SIZE) {
      console.error(
        `[mcp-exec] fd transport buffer overflow — received ${buffer.length} bytes, cap is ${MAX_BUFFER_SIZE} bytes`
      );
      try {
        responseFd.write(
          JSON.stringify({ id: -1, success: false, error: `fd transport buffer overflow — frame exceeds ${MAX_BUFFER_SIZE} bytes` }) + '\n'
        );
      } catch { /* EPIPE — ignore */ }
      responseFd.destroy();
      requestFd.destroy();
      return;
    }

    const lines = buffer.split('\n');
    // Keep the last (potentially incomplete) fragment in the buffer
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;

      // Parse the frame first, then filter before any type-guards.
      let parsed: Record<string, unknown>;
      try {
        parsed = JSON.parse(trimmed) as Record<string, unknown>;
      } catch {
        // Malformed frame — respond with error if id is recoverable
        const idMatch = trimmed.match(/"id"\s*:\s*(\d+)/);
        if (idMatch) {
          const id = parseInt(idMatch[1], 10);
          try {
            responseFd.write(
              JSON.stringify({ id, success: false, error: 'Malformed request frame: invalid JSON' }) + '\n'
            );
          } catch {
            // EPIPE — ignore
          }
        }
        continue;
      }

      // Ready handshake: {"ready":true} with no "server" field.
      // MUST be filtered BEFORE the server/tool type guards to avoid validation errors.
      // Uses the isReadyFrame type-guard for a clean discriminated-union check.
      if (isReadyFrame(parsed)) {
        sandboxReady = true;
        // Cancel the fast-fail timer — the channel is alive.
        cancelReadyTimer();
        continue; // do NOT dispatch or validate further
      }

      // If the channel is already marked dead (timer fired), reject immediately.
      if (fdChannelDead) {
        const frameId: number | undefined = typeof parsed.id === 'number' ? parsed.id as number : undefined;
        try {
          responseFd.write(
            JSON.stringify({ id: frameId, success: false, error: fdDeadError.message }) + '\n'
          );
        } catch { /* EPIPE */ }
        continue;
      }

      const frame = parsed as unknown as RequestFrame;
      const frameId: number | undefined = typeof frame.id === 'number' ? frame.id : undefined;

      // Validate frame fields before dispatching
      if (typeof frame.server !== 'string' || !frame.server) {
        try {
          responseFd.write(
            JSON.stringify({ id: frameId, success: false, error: 'Invalid frame: server must be a non-empty string' }) + '\n'
          );
        } catch { /* ignore */ }
        continue;
      }
      if (typeof frame.tool !== 'string' || !frame.tool) {
        try {
          responseFd.write(
            JSON.stringify({ id: frameId, success: false, error: 'Invalid frame: tool must be a non-empty string' }) + '\n'
          );
        } catch { /* ignore */ }
        continue;
      }
      if (frame.args !== undefined && (typeof frame.args !== 'object' || frame.args === null || Array.isArray(frame.args))) {
        try {
          responseFd.write(
            JSON.stringify({ id: frameId, success: false, error: 'Invalid frame: args must be a plain object' }) + '\n'
          );
        } catch { /* ignore */ }
        continue;
      }

      // Dispatch concurrently — do NOT await here; multiple calls may be in-flight.
      // Register a reject function in pendingRejects so the fast-fail timer can reject
      // this call if it fires before sandboxReady arrives.
      const dispatchPromise = new Promise<DispatchResponse>((resolve, reject) => {
        if (fdChannelDead) {
          reject(fdDeadError);
          return;
        }
        pendingRejects.push(reject);
        dispatch({ server: frame.server, tool: frame.tool, args: frame.args })
          .then((result) => {
            const idx = pendingRejects.indexOf(reject);
            if (idx !== -1) pendingRejects.splice(idx, 1);
            resolve(result);
          })
          .catch((err) => {
            const idx = pendingRejects.indexOf(reject);
            if (idx !== -1) pendingRejects.splice(idx, 1);
            reject(err);
          });
      });

      dispatchPromise
        .then((result: DispatchResponse) => {
          const response = JSON.stringify({ id: frame.id, ...result });
          try {
            responseFd.write(response + '\n');
          } catch {
            // EPIPE: child exited while we were writing — swallow, don't crash
          }
        })
        .catch((err: unknown) => {
          try {
            const msg = err instanceof Error ? err.message : 'Internal dispatch error';
            responseFd.write(
              JSON.stringify({ id: frame.id, success: false, error: msg }) + '\n'
            );
          } catch {
            // EPIPE — swallow
          }
        });
    }
  });

  requestFd.on('end', () => {
    // Flush any remaining bytes in the decoder
    const final = decoder.end();
    if (final) buffer += final;
  });

  // Tear down streams when child exits to avoid fd leaks.
  // Also mark childExited and cancel the ready-timer so it cannot fire after clean exit.
  child.on('close', () => {
    childExited = true;
    cancelReadyTimer();
    try { requestFd.destroy(); } catch { /* ignore */ }
    try { responseFd.destroy(); } catch { /* ignore */ }
  });
}

/**
 * Generate the sandbox-side (child) fd transport preamble.
 *
 * This code is prepended to every script that runs inside the sandbox.
 * It installs `__mcpFdCall` as a global — a function that writes a JSON
 * request frame to fd 3, then awaits the matching response frame on fd 4.
 *
 * Startup: immediately writes {"ready":true} on fd 3 so the host knows the
 * fd channel is alive. The host filters this frame before any dispatch logic.
 *
 * Concurrency is handled via a Map<id,{resolve,reject}> of pending calls.
 * A single async reader loop drains fd 4 and resolves/rejects waiters by id.
 *
 * Frame size cap: the resolved value from the host's resolveMaxFrameBytes()
 * is interpolated at generation time — the sandbox does NOT read env vars.
 *
 * IMPORTANT: NEVER read/write stdout or stderr in this preamble — those are
 * used exclusively for user-visible output (console.log etc.).
 */
export function buildFdPreamble(): string {
  // Resolve the cap on the host side and bake it into the generated code.
  // The sandbox never reads process.env — the value is a literal in the JS.
  const maxFrameBytes = resolveMaxFrameBytes();

  // This is emitted as JavaScript (not TypeScript) inside the sandboxed script.
  // It must be valid pure JS — no TypeScript syntax (no 'declare', no 'as', no type annotations).
  // top-level `import` works in both pure ESM (.mjs) and after esbuild transpilation.
  //
  // IMPORTANT: use net.Socket (not fs.createReadStream) for the response fd (fd 4).
  // fs.createReadStream uses a libuv threadpool blocking read() syscall, which prevents
  // process.exit(0) from completing teardown (the blocked thread holds the process open).
  // net.Socket uses poll-based non-blocking I/O, so process.exit(0) works correctly.
  return `
// ============================================================================
// MCP-EXEC SANDBOX TOOL CALL API
// ============================================================================
// Direct sandbox API for calling MCP tools via inherited file descriptors (fd 3 + 4).
// Production usage: generated typed wrappers (serverName.toolName({...})) and the
// server dictionary (mcp = fuzzyProxy over namespaces), both from generateMcpDictionaryFromMap.
// This preamble exports __mcpFdCall as the underlying RPC primitive; user code never calls it directly.
//
// IMPORTANT: globalThis.mcp is NOT available in production (shadowed by the generated dictionary).
// Use the typed wrappers or the fuzzy-proxy 'mcp' dictionary instead.
// ============================================================================

// Fd RPC transport — communicate with host over inherited file descriptors.
// fd 3: sandbox writes requests + ready handshake → host reads
// fd 4: sandbox reads responses                   ← host writes
// Works across the bwrap network-namespace boundary (no TCP socket needed).
// net.Socket is used (not fs streams) so process.exit(0) terminates cleanly.
import { Socket as __mcpSocket } from 'node:net';
import { StringDecoder as __mcpStringDecoder } from 'node:string_decoder';

const __mcpReqFd = new __mcpSocket({ fd: 3, readable: false, writable: true });  // sandbox → host
const __mcpResFd = new __mcpSocket({ fd: 4, readable: true, writable: false });  // host → sandbox
const __mcpMaxBuffer = ${maxFrameBytes}; // frame cap (resolved from MCP_EXEC_MAX_FRAME_BYTES on host, default 10MB)

// Ready handshake: tell the host the fd channel is alive immediately at startup.
// The host filters {"ready":true} before dispatch logic — it is NOT a tool call.
__mcpReqFd.write(JSON.stringify({ ready: true }) + '\\n');

let __mcpNextId = 1;
const __mcpPending = new Map();
let __mcpResBuf = '';
const __mcpDecoder = new __mcpStringDecoder('utf8');

__mcpResFd.on('data', (chunk) => {
  __mcpResBuf += __mcpDecoder.write(chunk);

  // Protect against buffer overflow (host should never send >${maxFrameBytes} bytes, but guard anyway)
  if (__mcpResBuf.length > __mcpMaxBuffer) {
    __mcpRejectAll('Response buffer exceeded frame-size limit');
    __mcpResFd.destroy();
    __mcpReqFd.destroy();
    return;
  }

  const lines = __mcpResBuf.split('\\n');
  __mcpResBuf = lines.pop() || '';
  for (const line of lines) {
    const t = line.trim();
    if (!t) continue;
    let resp;
    try { resp = JSON.parse(t); } catch { continue; }
    const waiter = __mcpPending.get(resp.id);
    if (waiter) {
      __mcpPending.delete(resp.id);
      waiter.resolve(resp);
    }
  }
});

__mcpResFd.on('end', () => {
  // Flush any remaining bytes
  const final = __mcpDecoder.end();
  if (final) __mcpResBuf += final;
});

function __mcpRejectAll(msg) {
  for (const [, waiter] of __mcpPending) {
    waiter.reject(new Error(msg));
  }
  __mcpPending.clear();
}

__mcpResFd.on('error', () => { __mcpRejectAll('MCP fd transport closed'); });
__mcpResFd.on('end',   () => { __mcpRejectAll('MCP fd transport closed'); });

globalThis.__mcpFdCall = function (server, tool, args) {
  return new Promise((resolve, reject) => {
    const id = __mcpNextId++;
    __mcpPending.set(id, { resolve, reject });
    const frame = JSON.stringify({ id, server, tool, args: args || {} }) + '\\n';
    __mcpReqFd.write(frame, (err) => {
      if (err) {
        __mcpPending.delete(id);
        reject(new Error('MCP fd write error: ' + err.message));
      }
    });
  });
};

`;
}
