import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

export interface WebviewTemplateOptions {
    extensionUri: vscode.Uri;
    nonce: string;
    cspSource: string;
}

function generateNonce(): string {
    let text = '';
    const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    for (let i = 0; i < 32; i++) {
        text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
}

function loadStylesheet(extensionUri: vscode.Uri): string {
    const stylesPath = path.join(extensionUri.fsPath, 'media', 'styles.css');
    try {
        if (fs.existsSync(stylesPath)) {
            return fs.readFileSync(stylesPath, 'utf8');
        }
    } catch (error) {
        console.error('Failed to load styles.css:', error);
    }
    return '';
}

export function getWebviewContent(options: WebviewTemplateOptions): string {
    const { extensionUri, nonce, cspSource } = options;
    const externalStyles = loadStylesheet(extensionUri);

    return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';">
    <title>Meta-MCP Configurator</title>
    <style>
        ${externalStyles}

        /* Inline critical styles using VS Code CSS variables */
        :root {
            --spacing-xs: 4px;
            --spacing-sm: 8px;
            --spacing-md: 16px;
            --spacing-lg: 24px;
            --border-radius: 4px;
        }

        * {
            box-sizing: border-box;
        }

        body {
            font-family: var(--vscode-font-family);
            font-size: var(--vscode-font-size);
            color: var(--vscode-foreground);
            background-color: var(--vscode-editor-background);
            margin: 0;
            padding: var(--spacing-md);
            line-height: 1.5;
        }

        /* View containers */
        .view-container {
            display: none;
        }

        .view-container.active {
            display: block;
        }

        /* Header */
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: var(--spacing-md);
            padding-bottom: var(--spacing-md);
            border-bottom: 1px solid var(--vscode-panel-border);
        }

        .header-title {
            font-size: 16px;
            font-weight: 600;
            color: var(--vscode-foreground);
        }

        .header-actions {
            display: flex;
            gap: var(--spacing-sm);
        }

        /* Buttons */
        .btn {
            padding: 6px 12px;
            border: none;
            border-radius: var(--border-radius);
            cursor: pointer;
            font-size: 13px;
            transition: background-color 0.2s;
        }

        .btn-primary {
            background-color: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
        }

        .btn-primary:hover {
            background-color: var(--vscode-button-hoverBackground);
        }

        .btn-secondary {
            background-color: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
        }

        .btn-secondary:hover {
            background-color: var(--vscode-button-secondaryHoverBackground);
        }

        .btn-icon {
            padding: 6px;
            background: transparent;
            border: none;
            color: var(--vscode-foreground);
            cursor: pointer;
            border-radius: var(--border-radius);
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .btn-icon:hover {
            background-color: var(--vscode-list-hoverBackground);
        }

        /* Server List */
        #server-list-container {
            display: flex;
            flex-direction: column;
            gap: var(--spacing-sm);
        }

        .server-card {
            border: 1px solid var(--vscode-panel-border);
            border-left: 3px solid var(--vscode-button-background);
            border-radius: var(--border-radius);
            padding: var(--spacing-md);
            background-color: var(--vscode-editor-background);
            transition: box-shadow 0.2s, transform 0.2s;
        }

        .server-card:hover {
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
            transform: translateY(-1px);
        }

        .server-card.connected {
            border-left-color: var(--vscode-charts-green);
        }

        .server-card.error {
            border-left-color: var(--vscode-errorForeground);
        }

        .server-card-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: var(--spacing-sm);
        }

        .server-name {
            font-weight: 600;
            font-size: 14px;
            color: var(--vscode-foreground);
        }

        .server-command {
            font-size: 12px;
            color: var(--vscode-descriptionForeground);
            font-family: var(--vscode-editor-font-family);
            background-color: var(--vscode-textCodeBlock-background);
            padding: 2px 6px;
            border-radius: 3px;
            margin-top: var(--spacing-xs);
            display: inline-block;
        }

        .server-status {
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 10px;
        }

        .server-status.connected {
            background-color: var(--vscode-charts-green);
            color: white;
        }

        .server-status.disconnected {
            background-color: var(--vscode-descriptionForeground);
            color: var(--vscode-editor-background);
        }

        .server-actions {
            display: flex;
            gap: var(--spacing-sm);
            margin-top: var(--spacing-sm);
        }

        /* Form styles */
        #form-container {
            max-width: 600px;
        }

        .form-group {
            margin-bottom: var(--spacing-md);
        }

        .form-label {
            display: block;
            font-size: 13px;
            font-weight: 500;
            margin-bottom: var(--spacing-xs);
            color: var(--vscode-foreground);
        }

        .form-input {
            width: 100%;
            padding: 8px 10px;
            border: 1px solid var(--vscode-input-border);
            background-color: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            border-radius: var(--border-radius);
            font-size: 13px;
            font-family: inherit;
        }

        .form-input:focus {
            outline: 1px solid var(--vscode-focusBorder);
            border-color: transparent;
        }

        .form-select {
            width: 100%;
            padding: 8px 10px;
            border: 1px solid var(--vscode-input-border);
            background-color: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            border-radius: var(--border-radius);
            font-size: 13px;
        }

        .form-hint {
            font-size: 12px;
            color: var(--vscode-descriptionForeground);
            margin-top: var(--spacing-xs);
        }

        /* Env vars */
        .env-vars-container {
            border: 1px solid var(--vscode-panel-border);
            border-radius: var(--border-radius);
            padding: var(--spacing-md);
            margin-top: var(--spacing-sm);
        }

        .env-var-row {
            display: flex;
            gap: var(--spacing-sm);
            margin-bottom: var(--spacing-sm);
            align-items: center;
        }

        .env-var-row input {
            flex: 1;
        }

        .env-var-row .btn-remove {
            color: var(--vscode-errorForeground);
            padding: 4px 8px;
        }

        /* Catalog */
        #catalog-container {
            display: flex;
            flex-direction: column;
            gap: var(--spacing-md);
        }

        .catalog-search {
            position: relative;
        }

        .catalog-search input {
            width: 100%;
            padding: 10px 12px;
            padding-left: 36px;
        }

        .catalog-search-icon {
            position: absolute;
            left: 12px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--vscode-descriptionForeground);
        }

        .catalog-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: var(--spacing-md);
        }

        .catalog-card {
            border: 1px solid var(--vscode-panel-border);
            border-radius: var(--border-radius);
            padding: var(--spacing-md);
            background-color: var(--vscode-editor-background);
            cursor: pointer;
            transition: border-color 0.2s;
        }

        .catalog-card:hover {
            border-color: var(--vscode-focusBorder);
        }

        .catalog-card-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: var(--spacing-xs);
        }

        .catalog-card-title {
            font-weight: 600;
            font-size: 14px;
        }

        .catalog-card-desc {
            font-size: 12px;
            color: var(--vscode-descriptionForeground);
            line-height: 1.4;
            margin-bottom: var(--spacing-sm);
        }

        .catalog-card-tags {
            display: flex;
            flex-wrap: wrap;
            gap: var(--spacing-xs);
            margin-bottom: var(--spacing-sm);
        }

        .catalog-card-actions {
            margin-top: var(--spacing-sm);
        }

        .btn-sm {
            padding: 4px 8px;
            font-size: 12px;
        }

        .lifecycle-experimental {
            background-color: var(--vscode-charts-orange);
            color: white;
        }

        .lifecycle-stable {
            background-color: var(--vscode-charts-green);
            color: white;
        }

        .lifecycle-deprecated {
            background-color: var(--vscode-charts-red);
            color: white;
        }

        .tag {
            font-size: 11px;
            padding: 2px 8px;
            background-color: var(--vscode-badge-background);
            color: var(--vscode-badge-foreground);
            border-radius: 10px;
        }

        /* Loading state */
        .loading {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: var(--spacing-lg);
        }

        .spinner {
            width: 32px;
            height: 32px;
            border: 3px solid var(--vscode-panel-border);
            border-top-color: var(--vscode-button-background);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .loading-text {
            margin-top: var(--spacing-md);
            color: var(--vscode-descriptionForeground);
        }

        /* Empty state */
        .empty-state {
            text-align: center;
            padding: var(--spacing-lg);
            color: var(--vscode-descriptionForeground);
        }

        .empty-state-icon {
            font-size: 48px;
            margin-bottom: var(--spacing-md);
            opacity: 0.5;
        }

        .empty-state-title {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: var(--spacing-sm);
            color: var(--vscode-foreground);
        }

        .empty-state-desc {
            font-size: 13px;
            margin-bottom: var(--spacing-md);
        }

        /* Messages */
        .message {
            padding: var(--spacing-md);
            border-radius: var(--border-radius);
            margin-bottom: var(--spacing-md);
        }

        .message-error {
            background-color: var(--vscode-inputValidation-errorBackground);
            border: 1px solid var(--vscode-inputValidation-errorBorder);
            color: var(--vscode-errorForeground);
        }

        .message-success {
            background-color: var(--vscode-inputValidation-infoBackground);
            border: 1px solid var(--vscode-inputValidation-infoBorder);
        }

        .message-warning {
            background-color: var(--vscode-inputValidation-warningBackground);
            border: 1px solid var(--vscode-inputValidation-warningBorder);
        }

        /* Navigation tabs */
        .nav-tabs {
            display: flex;
            border-bottom: 1px solid var(--vscode-panel-border);
            margin-bottom: var(--spacing-md);
        }

        .nav-tab {
            padding: var(--spacing-sm) var(--spacing-md);
            border: none;
            background: transparent;
            color: var(--vscode-descriptionForeground);
            cursor: pointer;
            font-size: 13px;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
        }

        .nav-tab:hover {
            color: var(--vscode-foreground);
        }

        .nav-tab.active {
            color: var(--vscode-foreground);
            border-bottom-color: var(--vscode-focusBorder);
        }

        /* Hidden utility */
        .hidden {
            display: none !important;
        }

        /* Local Server Setup Dialog */
        .local-server-dialog {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }

        .local-server-dialog-content {
            background: var(--vscode-editor-background);
            border: 1px solid var(--vscode-panel-border);
            border-radius: var(--border-radius);
            max-width: 500px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
            padding: var(--spacing-lg);
        }

        .local-server-dialog-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: var(--spacing-md);
            padding-bottom: var(--spacing-md);
            border-bottom: 1px solid var(--vscode-panel-border);
        }

        .local-server-dialog-title {
            font-size: 16px;
            font-weight: 600;
        }

        .local-server-repo-path {
            background: var(--vscode-textCodeBlock-background);
            padding: var(--spacing-sm) var(--spacing-md);
            border-radius: var(--border-radius);
            font-family: var(--vscode-editor-font-family);
            font-size: 12px;
            margin-bottom: var(--spacing-md);
            word-break: break-all;
        }

        .local-server-status {
            display: flex;
            align-items: center;
            gap: var(--spacing-sm);
            padding: var(--spacing-sm) var(--spacing-md);
            border-radius: var(--border-radius);
            margin-bottom: var(--spacing-md);
        }

        .local-server-status.built {
            background: rgba(40, 167, 69, 0.15);
            color: var(--vscode-charts-green);
        }

        .local-server-status.not-built {
            background: rgba(255, 193, 7, 0.15);
            color: var(--vscode-editorWarning-foreground);
        }

        .local-server-env-section {
            margin-top: var(--spacing-md);
        }

        .local-server-env-section h4 {
            margin: 0 0 var(--spacing-sm) 0;
            font-size: 13px;
        }

        .local-server-env-item {
            margin-bottom: var(--spacing-sm);
        }

        .local-server-env-item label {
            display: block;
            font-size: 12px;
            margin-bottom: 2px;
        }

        .local-server-env-item .required {
            color: var(--vscode-errorForeground);
        }

        .local-server-env-item .optional {
            color: var(--vscode-descriptionForeground);
            font-style: italic;
        }

        .local-server-dialog-actions {
            display: flex;
            justify-content: flex-end;
            gap: var(--spacing-sm);
            margin-top: var(--spacing-lg);
            padding-top: var(--spacing-md);
            border-top: 1px solid var(--vscode-panel-border);
        }
    </style>
