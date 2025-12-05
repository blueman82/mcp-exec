import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import * as vscode from 'vscode';
import {
    AI_TOOL_REGISTRY,
    AIToolDefinition,
    META_MCP_SERVER_NAME,
    getToolById,
} from '../data/aiToolRegistry';
import { getServersConfigPath } from '../utils/environment';

/**
 * Get the meta-mcp server path from settings
 */
function getMetaMcpServerPath(): string {
    const setting = vscode.workspace
        .getConfiguration('meta-mcp')
        .get<string>('serverPath');
    
    if (setting?.trim()) {
        return setting;
    }
    
    // No default - user must configure this
    return '';
}

export interface DetectedTool {
    tool: AIToolDefinition;
    installed: boolean;
    configured: boolean;
    configExists: boolean;
    hasExistingServers: boolean;
    existingServerCount: number;
}

export interface ConfigSnippet {
    toolId: string;
    toolName: string;
    snippet: string;
    fullConfig: Record<string, unknown>;
}

interface McpServerEntry {
    command: string;
    args: string[];
    env?: Record<string, string>;
    type?: string;
}

/**
 * AI Tool Configurator - Detects AI tools and manages MCP configuration
 */
export class AIToolConfigurator {
    private homeDir: string;
    private metaMcpPath: string;
    private serversConfigPath: string;

    constructor(metaMcpPath?: string) {
        this.homeDir = os.homedir();
        // Use provided path, or setting, or empty (will show error in UI)
        this.metaMcpPath = metaMcpPath ?? getMetaMcpServerPath();
        this.serversConfigPath = getServersConfigPath();
    }

    /**
     * Detect all installed AI tools and their configuration status
     */
    detectInstalledTools(): DetectedTool[] {
        return AI_TOOL_REGISTRY.map((tool) => {
            const detectFullPath = path.join(this.homeDir, tool.detectPath);
            const configFullPath = this.resolveConfigPath(tool.configPath);

            const installed = fs.existsSync(detectFullPath);
            const configExists = fs.existsSync(configFullPath);
            const configured = configExists && this.isMetaMcpConfigured(tool);
            
            // Check for existing servers (excluding meta-mcp)
            const existingServers = this.getExistingServers(tool);
            const hasExistingServers = existingServers.length > 0;
            const existingServerCount = existingServers.length;

            return { tool, installed, configured, configExists, hasExistingServers, existingServerCount };
        });
    }
    
    /**
     * Get existing server names from a tool's config (excluding meta-mcp)
     */
    getExistingServers(tool: AIToolDefinition): string[] {
        const configPath = this.resolveConfigPath(tool.configPath);
        if (!fs.existsSync(configPath)) return [];
        
        try {
            const content = fs.readFileSync(configPath, 'utf-8');
            const config = JSON.parse(content);
            const servers = config[tool.configKey] || {};
            return Object.keys(servers).filter(name => name !== META_MCP_SERVER_NAME);
        } catch {
            return [];
        }
    }
    
    /**
     * Migrate servers from a tool's config to servers.json
     * Returns { success, migratedCount, backupPath, configPath, serversConfigPath, toolName, error }
     */
    async migrateServers(toolId: string): Promise<{ 
        success: boolean; 
        migratedCount: number; 
        backupPath?: string; 
        configPath?: string;
        serversConfigPath?: string;
        toolName?: string;
        error?: string 
    }> {
        const tool = getToolById(toolId);
        if (!tool) {
            return { success: false, migratedCount: 0, error: `Unknown tool: ${toolId}` };
        }
        
        const configPath = this.resolveConfigPath(tool.configPath);
        if (!fs.existsSync(configPath)) {
            return { success: false, migratedCount: 0, error: `Config not found: ${configPath}` };
        }
        
        try {
            // Read existing config
            const content = fs.readFileSync(configPath, 'utf-8');
            const config = JSON.parse(content);
            const servers = config[tool.configKey] || {};
            
            // Find servers to migrate (excluding meta-mcp)
            const serversToMigrate = Object.entries(servers)
                .filter(([name]) => name !== META_MCP_SERVER_NAME);
            
            if (serversToMigrate.length === 0) {
                return { success: true, migratedCount: 0, configPath, serversConfigPath: this.serversConfigPath, toolName: tool.name };
            }
            
            // Load or create servers.json
            let serversConfig: { mcpServers: Record<string, unknown> } = { mcpServers: {} };
            const serversJsonPath = this.serversConfigPath;
            
            if (fs.existsSync(serversJsonPath)) {
                const serversContent = fs.readFileSync(serversJsonPath, 'utf-8');
                serversConfig = JSON.parse(serversContent);
            }
            
            // Ensure mcpServers exists (in case file had unexpected structure)
            if (!serversConfig.mcpServers) {
                serversConfig.mcpServers = {};
            }
            
            // Merge servers (don't overwrite existing)
            for (const [name, serverConfig] of serversToMigrate) {
                if (!(name in serversConfig.mcpServers)) {
                    serversConfig.mcpServers[name] = serverConfig;
                }
            }
            
            // Create backup of original config
            const backupPath = `${configPath}.backup.${Date.now()}`;
            fs.copyFileSync(configPath, backupPath);
            
            // Save merged servers.json
            const serversDir = path.dirname(serversJsonPath);
            if (!fs.existsSync(serversDir)) {
                fs.mkdirSync(serversDir, { recursive: true });
            }
            fs.writeFileSync(serversJsonPath, JSON.stringify(serversConfig, null, 2));
            
            // Update original config to only have meta-mcp
            const metaMcpConfig = servers[META_MCP_SERVER_NAME];
            config[tool.configKey] = metaMcpConfig 
                ? { [META_MCP_SERVER_NAME]: metaMcpConfig }
                : {};
            fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
            
            return { 
                success: true, 
                migratedCount: serversToMigrate.length, 
                backupPath,
                configPath,
                serversConfigPath: this.serversConfigPath,
                toolName: tool.name
            };
        } catch (err) {
            const errorMsg = err instanceof Error ? err.message : String(err);
            return { success: false, migratedCount: 0, error: errorMsg };
        }
    }

