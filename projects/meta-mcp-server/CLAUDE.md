# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Meta-MCP Server wraps multiple backend MCP servers, exposing only 3 meta-tools instead of loading 100+ tool schemas upfront. This reduces context token consumption for AI tools.

**Meta-Tools:**
- `list_servers` - List available backends (optional `filter` param)
- `get_server_tools` - Fetch tools (`summary_only`: names only, `tools`: specific schemas)
- `call_tool` - Execute tool on backend (`server_name`, `tool_name`, `arguments`)

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

**Request Flow** (two-tier lazy loading):
1. AI calls `get_server_tools({server_name, summary_only: true})` → returns tool names/descriptions only (~100 tokens)
2. AI calls `get_server_tools({server_name, tools: ["specific_tool"]})` → returns full schema for selected tools
3. AI calls `call_tool({server_name, tool_name, arguments})` → pool returns existing connection → forwards to backend

**Token Optimization**: `summary_only` and `tools` params reduce 16k tokens → ~2k (87% reduction)

**Configuration**: `SERVERS_CONFIG` env var points to backends.json (format matches Claude Desktop mcp.json)

## Testing

Tests use vitest. Integration tests in `tests/integration/` test real backend scenarios (Docker, Node, uvx servers). Unit tests mock the pool/connections.
