# Plan: Extension UI Toggle for meta-mcp / mcp-exec switching

## StrictCode Pre-Implementation Analysis

### Bug Found (SSOT Violation)
`buildMcpExecEntry` (AIToolConfigurator.ts:580-591) does NOT set `SERVERS_CONFIG` env var, while `buildServerEntry` does. This is the root cause -- both packages need `SERVERS_CONFIG` to find backend servers. The generic snippet at line 274-277 has the same gap.

### Principle Enforcement
- **SSOT**: Fix `SERVERS_CONFIG` on both entries (root cause)
- **KISS**: Radio buttons in existing tool cards, no new tabs/views
- **DRY**: Single `buildPackageEntry(packageName, tool)` instead of two separate builders
- **YAGNI**: Only add toggle + fix, no config file watchers, no undo, no animations

---

## Changes (4 files)

### 1. `extension/src/services/AIToolConfigurator.ts`

**a) Fix `buildMcpExecEntry` -- add `SERVERS_CONFIG` env var**

```typescript
// BEFORE (line 581-585)
private buildMcpExecEntry(tool: AIToolDefinition): McpServerEntry {
    const entry: McpServerEntry = {
        command: 'npx',
        args: ['-y', '@justanothermldude/mcp-exec'],
    };

// AFTER
private buildMcpExecEntry(tool: AIToolDefinition): McpServerEntry {
    const entry: McpServerEntry = {
        command: 'npx',
        args: ['-y', '@justanothermldude/mcp-exec'],
        env: {
            SERVERS_CONFIG: this.serversConfigPath,
        },
    };
```

**b) Fix `generateGenericSnippet` -- add `SERVERS_CONFIG` to mcp-exec entry**

```typescript
// BEFORE (line 274-277)
const mcpExecEntry = {
    command: 'npx',
    args: ['-y', '@justanothermldude/mcp-exec'],
};

// AFTER
const mcpExecEntry = {
    command: 'npx',
    args: ['-y', '@justanothermldude/mcp-exec'],
    env: { SERVERS_CONFIG: this.serversConfigPath },
};
```

**c) Add `getActivePackage(tool)` method**

Reads the tool's config file and returns which package(s) are currently configured.

```typescript
getActivePackage(tool: AIToolDefinition): 'meta-mcp' | 'mcp-exec' | 'both' | 'none' {
    const configPath = this.resolveConfigPath(tool.configPath);
    if (!fs.existsSync(configPath)) return 'none';
    try {
        const content = fs.readFileSync(configPath, 'utf-8');
        const config = JSON.parse(content);
        const servers = config[tool.configKey] || {};
        const hasMeta = META_MCP_SERVER_NAME in servers;
        const hasExec = 'mcp-exec' in servers;
        if (hasMeta && hasExec) return 'both';
        if (hasMeta) return 'meta-mcp';
        if (hasExec) return 'mcp-exec';
        return 'none';
    } catch {
        return 'none';
    }
}
```

**d) Add `switchActivePackage(toolId, mode)` method**

Rewrites the tool's config to contain only the selected package(s), preserving any other non-MCP config in the file.

```typescript
async switchActivePackage(
    toolId: string,
    mode: 'meta-mcp' | 'mcp-exec' | 'both'
): Promise<{ success: boolean; error?: string }> {
    const packages = this.detectMcpPackages();
    const tool = getToolById(toolId);
    if (!tool) return { success: false, error: `Unknown tool: ${toolId}` };

    const configPath = this.resolveConfigPath(tool.configPath);
    let existingConfig: Record<string, unknown> = {};
    if (fs.existsSync(configPath)) {
        const content = fs.readFileSync(configPath, 'utf-8');
        existingConfig = JSON.parse(content);
    }

    const newServers: Record<string, unknown> = {};

    if (mode === 'meta-mcp' || mode === 'both') {
        newServers[META_MCP_SERVER_NAME] = this.buildServerEntry(tool, packages.metaMcpInstalled);
    }
    if (mode === 'mcp-exec' || mode === 'both') {
        newServers['mcp-exec'] = this.buildMcpExecEntry(tool);
    }

    existingConfig[tool.configKey] = newServers;
    this.ensureServersConfig();

    const configDir = path.dirname(configPath);
    if (!fs.existsSync(configDir)) {
        fs.mkdirSync(configDir, { recursive: true });
    }
    fs.writeFileSync(configPath, JSON.stringify(existingConfig, null, 2), 'utf-8');
    return { success: true };
}
```

