/**
 * Setup Wizard UI Component
 * Displays detected AI tools and provides one-click setup or copy-paste snippets.
 */

import { DetectedTool, ConfigSnippet } from '../../services/AIToolConfigurator';

export interface SetupWizardCallbacks {
    onCopySnippet: (toolId: string, snippet: string) => void;
    onAutoConfigure: (toolId: string) => Promise<void>;
    onConfigureCustom: (path: string, configKey: string, requiresType: boolean) => Promise<void>;
    onRefresh: () => void;
}

interface ToolIconConfig {
    icon: string;
    color: string;
}

const TOOL_ICONS: Record<string, ToolIconConfig> = {
    'claude-desktop': { icon: '🤖', color: '#CC785C' },
    'cursor': { icon: '⌨️', color: '#00D4AA' },
    'droid': { icon: '🏭', color: '#7C3AED' },
    'vscode': { icon: '💻', color: '#007ACC' },
    'custom': { icon: '⚙️', color: '#6B7280' },
};

/**
 * Escapes HTML special characters
 */
function escapeHtml(str: string): string {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

/**
 * Renders status badge for a detected tool
 */
function renderStatusBadge(tool: DetectedTool): string {
    if (tool.configured) {
        return '<span class="status-badge configured">✓ Configured</span>';
    }
    if (tool.installed) {
        return '<span class="status-badge installed">Detected</span>';
    }
    return '<span class="status-badge not-found">Not Found</span>';
}

/**
 * Renders a single tool card
 */
export function renderToolCard(tool: DetectedTool, snippet: ConfigSnippet | null): string {
    const iconConfig = TOOL_ICONS[tool.tool.id] || TOOL_ICONS.custom;
    const statusBadge = renderStatusBadge(tool);
    const isConfigurable = tool.installed && !tool.configured;

    return `
        <div class="tool-card ${tool.configured ? 'configured' : ''} ${!tool.installed ? 'not-installed' : ''}"
             data-tool-id="${escapeHtml(tool.tool.id)}">
            <div class="tool-card-header">
                <div class="tool-icon" style="background-color: ${iconConfig.color}20; color: ${iconConfig.color}">
                    ${iconConfig.icon}
                </div>
                <div class="tool-info">
                    <div class="tool-name">${escapeHtml(tool.tool.name)}</div>
                    <div class="tool-path">${escapeHtml(tool.tool.configPath)}</div>
                </div>
                ${statusBadge}
            </div>
            ${isConfigurable && snippet ? renderToolActions(tool.tool.id, snippet.snippet) : ''}
            ${tool.configured ? renderConfiguredMessage() : ''}
            ${!tool.installed ? renderNotInstalledMessage() : ''}
        </div>
    `;
}

/**
 * Renders action buttons for configurable tools
 */
function renderToolActions(toolId: string, snippet: string): string {
    return `
        <div class="tool-actions">
            <button class="btn btn-primary btn-auto-configure"
                    data-action="auto-configure"
                    data-tool-id="${escapeHtml(toolId)}"
                    title="Automatically add mcp-exec to this tool's config">
                🚀 Auto-Configure
            </button>
            <button class="btn btn-secondary btn-copy-snippet"
                    data-action="copy-snippet"
                    data-tool-id="${escapeHtml(toolId)}"
                    data-snippet="${escapeHtml(snippet)}"
                    title="Copy configuration snippet to clipboard">
                📋 Copy Snippet
            </button>
        </div>
        <div class="snippet-preview collapsed" data-tool-id="${escapeHtml(toolId)}">
            <button class="btn-toggle-snippet" data-action="toggle-snippet" data-tool-id="${escapeHtml(toolId)}">
                ▶ Show Snippet
            </button>
            <pre class="snippet-code hidden"><code>${escapeHtml(snippet)}</code></pre>
        </div>
    `;
}

function renderConfiguredMessage(): string {
    return `
        <div class="tool-message success">
            ✓ mcp-exec is already configured for this tool
        </div>
    `;
}

function renderNotInstalledMessage(): string {
    return `
        <div class="tool-message muted">
            This tool was not detected on your system
        </div>
    `;
}

/**
 * Renders custom path configuration section
 */
export function renderCustomPathSection(): string {
    return `
        <div class="custom-path-section">
            <div class="section-header">
                <h3>Configure Custom Path</h3>
                <p class="section-desc">Add mcp-exec to a custom configuration file</p>
            </div>
            <div class="custom-path-form">
                <div class="form-group">
                    <label class="form-label" for="custom-path-input">Config File Path</label>
                    <input type="text"
                           id="custom-path-input"
                           class="form-input"
                           placeholder="~/.config/my-tool/mcp.json">
                    <div class="form-hint">Absolute path or path starting with ~</div>
                </div>
                <div class="form-group">
                    <label class="form-label" for="custom-format-select">Config Format</label>
                    <select id="custom-format-select" class="form-select">
                        <option value="mcpServers">mcpServers (Cursor, VS Code)</option>
                        <option value="servers">servers (VS Code style)</option>
                    </select>
                </div>
                <button class="btn btn-primary" id="btn-configure-custom" data-action="configure-custom">
                    Configure Custom Path
                </button>
            </div>
        </div>
    `;
}

/**
 * Renders the complete setup wizard
 */
export function renderSetupWizard(
    detectedTools: DetectedTool[],
    snippets: Map<string, ConfigSnippet>
): string {
    const installedTools = detectedTools.filter(t => t.installed);
    const notInstalledTools = detectedTools.filter(t => !t.installed);
    const configuredCount = detectedTools.filter(t => t.configured).length;
    const pendingCount = installedTools.filter(t => !t.configured).length;

    return `
        <div class="setup-wizard">
            <div class="wizard-header">
                <h2>🔧 Setup Wizard</h2>
                <p class="wizard-desc">Configure mcp-exec for your AI development tools</p>
                <div class="wizard-stats">
                    <span class="stat">${installedTools.length} tools detected</span>
                    <span class="stat-separator">•</span>
                    <span class="stat configured">${configuredCount} configured</span>
                    ${pendingCount > 0 ? `<span class="stat-separator">•</span><span class="stat pending">${pendingCount} pending</span>` : ''}
                </div>
            </div>

            ${pendingCount > 0 ? `
                <div class="quick-actions">
                    <button class="btn btn-primary btn-configure-all" data-action="configure-all">
                        🚀 Configure All (${pendingCount})
                    </button>
                </div>
            ` : ''}

            <div class="tools-section">
                <h3>Detected Tools</h3>
                <div class="tools-grid">
                    ${installedTools.map(t => renderToolCard(t, snippets.get(t.tool.id) || null)).join('')}
                </div>
            </div>

            ${notInstalledTools.length > 0 ? `
                <div class="tools-section collapsed-section">
                    <button class="section-toggle" data-action="toggle-section" data-section="not-installed">
                        ▶ Not Installed (${notInstalledTools.length})
                    </button>
                    <div class="tools-grid hidden" id="not-installed-tools">
                        ${notInstalledTools.map(t => renderToolCard(t, snippets.get(t.tool.id) || null)).join('')}
                    </div>
                </div>
            ` : ''}

            ${renderCustomPathSection()}

            <div class="wizard-footer">
                <button class="btn btn-secondary" id="btn-refresh-wizard" data-action="refresh">
                    🔄 Refresh Detection
                </button>
                <div class="wizard-docs">
                    <span class="docs-label">Need help?</span>
                    <a href="https://github.com/OneAdobe/camp-ops-emea/tree/main/projects/meta-mcp-server#readme" class="docs-link" data-action="open-docs">
                        📖 View Documentation
                    </a>
                </div>
            </div>
        </div>

        <style>
            .setup-wizard {
                padding: var(--spacing-md);
            }

            .wizard-header {
                margin-bottom: var(--spacing-lg);
            }

            .wizard-header h2 {
                margin: 0 0 var(--spacing-xs);
                font-size: 18px;
            }

            .wizard-desc {
                color: var(--vscode-descriptionForeground);
                margin: 0 0 var(--spacing-sm);
            }

            .wizard-stats {
                display: flex;
                gap: var(--spacing-sm);
                font-size: 12px;
                color: var(--vscode-descriptionForeground);
            }

            .wizard-stats .stat.configured {
                color: var(--vscode-charts-green);
            }

            .wizard-stats .stat.pending {
                color: var(--vscode-editorWarning-foreground);
            }

            .stat-separator {
                opacity: 0.5;
            }

            .quick-actions {
                margin-bottom: var(--spacing-lg);
            }

            .btn-configure-all {
                width: 100%;
                padding: 12px;
                font-size: 14px;
            }

            .tools-section {
                margin-bottom: var(--spacing-lg);
            }

            .tools-section h3 {
                font-size: 14px;
                margin: 0 0 var(--spacing-md);
                color: var(--vscode-foreground);
            }

            .tools-grid {
                display: flex;
                flex-direction: column;
                gap: var(--spacing-sm);
            }

            .tool-card {
                border: 1px solid var(--vscode-panel-border);
                border-radius: var(--border-radius);
                padding: var(--spacing-md);
                background: var(--vscode-editor-background);
                transition: border-color 0.2s;
            }

            .tool-card:hover {
                border-color: var(--vscode-focusBorder);
            }

            .tool-card.configured {
                border-left: 3px solid var(--vscode-charts-green);
            }

            .tool-card.not-installed {
                opacity: 0.6;
            }

            .tool-card-header {
                display: flex;
                align-items: center;
                gap: var(--spacing-md);
            }

            .tool-icon {
                width: 40px;
                height: 40px;
                border-radius: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 20px;
                flex-shrink: 0;
            }

            .tool-info {
                flex: 1;
                min-width: 0;
            }

            .tool-name {
                font-weight: 600;
                font-size: 14px;
            }

            .tool-path {
                font-size: 11px;
                color: var(--vscode-descriptionForeground);
                font-family: var(--vscode-editor-font-family);
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }

            .status-badge {
                padding: 4px 8px;
                border-radius: 10px;
                font-size: 11px;
                font-weight: 500;
                flex-shrink: 0;
            }

            .status-badge.configured {
                background: rgba(40, 167, 69, 0.2);
                color: var(--vscode-charts-green);
            }

            .status-badge.installed {
                background: rgba(0, 122, 204, 0.2);
                color: var(--vscode-textLink-foreground);
            }

            .status-badge.not-found {
                background: var(--vscode-badge-background);
                color: var(--vscode-badge-foreground);
            }

            .tool-actions {
                display: flex;
                gap: var(--spacing-sm);
                margin-top: var(--spacing-md);
                padding-top: var(--spacing-md);
                border-top: 1px solid var(--vscode-panel-border);
            }

            .tool-actions .btn {
                flex: 1;
            }

            .snippet-preview {
                margin-top: var(--spacing-sm);
            }

            .btn-toggle-snippet {
                background: none;
                border: none;
                color: var(--vscode-textLink-foreground);
                cursor: pointer;
                font-size: 12px;
                padding: var(--spacing-xs) 0;
            }

            .btn-toggle-snippet:hover {
                text-decoration: underline;
            }

            .snippet-code {
                margin: var(--spacing-sm) 0 0;
                padding: var(--spacing-md);
                background: var(--vscode-textCodeBlock-background);
                border-radius: var(--border-radius);
                overflow-x: auto;
                font-size: 12px;
                line-height: 1.4;
            }

            .snippet-code code {
                background: none;
                padding: 0;
            }

            .tool-message {
                margin-top: var(--spacing-md);
                padding: var(--spacing-sm) var(--spacing-md);
                border-radius: var(--border-radius);
                font-size: 12px;
            }

            .tool-message.success {
                background: rgba(40, 167, 69, 0.1);
                color: var(--vscode-charts-green);
            }

            .tool-message.muted {
                color: var(--vscode-descriptionForeground);
            }

            .collapsed-section {
                border: 1px solid var(--vscode-panel-border);
                border-radius: var(--border-radius);
                padding: var(--spacing-sm);
            }

            .section-toggle {
                background: none;
                border: none;
                color: var(--vscode-foreground);
                cursor: pointer;
                font-size: 13px;
                padding: var(--spacing-sm);
                width: 100%;
                text-align: left;
            }

            .section-toggle:hover {
                background: var(--vscode-list-hoverBackground);
            }

            .custom-path-section {
                margin-top: var(--spacing-lg);
                padding: var(--spacing-md);
                border: 1px dashed var(--vscode-panel-border);
                border-radius: var(--border-radius);
            }

            .section-header h3 {
                margin: 0 0 var(--spacing-xs);
                font-size: 14px;
            }

            .section-desc {
                color: var(--vscode-descriptionForeground);
                font-size: 12px;
                margin: 0 0 var(--spacing-md);
            }

            .custom-path-form {
                display: flex;
                flex-direction: column;
                gap: var(--spacing-md);
            }

            .custom-path-form .form-group {
                margin: 0;
            }

            .wizard-footer {
                margin-top: var(--spacing-lg);
                padding-top: var(--spacing-md);
                border-top: 1px solid var(--vscode-panel-border);
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: var(--spacing-sm);
            }

            .wizard-docs {
                display: flex;
                align-items: center;
                gap: var(--spacing-sm);
                font-size: 12px;
            }

            .docs-label {
                color: var(--vscode-descriptionForeground);
            }

            .docs-link {
                color: var(--vscode-textLink-foreground);
                text-decoration: none;
            }

            .docs-link:hover {
                text-decoration: underline;
            }

            .hidden {
                display: none !important;
            }
        </style>
    `;
}

/**
 * Attaches event listeners to the setup wizard
 */
export function attachSetupWizardListeners(
    container: HTMLElement,
    callbacks: SetupWizardCallbacks,
    snippets: Map<string, ConfigSnippet>
): void {
    container.addEventListener('click', async (event) => {
        const target = event.target as HTMLButtonElement;
        const action = target.dataset?.action;

        if (!action) return;

        switch (action) {
            case 'auto-configure': {
                const toolId = target.dataset.toolId;
                if (toolId) {
                    target.disabled = true;
                    target.textContent = '⏳ Configuring...';
                    try {
                        await callbacks.onAutoConfigure(toolId);
                    } finally {
                        target.disabled = false;
                        target.textContent = '🚀 Auto-Configure';
                    }
                }
                break;
            }

            case 'copy-snippet': {
                const toolId = target.dataset.toolId;
                const snippet = snippets.get(toolId || '')?.snippet;
                if (toolId && snippet) {
                    await navigator.clipboard.writeText(snippet);
                    callbacks.onCopySnippet(toolId, snippet);
                    const originalText = target.textContent;
                    target.textContent = '✓ Copied!';
                    setTimeout(() => {
                        target.textContent = originalText;
                    }, 2000);
                }
                break;
            }

            case 'toggle-snippet': {
                const toolId = target.dataset.toolId;
                const previewContainer = container.querySelector(`.snippet-preview[data-tool-id="${toolId}"]`);
                const codeBlock = previewContainer?.querySelector('.snippet-code');
                if (codeBlock) {
                    const isHidden = codeBlock.classList.contains('hidden');
                    codeBlock.classList.toggle('hidden');
                    target.textContent = isHidden ? '▼ Hide Snippet' : '▶ Show Snippet';
                }
                break;
            }

            case 'toggle-section': {
                const sectionId = target.dataset.section;
                const sectionContent = container.querySelector(`#${sectionId}-tools`);
                if (sectionContent) {
                    const isHidden = sectionContent.classList.contains('hidden');
                    sectionContent.classList.toggle('hidden');
                    target.textContent = target.textContent?.replace(isHidden ? '▶' : '▼', isHidden ? '▼' : '▶') || '';
                }
                break;
            }

            case 'configure-all': {
                const toolCards = Array.from(container.querySelectorAll('.tool-card:not(.configured):not(.not-installed)'));
                target.disabled = true;
                target.textContent = '⏳ Configuring...';

                for (const card of toolCards) {
                    const toolId = (card as HTMLElement).dataset.toolId;
                    if (toolId) {
                        try {
                            await callbacks.onAutoConfigure(toolId);
                        } catch {
                            // Continue with other tools
                        }
                    }
                }

                target.disabled = false;
                callbacks.onRefresh();
                break;
            }

            case 'configure-custom': {
                const pathInput = container.querySelector('#custom-path-input') as HTMLInputElement;
                const formatSelect = container.querySelector('#custom-format-select') as HTMLSelectElement;

                const path = pathInput?.value.trim();
                const format = formatSelect?.value || 'mcpServers';
                const requiresType = format === 'servers';

                if (!path) {
                    pathInput?.classList.add('invalid');
                    return;
                }

                pathInput?.classList.remove('invalid');
                target.disabled = true;
                target.textContent = '⏳ Configuring...';

                try {
                    await callbacks.onConfigureCustom(path, format, requiresType);
                    pathInput.value = '';
                } finally {
                    target.disabled = false;
                    target.textContent = 'Configure Custom Path';
                }
                break;
            }

            case 'refresh':
                callbacks.onRefresh();
                break;
        }
    });
}

/**
 * Creates and initializes the setup wizard component
 */
export function createSetupWizardComponent(
    container: HTMLElement,
    callbacks: SetupWizardCallbacks
): {
    update: (tools: DetectedTool[], snippets: ConfigSnippet[]) => void;
} {
    let snippetMap = new Map<string, ConfigSnippet>();

    function update(tools: DetectedTool[], snippets: ConfigSnippet[]): void {
        snippetMap = new Map(snippets.map(s => [s.toolId, s]));
        container.innerHTML = renderSetupWizard(tools, snippetMap);
        attachSetupWizardListeners(container, callbacks, snippetMap);
    }

    return { update };
}

/**
 * Shows a confirmation dialog before auto-configuring
 */
export function showConfigureConfirmDialog(
    toolName: string,
    configPath: string
): Promise<boolean> {
    return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.className = 'dialog-overlay';
        overlay.innerHTML = `
            <div class="dialog-content">
                <div class="dialog-title">Configure ${escapeHtml(toolName)}?</div>
                <div class="dialog-message">
                    This will add mcp-exec to:<br>
                    <code>${escapeHtml(configPath)}</code><br><br>
                    A backup will be created before making changes.
                </div>
                <div class="dialog-actions">
                    <button class="btn btn-secondary" data-action="cancel">Cancel</button>
                    <button class="btn btn-primary" data-action="confirm">Configure</button>
                </div>
            </div>
        `;

        overlay.addEventListener('click', (e) => {
            const target = e.target as HTMLElement;
            const action = target.dataset.action;

            if (action === 'confirm') {
                overlay.remove();
                resolve(true);
            } else if (action === 'cancel' || target === overlay) {
                overlay.remove();
                resolve(false);
            }
        });

        document.body.appendChild(overlay);
    });
}