    /**
     * Check if meta-mcp is already configured in a tool's config
     */
    isMetaMcpConfigured(tool: AIToolDefinition): boolean {
        const configPath = this.resolveConfigPath(tool.configPath);
        if (!fs.existsSync(configPath)) {
            return false;
        }

        try {
            const content = fs.readFileSync(configPath, 'utf-8');
            const config = JSON.parse(content);
            const servers = config[tool.configKey];
            return servers && META_MCP_SERVER_NAME in servers;
        } catch {
            return false;
        }
    }

    /**
     * Generate config snippet for a specific tool
     */
    generateSnippet(toolId: string): ConfigSnippet | null {
        const tool = getToolById(toolId);
        if (!tool) {
            return null;
        }

        const serverEntry = this.buildServerEntry(tool);
        const fullConfig = {
            [tool.configKey]: {
                [META_MCP_SERVER_NAME]: serverEntry,
            },
        };

        return {
            toolId: tool.id,
            toolName: tool.name,
            snippet: JSON.stringify(fullConfig, null, 2),
            fullConfig,
        };
    }

    /**
     * Generate snippets for all registered tools
     */
    generateAllSnippets(): ConfigSnippet[] {
        return AI_TOOL_REGISTRY.map((tool) => this.generateSnippet(tool.id)!).filter(
            Boolean
        );
    }

    /**
     * Generate a generic snippet for other platforms (Augment, etc.)
     * Uses npx if no local path is configured (npm users)
     */
    generateGenericSnippet(): ConfigSnippet {
        const serverEntry = this.metaMcpPath
            ? {
                command: 'node',
                args: [this.metaMcpPath],
                env: { SERVERS_CONFIG: this.serversConfigPath },
            }
            : {
                command: 'npx',
                args: ['-y', '@justanothermldude/meta-mcp-server'],
                env: { SERVERS_CONFIG: this.serversConfigPath },
            };

        const fullConfig = {
            mcpServers: {
                [META_MCP_SERVER_NAME]: serverEntry,
            },
        };

        return {
            toolId: 'generic',
            toolName: 'Other Platforms',
            snippet: JSON.stringify(fullConfig, null, 2),
            fullConfig,
        };
    }

