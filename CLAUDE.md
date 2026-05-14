# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

MCP-Exec provides sandboxed TypeScript/JavaScript code execution with typed access to other MCP tools. The `packages/core` library manages backend MCP server connections (pool, registry, auth).

**MCP-Exec Tools:**
- `execute_code_with_wrappers` - Execute TypeScript/JavaScript in a sandbox with typed MCP tool wrappers
- `list_available_mcp_servers` - List available backend servers from servers.json
- `get_mcp_tool_schema` - Fetch full schema for a specific tool

## Project Structure

```
meta-mcp-server/
├── packages/               # npm workspaces (publishable)
│   ├── core/               # @justanothermldude/mcp-exec-oss-core
│   └── mcp-exec/           # @justanothermldude/mcp-exec-oss
├── extension/              # VS Code/Cursor extension
└── servers.json            # Backend MCP server config
```

**npm workspaces:** Dependencies are hoisted to root `node_modules/`. Always run `npm install` from repo root, never from individual packages (causes symlink conflicts).

## Commands

```bash
# Build extension
cd extension && npm run compile

# Run all tests (vitest)
npx vitest run

# Run single test file
npx vitest run packages/mcp-exec/tests/executor.test.ts

# Run tests matching pattern
npx vitest run -t "should execute"

# Type check
npx tsc --noEmit

# Watch mode
npm run dev
```

## Configuration

**servers.json** (`~/.meta-mcp/servers.json`): Defines all backend MCP servers mcp-exec manages.

**AI Tool Configs**:
- Claude: `~/.claude.json`
- Droid: `~/.factory/mcp.json`

**Internal servers**: Clone https://github.com/Adobe-AIFoundations/adobe-mcp-servers for corp-jira and other internal MCP servers.

## Architecture

### Quick Reference
- **Entry Flow**: `packages/mcp-exec/src/server.ts` → exposes 3 tools with dynamic catalog
- **Token Optimization**: See [Token Economics](docs/diagrams/token-economics.md) for 87-91% savings breakdown
- **Configuration**: `SERVERS_CONFIG` env var points to servers.json (standard MCP format)
- **Timeouts**: `MCP_DEFAULT_TIMEOUT` env var sets global timeout (ms). Per-server `timeout` in servers.json takes precedence.

### Visual Diagrams
See [Architecture Guide](docs/ARCHITECTURE.md) and [Diagram Index](docs/diagrams/README.md) for complete visual documentation:
- [Architecture](docs/diagrams/architecture.md) - System, config, lifecycle
- [Token Economics](docs/diagrams/token-economics.md) - ROI analysis

### mcp-exec Components (`packages/mcp-exec/src/`)
- `tools/tool-catalog.ts` - Disk-persisted tool catalog (`~/.meta-mcp/tool-catalog.json`). Auto-populates on first tool call, refreshes on every call, prunes against `servers.json` on startup. Embedded in tool description so the agent sees API signatures before writing code.
- `tools/execute-with-wrappers.ts` - Main execution handler. Generates typed wrappers, updates catalog, composes sandbox code.
- `codegen/wrapper-generator.ts` - Generates TypeScript wrappers with FuzzyProxy (case-agnostic access, helpful errors on wrong names), required param guards, and field guards on responses.
- `server.ts` - MCP server exposing `execute_code_with_wrappers`, `list_available_mcp_servers`, `get_mcp_tool_schema`. Tool description rebuilt dynamically on each `tools/list` request to include latest catalog.

**Extension Components** (`extension/src/`):
- `views/MetaMcpViewProvider.ts` - Main webview provider
- `views/webviewTemplate.ts` - UI template (Servers, Setup, Catalog tabs)
- `services/ServersConfigManager.ts` - CRUD for servers.json
- `services/AIToolConfigurator.ts` - Detects AI tools, generates config snippets
- `services/GitHubCatalogService.ts` - Fetches MCP server catalog from GitHub

### Request Flow
1. Agent calls `list_available_mcp_servers()` → returns server names from servers.json
2. Agent calls `get_mcp_tool_schema({server_name, tool_name})` → returns full schema
3. Agent calls `execute_code_with_wrappers({code, servers})` → generates typed wrappers → executes in sandbox

## Testing

Tests in `packages/mcp-exec/tests/` use vitest.

## Publishing

**NPM Packages** (in `packages/`):
| Package | npm Name | Purpose |
|---------|----------|---------|
| `packages/core` | `@justanothermldude/mcp-exec-oss-core` | Shared types/utils |
| `packages/mcp-exec` | `@justanothermldude/mcp-exec-oss` | Code execution MCP server |

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
