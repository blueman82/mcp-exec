# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

mcp-exec provides sandboxed TypeScript/JavaScript code execution with typed access to other MCP tools. The `packages/core` library manages backend MCP server connections (pool, registry, auth). It is a private, local-only, STDIO MCP server — not published to any registry.

**mcp-exec Tools:**
- `execute_code_with_wrappers` - Execute TypeScript/JavaScript in a sandbox with typed MCP tool wrappers
- `list_available_mcp_servers` - List available backend servers from servers.json
- `get_mcp_tool_schema` - Fetch full schema for a specific tool

## Project Structure

```
mcp-exec/
├── packages/               # npm workspaces
│   ├── core/               # mcp-exec-core
│   └── mcp-exec/           # mcp-exec
└── extension/              # VS Code/Cursor extension
```

**npm workspaces:** Dependencies are hoisted to root `node_modules/`. Always run `npm install` from repo root, never from individual packages (causes symlink conflicts).

## Commands

```bash
# Build all packages
npm run build

# Build extension
cd extension && npm run compile

# Run all tests (vitest)
npx vitest run

# Run single test file
npx vitest run packages/mcp-exec/tests/executor.test.ts

# Run tests matching pattern
npx vitest run -t "should execute"

# Type check (per-package tsconfig)
npx tsc --noEmit -p packages/core/tsconfig.json
npx tsc --noEmit -p packages/mcp-exec/tsconfig.json

# Watch mode
npm run dev
```

## Configuration

**servers.json** (`~/.meta-mcp/servers.json`): Defines all backend MCP servers mcp-exec manages. Standard MCP config format. Path overridable via `SERVERS_CONFIG`.

**Backend auth**: For HTTP/SSE backends, `${VAR_NAME}` references inside a `headers` value are resolved from the process environment at connection time (see `packages/core/src/auth/backend-auth.ts`).

## Architecture

### Quick Reference
- **Entry Flow**: `packages/mcp-exec/src/server.ts` → exposes 3 tools with dynamic catalog
- **Token Optimization**: See [Token Economics](docs/diagrams/token-economics.md) for the savings breakdown
- **Configuration**: `SERVERS_CONFIG` env var points to servers.json (standard MCP format)
- **Timeouts**: `MCP_DEFAULT_TIMEOUT` env var sets global timeout (ms). Per-server `timeout` in servers.json takes precedence.

### mcp-exec Components (`packages/mcp-exec/src/`)
- `tools/tool-catalog.ts` - Disk-persisted tool catalog (`~/.meta-mcp/tool-catalog.json`). Auto-populates on first tool call, refreshes on every call, prunes against `servers.json` on startup. Embedded in tool description so the agent sees API signatures before writing code.
- `tools/execute-with-wrappers.ts` - Main execution handler. Generates typed wrappers, updates catalog, composes sandbox code, dispatches tool calls over the fd-pipe bridge.
- `codegen/wrapper-generator.ts` - Generates TypeScript wrappers with FuzzyProxy (case-agnostic access, helpful errors on wrong names), required param guards, and field guards on responses.
- `server.ts` - MCP server exposing `execute_code_with_wrappers`, `list_available_mcp_servers`, `get_mcp_tool_schema`. Tool description rebuilt dynamically on each `tools/list` request to include latest catalog.

**Extension Components** (`extension/src/`):
- `views/MetaMcpViewProvider.ts` - Main webview provider
- `views/webviewTemplate.ts` - UI template (Servers, Setup, Catalog tabs)
- `services/ServersConfigManager.ts` - CRUD for servers.json
- `services/AIToolConfigurator.ts` - Detects AI tools, generates config snippets

### Request Flow
1. Agent calls `list_available_mcp_servers()` → returns server names from servers.json
2. Agent calls `get_mcp_tool_schema({server_name, tool_name})` → returns full schema
3. Agent calls `execute_code_with_wrappers({code, wrappers})` → generates typed wrappers → executes in sandbox

## Testing

Tests in `packages/mcp-exec/tests/` and `packages/core/tests/` use vitest. Run `npx vitest run` from the repo root.
