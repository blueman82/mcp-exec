# Meta-MCP JetBrains Plugin

JetBrains IntelliJ IDEA plugin for managing MCP (Model Context Protocol) servers. Works with **Junie** (JetBrains' native AI agent).

## Quick Start

1. **Install the plugin** (see Installation below)
2. **Open Meta-MCP tool window** from the right sidebar
3. **Setup tab**: Install meta-mcp-server or mcp-exec via npm
4. **Catalog tab**: Browse and add MCP servers
5. **Configure Junie**: Click "Configure" next to Junie in Setup tab
6. **Restart IntelliJ** to load the new configuration

## Features

- **Servers Tab**: Manage servers in `~/.meta-mcp/servers.json`
  - Add, edit, delete servers
  - Support for stdio (npx, uvx, python, docker, custom) and HTTP transports
  - Environment variables configuration

- **Catalog Tab**: Browse and install MCP servers from GitHub catalog
  - Search and filter servers
  - Lifecycle badges (experimental, stable, deprecated)
  - Automatic repo download for internal servers
  - Build support for local server installation

- **Setup Tab**: Configure AI tools with meta-mcp
  - Detect installed AI tools (Claude Code, Cursor, VS Code, Droid, Junie)
  - Install meta-mcp-server and mcp-exec packages
  - Auto-configure tools with server migration
  - Generic config snippet for other platforms
  - Supports JSONC config files (handles `//` comments)

## Compatibility

This plugin configures MCP servers for **Junie** (JetBrains' native AI agent). Junie's config is stored at:

```
~/.junie/mcp/mcp.json
```

## Installation

### From ZIP

1. Build the plugin (see Development below)
2. Go to IntelliJ IDEA → Settings → Plugins
3. Click gear icon → Install Plugin from Disk
4. Select `build/distributions/meta-mcp-jetbrains-1.0.0.zip`
5. Restart IntelliJ IDEA

## Development

### Prerequisites

- **IntelliJ IDEA** (required for its bundled JDK)
- The plugin must be built using IntelliJ's bundled JetBrains Runtime (JBR), not system Java

### Build

```bash
cd jetbrains-plugin

# IMPORTANT: Must use IntelliJ's bundled JDK
export JAVA_HOME="/Applications/IntelliJ IDEA.app/Contents/jbr/Contents/Home"

# Build plugin
./gradlew clean buildPlugin

# Run plugin in sandbox IDE
./gradlew runIde

# Run tests
./gradlew test
```

### Project Structure

```
jetbrains-plugin/
├── src/main/kotlin/com/adobe/metamcp/
│   ├── model/           # Data classes
│   ├── services/        # Business logic (ported from VS Code extension)
│   ├── ui/
│   │   ├── panels/      # Tab panels (Servers, Catalog, Setup)
│   │   └── dialogs/     # Dialog wrappers
│   └── actions/         # IntelliJ actions
├── src/main/resources/
│   ├── META-INF/plugin.xml
│   └── icons/
└── build.gradle.kts
```

## Shared Configuration

Both VS Code and JetBrains plugins share the same configuration file:
- `~/.meta-mcp/servers.json` - Server definitions

This allows using both IDEs with the same MCP server setup.

## Requirements

- IntelliJ IDEA 2024.1 or later
- Node.js (for npm install commands)
- meta-mcp-server or mcp-exec npm package

## License

Apache 2.0
