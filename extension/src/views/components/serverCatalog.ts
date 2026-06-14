/**
 * Server Catalog Component
 * Provides UI functions for browsing and installing curated MCP servers
 */

import {
    CuratedServer,
    CURATED_SERVERS,
    CATEGORY_LABELS,
    ServerCategory,
    getAllCategories,
    searchServers,
} from '../../data/curatedServers';

/**
 * Convert CuratedServer to format expected by webview
 */
export interface CatalogItem {
    id: string;
    name: string;
    description: string;
    tags: string[];
    category: string;
    categoryLabel: string;
}

/**
 * Transform curated servers to catalog items for webview
 */
export function getCatalogItems(): CatalogItem[] {
    return CURATED_SERVERS.map((server) => ({
        id: server.id,
        name: server.name,
        description: server.description,
        tags: server.tags,
        category: server.category,
        categoryLabel: CATEGORY_LABELS[server.category],
    }));
}

/**
 * Get catalog items grouped by category
 */
export function getCatalogByCategory(): Record<string, CatalogItem[]> {
    const categories = getAllCategories();
    const result: Record<string, CatalogItem[]> = {};

    for (const category of categories) {
        result[CATEGORY_LABELS[category]] = CURATED_SERVERS.filter(
            (s) => s.category === category
        ).map((server) => ({
            id: server.id,
            name: server.name,
            description: server.description,
            tags: server.tags,
            category: server.category,
            categoryLabel: CATEGORY_LABELS[server.category],
        }));
    }

    return result;
}

/**
 * Search catalog and return matching items
 */
export function searchCatalog(query: string): CatalogItem[] {
    const results = searchServers(query);
    return results.map((server) => ({
        id: server.id,
        name: server.name,
        description: server.description,
        tags: server.tags,
        category: server.category,
        categoryLabel: CATEGORY_LABELS[server.category],
    }));
}

/**
 * Data needed to prompt user for env vars when installing
 */
export interface InstallPrompt {
    server: CuratedServer;
    envVarsNeeded: Array<{
        name: string;
        description: string;
        placeholder?: string;
        sensitive?: boolean;
    }>;
}

/**
 * Get installation data for a server
 * Returns server config and any env vars user needs to provide
 */
export function getInstallPrompt(serverId: string): InstallPrompt | null {
    const server = CURATED_SERVERS.find((s) => s.id === serverId);
    if (!server) {
        return null;
    }

    return {
        server,
        envVarsNeeded: server.requiredEnv || [],
    };
}

/**
 * Server configuration ready to be added to backends.json
 */
export interface ServerConfig {
    command: string;
    args: string[];
    env?: Record<string, string>;
}

/**
 * Build final server config from curated server + user-provided env vars
 */
export function buildServerConfig(
    serverId: string,
    envValues: Record<string, string> = {},
    argsOverrides: string[] = []
): ServerConfig | null {
    const server = CURATED_SERVERS.find((s) => s.id === serverId);
    if (!server) {
        return null;
    }

    const config: ServerConfig = {
        command: server.command,
        args: argsOverrides.length > 0 ? argsOverrides : [...server.args],
    };

    // Only add env if there are values
    if (Object.keys(envValues).length > 0) {
        config.env = envValues;
    }

    return config;
}

/**
 * Get category icon/emoji for display
 */
export function getCategoryIcon(category: ServerCategory): string {
    const icons: Record<ServerCategory, string> = {
        filesystem: '📁',
        memory: '🧠',
        web: '🌐',
        code: '💻',
        database: '🗄️',
        ai: '🤖',
        utility: '🔧',
    };
    return icons[category] || '📦';
}

/**
 * Generate HTML for catalog grid (used in webview)
 */
export function renderCatalogHTML(): string {
    const categories = getAllCategories();

    let html = '';

    for (const category of categories) {
        const servers = CURATED_SERVERS.filter((s) => s.category === category);
        const icon = getCategoryIcon(category);
        const label = CATEGORY_LABELS[category];

        html += `
            <div class="catalog-category">
                <h3 class="catalog-category-title">${icon} ${escapeHtml(label)}</h3>
                <div class="catalog-category-grid">
        `;

        for (const server of servers) {
            html += `
                <div class="catalog-card" data-server-id="${escapeHtml(server.id)}">
                    <div class="catalog-card-title">${escapeHtml(server.name)}</div>
                    <div class="catalog-card-desc">${escapeHtml(server.description)}</div>
                    <div class="catalog-card-tags">
                        ${server.tags
                            .slice(0, 3)
                            .map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`)
                            .join('')}
                    </div>
                    ${
                        server.requiredEnv && server.requiredEnv.length > 0
                            ? '<div class="catalog-card-env-hint">🔑 Requires configuration</div>'
                            : ''
                    }
                </div>
            `;
        }

        html += `
                </div>
            </div>
        `;
    }

    return html;
}

/**
 * Escape HTML entities
 */
function escapeHtml(str: string): string {
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
