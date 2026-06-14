/**
 * Tripwire test: @anthropic-ai/sandbox-runtime must be exact-pinned (no caret).
 *
 * WHY: the fd-pipe transport's survival across bwrap + apply-seccomp was
 * empirically proven against version 0.0.19 on WSL2 on 2026-06-10.
 * Any version bump MUST be accompanied by a full Linux pilot re-run before
 * landing. An exact pin (no "^") makes an accidental range-bump a CI failure
 * rather than a silent in-prod regression.
 *
 * Re-pilot: run the fd-transport suite on a Linux/WSL2 box and confirm green
 * before merging any bump to @anthropic-ai/sandbox-runtime (fd survival is
 * version-sensitive).
 */
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
const pkgPath = join(__dirname, '..', 'package.json');
const pkg = JSON.parse(readFileSync(pkgPath, 'utf-8')) as {
  dependencies: Record<string, string>;
};

describe('sandbox-runtime version pin tripwire', () => {
  it('@anthropic-ai/sandbox-runtime is pinned to 0.0.19 (exact, no ^ or ~ prefix)', () => {
    const version = pkg.dependencies['@anthropic-ai/sandbox-runtime'];
    // toBe enforces both the exact version and the no-caret format because it is
    // a string equality check — a range like "^0.0.19" would not equal "0.0.19".
    // Fail immediately if someone bumps it with a range: re-run the Linux pilot first.
    expect(version).toBe('0.0.19');
  });
});
