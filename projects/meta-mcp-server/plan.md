# Plan: Fix findLocalServer() to support all server types

## Problem
`findLocalServer()` gates on `package.json` or `requirements.txt`, blocking 27% (19/70) of internal servers from being installed via the catalog. This includes Firefly, Coronet, Sign, Crashreporter, and others using `pyproject.toml`, `Cargo.toml`, `go.mod`, or `setup.py`.

## Root Cause (traced via Serena LSP)
The call chain has restrictive checks at multiple points:

1. **`findLocalServer(serverId)`** (`MetaMcpViewProvider.ts:302-339`) — requires `package.json` or `requirements.txt` in the directory. Ignores `item.packagePath` from catalog.
2. **`parseLocalServer(packagePath)`** (`LocalServerParser.ts:22-54`) — defaults non-`package.json` to `python` with hardcoded `server.py` entry point. Many Python servers use `src/server.py` or module entry points.
3. **`handleRunLocalServerBuild()`** (`MetaMcpViewProvider.ts:371-437`) — hardcodes `npm install && npm run build` for ALL servers, polls for `dist/index.js`.

## Codex Review Findings
- **0 out of 69** internal servers have `package_path` in the catalog — so `packagePath` support is future-proofing only
- Removing marker gates would recover **18 currently blocked** servers
- **2 servers** use non-`adobe-mcp-servers` repos (`g11n-mcp-server`, `adobe-vault`) — needs `repo_hint` support (separate fix)
- **8 servers** have no markers at all — directory existence check is sufficient for known paths
- JetBrains plugin already solved this with directory-existence-only checks

## Scope Decision
- **In scope**: Fix detection and Python entry point handling
- **Deferred**: Rust/Go/Docker runtime support, `repo_hint` multi-repo support

## Changes

### 1. `MetaMcpViewProvider.ts` — `findLocalServer()` (lines 302-339)
**Change**: Accept optional `CatalogServer` item. Use `item.packagePath` first (with containment validation). Remove marker file gates — check directory existence only (mirror JetBrains `RepoDetector.kt:123-131`).

```typescript
// Before
private async findLocalServer(serverId: string): Promise<...>

// After
private async findLocalServer(serverId: string, item?: CatalogServer): Promise<...>
```

Remove both `package.json`/`requirements.txt` existence checks at lines 316-318 and 330-332. Replace with `fs.statSync(fullPath).isDirectory()`.

### 2. `MetaMcpViewProvider.ts` — `handleInstallFromCatalog()` (line 239, 246)
**Change**: Pass `item` to `findLocalServer()`.

```typescript
// Before
const localServerPath = await this.findLocalServer(item.id);

// After
const localServerPath = await this.findLocalServer(item.id, item);
```

### 3. `LocalServerParser.ts` — `parseLocalServer()` (lines 22-54)
**Change**: Expand Python entry point detection. Check `server.py`, `src/server.py`, `src/{name}/server.py`, `__main__.py` in order. Add `pyproject.toml` detection for Python confirmation.

```typescript
// Before
const runtime: 'node' | 'python' = hasPackageJson ? 'node' : 'python';
const entryPoint = runtime === 'node' ? 'dist/index.js' : 'server.py';

// After
const hasPyprojectToml = fs.existsSync(path.join(packagePath, 'pyproject.toml'));
const hasSetupPy = fs.existsSync(path.join(packagePath, 'setup.py'));
const runtime: 'node' | 'python' = hasPackageJson ? 'node' : 'python';
const entryPoint = runtime === 'node'
    ? 'dist/index.js'
    : findPythonEntryPoint(packagePath);
```

New helper `findPythonEntryPoint(packagePath)` checks in order:
- `server.py`
- `src/server.py`
- `src/*/server.py` (glob for nested package)
- `__main__.py`
- Falls back to `server.py` (existing behavior)

### 4. `MetaMcpViewProvider.ts` — `handleRunLocalServerBuild()` (lines 371-437)
**Change**: Only show npm build for node runtime. For Python, show pip/uv install instead or skip build.

```typescript
// Before (hardcoded)
terminal.sendText('npm install --ignore-scripts && npm run build');
const entryPoint = path.join(data.packagePath, 'dist', 'index.js');

// After (runtime-aware)
if (data.runtime === 'node') {
    terminal.sendText('npm install --ignore-scripts && npm run build');
} else {
    terminal.sendText('pip install -e . || uv pip install -e .');
}
```

### 5. `MetaMcpViewProvider.ts` — `handleRunLocalServerBuild()`
**Change**: Accept `runtime` and `entryPoint` in the data payload instead of hardcoding `dist/index.js`.

### 6. Extension version bump
**Change**: Bump `extension/package.json` version from `0.4.0` to `0.5.0`.

## Files Modified
| File | Change |
|------|--------|
| `extension/src/views/MetaMcpViewProvider.ts` | findLocalServer, handleInstallFromCatalog, handleRunLocalServerBuild |
| `extension/src/services/LocalServerParser.ts` | parseLocalServer, new findPythonEntryPoint helper |
| `extension/package.json` | Version bump to 0.5.0 |

## Testing
- Verify Firefly (`pyproject.toml` only) is found and installable
- Verify existing Node servers (corp-jira, etc.) still work unchanged
- Verify `parseLocalServer` returns correct entry point for Python servers
- Build new VSIX and install in Cursor

## Branch
`fix/extension-find-local-server`
