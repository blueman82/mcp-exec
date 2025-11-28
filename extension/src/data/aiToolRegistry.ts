/**
 * AI Tool Registry - Configuration patterns for supported AI tools
 */

export type ConfigFormat = 'mcpServers' | 'servers';

export interface AIToolDefinition {
    /** Unique identifier */
    id: string;
    /** Display name */
    name: string;
    /** Path to check for tool installation (relative to home) */
    detectPath: string;
    /** Path to config file (relative to home, or absolute) */
    configPath: string;
    /** Config format: 'mcpServers' or 'servers' (VS Code style) */
    configFormat: ConfigFormat;
    /** Key in config where MCP servers are defined */
    configKey: string;
    /** Whether VS Code-style 'type' field is required */
    requiresType?: boolean;
}

/**
 * Registry of known AI tools and their MCP configuration patterns
 */
export const AI_TOOL_REGISTRY: AIToolDefinition[] = [
    {
        id: 'claude',
        name: 'Claude',
        detectPath: '.claude.json',
        configPath: '.claude.json',
        configFormat: 'mcpServers',
        configKey: 'mcpServers',
    },
    {
        id: 'cursor',
        name: 'Cursor',
        detectPath: '.cursor',
        configPath: '.cursor/mcp.json',
        configFormat: 'mcpServers',
        configKey: 'mcpServers',
    },
    {
        id: 'droid',
        name: 'Droid (Factory)',
        detectPath: '.factory',
        configPath: '.factory/mcp.json',
        configFormat: 'mcpServers',
        configKey: 'mcpServers',
    },
    {
        id: 'vscode',
        name: 'VS Code',
        detectPath: '.vscode',
        configPath: '.vscode/mcp.json',
        configFormat: 'servers',
        configKey: 'servers',
        requiresType: true,
    },
];

/**
 * Meta-MCP server entry name
 */
export const META_MCP_SERVER_NAME = 'meta-mcp';

/**
 * Gets tool definition by ID
 */
export function getToolById(id: string): AIToolDefinition | undefined {
    return AI_TOOL_REGISTRY.find((t) => t.id === id);
}