    /**
     * Auto-configure a tool with meta-mcp (creates backup first)
     * Uses npx if no local path configured, creates servers.json if needed
     * @returns Paths to config files and backup
     */
    async autoConfigure(toolId: string): Promise<{ 
        backupPath?: string; 
        configPath?: string;
        serversConfigPath?: string;
        toolName?: string;
        success: boolean; 
        error?: string 
    }> {
        // If local path is set, verify it exists
        if (this.metaMcpPath && !fs.existsSync(this.metaMcpPath)) {
            return { 
                success: false, 
                error: `Server not found at: ${this.metaMcpPath}. Check meta-mcp.serverPath setting.` 
            };
        }

        // Ensure servers.json exists
        this.ensureServersConfig();

        const tool = getToolById(toolId);
        if (!tool) {
            return { success: false, error: `Unknown tool: ${toolId}` };
        }

        const configPath = this.resolveConfigPath(tool.configPath);
        const configDir = path.dirname(configPath);

        // Ensure config directory exists
        if (!fs.existsSync(configDir)) {
            fs.mkdirSync(configDir, { recursive: true });
        }

        // Read existing config or create empty
        let existingConfig: Record<string, unknown> = {};
        let backupPath: string | undefined;

        if (fs.existsSync(configPath)) {
            try {
                const content = fs.readFileSync(configPath, 'utf-8');
                existingConfig = JSON.parse(content);

                // Create backup
                backupPath = `${configPath}.bak`;
                fs.copyFileSync(configPath, backupPath);
            } catch (e) {
                return { success: false, error: `Failed to parse existing config: ${e}` };
            }
        }

        // Check if already configured
        const servers = (existingConfig[tool.configKey] as Record<string, unknown>) ?? {};
        if (META_MCP_SERVER_NAME in servers) {
            return { 
                success: true, 
                backupPath, 
                configPath, 
                serversConfigPath: this.serversConfigPath,
                toolName: tool.name
            }; // Already configured
        }

        // Merge in meta-mcp entry
        const serverEntry = this.buildServerEntry(tool);
        existingConfig[tool.configKey] = {
            ...servers,
            [META_MCP_SERVER_NAME]: serverEntry,
        };

        // Write updated config
        try {
            fs.writeFileSync(configPath, JSON.stringify(existingConfig, null, 2), 'utf-8');
            return { 
                success: true, 
                backupPath, 
                configPath, 
                serversConfigPath: this.serversConfigPath,
                toolName: tool.name
            };
        } catch (e) {
            return { success: false, error: `Failed to write config: ${e}` };
        }
    }

    /**
     * Configure a custom path with meta-mcp entry
     */
    async configureCustomPath(
        configPath: string,
        configKey: string = 'mcpServers',
        requiresType: boolean = false
    ): Promise<{ backupPath?: string; success: boolean; error?: string }> {
        const customTool: AIToolDefinition = {
            id: 'custom',
            name: 'Custom',
            detectPath: '',
            configPath,
            configFormat: requiresType ? 'servers' : 'mcpServers',
            configKey,
            requiresType,
        };

        // Use absolute path directly
        const resolvedPath = configPath.startsWith('~')
            ? path.join(this.homeDir, configPath.slice(1))
            : configPath;

        const configDir = path.dirname(resolvedPath);

        if (!fs.existsSync(configDir)) {
            fs.mkdirSync(configDir, { recursive: true });
        }

        let existingConfig: Record<string, unknown> = {};
        let backupPath: string | undefined;

        if (fs.existsSync(resolvedPath)) {
            try {
                const content = fs.readFileSync(resolvedPath, 'utf-8');
                existingConfig = JSON.parse(content);
                backupPath = `${resolvedPath}.bak`;
                fs.copyFileSync(resolvedPath, backupPath);
            } catch (e) {
                return { success: false, error: `Failed to parse config: ${e}` };
            }
        }

        const servers = (existingConfig[configKey] as Record<string, unknown>) ?? {};
        const serverEntry = this.buildServerEntry(customTool);
        existingConfig[configKey] = {
            ...servers,
            [META_MCP_SERVER_NAME]: serverEntry,
        };

        try {
            fs.writeFileSync(resolvedPath, JSON.stringify(existingConfig, null, 2), 'utf-8');
            return { success: true, backupPath };
        } catch (e) {
            return { success: false, error: `Failed to write config: ${e}` };
        }
    }

    /**
     * Build the meta-mcp server entry for a tool
     * Uses npx if no local path is configured (npm users)
     */
    private buildServerEntry(tool: AIToolDefinition): McpServerEntry {
        let entry: McpServerEntry;
        
        if (this.metaMcpPath) {
            // Local development: use node + local path
            entry = {
                command: 'node',
                args: [this.metaMcpPath],
                env: {
                    SERVERS_CONFIG: this.serversConfigPath,
                },
            };
        } else {
            // npm users: use npx to run the published package
            entry = {
                command: 'npx',
                args: ['-y', '@justanothermldude/meta-mcp-server'],
                env: {
                    SERVERS_CONFIG: this.serversConfigPath,
                },
            };
        }

        if (tool.requiresType) {
            entry.type = 'stdio';
        }

        return entry;
    }

    /**
     * Ensure servers.json exists, create with empty config if not
     */
    private ensureServersConfig(): void {
        if (fs.existsSync(this.serversConfigPath)) {
            return;
        }
        
        const dir = path.dirname(this.serversConfigPath);
        if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true });
        }
        
        const emptyConfig = { mcpServers: {} };
        fs.writeFileSync(this.serversConfigPath, JSON.stringify(emptyConfig, null, 2), 'utf-8');
    }

    /**
     * Resolve config path (handle ~ and relative paths)
     */
    private resolveConfigPath(configPath: string): string {
        if (configPath.startsWith('~')) {
            return path.join(this.homeDir, configPath.slice(1));
        }
        if (path.isAbsolute(configPath)) {
            return configPath;
        }
        return path.join(this.homeDir, configPath);
    }
}
