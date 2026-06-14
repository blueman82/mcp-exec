# mcp-exec

A visual interface for configuring and managing mcp-exec — the local MCP proxy that connects your AI tools (Claude Code, Cursor, VS Code) to backend MCP servers. Private/local-only: build mcp-exec from source and point your AI tool at the local build.

## Features

### Servers tab
Add, edit, and remove backend MCP servers from `~/.meta-mcp/servers.json`. Each entry shows live connection status.

### Setup tab
Auto-detects your installed AI tools and generates the correct MCP config snippet for each one. Supports:
- Claude Code (`~/.claude.json`)
- Cursor (`~/.cursor/mcp.json`)
- VS Code / GitHub Copilot

### Catalog tab
Browse a curated list of public MCP servers and add them directly into your `servers.json`.

## Quick Start

1. Install this extension from VSIX
2. Open the **mcp-exec** panel in the activity bar
3. Go to **Servers** → **+ Add Server** to add a backend MCP server
4. Go to **Setup** → click **Configure** next to your AI tool to inject the mcp-exec config

## Requirements

- Node.js 18+
- A local mcp-exec build (`npm install && npm run build` at the repo root)
- A `~/.meta-mcp/servers.json` file (created automatically on first use)

## Extension Settings

- `mcp-exec.serversConfigPath` — path to a custom `servers.json` (default: `~/.meta-mcp/servers.json`)
- `mcp-exec.mcpExecPath` — path to a local mcp-exec build (`packages/mcp-exec/dist/index.js`)
