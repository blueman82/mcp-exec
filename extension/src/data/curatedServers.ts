/**
 * Curated MCP Server Catalog
 * Popular/recommended MCP servers for quick installation
 */

export type ServerCategory =
    | 'filesystem'
    | 'memory'
    | 'web'
    | 'code'
    | 'database'
    | 'ai'
    | 'utility';

export interface RequiredEnvVar {
    /** Environment variable name */
    name: string;
    /** Description shown to user */
    description: string;
    /** Placeholder/hint for input */
    placeholder?: string;
    /** Whether the value is sensitive (password, API key) */
    sensitive?: boolean;
}

export interface CuratedServer {
    /** Unique identifier */
    id: string;
    /** Display name */
    name: string;
    /** Short description */
    description: string;
    /** Category for grouping */
    category: ServerCategory;
    /** Command to run (npx, uvx, node, etc.) */
    command: string;
    /** Command arguments */
    args: string[];
    /** Required environment variables user must provide */
    requiredEnv?: RequiredEnvVar[];
    /** Tags for search/filtering */
    tags: string[];
    /** URL to documentation/repo */
    docsUrl?: string;
}

/**
 * Curated list of popular MCP servers
 */
export const CURATED_SERVERS: CuratedServer[] = [
    // Filesystem
    {
        id: 'filesystem',
        name: 'Filesystem',
        description: 'Read, write, and manage files on your local system',
        category: 'filesystem',
        command: 'npx',
        args: ['-y', '@modelcontextprotocol/server-filesystem', '/path/to/allowed/dir'],
        tags: ['filesystem', 'files', 'read', 'write', 'official'],
        docsUrl: 'https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem',
    },

    // Memory
    {
        id: 'memory',
        name: 'Memory',
        description: 'Knowledge graph-based persistent memory for AI conversations',
        category: 'memory',
        command: 'npx',
        args: ['-y', '@modelcontextprotocol/server-memory'],
        tags: ['memory', 'knowledge', 'graph', 'persistence', 'official'],
        docsUrl: 'https://github.com/modelcontextprotocol/servers/tree/main/src/memory',
    },

    // Web
    {
        id: 'fetch',
        name: 'Fetch',
        description: 'Retrieve and process web content from URLs',
        category: 'web',
        command: 'uvx',
        args: ['mcp-server-fetch'],
        tags: ['web', 'fetch', 'http', 'url', 'scrape', 'official'],
        docsUrl: 'https://github.com/modelcontextprotocol/servers/tree/main/src/fetch',
    },
    {
        id: 'brave-search',
        name: 'Brave Search',
        description: 'Web search using Brave Search API',
        category: 'web',
        command: 'npx',
        args: ['-y', '@modelcontextprotocol/server-brave-search'],
        requiredEnv: [
            {
                name: 'BRAVE_API_KEY',
                description: 'Brave Search API key',
                placeholder: 'BSA...',
                sensitive: true,
            },
        ],
        tags: ['web', 'search', 'brave', 'official'],
        docsUrl: 'https://github.com/modelcontextprotocol/servers/tree/main/src/brave-search',
    },
    {
        id: 'puppeteer',
        name: 'Puppeteer',
        description: 'Browser automation for web scraping and testing',
        category: 'web',
        command: 'npx',
        args: ['-y', '@modelcontextprotocol/server-puppeteer'],
        tags: ['web', 'browser', 'automation', 'scrape', 'puppeteer', 'official'],
        docsUrl: 'https://github.com/modelcontextprotocol/servers/tree/main/src/puppeteer',
    },

    // Code
    {
        id: 'github',
        name: 'GitHub',
        description: 'Interact with GitHub repositories, issues, and PRs',
        category: 'code',
        command: 'npx',
        args: ['-y', '@modelcontextprotocol/server-github'],
        requiredEnv: [
            {
                name: 'GITHUB_PERSONAL_ACCESS_TOKEN',
                description: 'GitHub Personal Access Token',
                placeholder: 'ghp_...',
                sensitive: true,
            },
        ],
        tags: ['code', 'github', 'git', 'repository', 'official'],
        docsUrl: 'https://github.com/modelcontextprotocol/servers/tree/main/src/github',
    },
    {
        id: 'gitlab',
        name: 'GitLab',
        description: 'Interact with GitLab projects, issues, and merge requests',
        category: 'code',
        command: 'npx',
        args: ['-y', '@modelcontextprotocol/server-gitlab'],
        requiredEnv: [
            {
                name: 'GITLAB_PERSONAL_ACCESS_TOKEN',
                description: 'GitLab Personal Access Token',
                placeholder: 'glpat-...',
                sensitive: true,
            },
            {
                name: 'GITLAB_API_URL',
                description: 'GitLab API URL (optional, defaults to gitlab.com)',
                placeholder: 'https://gitlab.com/api/v4',
            },
        ],
        tags: ['code', 'gitlab', 'git', 'repository', 'official'],
        docsUrl: 'https://github.com/modelcontextprotocol/servers/tree/main/src/gitlab',
    },

    // Database
    {
        id: 'sqlite',
        name: 'SQLite',
        description: 'Query and manage SQLite databases',
        category: 'database',
        command: 'uvx',
        args: ['mcp-server-sqlite', '--db-path', '/path/to/database.db'],
        tags: ['database', 'sqlite', 'sql', 'query', 'official'],
        docsUrl: 'https://github.com/modelcontextprotocol/servers/tree/main/src/sqlite',
    },
    {
        id: 'postgres',
        name: 'PostgreSQL',
        description: 'Connect to and query PostgreSQL databases',
        category: 'database',
        command: 'npx',
        args: ['-y', '@modelcontextprotocol/server-postgres'],
        requiredEnv: [
            {
                name: 'POSTGRES_CONNECTION_STRING',
                description: 'PostgreSQL connection string',
                placeholder: 'postgresql://user:pass@localhost:5432/db',
                sensitive: true,
            },
        ],
        tags: ['database', 'postgres', 'postgresql', 'sql', 'official'],
        docsUrl: 'https://github.com/modelcontextprotocol/servers/tree/main/src/postgres',
    },

    // AI
    {
        id: 'context7',
        name: 'Context7',
        description: 'Up-to-date documentation lookup for libraries and frameworks',
        category: 'ai',
        command: 'npx',
        args: ['-y', '@upstash/context7-mcp'],
        tags: ['ai', 'documentation', 'context', 'libraries'],
        docsUrl: 'https://github.com/upstash/context7',
    },
    {
        id: 'sequential-thinking',
        name: 'Sequential Thinking',
        description: 'Dynamic problem-solving through structured thought sequences',
        category: 'ai',
        command: 'npx',
        args: ['-y', '@modelcontextprotocol/server-sequential-thinking'],
        tags: ['ai', 'thinking', 'reasoning', 'problem-solving', 'official'],
        docsUrl: 'https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking',
    },

    // Utility
    {
        id: 'time',
        name: 'Time',
        description: 'Get current time and timezone conversions',
        category: 'utility',
        command: 'uvx',
        args: ['mcp-server-time'],
        tags: ['utility', 'time', 'timezone', 'official'],
        docsUrl: 'https://github.com/modelcontextprotocol/servers/tree/main/src/time',
    },
    {
        id: 'slack',
        name: 'Slack',
        description: 'Send messages and interact with Slack workspaces',
        category: 'utility',
        command: 'npx',
        args: ['-y', '@modelcontextprotocol/server-slack'],
        requiredEnv: [
            {
                name: 'SLACK_BOT_TOKEN',
                description: 'Slack Bot OAuth Token',
                placeholder: 'xoxb-...',
                sensitive: true,
            },
            {
                name: 'SLACK_TEAM_ID',
                description: 'Slack Team/Workspace ID',
                placeholder: 'T0123456789',
            },
        ],
        tags: ['utility', 'slack', 'messaging', 'communication', 'official'],
        docsUrl: 'https://github.com/modelcontextprotocol/servers/tree/main/src/slack',
    },
    {
        id: 'google-drive',
        name: 'Google Drive',
        description: 'Access and search files in Google Drive',
        category: 'utility',
        command: 'npx',
        args: ['-y', '@modelcontextprotocol/server-gdrive'],
        requiredEnv: [
            {
                name: 'GDRIVE_CREDENTIALS_PATH',
                description: 'Path to Google OAuth credentials JSON',
                placeholder: '/path/to/credentials.json',
            },
        ],
        tags: ['utility', 'google', 'drive', 'files', 'storage', 'official'],
        docsUrl: 'https://github.com/modelcontextprotocol/servers/tree/main/src/gdrive',
    },
    {
        id: 'everart',
        name: 'EverArt',
        description: 'AI image generation with multiple models',
        category: 'ai',
        command: 'npx',
        args: ['-y', '@modelcontextprotocol/server-everart'],
        requiredEnv: [
            {
                name: 'EVERART_API_KEY',
                description: 'EverArt API key',
                placeholder: 'ea_...',
                sensitive: true,
            },
        ],
        tags: ['ai', 'image', 'generation', 'art', 'official'],
        docsUrl: 'https://github.com/modelcontextprotocol/servers/tree/main/src/everart',
    },
];

/**
 * Get servers by category
 */
export function getServersByCategory(category: ServerCategory): CuratedServer[] {
    return CURATED_SERVERS.filter((s) => s.category === category);
}

/**
 * Get all unique categories from catalog
 */
export function getAllCategories(): ServerCategory[] {
    return [...new Set(CURATED_SERVERS.map((s) => s.category))];
}

/**
 * Search servers by query (searches name, description, tags)
 */
export function searchServers(query: string): CuratedServer[] {
    const q = query.toLowerCase();
    return CURATED_SERVERS.filter(
        (s) =>
            s.name.toLowerCase().includes(q) ||
            s.description.toLowerCase().includes(q) ||
            s.tags.some((t) => t.toLowerCase().includes(q))
    );
}

/**
 * Get server by ID
 */
export function getServerById(id: string): CuratedServer | undefined {
    return CURATED_SERVERS.find((s) => s.id === id);
}

/**
 * Category display names
 */
export const CATEGORY_LABELS: Record<ServerCategory, string> = {
    filesystem: 'Filesystem',
    memory: 'Memory & Knowledge',
    web: 'Web & Search',
    code: 'Code & Repositories',
    database: 'Databases',
    ai: 'AI & Reasoning',
    utility: 'Utilities',
};
