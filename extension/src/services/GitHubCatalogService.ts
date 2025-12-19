import * as vscode from 'vscode';
import { Octokit } from '@octokit/rest';

const REPO_OWNER = 'Adobe-AIFoundations';
const REGISTRY_REPO = 'easymcp';
const REGISTRY_BRANCH = 'mcp-registry';
const SERVER_LIST_PATH = 'mcp-server-list.json';

export interface McpServerEnvVar {
    default?: string;
    optional: boolean;
}

export interface McpServerEntry {
    name: string;
    description: string;
    tags: string[];
    url: string;
    remote_url?: string;
    icon?: string;
    functions?: string[];
    mode?: string;
    lifecycle?: string;
    published_on?: string;
    server_type?: string;
    package_path?: string;
    repo_hint?: string;
    owner?: string;
    env?: Record<string, McpServerEnvVar>;
    base64_icon?: string;
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

let cachedServers: CatalogServer[] | null = null;
let cacheTimestamp = 0;
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

/**
 * Fetch server catalog from GitHub using VS Code authentication + Octokit
 */
export async function fetchCatalog(): Promise<CatalogServer[]> {
    // Return cached data if still valid
    if (cachedServers && Date.now() - cacheTimestamp < CACHE_TTL_MS) {
        return cachedServers;
    }

    try {
        // Get GitHub session from VS Code (prompts user to sign in if needed)
        const session = await vscode.authentication.getSession('github', ['repo'], { createIfNone: true });
        
        if (!session) {
            throw new Error('GitHub authentication required. Please sign in to GitHub.');
        }
        
        const octokit = new Octokit({ auth: session.accessToken });
        
        const response = await octokit.repos.getContent({
            owner: REPO_OWNER,
            repo: REGISTRY_REPO,
            path: SERVER_LIST_PATH,
            ref: REGISTRY_BRANCH
        });
        
        if (!('content' in response.data)) {
            throw new Error('Response is not a file with content');
        }
        
        const content = Buffer.from(response.data.content, 'base64').toString('utf-8');
        const servers: McpServerEntry[] = JSON.parse(content);
        
        console.log(`[Meta-MCP] Fetched ${servers.length} servers from catalog`);
        
        cachedServers = servers.map(transformServer);
        cacheTimestamp = Date.now();
        
        return cachedServers;
    } catch (err) {
        const errorMsg = err instanceof Error ? err.message : String(err);
        console.error('[Meta-MCP] Failed to fetch catalog:', errorMsg);
        // Return cached data even if stale, or empty array
        return cachedServers ?? [];
    }
}

/**
 * Transform raw server entry to catalog format
 */
function transformServer(entry: McpServerEntry): CatalogServer {
    // Extract ID from URL (last part of path)
    const urlParts = entry.url.split('/');
    const id = urlParts[urlParts.length - 1] || entry.name.toLowerCase().replace(/\s+/g, '-');
    
    return {
        id,
        name: entry.name,
        description: entry.description,
        tags: entry.tags || [],
        repoUrl: entry.url,
        env: entry.env || {},
        lifecycle: entry.lifecycle,
        serverType: entry.server_type,
        packagePath: entry.package_path,
        repoHint: entry.repo_hint,
        functions: entry.functions,
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
 * Clear the cache (useful for refresh)
 */
export function clearCatalogCache(): void {
    cachedServers = null;
    cacheTimestamp = 0;
}


