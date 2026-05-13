# MCP-Exec

A visual interface for configuring and managing [mcp-exec](https://www.npmjs.com/package/@justanothermldude/mcp-exec) — the MCP proxy that connects your AI tools (Claude Code, Cursor, Droid, Augment, VS Code) to backend MCP servers with automatic token injection.

## Features

### Servers tab
Add, edit, and remove backend MCP servers from `~/.meta-mcp/servers.json`. Each entry shows live connection status.

### Setup tab
Auto-detects your installed AI tools and generates the correct MCP config snippet for each one. Supports:
- Claude Code (`~/.claude.json`)
- Cursor (`~/.cursor/mcp.json`)
- Factory / Droid (`~/.factory/mcp.json`)
- Augment
- VS Code / GitHub Copilot

### Catalog tab
Browse and add MCP servers from the GitHub catalog directly into your `servers.json`.

## Quick Start

1. Install this extension from VSIX
2. Open the **MCP-Exec** panel in the activity bar
3. Go to **Servers** → **+ Add Server** to add your Gateway URL and token env file
4. Go to **Setup** → click **Configure** next to your AI tool to inject the mcp-exec config

## Requirements

- Node.js 18+ (for mcp-exec via `npx`)
- A `~/.meta-mcp/servers.json` file (created automatically on first use)

## Extension Settings

- `mcp-exec.serversConfigPath` — path to a custom `servers.json` (default: `~/.meta-mcp/servers.json`)
- `mcp-exec.mcpExecPath` — path to a local mcp-exec build for development

## Links

- [mcp-exec on npm](https://www.npmjs.com/package/@justanothermldude/mcp-exec)
- [ADA MCP Gateway](https://mcp.adobe.io)
- [Source](https://github.com/OneAdobe/camp-ops-emea/tree/main/projects/meta-mcp-server)
