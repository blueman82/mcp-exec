/**
 * Server List Component
 * Renders list of configured servers with toggle/delete actions.
 * Uses event delegation for efficient DOM event handling.
 */

export interface ServerConfig {
    name: string;
    commandType: 'node' | 'npx' | 'uvx' | 'python' | 'custom';
    command: string;
    args?: string[];
    env?: Record<string, string>;
    connected?: boolean;
    error?: boolean;
}

export interface ServerListCallbacks {
    onEdit: (server: ServerConfig) => void;
    onDelete: (serverName: string) => void;
    onToggle?: (serverName: string) => void;
}

/**
 * Transport type badge configuration
 */
const TRANSPORT_BADGES: Record<string, { label: string; className: string }> = {
    node: { label: 'NODE', className: 'command-badge node' },
    npx: { label: 'NPX', className: 'command-badge npx' },
    uvx: { label: 'UVX', className: 'command-badge uvx' },
    python: { label: 'PY', className: 'command-badge python' },
    custom: { label: 'CMD', className: 'command-badge custom' },
};

/**
 * Escapes HTML special characters to prevent XSS
 */
function escapeHtml(str: string): string {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

/**
 * Truncates command preview for display
 */
function truncateCommand(command: string, maxLength = 40): string {
    if (command.length <= maxLength) return command;
    return command.substring(0, maxLength - 3) + '...';
}

/**
 * Generates HTML for a single server card
 */
export function renderServerCard(server: ServerConfig): string {
    const badge = TRANSPORT_BADGES[server.commandType] || TRANSPORT_BADGES.custom;
    const commandPreview = truncateCommand(server.command || 'No command specified');
    const statusClass = server.connected ? 'connected' : server.error ? 'error' : '';
    const statusLabel = server.connected ? 'Connected' : 'Disconnected';
    const cardClass = `server-card${statusClass ? ` ${statusClass}` : ''}`;

    return `
        <div class="${cardClass}" data-server-name="${escapeHtml(server.name)}">
            <div class="server-card-header">
                <div>
                    <div class="server-name">
                        <span class="status-dot ${server.connected ? 'connected' : server.error ? 'error' : 'disconnected'}"></span>
                        ${escapeHtml(server.name)}
                    </div>
                    <div class="server-command">${escapeHtml(commandPreview)}</div>
                </div>
                <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 4px;">
                    <span class="${badge.className}">${badge.label}</span>
                    <span class="server-status ${server.connected ? 'connected' : 'disconnected'}">
                        ${statusLabel}
                    </span>
                </div>
            </div>
            <div class="server-actions">
                <button class="btn btn-secondary btn-edit" data-action="edit" data-server="${escapeHtml(server.name)}">Edit</button>
                <button class="btn btn-secondary btn-delete" data-action="delete" data-server="${escapeHtml(server.name)}">Delete</button>
            </div>
        </div>
    `;
}

/**
 * Renders the complete server list into the container
 */
export function renderServerList(
    container: HTMLElement,
    servers: ServerConfig[],
    callbacks: ServerListCallbacks
): void {
    // Clear container
    container.innerHTML = '';

    if (servers.length === 0) {
        return;
    }

    // Render all server cards
    const html = servers.map(renderServerCard).join('');
    container.innerHTML = html;

    // Event delegation - single listener on container
    container.addEventListener('click', (event) => {
        const target = event.target as HTMLElement;
        const action = target.dataset.action;
        const serverName = target.dataset.server;

        if (!action || !serverName) return;

        const server = servers.find((s) => s.name === serverName);
        if (!server) return;

        switch (action) {
            case 'edit':
                callbacks.onEdit(server);
                break;
            case 'delete':
                callbacks.onDelete(serverName);
                break;
            case 'toggle':
                callbacks.onToggle?.(serverName);
                break;
        }
    });
}

/**
 * Creates server list component with state management
 */
export function createServerListComponent(
    container: HTMLElement,
    callbacks: ServerListCallbacks
): {
    update: (servers: ServerConfig[]) => void;
    getServers: () => ServerConfig[];
} {
    let currentServers: ServerConfig[] = [];

    function update(servers: ServerConfig[]): void {
        currentServers = [...servers];
        renderServerList(container, currentServers, callbacks);
    }

    function getServers(): ServerConfig[] {
        return [...currentServers];
    }

    return { update, getServers };
}
