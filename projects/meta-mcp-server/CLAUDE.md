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
├── packages/               # npm workspaces (publishable)
│   ├── core/               # @justanothermldude/meta-mcp-core
│   ├── mcp-exec/           # @justanothermldude/mcp-exec
│   └── meta-mcp/           # @justanothermldude/meta-mcp-server
├── src/                    # Core MCP server source
├── extension/              # VS Code/Cursor extension
├── tests/                  # Vitest tests
└── servers.json            # Backend MCP server config
```

**npm workspaces:** Dependencies are hoisted to root `node_modules/`. Always run `npm install` from repo root, never from individual packages (causes symlink conflicts).

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
- **Token Optimization**: See [Token Economics](docs/diagrams/token-economics.md) for 87-91% savings breakdown
- **Configuration**: `SERVERS_CONFIG` env var points to servers.json (standard MCP format)
- **Timeouts**: `MCP_DEFAULT_TIMEOUT` env var sets global timeout (ms). Per-server `timeout` in servers.json takes precedence.

### Visual Diagrams
See [Architecture Guide](docs/ARCHITECTURE.md) and [Diagram Index](docs/diagrams/README.md) for complete visual documentation:
- [Architecture](docs/diagrams/architecture.md) - System, config, lifecycle
- [Core Mechanics](docs/diagrams/core-mechanics.md) - Pool, connections, caching, tools
- [Token Economics](docs/diagrams/token-economics.md) - ROI analysis

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

## Publishing

**NPM Packages** (in `packages/`):
| Package | npm Name | Purpose |
|---------|----------|---------|
| `packages/core` | `@justanothermldude/meta-mcp-core` | Shared types/utils |
| `packages/mcp-exec` | `@justanothermldude/mcp-exec` | Code execution MCP server |
| `packages/meta-mcp` | `@justanothermldude/meta-mcp-server` | Main meta-MCP server |

**Publish workflow:**
```bash
# 1. Bump version in package.json
cd packages/<package>
npm version patch  # or minor/major

# 2. Build
npm run build

# 3. Publish (requires npm login to @justanothermldude scope)
npm publish --access public

# 4. Commit version bump
git add -A && git commit -m "chore(release): @justanothermldude/<package>@X.Y.Z"
```

**Note:** Monorepo git tags (v0.4.x) are separate from npm package versions. Git tags track overall project releases; npm versions track individual package releases.
