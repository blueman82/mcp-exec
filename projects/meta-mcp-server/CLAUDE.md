# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Meta-MCP Server wraps multiple backend MCP servers, exposing only 3 meta-tools instead of loading 100+ tool schemas upfront. This reduces context token consumption for AI tools.

**Meta-Tools:**
- `list_servers` - List available backends (optional `filter` param)
- `get_server_tools` - Fetch tools (`summary_only`: names only, `tools`: specific schemas)
- `call_tool` - Execute tool on backend (`server_name`, `tool_name`, `arguments`)

## Project Structure

```
meta-mcp-server/
├── src/                    # Core MCP server (npm package)
├── extension/              # VS Code/Cursor extension
├── tests/                  # Vitest tests
└── servers.json            # Backend MCP server config
```

## Commands

```bash
# Build core server
npm run build

# Build extension
cd extension && npm run compile

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

## Configuration

**servers.json** (`~/.meta-mcp/servers.json`): Defines all backend MCP servers meta-mcp manages.

**AI Tool Configs**:
- Claude: `~/.claude.json`
- Droid: `~/.factory/mcp.json`

**npm package**: `@justanothermldude/meta-mcp-server`

**Internal servers**: Clone https://github.com/Adobe-AIFoundations/adobe-mcp-servers for corp-jira and other internal MCP servers.

## Architecture

### Quick Reference
- **Entry Flow**: `src/index.ts` → creates `ServerPool` + `ToolCache` → `createServer()` → stdio transport
- **Token Optimization**: See [Token Optimization Analysis](docs/diagrams/10-token-optimization.md) for 87-91% savings breakdown
- **Configuration**: `SERVERS_CONFIG` env var points to servers.json (standard MCP format)

### Visual Diagrams
See [Architecture Guide](docs/ARCHITECTURE.md) and [Diagram Index](docs/diagrams/README.md) for complete visual documentation:
- [System Architecture](docs/diagrams/01-system-architecture.md) - Component overview
- [Request Flow](docs/diagrams/02-request-flow.md) - Two-tier discovery
- [Pool Lifecycle](docs/diagrams/03-pool-lifecycle.md) - Connection management
- [Token Optimization](docs/diagrams/10-token-optimization.md) - 87% reduction analysis

### Core Components
- `src/server.ts` - MCP server with request handlers routing to 3 meta-tools
- `src/pool/server-pool.ts` - LRU connection pool (max 20, 5min idle timeout, 1min cleanup interval)
- `src/pool/connection.ts` - MCP client wrapper managing spawn/connect lifecycle
- `src/registry/loader.ts` - Loads `servers.json`, validates with Zod, caches manifest
- `src/tools/tool-cache.ts` - Per-server tool definition cache

**Extension Components** (`extension/src/`):
- `views/MetaMcpViewProvider.ts` - Main webview provider
- `views/webviewTemplate.ts` - UI template (Servers, Setup, Catalog tabs)
- `services/ServersConfigManager.ts` - CRUD for servers.json
- `services/AIToolConfigurator.ts` - Detects AI tools, generates config snippets
- `services/GitHubCatalogService.ts` - Fetches MCP server catalog from GitHub

### Request Flow (two-tier lazy loading)
1. AI calls `get_server_tools({server_name, summary_only: true})` → returns tool names/descriptions only (~100 tokens)
2. AI calls `get_server_tools({server_name, tools: ["specific_tool"]})` → returns full schema for selected tools
3. AI calls `call_tool({server_name, tool_name, arguments})` → pool returns existing connection → forwards to backend

## Testing

Tests use vitest. Integration tests in `tests/integration/` test real backend scenarios (Docker, Node, uvx servers). Unit tests mock the pool/connections.