### 2. `extension/src/views/MetaMcpViewProvider.ts`

**Add `switchActivePackage` case to `handleWebviewMessage`**

```typescript
case 'switchActivePackage':
    await this.handleSwitchActivePackage(
        message.payload as { toolId: string; mode: 'meta-mcp' | 'mcp-exec' | 'both' }
    );
    break;
```

**Add handler method:**

```typescript
private async handleSwitchActivePackage(
    payload: { toolId: string; mode: 'meta-mcp' | 'mcp-exec' | 'both' }
): Promise<void> {
    const result = await this.toolConfigurator.switchActivePackage(payload.toolId, payload.mode);
    if (result.success) {
        vscode.window.showInformationMessage(
            `Switched to ${payload.mode}. Restart your AI tool to apply.`
        );
        await this.handleLoadSetup();
    } else {
        vscode.window.showErrorMessage(result.error || 'Failed to switch');
    }
    this.postMessage({
        type: 'switchActivePackageResponse',
        success: result.success,
        error: result.error
    });
}
```

### 3. `extension/src/views/webviewTemplate.ts`

**Add `activePackage` to `updateSetup` message data and pass to `renderSetup`**

In `handleLoadSetup`, compute active package per tool:

```typescript
// In MetaMcpViewProvider.handleLoadSetup, add to the message:
const activePackages: Record<string, string> = {};
for (const t of tools) {
    activePackages[t.tool.id] = this.toolConfigurator.getActivePackage(t.tool);
}
this.postMessage({ type: 'updateSetup', tools, snippets, genericSnippet, mcpPackages, activePackages });
```

**In webview JS, add state variable and render radio toggle in each tool card**

Add to state: `let activePackages = {};`

In `updateSetup` handler: `activePackages = message.activePackages || {};`

In `renderSetup`, inside each tool card (after the `.tool-actions` div), add:

```html
<div class="package-toggle" data-tool-id="${tool.tool.id}">
    <span class="toggle-label">Active package:</span>
    <label class="toggle-option">
        <input type="radio" name="pkg-${tool.tool.id}" value="meta-mcp"
            ${activePackages[tool.tool.id] === 'meta-mcp' ? 'checked' : ''}>
        meta-mcp
    </label>
    <label class="toggle-option">
        <input type="radio" name="pkg-${tool.tool.id}" value="mcp-exec"
            ${activePackages[tool.tool.id] === 'mcp-exec' ? 'checked' : ''}>
        mcp-exec
    </label>
    <label class="toggle-option">
        <input type="radio" name="pkg-${tool.tool.id}" value="both"
            ${activePackages[tool.tool.id] === 'both' ? 'checked' : ''}>
        Both
    </label>
</div>
```

**Attach event listener to radio buttons:**

```javascript
setupContainer.querySelectorAll('.package-toggle input[type="radio"]').forEach(radio => {
    radio.addEventListener('change', (e) => {
        const toolId = e.target.closest('.package-toggle').dataset.toolId;
        const mode = e.target.value;
        vscode.postMessage({
            type: 'switchActivePackage',
            payload: { toolId, mode }
        });
    });
});
```

**Add CSS for the toggle:**

```css
.package-toggle { display: flex; align-items: center; gap: var(--spacing-sm); margin-top: var(--spacing-sm); padding-top: var(--spacing-sm); border-top: 1px solid var(--vscode-panel-border); }
.toggle-label { font-size: 12px; color: var(--vscode-descriptionForeground); }
.toggle-option { font-size: 12px; display: flex; align-items: center; gap: 4px; cursor: pointer; }
.toggle-option input { margin: 0; }
```

### 4. `extension/src/services/MessageHandler.ts`

Add `'switchActivePackage'` to the `MessageType` union (for type safety, though the ViewProvider handles it directly). This is optional since the ViewProvider handles the message before it reaches MessageHandler.

---

## Conditions for toggle visibility

Only show the toggle when:
- The tool is installed (`tool.installed === true`)
- At least one MCP package is installed (`mcpPackages.metaMcpInstalled || mcpPackages.mcpExecInstalled`)

Disable individual radio options when the corresponding package is not installed (e.g., disable "meta-mcp" radio if `mcpPackages.metaMcpInstalled === false`).

---

## Testing

- Existing tests should still pass (no behavioral changes to pool/cache/server)
- Manual verification: open extension, go to Setup tab, toggle between options, verify the tool's mcp.json is rewritten correctly with `SERVERS_CONFIG` on both entries
