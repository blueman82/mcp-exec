import { CURATED_SERVERS, type CuratedServer } from '../data/curatedServers';

export interface McpServerEnvVar {
    default?: string;
    optional: boolean;
}

export interface CatalogServer {
    id: string;
    name: string;
    description: string;
    tags: string[];
    repoUrl: string;
    env: Record<string, McpServerEnvVar>;
    lifecycle?: string;
    serverType?: string;
    packagePath?: string;
    repoHint?: string;
    functions?: string[];
}

/**
 * Return the local curated server catalog.
 *
 * The catalog is a static, bundled list of public MCP servers (see
 * data/curatedServers.ts). No network fetch is performed.
 */
export async function fetchCatalog(): Promise<CatalogServer[]> {
    return CURATED_SERVERS.map(transformServer);
}

/**
 * Transform a curated server entry to catalog format.
 */
function transformServer(entry: CuratedServer): CatalogServer {
    const env: Record<string, McpServerEnvVar> = {};
    for (const required of entry.requiredEnv ?? []) {
        env[required.name] = { optional: false };
    }

    return {
        id: entry.id,
        name: entry.name,
        description: entry.description,
        tags: entry.tags,
        repoUrl: entry.docsUrl ?? '',
        env,
        serverType: entry.category,
    };
}

/**
 * Search/filter catalog servers
 */
export function filterCatalog(servers: CatalogServer[], query: string): CatalogServer[] {
    if (!query.trim()) {
        return servers;
    }

    const q = query.toLowerCase();
    return servers.filter(s =>
        s.name.toLowerCase().includes(q) ||
        s.description.toLowerCase().includes(q) ||
        s.tags.some(t => t.toLowerCase().includes(q))
    );
}

/**
 * Clear the cache (no-op — the catalog is static/local).
 */
export function clearCatalogCache(): void {
    // The catalog is bundled and static; nothing to clear.
}
