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

        .btn-success {
            background-color: var(--vscode-charts-green) !important;
            color: white !important;
        }

        .btn-warning {
            background-color: var(--vscode-editorWarning-foreground) !important;
            color: black !important;
        }

        /* Modal styles */
        .modal-overlay {
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

        .modal-content {
            background: var(--vscode-editor-background);
            border: 1px solid var(--vscode-panel-border);
            border-radius: var(--border-radius);
            padding: var(--spacing-lg);
            min-width: 300px;
            position: relative;
        }

        .modal-content h3 {
            margin: 0 0 var(--spacing-sm);
        }

        .modal-content p {
            color: var(--vscode-descriptionForeground);
            margin: 0 0 var(--spacing-md);
        }

        .modal-actions {
            display: flex;
            gap: var(--spacing-sm);
        }

        .modal-close {
            position: absolute;
            top: 8px;
            right: 8px;
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

        .search-container {
            margin-bottom: var(--spacing-md);
        }

        .search-container input {
            width: 100%;
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

        <div class="search-container">
            <input type="text" class="form-input" id="server-search-input" placeholder="Search servers...">
        </div>

        <div id="server-list-container">
            <!-- Server cards will be rendered here -->
        </div>

        <div id="empty-list" class="empty-state hidden">
            <div class="empty-state-icon">📦</div>
            <div class="empty-state-title">No servers configured</div>
            <div class="empty-state-desc">Click "+ Add Server" above to get started</div>
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
                <label class="form-label" for="command-type-select">Command Type</label>
                <select id="command-type-select" class="form-select">
                    <option value="node">node</option>
                    <option value="npx">npx</option>
                    <option value="uvx">uvx</option>
                    <option value="python">python</option>
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

            // Buttons - Show choice modal for Add Server
            document.getElementById('btn-add-server').addEventListener('click', () => showAddChoiceModal());
            
            // Server search
            document.getElementById('server-search-input').addEventListener('input', (e) => {
                filterServers(e.target.value);
            });
            
            function showAddChoiceModal() {
                const modal = document.createElement('div');
                modal.className = 'modal-overlay';
                modal.innerHTML = \`
                    <div class="modal-content">
                        <h3>Add Server</h3>
                        <p>How would you like to add a server?</p>
                        <div class="modal-actions">
                            <button class="btn btn-primary" id="modal-btn-catalog">From Catalog</button>
                            <button class="btn btn-secondary" id="modal-btn-manual">Manual</button>
                        </div>
                        <button class="btn btn-icon modal-close">&times;</button>
                    </div>
                \`;
                document.body.appendChild(modal);
                
                modal.querySelector('#modal-btn-catalog').addEventListener('click', () => {
                    modal.remove();
                    switchView('catalog');
                });
                modal.querySelector('#modal-btn-manual').addEventListener('click', () => {
                    modal.remove();
                    showAddForm();
                });
                modal.querySelector('.modal-close').addEventListener('click', () => modal.remove());
                modal.addEventListener('click', (e) => {
                    if (e.target === modal) modal.remove();
                });
            }
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
                
                // Detect command type from command value
                const knownCommands = ['npx', 'node', 'uvx', 'docker'];
                const cmd = server.command || '';
                const detectedType = knownCommands.includes(cmd) ? cmd : 'custom';
                commandTypeSelect.value = detectedType;
                
                // For known commands, the "command" input should be empty (args has the actual command)
                // For custom, show the full command
                commandInput.value = detectedType === 'custom' ? cmd : '';
                argsInput.value = (server.args || []).join(' ');

                envVarRows.innerHTML = '';
                if (server.env) {
                    Object.entries(server.env).forEach(([key, value]) => {
                        addEnvVarRow(key, value);
                    });
                }
            }

            function addEnvVarRow(key = '', value = '') {
                const row = document.createElement('div');
                row.className = 'env-var-row';
                const isSensitive = /password|token|secret|key|pat|credential|api_key/i.test(key);
                row.innerHTML = \`
                    <input type="text" class="form-input env-key" placeholder="KEY" value="\${key}">
                    <input type="\${isSensitive ? 'password' : 'text'}" class="form-input env-value" placeholder="value" value="\${value}">
                    <button class="btn btn-icon btn-toggle-visibility" title="Show/Hide" type="button">\${isSensitive ? '👁' : ''}</button>
                    <button class="btn btn-icon btn-remove" title="Remove">&times;</button>
                \`;
                row.querySelector('.btn-remove').addEventListener('click', () => row.remove());
                
                // Toggle password visibility
                const toggleBtn = row.querySelector('.btn-toggle-visibility');
                const valueInput = row.querySelector('.env-value');
                toggleBtn.addEventListener('click', () => {
                    if (valueInput.type === 'password') {
                        valueInput.type = 'text';
                        toggleBtn.textContent = '🙈';
                    } else {
                        valueInput.type = 'password';
                        toggleBtn.textContent = '👁';
                    }
                });
                
                // Update input type when key changes (detect sensitive keys)
                const keyInput = row.querySelector('.env-key');
                keyInput.addEventListener('blur', () => {
                    const newIsSensitive = /password|token|secret|key|pat|credential|api_key/i.test(keyInput.value);
                    if (newIsSensitive && valueInput.type === 'text') {
                        valueInput.type = 'password';
                        toggleBtn.textContent = '👁';
                    }
                    toggleBtn.style.visibility = newIsSensitive ? 'visible' : 'hidden';
                });
                toggleBtn.style.visibility = isSensitive ? 'visible' : 'hidden';
                
                envVarRows.appendChild(row);
            }

            function saveServer() {
                const name = serverNameInput.value.trim();
                if (!name) {
                    vscode.postMessage({ type: 'showError', message: 'Server name is required' });
                    return;
                }

                const commandType = commandTypeSelect.value;
                const command = commandInput.value.trim();
                const args = argsInput.value.trim().split(/\\s+/).filter(Boolean);

                const env = {};
                envVarRows.querySelectorAll('.env-var-row').forEach(row => {
                    const key = row.querySelector('.env-key').value.trim();
                    const value = row.querySelector('.env-value').value;
                    if (key) env[key] = value;
                });

                const serverConfig = {
                    name,
                    commandType,
                    command,
                    args: args.length > 0 ? args : undefined,
                    env: Object.keys(env).length > 0 ? env : undefined
                };

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
                    card.innerHTML = \`
                        <div class="server-card-header">
                            <div>
                                <div class="server-name">\${escapeHtml(server.name)}</div>
                                <div class="server-command">\${escapeHtml(server.command || 'No command specified')}</div>
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

            function filterServers(query) {
                const q = query.toLowerCase();
                const cards = serverListContainer.querySelectorAll('.server-card');
                cards.forEach((card, i) => {
                    const server = servers[i];
                    const matches =
                        server.name.toLowerCase().includes(q) ||
                        (server.command || '').toLowerCase().includes(q) ||
                        (server.description || '').toLowerCase().includes(q);
                    card.classList.toggle('hidden', !matches);
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
                            </div>
                            <p class="section-desc">Install the meta-mcp server globally via npm (required for all tools).</p>
                            <div class="install-actions">
                                <button class="btn btn-primary" id="btn-install-server">
                                    Install via npm
                                </button>
                                <span class="or-text">or run:</span>
                                <code class="install-cmd">npm install -g @justanothermldude/meta-mcp-server</code>
                            </div>
                            <p class="hint-text">After installing, run <code>meta-mcp-server --version</code> to verify.</p>
                        </div>
                        
                        <!-- Step 2: Configure AI Tools -->
                        <div class="setup-section tools-section">
                            <div class="section-header">
                                <span class="section-number">2</span>
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
                                    \${tool.hasExistingServers ? \`
                                        <button class="btn btn-secondary btn-migrate" data-tool-id="\${escapeHtml(tool.tool.id)}">
                                            Migrate Servers
                                        </button>
                                    \` : ''}
                                </div>
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
                
                setupContainer.querySelectorAll('.btn-migrate').forEach(btn => {
                    btn.addEventListener('click', () => {
                        const toolId = btn.dataset.toolId;
                        btn.disabled = true;
                        btn.textContent = 'Migrating...';
                        vscode.postMessage({ type: 'migrateServers', payload: { toolId } });
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
                        btn.textContent = 'Opening terminal...';
                        btn.disabled = true;
                        
                        // Poll for installation status after 5 seconds
                        setTimeout(() => {
                            btn.textContent = 'Checking...';
                            vscode.postMessage({ type: 'checkInstallStatus' });
                        }, 5000);
                    }
                    vscode.postMessage({ type: 'installMetaMcpServer' });
                });
            }

            // Message handling
            window.addEventListener('message', event => {
                const message = event.data;
                switch (message.type) {
                    case 'updateServers':
                        servers = message.servers || [];
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
                    case 'installStatusResponse':
                        const installBtn = document.getElementById('btn-install-server');
                        if (installBtn) {
                            if (message.installed) {
                                installBtn.textContent = 'Installed!';
                                installBtn.classList.add('btn-success');
                                setTimeout(() => {
                                    installBtn.textContent = 'Install via npm';
                                    installBtn.classList.remove('btn-success');
                                    installBtn.disabled = false;
                                }, 3000);
                            } else {
                                installBtn.textContent = 'Not found - check terminal';
                                installBtn.classList.add('btn-warning');
                                setTimeout(() => {
                                    installBtn.textContent = 'Install via npm';
                                    installBtn.classList.remove('btn-warning');
                                    installBtn.disabled = false;
                                }, 5000);
                            }
                        }
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