</head>
<body>
    <!-- Navigation -->
    <div class="nav-tabs">
        <button class="nav-tab active" data-view="list">Servers</button>
        <button class="nav-tab" data-view="catalog">Catalog</button>
        <button class="nav-tab" data-view="setup">Setup</button>
    </div>

    <!-- Server List View -->
    <div id="list-view" class="view-container active">
        <div class="header">
            <span class="header-title">Configured Servers</span>
            <div class="header-actions">
                <button class="btn btn-primary" id="btn-add-server">+ Add Server</button>
            </div>
        </div>

        <div id="server-list-container">
            <!-- Server cards will be rendered here -->
        </div>

        <div id="empty-list" class="empty-state hidden">
            <div class="empty-state-icon">📦</div>
            <div class="empty-state-title">No servers configured</div>
            <div class="empty-state-desc">Add your first MCP server to get started</div>
            <button class="btn btn-primary" id="btn-add-first-server">+ Add Server</button>
        </div>
    </div>

    <!-- Form View -->
    <div id="form-view" class="view-container">
        <div class="header">
            <span class="header-title" id="form-title">Add Server</span>
            <div class="header-actions">
                <button class="btn btn-secondary" id="btn-cancel-form">Cancel</button>
                <button class="btn btn-primary" id="btn-save-server">Save</button>
            </div>
        </div>

        <div id="form-container">
            <div class="form-group">
                <label class="form-label" for="server-name-input">Server Name *</label>
                <input type="text" id="server-name-input" class="form-input" placeholder="e.g., my-server" required>
                <div class="form-hint">Unique identifier for this server</div>
            </div>

            <div class="form-group">
                <label class="form-label" for="command-type-select">Transport Type</label>
                <select id="command-type-select" class="form-select">
                    <option value="node">node</option>
                    <option value="npx">npx</option>
                    <option value="uvx">uvx</option>
                    <option value="python">python</option>
                    <option value="docker">docker</option>
                    <option value="url">🌐 URL (HTTP/SSE)</option>
                    <option value="custom">custom</option>
                </select>
            </div>

            <div class="form-group">
                <label class="form-label" for="command-input">Command / Package</label>
                <input type="text" id="command-input" class="form-input" placeholder="e.g., @modelcontextprotocol/server-filesystem">
                <div class="form-hint">The command or package to execute</div>
            </div>

            <div class="form-group">
                <label class="form-label" for="args-input">Arguments</label>
                <input type="text" id="args-input" class="form-input" placeholder='e.g., --path /some/path'>
                <div class="form-hint">Space-separated command arguments</div>
            </div>

            <div class="form-group">
                <label class="form-label">Environment Variables</label>
                <div class="env-vars-container" id="env-vars-container">
                    <div id="env-var-rows">
                        <!-- Env var rows will be added here -->
                    </div>
                    <button class="btn btn-secondary" id="btn-add-env-var" type="button">+ Add Variable</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Catalog View -->
    <div id="catalog-view" class="view-container">
        <div class="header">
            <span class="header-title">MCP Server Catalog</span>
        </div>

        <div class="catalog-search">
            <span class="catalog-search-icon">🔍</span>
            <input type="text" id="catalog-search-input" class="form-input" placeholder="Search servers...">
        </div>

        <div id="catalog-container" class="catalog-grid">
            <!-- Catalog cards will be rendered here -->
        </div>

        <div id="catalog-loading" class="loading hidden">
            <div class="spinner"></div>
            <div class="loading-text">Loading catalog from GitHub...</div>
        </div>

        <div id="catalog-error" class="message message-error hidden"></div>
    </div>

    <!-- Setup View -->
    <div id="setup-view" class="view-container">
        <div class="header">
            <span class="header-title">Setup Wizard</span>
        </div>
        
        <div id="setup-container">
            <!-- Setup wizard will be rendered here -->
        </div>
        
        <div id="setup-loading" class="loading hidden">
            <div class="spinner"></div>
            <div class="loading-text">Detecting installed tools...</div>
        </div>
    </div>

    <script nonce="${nonce}">
        (function() {
            const vscode = acquireVsCodeApi();

            // State
            let currentView = 'list';
            let editingServer = null;
            let servers = [];
            let catalog = [];
            let setupTools = [];
            let setupSnippets = [];
            let genericSnippet = null;
            let mcpPackages = { metaMcpInstalled: false, metaMcpVersion: null, mcpExecInstalled: false, mcpExecVersion: null };
            let localServerSetupData = null;
            let activePackages = {};

            // DOM Elements
            const navTabs = document.querySelectorAll('.nav-tab');
            const listView = document.getElementById('list-view');
            const formView = document.getElementById('form-view');
            const catalogView = document.getElementById('catalog-view');
            const setupView = document.getElementById('setup-view');
            const serverListContainer = document.getElementById('server-list-container');
            const emptyList = document.getElementById('empty-list');
            const formTitle = document.getElementById('form-title');
            const catalogContainer = document.getElementById('catalog-container');
            const setupContainer = document.getElementById('setup-container');

            // Form elements
            const serverNameInput = document.getElementById('server-name-input');
            const commandTypeSelect = document.getElementById('command-type-select');
            const commandInput = document.getElementById('command-input');
            const argsInput = document.getElementById('args-input');
            const envVarRows = document.getElementById('env-var-rows');

            // Navigation
            navTabs.forEach(tab => {
                tab.addEventListener('click', () => {
                    const view = tab.dataset.view;
                    switchView(view);
                });
            });

            function switchView(view) {
                currentView = view;
                navTabs.forEach(t => t.classList.toggle('active', t.dataset.view === view));
                listView.classList.toggle('active', view === 'list');
                formView.classList.toggle('active', view === 'form');
                catalogView.classList.toggle('active', view === 'catalog');
                setupView.classList.toggle('active', view === 'setup');

                if (view === 'catalog' && catalog.length === 0) {
                    vscode.postMessage({ type: 'loadCatalog' });
                }
                
                if (view === 'setup' && setupTools.length === 0) {
                    vscode.postMessage({ type: 'loadSetup' });
                }
            }

            // Buttons
            document.getElementById('btn-add-server').addEventListener('click', () => showAddForm());
            document.getElementById('btn-add-first-server')?.addEventListener('click', () => showAddForm());
            document.getElementById('btn-cancel-form').addEventListener('click', () => switchView('list'));
            document.getElementById('btn-save-server').addEventListener('click', saveServer);
            document.getElementById('btn-add-env-var').addEventListener('click', addEnvVarRow);

            // Catalog search
            document.getElementById('catalog-search-input').addEventListener('input', (e) => {
                filterCatalog(e.target.value);
            });

            function showAddForm() {
                editingServer = null;
                formTitle.textContent = 'Add Server';
                resetForm();
                switchView('form');
            }

            function showEditForm(server) {
                editingServer = server.name;
                formTitle.textContent = 'Edit Server';
                populateForm(server);
                switchView('form');
            }

            function resetForm() {
                serverNameInput.value = '';
                commandTypeSelect.value = 'npx';
                commandInput.value = '';
                argsInput.value = '';
                envVarRows.innerHTML = '';
            }

            function populateForm(server) {
                serverNameInput.value = server.name || '';

                // Determine transport type
                if (server.url) {
                    commandTypeSelect.value = 'url';
                    commandInput.value = server.url || '';
                    argsInput.value = '';
                    // Populate headers as env vars for URL transport
                    envVarRows.innerHTML = '';
                    if (server.headers) {
                        Object.entries(server.headers).forEach(([key, value]) => {
                            addEnvVarRow(key, value);
                        });
                    }
                } else {
                    commandTypeSelect.value = server.commandType || 'npx';
                    commandInput.value = server.command || '';
                    argsInput.value = (server.args || []).join(' ');
                    envVarRows.innerHTML = '';
                    if (server.env) {
                        Object.entries(server.env).forEach(([key, value]) => {
                            addEnvVarRow(key, value);
                        });
                    }
                }

                updateFormLabels();
            }

            function updateFormLabels() {
                const isUrl = commandTypeSelect.value === 'url';
                const commandLabel = document.querySelector('label[for="command-input"]');
                const argsGroup = document.getElementById('args-group');
                const envLabel = document.querySelector('.env-vars-label');

                if (commandLabel) {
                    commandLabel.textContent = isUrl ? 'Server URL' : 'Command / Package';
                }
                if (argsGroup) {
                    argsGroup.style.display = isUrl ? 'none' : 'block';
                }
                if (envLabel) {
                    envLabel.textContent = isUrl ? 'Headers' : 'Environment Variables';
                }
            }

            commandTypeSelect.addEventListener('change', updateFormLabels);

            function addEnvVarRow(key = '', value = '') {
                const row = document.createElement('div');
                row.className = 'env-var-row';
                row.innerHTML = \`
                    <input type="text" class="form-input env-key" placeholder="KEY" value="\${key}">
                    <input type="text" class="form-input env-value" placeholder="value" value="\${value}">
                    <button class="btn btn-icon btn-remove" title="Remove">&times;</button>
                \`;
                row.querySelector('.btn-remove').addEventListener('click', () => row.remove());
                envVarRows.appendChild(row);
            }

            function saveServer() {
                const name = serverNameInput.value.trim();
                if (!name) {
                    vscode.postMessage({ type: 'showError', message: 'Server name is required' });
                    return;
                }

                const commandType = commandTypeSelect.value;
                const isUrl = commandType === 'url';

                // Collect key-value pairs (either headers or env vars)
                const keyValuePairs = {};
                envVarRows.querySelectorAll('.env-var-row').forEach(row => {
                    const key = row.querySelector('.env-key').value.trim();
                    const value = row.querySelector('.env-value').value;
                    if (key) keyValuePairs[key] = value;
                });

                let serverConfig;
                if (isUrl) {
                    // URL-based transport
                    const url = commandInput.value.trim();
                    if (!url) {
                        vscode.postMessage({ type: 'showError', message: 'Server URL is required' });
                        return;
                    }
                    serverConfig = {
                        name,
                        url,
                        headers: Object.keys(keyValuePairs).length > 0 ? keyValuePairs : undefined
                    };
                } else {
                    // Stdio transport
                    const command = commandInput.value.trim();
                    const args = argsInput.value.trim().split(/\\s+/).filter(Boolean);
                    serverConfig = {
                        name,
                        commandType,
                        command,
                        args: args.length > 0 ? args : undefined,
                        env: Object.keys(keyValuePairs).length > 0 ? keyValuePairs : undefined
                    };
                }

                vscode.postMessage({
                    type: editingServer ? 'updateServer' : 'addServer',
                    server: serverConfig,
                    originalName: editingServer
                });
            }

            function renderServerList() {
                serverListContainer.innerHTML = '';

                if (servers.length === 0) {
                    emptyList.classList.remove('hidden');
                    return;
                }

                emptyList.classList.add('hidden');

                servers.forEach(server => {
                    const card = document.createElement('div');
                    card.className = 'server-card' + (server.connected ? ' connected' : '') + (server.error ? ' error' : '');
                    const transportInfo = server.url
                        ? \`🌐 \${escapeHtml(server.url)}\`
                        : escapeHtml(server.command || 'No command specified');
                    card.innerHTML = \`
                        <div class="server-card-header">
                            <div>
                                <div class="server-name">\${escapeHtml(server.name)}</div>
                                <div class="server-command">\${transportInfo}</div>
                            </div>
                            <span class="server-status \${server.connected ? 'connected' : 'disconnected'}">
                                \${server.connected ? 'Connected' : 'Disconnected'}
                            </span>
                        </div>
                        <div class="server-actions">
                            <button class="btn btn-secondary btn-edit">Edit</button>
                            <button class="btn btn-secondary btn-delete">Delete</button>
                        </div>
                    \`;

                    card.querySelector('.btn-edit').addEventListener('click', () => showEditForm(server));
                    card.querySelector('.btn-delete').addEventListener('click', () => {
                        vscode.postMessage({ type: 'deleteServer', name: server.name });
                    });

                    serverListContainer.appendChild(card);
                });
            }

            function renderCatalog() {
                catalogContainer.innerHTML = '';

                if (catalog.length === 0) {
                    catalogContainer.innerHTML = '<div class="empty-state"><div class="empty-state-title">No servers found</div></div>';
                    return;
                }

                catalog.forEach(item => {
                    const card = document.createElement('div');
                    card.className = 'catalog-card';
                    const lifecycleBadge = item.lifecycle 
                        ? \`<span class="tag lifecycle-\${(item.lifecycle || '').toLowerCase()}">\${escapeHtml(item.lifecycle)}</span>\` 
                        : '';
                    card.innerHTML = \`
                        <div class="catalog-card-header">
                            <div class="catalog-card-title">\${escapeHtml(item.name)}</div>
                            \${lifecycleBadge}
                        </div>
                        <div class="catalog-card-desc">\${escapeHtml(item.description || '')}</div>
                        <div class="catalog-card-tags">
                            \${(item.tags || []).slice(0, 4).map(tag => \`<span class="tag">\${escapeHtml(tag)}</span>\`).join('')}
                        </div>
                        <div class="catalog-card-actions">
                            <button class="btn btn-primary btn-sm">+ Add</button>
                        </div>
                    \`;
                    card.querySelector('.btn-primary').addEventListener('click', (e) => {
                        e.stopPropagation();
                        vscode.postMessage({ type: 'installFromCatalog', item });
                    });
                    catalogContainer.appendChild(card);
                });
            }

            function filterCatalog(query) {
                const q = query.toLowerCase();
                const cards = catalogContainer.querySelectorAll('.catalog-card');
                cards.forEach((card, i) => {
                    const item = catalog[i];
                    const matches =
                        item.name.toLowerCase().includes(q) ||
                        (item.description || '').toLowerCase().includes(q) ||
                        (item.tags || []).some(t => t.toLowerCase().includes(q));
                    card.classList.toggle('hidden', !matches);
                });
            }

            function escapeHtml(str) {
                const div = document.createElement('div');
                div.textContent = str;
                return div.innerHTML;
            }

            // Setup wizard rendering
            function renderSetup() {
                document.getElementById('setup-loading').classList.add('hidden');
                setupContainer.innerHTML = '';
                
                const installedTools = setupTools.filter(t => t.installed);
                const configuredCount = setupTools.filter(t => t.configured).length;
                
                let html = \`
                    <div class="setup-wizard">
                        <!-- Step 1: Install meta-mcp-server -->
                        <div class="setup-section install-section">
                            <div class="section-header">
                                <span class="section-number">1</span>
                                <h3>Install meta-mcp-server</h3>
                                \${mcpPackages.metaMcpInstalled
                                    ? \`<span class="installed-badge">✓ Installed\${mcpPackages.metaMcpVersion ? \` v\${mcpPackages.metaMcpVersion}\` : ''}</span>\`
                                    : '<span class="not-installed-badge">Not installed</span>'}
                            </div>
                            <p class="section-desc">Proxy server for lazy-loading MCP tools. Reduces token usage by exposing only 3 meta-tools.</p>
                            <div class="install-actions">
                                <button class="btn \${mcpPackages.metaMcpInstalled ? 'btn-secondary' : 'btn-primary'}" id="btn-install-server">
                                    \${mcpPackages.metaMcpInstalled ? 'Reinstall' : 'Install via npm'}
                                </button>
                                <span class="or-text">or run:</span>
                                <code class="install-cmd">npm install -g @justanothermldude/meta-mcp-server</code>
                            </div>
                            <p class="hint-text">After installing, run <code>meta-mcp-server --version</code> to verify.</p>
                        </div>

                        <!-- Step 2: Install mcp-exec (Optional) -->
                        <div class="setup-section install-section">
                            <div class="section-header">
                                <span class="section-number">2</span>
                                <h3>Install mcp-exec <span class="optional-badge">Optional</span></h3>
                                \${mcpPackages.mcpExecInstalled
                                    ? \`<span class="installed-badge">✓ Installed\${mcpPackages.mcpExecVersion ? \` v\${mcpPackages.mcpExecVersion}\` : ''}</span>\`
                                    : '<span class="not-installed-badge">Not installed</span>'}
                            </div>
                            <p class="section-desc">Execute TypeScript/JavaScript code in a secure sandbox with access to other MCP tools.</p>
                            <div class="install-actions">
                                <button class="btn \${mcpPackages.mcpExecInstalled ? 'btn-secondary' : 'btn-primary'}" id="btn-install-mcp-exec">
                                    \${mcpPackages.mcpExecInstalled ? 'Reinstall' : 'Install via npm'}
                                </button>
                                <span class="or-text">or run:</span>
                                <code class="install-cmd">npm install -g @justanothermldude/mcp-exec</code>
                            </div>
                            <p class="hint-text">Enables AI to write and run code that calls other MCP servers.</p>
                        </div>

                        <!-- Step 3: Configure AI Tools -->
                        <div class="setup-section tools-section">
                            <div class="section-header">
                                <span class="section-number">3</span>
                                <h3>Configure Your AI Tools</h3>
                            </div>
                            <p class="section-desc">Add meta-mcp to your AI tools. Detected \${installedTools.length} tool(s), \${configuredCount} configured.</p>
                            <div class="tools-list">
                \`;
                
                // Render each detected tool
                setupTools.forEach(tool => {
                    const statusClass = tool.configured ? 'configured' : (tool.installed ? 'pending' : 'not-installed');
                    const statusText = tool.configured ? '✓ Configured' : (tool.installed ? 'Ready to configure' : 'Not detected');
                    
                    html += \`
                        <div class="tool-card \${statusClass}">
                            <div class="tool-header">
                                <div class="tool-info">
                                    <div class="tool-name">\${escapeHtml(tool.tool.name)}</div>
                                    <div class="tool-path">~\${escapeHtml(tool.tool.configPath)}</div>
                                </div>
                                <span class="tool-status \${statusClass}">\${statusText}</span>
                            </div>
                            \${tool.installed ? \`
                                <div class="tool-actions">
                                    \${!tool.configured ? \`
                                        <button class="btn btn-primary btn-configure" data-tool-id="\${escapeHtml(tool.tool.id)}">
                                            Configure
                                        </button>
                                    \` : \`
                                        <button class="btn btn-secondary btn-configure" data-tool-id="\${escapeHtml(tool.tool.id)}">
                                            Reconfigure
                                        </button>
                                    \`}
                                    <button class="btn btn-secondary btn-copy-snippet" data-tool-id="\${escapeHtml(tool.tool.id)}">
                                        Copy Snippet
                                    </button>
                                </div>
                                \${(mcpPackages.metaMcpInstalled || mcpPackages.mcpExecInstalled) ? \`
                                <div class="package-toggle" data-tool-id="\${escapeHtml(tool.tool.id)}">
                                    <span class="toggle-label">Active package:</span>
                                    <label class="toggle-option\${!mcpPackages.metaMcpInstalled ? ' disabled' : ''}">
                                        <input type="radio" name="pkg-\${escapeHtml(tool.tool.id)}" value="meta-mcp"
                                            \${activePackages[tool.tool.id] === 'meta-mcp' ? 'checked' : ''}
                                            \${!mcpPackages.metaMcpInstalled ? 'disabled' : ''}>
                                        meta-mcp
                                    </label>
                                    <label class="toggle-option\${!mcpPackages.mcpExecInstalled ? ' disabled' : ''}">
                                        <input type="radio" name="pkg-\${escapeHtml(tool.tool.id)}" value="mcp-exec"
                                            \${activePackages[tool.tool.id] === 'mcp-exec' ? 'checked' : ''}
                                            \${!mcpPackages.mcpExecInstalled ? 'disabled' : ''}>
                                        mcp-exec
                                    </label>
                                </div>
                                \` : ''}
                            \` : ''}
                        </div>
                    \`;
                });
                
                html += \`
                            </div>
                        </div>
                        
                        <!-- Other Platforms -->
                        <div class="setup-section other-section">
                            <div class="section-header">
                                <h3>Other Platforms</h3>
                            </div>
                            <p class="section-desc">For Augment, Windsurf, or any other MCP-compatible tool, copy this snippet:</p>
                            <div class="generic-snippet-actions">
                                <button class="btn btn-primary" id="btn-copy-generic-snippet">
                                    Copy Snippet
                                </button>
                            </div>
                            <pre class="snippet-code"><code>\${genericSnippet ? escapeHtml(genericSnippet.snippet) : \`{
  "mcpServers": {
    "meta-mcp": {
      "command": "npx",
      "args": ["-y", "@justanothermldude/meta-mcp-server"],
      "env": {
        "SERVERS_CONFIG": "~/.meta-mcp/servers.json"
      }
    },
    "mcp-exec": {
      "command": "npx",
      "args": ["-y", "@justanothermldude/mcp-exec"],
      "env": {
        "SERVERS_CONFIG": "~/.meta-mcp/servers.json"
      }
    }
  }
}\`}</code></pre>
                        </div>
                        
                        <div class="wizard-footer">
                            <button class="btn btn-secondary" id="btn-refresh-setup">Refresh</button>
                        </div>
                    </div>
                    
                    <style>
                        .setup-wizard { padding: 0; }
                        .setup-section { margin-bottom: var(--spacing-lg); padding: var(--spacing-md); border: 1px solid var(--vscode-panel-border); border-radius: var(--border-radius); }
                        .section-header { display: flex; align-items: center; gap: var(--spacing-sm); margin-bottom: var(--spacing-sm); }
                        .section-header h3 { margin: 0; font-size: 14px; }
                        .section-number { display: flex; align-items: center; justify-content: center; width: 24px; height: 24px; border-radius: 50%; background: var(--vscode-button-background); color: var(--vscode-button-foreground); font-size: 12px; font-weight: 600; }
                        .optional-badge { font-size: 10px; font-weight: 500; color: var(--vscode-descriptionForeground); background: var(--vscode-badge-background); padding: 2px 6px; border-radius: 4px; margin-left: 8px; }
                        .installed-badge { font-size: 10px; font-weight: 500; color: var(--vscode-testing-iconPassed, #73c991); background: rgba(115, 201, 145, 0.15); padding: 2px 8px; border-radius: 4px; margin-left: auto; }
                        .not-installed-badge { font-size: 10px; font-weight: 500; color: var(--vscode-descriptionForeground); background: var(--vscode-badge-background); padding: 2px 8px; border-radius: 4px; margin-left: auto; }
                        .section-desc { color: var(--vscode-descriptionForeground); font-size: 12px; margin: 0 0 var(--spacing-md); }
                        .install-actions { display: flex; align-items: center; gap: var(--spacing-sm); flex-wrap: wrap; }
                        .or-text { color: var(--vscode-descriptionForeground); font-size: 12px; }
                        .install-cmd { background: var(--vscode-textCodeBlock-background); padding: 4px 8px; border-radius: var(--border-radius); font-size: 11px; }
                        .tools-list { display: flex; flex-direction: column; gap: var(--spacing-sm); }
                        .tool-card { border: 1px solid var(--vscode-panel-border); border-radius: var(--border-radius); padding: var(--spacing-md); }
                        .tool-card.configured { border-left: 3px solid var(--vscode-charts-green); }
                        .tool-card.pending { border-left: 3px solid var(--vscode-editorWarning-foreground); }
                        .tool-card.not-installed { opacity: 0.5; }
                        .tool-header { display: flex; justify-content: space-between; align-items: center; }
                        .tool-name { font-weight: 600; }
                        .tool-path { font-size: 11px; color: var(--vscode-descriptionForeground); font-family: var(--vscode-editor-font-family); }
                        .tool-status { font-size: 12px; padding: 2px 8px; border-radius: 10px; }
                        .tool-status.configured { background: rgba(40,167,69,0.2); color: var(--vscode-charts-green); }
                        .tool-status.pending { background: rgba(255,193,7,0.2); color: var(--vscode-editorWarning-foreground); }
                        .tool-actions { display: flex; gap: var(--spacing-sm); margin-top: var(--spacing-md); padding-top: var(--spacing-md); border-top: 1px solid var(--vscode-panel-border); flex-wrap: wrap; }
                        .wizard-footer { margin-top: var(--spacing-lg); padding-top: var(--spacing-md); border-top: 1px solid var(--vscode-panel-border); }
                        .other-section { border-style: dashed; }
                        .generic-snippet-actions { margin-bottom: var(--spacing-sm); }
                        .snippet-code { margin: var(--spacing-sm) 0 0; padding: var(--spacing-md); background: var(--vscode-textCodeBlock-background); border-radius: var(--border-radius); overflow-x: auto; font-size: 11px; }
                        .hint-text { color: var(--vscode-descriptionForeground); font-size: 11px; margin-top: var(--spacing-sm); font-style: italic; }
                        .hint-text code { background: var(--vscode-textCodeBlock-background); padding: 1px 4px; border-radius: 3px; }
                        .package-toggle { display: flex; align-items: center; gap: var(--spacing-sm); margin-top: var(--spacing-sm); padding-top: var(--spacing-sm); border-top: 1px solid var(--vscode-panel-border); flex-wrap: wrap; }
                        .toggle-label { font-size: 12px; color: var(--vscode-descriptionForeground); }
                        .toggle-option { font-size: 12px; display: flex; align-items: center; gap: 4px; cursor: pointer; }
                        .toggle-option.disabled { opacity: 0.4; cursor: not-allowed; }
                        .toggle-option input { margin: 0; }
                    </style>
                \`;
                
                setupContainer.innerHTML = html;
                
                // Attach event listeners
                setupContainer.querySelectorAll('.btn-configure').forEach(btn => {
                    btn.addEventListener('click', () => {
                        const toolId = btn.dataset.toolId;
                        btn.disabled = true;
                        btn.textContent = 'Configuring...';
                        vscode.postMessage({ type: 'configureMetaMcp', payload: { toolId } });
                    });
                });
                
                setupContainer.querySelectorAll('.package-toggle input[type="radio"]').forEach(radio => {
                    radio.addEventListener('change', (e) => {
                        const toggle = e.target.closest('.package-toggle');
                        const toolId = toggle?.dataset?.toolId;
                        const mode = e.target.value;
                        if (toolId && mode) {
                            vscode.postMessage({
                                type: 'switchActivePackage',
                                payload: { toolId, mode }
                            });
                        }
                    });
                });

                setupContainer.querySelectorAll('.btn-copy-snippet').forEach(btn => {
                    btn.addEventListener('click', async () => {
                        const toolId = btn.dataset.toolId;
                        const snippetObj = setupSnippets.find(s => s.toolId === toolId);
                        if (snippetObj?.snippet) {
                            await navigator.clipboard.writeText(snippetObj.snippet);
                            const orig = btn.textContent;
                            btn.textContent = 'Copied!';
                            setTimeout(() => btn.textContent = orig, 2000);
                        }
                    });
                });

                document.getElementById('btn-refresh-setup')?.addEventListener('click', () => {
                    setupTools = [];
                    vscode.postMessage({ type: 'loadSetup' });
                });
                
                document.getElementById('btn-copy-generic-snippet')?.addEventListener('click', async () => {
                    const snippet = genericSnippet?.snippet || \`{
  "mcpServers": {
    "meta-mcp": {
      "command": "npx",
      "args": ["-y", "@justanothermldude/meta-mcp-server"],
      "env": {
        "SERVERS_CONFIG": "~/.meta-mcp/servers.json"
      }
    },
    "mcp-exec": {
      "command": "npx",
      "args": ["-y", "@justanothermldude/mcp-exec"],
      "env": {
        "SERVERS_CONFIG": "~/.meta-mcp/servers.json"
      }
    }
  }
}\`;
                    await navigator.clipboard.writeText(snippet);
                    const btn = document.getElementById('btn-copy-generic-snippet');
                    if (btn) {
                        const orig = btn.textContent;
                        btn.textContent = 'Copied!';
                        setTimeout(() => btn.textContent = orig, 2000);
                    }
                });
                
                document.getElementById('btn-install-server')?.addEventListener('click', () => {
                    const btn = document.getElementById('btn-install-server');
                    if (btn) {
                        btn.textContent = 'Installing...';
                        btn.disabled = true;
                    }
                    vscode.postMessage({ type: 'installMetaMcpServer' });
                });

                document.getElementById('btn-install-mcp-exec')?.addEventListener('click', () => {
                    const btn = document.getElementById('btn-install-mcp-exec');
                    if (btn) {
                        btn.textContent = 'Installing...';
                        btn.disabled = true;
                    }
                    vscode.postMessage({ type: 'installMcpExec' });
                });
            }

            // Local server setup dialog
            function showLocalServerSetupDialog(data) {
                localServerSetupData = data;
                const fullPackagePath = data.repoPath + '/' + data.packagePath;
                
                // Build env var inputs
                let envInputsHtml = '';
                if (data.envVars && data.envVars.length > 0) {
                    envInputsHtml = data.envVars.map(env => \`
                        <div class="local-server-env-item">
                            <label>
                                \${escapeHtml(env.key)}
                                \${env.optional 
                                    ? '<span class="optional">(optional)</span>' 
                                    : '<span class="required">*</span>'}
                            </label>
                            <input type="text" 
                                class="form-input local-env-input" 
                                data-key="\${escapeHtml(env.key)}"
                                placeholder="\${escapeHtml(env.placeholder || '')}"
                                value="\${escapeHtml(env.placeholder || '')}">
                        </div>
                    \`).join('');
                } else {
                    envInputsHtml = '<p class="form-hint">No environment variables required.</p>';
                }
                
                const dialogHtml = \`
                    <div class="local-server-dialog" id="local-server-dialog">
                        <div class="local-server-dialog-content">
                            <div class="local-server-dialog-header">
                                <span class="local-server-dialog-title">Install \${escapeHtml(data.serverName)}</span>
                                <button class="btn btn-icon" id="btn-close-local-dialog">&times;</button>
                            </div>
                            
                            <div class="local-server-repo-path">
                                📁 \${escapeHtml(fullPackagePath)}
                            </div>
                            
                            <div class="local-server-status \${data.isBuilt ? 'built' : 'not-built'}">
                                \${data.isBuilt 
                                    ? '✅ Server is built' 
                                    : '⚠️ Server needs to be built'}
                            </div>
                            
                            \${!data.isBuilt ? \`
                                <button class="btn btn-primary" id="btn-build-local-server" style="margin-bottom: var(--spacing-md);">
                                    Build Server (npm install && npm run build)
                                </button>
                            \` : ''}
                            
                            <div class="local-server-env-section">
                                <h4>🔑 Environment Variables</h4>
                                \${envInputsHtml}
                            </div>
                            
                            <div class="local-server-dialog-actions">
                                <button class="btn btn-secondary" id="btn-cancel-local-setup">Cancel</button>
                                <button class="btn btn-primary" id="btn-complete-local-setup" \${!data.isBuilt ? 'disabled' : ''}>
                                    Install
                                </button>
                            </div>
                        </div>
                    </div>
                \`;
                
                // Add dialog to body
                const dialogContainer = document.createElement('div');
                dialogContainer.innerHTML = dialogHtml;
                document.body.appendChild(dialogContainer.firstElementChild);
                
                // Attach event listeners
                document.getElementById('btn-close-local-dialog')?.addEventListener('click', closeLocalServerDialog);
                document.getElementById('btn-cancel-local-setup')?.addEventListener('click', closeLocalServerDialog);
                
                document.getElementById('btn-build-local-server')?.addEventListener('click', () => {
                    const btn = document.getElementById('btn-build-local-server');
                    if (btn) {
                        btn.textContent = 'Building...';
                        btn.disabled = true;
                    }
                    vscode.postMessage({ 
                        type: 'runLocalServerBuild', 
                        data: { 
                            packagePath: fullPackagePath,
                            serverName: data.serverName 
                        } 
                    });
                });
                
                document.getElementById('btn-complete-local-setup')?.addEventListener('click', () => {
                    // Collect env var values
                    const env = {};
                    document.querySelectorAll('.local-env-input').forEach(input => {
                        const key = input.dataset.key;
                        const value = input.value.trim();
                        if (key && value) {
                            env[key] = value;
                        }
                    });
                    
                    vscode.postMessage({
                        type: 'localServerSetupComplete',
                        data: {
                            serverName: localServerSetupData.serverName,
                            repoPath: localServerSetupData.repoPath,
                            packagePath: localServerSetupData.packagePath,
                            entryPoint: localServerSetupData.entryPoint,
                            runtime: localServerSetupData.runtime,
                            env
                        }
                    });
                    
                    closeLocalServerDialog();
                });
            }
            
            function closeLocalServerDialog() {
                const dialog = document.getElementById('local-server-dialog');
                if (dialog) {
                    dialog.remove();
                }
                localServerSetupData = null;
            }
            
            function updateLocalServerBuildStatus(success) {
                if (success && localServerSetupData) {
                    localServerSetupData.isBuilt = true;
                    // Update the dialog UI
                    const statusEl = document.querySelector('.local-server-status');
                    if (statusEl) {
                        statusEl.className = 'local-server-status built';
                        statusEl.innerHTML = '✅ Server is built';
                    }
                    const buildBtn = document.getElementById('btn-build-local-server');
                    if (buildBtn) {
                        buildBtn.remove();
                    }
                    const installBtn = document.getElementById('btn-complete-local-setup');
                    if (installBtn) {
                        installBtn.disabled = false;
                    }
                } else {
                    // Reset build button
                    const buildBtn = document.getElementById('btn-build-local-server');
                    if (buildBtn) {
                        buildBtn.textContent = 'Build Server (npm install && npm run build)';
                        buildBtn.disabled = false;
                    }
                }
            }

            // Message handling
            window.addEventListener('message', event => {
                const message = event.data;
                console.log('[Meta-MCP Webview] Received message:', message.type, message);
                switch (message.type) {
                    case 'updateServers':
                        servers = message.servers || [];
                        console.log('[Meta-MCP Webview] updateServers:', servers.length, 'servers');
                        renderServerList();
                        break;
                    case 'updateCatalog':
                        catalog = message.catalog || [];
                        document.getElementById('catalog-loading').classList.add('hidden');
                        document.getElementById('catalog-error').classList.add('hidden');
                        renderCatalog();
                        break;
                    case 'catalogLoading':
                        document.getElementById('catalog-loading').classList.remove('hidden');
                        document.getElementById('catalog-error').classList.add('hidden');
                        catalogContainer.innerHTML = '';
                        break;
                    case 'catalogError':
                        document.getElementById('catalog-loading').classList.add('hidden');
                        document.getElementById('catalog-error').classList.remove('hidden');
                        document.getElementById('catalog-error').textContent = message.message || 'Failed to load catalog';
                        break;
                    case 'serverSaved':
                        switchView('list');
                        break;
                    case 'serverDeleted':
                        // List will be refreshed via updateServers
                        break;
                    case 'showError':
                        // Could show inline error, for now just alert
                        break;
                    case 'setupLoading':
                        document.getElementById('setup-loading').classList.remove('hidden');
                        setupContainer.innerHTML = '';
                        break;
                    case 'updateSetup':
                        setupTools = message.tools || [];
                        setupSnippets = message.snippets || [];
                        genericSnippet = message.genericSnippet || null;
                        mcpPackages = message.mcpPackages || { metaMcpInstalled: false, metaMcpVersion: null, mcpExecInstalled: false, mcpExecVersion: null };
                        activePackages = message.activePackages || {};
                        document.getElementById('setup-loading').classList.add('hidden');
                        renderSetup();
                        break;
                    case 'configureMetaMcpResponse':
                        if (message.success) {
                            // Refresh the setup view
                            setupTools = [];
                            vscode.postMessage({ type: 'loadSetup' });
                        }
                        break;
                    case 'switchActivePackageResponse':
                        if (message.success) {
                            setupTools = [];
                            vscode.postMessage({ type: 'loadSetup' });
                        }
                        break;
                    case 'showLocalServerSetup':
                        showLocalServerSetupDialog(message.data);
                        break;
                    case 'localServerBuildComplete':
                        updateLocalServerBuildStatus(message.success);
                        break;
                }
            });

            // Initial load
            vscode.postMessage({ type: 'ready' });
        })();
    </script>
</body>
</html>`;
}

export function createWebviewTemplate(webview: vscode.Webview, extensionUri: vscode.Uri): string {
    const nonce = generateNonce();
    return getWebviewContent({
        extensionUri,
        nonce,
        cspSource: webview.cspSource,
    });
}
