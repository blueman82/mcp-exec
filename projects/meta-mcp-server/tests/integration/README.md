# Integration Tests

Integration tests for meta-mcp-server against real backend servers.

## Prerequisites

1. A valid backends.json config file with real server definitions
2. Network access to the configured MCP servers

## Running Tests

```bash
# Set config path and run
SERVERS_CONFIG=~/.config/mcp/backends.json npx vitest run tests/integration/

# Or with expanded path
SERVERS_CONFIG=/Users/$(whoami)/.config/mcp/backends.json npx vitest run tests/integration/
```

## Test Coverage

### corp-jira.test.ts

Tests against the corp-jira MCP server:

- `list_servers includes corp-jira` - Verifies corp-jira appears in server list
- `get_server_tools returns jira tools` - Validates 25+ tools returned
- `call_tool executes test_jira_auth` - Confirms auth tool succeeds
- `connections are reused` - Ensures connection pooling works

## Skipped Tests

Tests auto-skip when `SERVERS_CONFIG` env var is not set or config cannot be loaded.
