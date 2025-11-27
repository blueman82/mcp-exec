# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Meta-MCP Server wraps multiple backend MCP servers, exposing only 3 meta-tools (`list_servers`, `get_server_tools`, `call_tool`) instead of loading 100+ tool schemas upfront. This reduces context token consumption for AI tools.

## Commands

```bash
# Build
npm run build

# Run all tests (vitest)
npx vitest run

# Run single test file
npx vitest run tests/pool.test.ts

# Run tests matching pattern
npx vitest run -t "should evict"

# Type check
npx tsc --noEmit

# Watch mode
npm run dev
```

## Architecture

**Entry Flow**: `src/index.ts` → creates `ServerPool` + `ToolCache` → `createServer()` → stdio transport

**Core Components**:
- `src/server.ts` - MCP server with request handlers routing to 3 meta-tools
- `src/pool/server-pool.ts` - LRU connection pool (max 6, 5min idle timeout, 1min cleanup interval)
- `src/pool/connection.ts` - MCP client wrapper managing spawn/connect lifecycle
- `src/registry/loader.ts` - Loads `backends.json`, validates with Zod, caches manifest
- `src/tools/tool-cache.ts` - Per-server tool definition cache

**Request Flow**:
1. AI calls `get_server_tools({server_name})` → pool lazily spawns backend → caches tools
2. AI calls `call_tool({server_name, tool_name, arguments})` → pool returns existing connection → forwards to backend

**Configuration**: `SERVERS_CONFIG` env var points to backends.json (format matches Claude Desktop mcp.json)

## Testing

Tests use vitest. Integration tests in `tests/integration/` test real backend scenarios (Docker, Node, uvx servers). Unit tests mock the pool/connections.
