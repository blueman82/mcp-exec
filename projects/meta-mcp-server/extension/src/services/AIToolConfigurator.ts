import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import * as vscode from 'vscode';
import { execSync } from 'child_process';
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

export interface McpPackageStatus {
    metaMcpInstalled: boolean;
    metaMcpVersion: string | null;
    metaMcpSource: 'global' | 'local' | null;
    mcpExecInstalled: boolean;
    mcpExecVersion: string | null;
    mcpExecSource: 'global' | 'local' | null;
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
    private mcpExecPath: string;
    private serversConfigPath: string;

    constructor(metaMcpPath?: string, mcpExecPath?: string) {
        this.homeDir = os.homedir();
        // Use provided path, or setting, or empty (will show error in UI)
        this.metaMcpPath = metaMcpPath ?? getMetaMcpServerPath();
        this.mcpExecPath = mcpExecPath ?? this.getMcpExecPath();
        this.serversConfigPath = getServersConfigPath();
    }

    private getMcpExecPath(): string {
        const setting = vscode.workspace
            .getConfiguration('meta-mcp')
            .get<string>('mcpExecPath');
        return setting?.trim() || '';
    }

    /**
     * Auto-detect local monorepo builds without requiring settings.
     * Checks paths relative to the extension location.
     */
    private detectLocalBuilds(): { metaMcp: string | null; mcpExec: string | null } {
        // Extension is at: extension/dist/extension.js
        // Monorepo packages are at: packages/meta-mcp/dist/index.js, packages/mcp-exec/dist/index.js
        const extensionDir = __dirname; // extension/dist
        const monorepoRoot = path.resolve(extensionDir, '..', '..'); // meta-mcp-server/

        const metaMcpLocal = path.join(monorepoRoot, 'packages', 'meta-mcp', 'dist', 'index.js');
        const mcpExecLocal = path.join(monorepoRoot, 'packages', 'mcp-exec', 'dist', 'index.js');

        return {
            metaMcp: fs.existsSync(metaMcpLocal) ? metaMcpLocal : null,
            mcpExec: fs.existsSync(mcpExecLocal) ? mcpExecLocal : null,
        };
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

        const packages = this.detectMcpPackages();
        const serverEntry = this.buildServerEntry(tool, packages.metaMcpInstalled);
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
     * Includes mcp-exec as a separate server entry
     */
    generateGenericSnippet(): ConfigSnippet {
        const metaMcpEntry = this.metaMcpPath
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

        const mcpExecEntry = {
            command: 'npx',
            args: ['-y', '@justanothermldude/mcp-exec'],
            env: { SERVERS_CONFIG: this.serversConfigPath },
        };

        const fullConfig = {
            mcpServers: {
                [META_MCP_SERVER_NAME]: metaMcpEntry,
                'mcp-exec': mcpExecEntry,
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
     * Detect if meta-mcp-server and mcp-exec are installed (global npm or local builds)
     * Checks: 1) npm list -g, 2) meta-mcp.serverPath setting, 3) local monorepo builds
     */
    detectMcpPackages(): McpPackageStatus {
        const status: McpPackageStatus = {
            metaMcpInstalled: false,
            metaMcpVersion: null,
            metaMcpSource: null,
            mcpExecInstalled: false,
            mcpExecVersion: null,
            mcpExecSource: null,
        };

        // 1. Check global npm packages
        try {
            const metaMcpResult = execSync(
                'npm list -g @justanothermldude/meta-mcp-server --depth=0 --json',
                { encoding: 'utf-8', timeout: 5000, stdio: ['pipe', 'pipe', 'pipe'] }
            );
            const metaMcpJson = JSON.parse(metaMcpResult);
            if (metaMcpJson.dependencies?.['@justanothermldude/meta-mcp-server']) {
                status.metaMcpInstalled = true;
                status.metaMcpVersion = metaMcpJson.dependencies['@justanothermldude/meta-mcp-server'].version || null;
                status.metaMcpSource = 'global';
            }
        } catch {
            // Not installed globally
        }

        try {
            const mcpExecResult = execSync(
                'npm list -g @justanothermldude/mcp-exec --depth=0 --json',
                { encoding: 'utf-8', timeout: 5000, stdio: ['pipe', 'pipe', 'pipe'] }
            );
            const mcpExecJson = JSON.parse(mcpExecResult);
            if (mcpExecJson.dependencies?.['@justanothermldude/mcp-exec']) {
                status.mcpExecInstalled = true;
                status.mcpExecVersion = mcpExecJson.dependencies['@justanothermldude/mcp-exec'].version || null;
                status.mcpExecSource = 'global';
            }
        } catch {
            // Not installed globally
        }

        // 2. Check local builds (auto-detect from monorepo structure, then settings)
        const localBuilds = this.detectLocalBuilds();

        if (!status.metaMcpInstalled) {
            const localPath = localBuilds.metaMcp ?? (this.metaMcpPath && fs.existsSync(this.metaMcpPath) ? this.metaMcpPath : null);
            if (localPath) {
                status.metaMcpInstalled = true;
                status.metaMcpVersion = 'local';
                status.metaMcpSource = 'local';
            }
        }

        if (!status.mcpExecInstalled) {
            const localPath = localBuilds.mcpExec ?? (this.mcpExecPath && fs.existsSync(this.mcpExecPath) ? this.mcpExecPath : null);
            if (localPath) {
                status.mcpExecInstalled = true;
                status.mcpExecVersion = 'local';
                status.mcpExecSource = 'local';
            }
        }

        return status;
    }

    /**
     * Auto-configure a tool with installed MCP packages (meta-mcp and/or mcp-exec)
     * Also migrates existing servers from tool's config to servers.json
     * @returns Paths to config files, backup, and migration count
     */
    async autoConfigure(toolId: string): Promise<{
        backupPath?: string;
        configPath?: string;
        serversConfigPath?: string;
        toolName?: string;
        migratedCount: number;
        success: boolean;
        error?: string
    }> {
        // Detect which packages are installed
        const packages = this.detectMcpPackages();

        if (!packages.metaMcpInstalled && !packages.mcpExecInstalled) {
            return {
                success: false,
                migratedCount: 0,
                error: 'No MCP packages installed. Install meta-mcp-server or mcp-exec first.'
            };
        }

        // If meta-mcp is installed and local path is set, verify it exists
        if (packages.metaMcpInstalled && this.metaMcpPath && !fs.existsSync(this.metaMcpPath)) {
            return {
                success: false,
                migratedCount: 0,
                error: `Server not found at: ${this.metaMcpPath}. Check meta-mcp.serverPath setting.`
            };
        }

        // Ensure servers.json exists (needed for meta-mcp and for migration)
        this.ensureServersConfig();

        const tool = getToolById(toolId);
        if (!tool) {
            return { success: false, migratedCount: 0, error: `Unknown tool: ${toolId}` };
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
                return { success: false, migratedCount: 0, error: `Failed to parse existing config: ${e}` };
            }
        }

        // Get existing servers from tool config
        const existingServers = (existingConfig[tool.configKey] as Record<string, unknown>) ?? {};

        // Identify servers to migrate (everything except meta-mcp and mcp-exec)
        const serversToMigrate: [string, unknown][] = [];
        for (const [name, config] of Object.entries(existingServers)) {
            if (name !== META_MCP_SERVER_NAME && name !== 'mcp-exec') {
                serversToMigrate.push([name, config]);
            }
        }

        // Migrate servers to servers.json if there are any
        let migratedCount = 0;
        if (serversToMigrate.length > 0) {
            try {
                // Load existing servers.json
                let serversConfig: { mcpServers: Record<string, unknown> } = { mcpServers: {} };
                if (fs.existsSync(this.serversConfigPath)) {
                    const content = fs.readFileSync(this.serversConfigPath, 'utf-8');
                    serversConfig = JSON.parse(content);
                    if (!serversConfig.mcpServers) {
                        serversConfig.mcpServers = {};
                    }
                }

                // Add migrated servers (don't overwrite existing)
                for (const [name, config] of serversToMigrate) {
                    if (!(name in serversConfig.mcpServers)) {
                        serversConfig.mcpServers[name] = config;
                        migratedCount++;
                    }
                }

                // Save servers.json
                fs.writeFileSync(this.serversConfigPath, JSON.stringify(serversConfig, null, 2), 'utf-8');
            } catch (e) {
                return { success: false, migratedCount: 0, error: `Failed to migrate servers: ${e}` };
            }
        }

        // Build new tool config with only meta-mcp and mcp-exec
        const newServers: Record<string, unknown> = {};

        // Add meta-mcp entry if installed
        if (packages.metaMcpInstalled) {
            newServers[META_MCP_SERVER_NAME] = this.buildServerEntry(tool, packages.metaMcpInstalled);
        }

        // Add mcp-exec entry if installed
        if (packages.mcpExecInstalled) {
            newServers['mcp-exec'] = this.buildMcpExecEntry(tool);
        }

        existingConfig[tool.configKey] = newServers;

        // Write updated tool config
        try {
            fs.writeFileSync(configPath, JSON.stringify(existingConfig, null, 2), 'utf-8');
            return {
                success: true,
                backupPath,
                configPath,
                serversConfigPath: this.serversConfigPath,
                toolName: tool.name,
                migratedCount
            };
        } catch (e) {
            return { success: false, migratedCount: 0, error: `Failed to write config: ${e}` };
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
     * Priority: 1) global npm, 2) auto-detected local build, 3) setting, 4) npx fallback
     */
    private buildServerEntry(tool: AIToolDefinition, packageInstalled = false): McpServerEntry {
        let entry: McpServerEntry;

        if (packageInstalled) {
            // Package is installed globally - use npx (preferred)
            entry = {
                command: 'npx',
                args: ['-y', '@justanothermldude/meta-mcp-server'],
                env: {
                    SERVERS_CONFIG: this.serversConfigPath,
                },
            };
        } else {
            // Check auto-detected local build or setting
            const localBuilds = this.detectLocalBuilds();
            const localPath = localBuilds.metaMcp ?? (this.metaMcpPath && fs.existsSync(this.metaMcpPath) ? this.metaMcpPath : null);

            if (localPath) {
                entry = {
                    command: 'node',
                    args: [localPath],
                    env: {
                        SERVERS_CONFIG: this.serversConfigPath,
                    },
                };
            } else {
                // Default to npx (will prompt install on first run)
                entry = {
                    command: 'npx',
                    args: ['-y', '@justanothermldude/meta-mcp-server'],
                    env: {
                        SERVERS_CONFIG: this.serversConfigPath,
                    },
                };
            }
        }

        if (tool.requiresType) {
            entry.type = 'stdio';
        }

        return entry;
    }

    /**
     * Build the mcp-exec server entry for a tool
     * Priority: 1) auto-detected local build, 2) setting, 3) npx fallback
     */
    private buildMcpExecEntry(tool: AIToolDefinition): McpServerEntry {
        let entry: McpServerEntry;

        // Check auto-detected local build or setting
        const localBuilds = this.detectLocalBuilds();
        const localPath = localBuilds.mcpExec ?? (this.mcpExecPath && fs.existsSync(this.mcpExecPath) ? this.mcpExecPath : null);

        if (localPath) {
            entry = {
                command: 'node',
                args: [localPath],
                env: {
                    SERVERS_CONFIG: this.serversConfigPath,
                },
            };
        } else {
            // Default: use npx
            entry = {
                command: 'npx',
                args: ['-y', '@justanothermldude/mcp-exec'],
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
     * Get which MCP package(s) are currently configured in a tool's config
     */
    getActivePackage(tool: AIToolDefinition): 'meta-mcp' | 'mcp-exec' | 'none' {
        const configPath = this.resolveConfigPath(tool.configPath);
        if (!fs.existsSync(configPath)) return 'none';
        try {
            const content = fs.readFileSync(configPath, 'utf-8');
            const config = JSON.parse(content);
            const servers = config[tool.configKey] || {};
            const hasMeta = META_MCP_SERVER_NAME in servers;
            const hasExec = 'mcp-exec' in servers;
            // Prefer mcp-exec if both are configured (legacy state)
            if (hasExec) return 'mcp-exec';
            if (hasMeta) return 'meta-mcp';
            return 'none';
        } catch {
            return 'none';
        }
    }

    /**
     * Switch which MCP package is active in a tool's config
     */
    async switchActivePackage(
        toolId: string,
        mode: 'meta-mcp' | 'mcp-exec'
    ): Promise<{ success: boolean; error?: string }> {
        const packages = this.detectMcpPackages();
        const tool = getToolById(toolId);
        if (!tool) return { success: false, error: `Unknown tool: ${toolId}` };

        const configPath = this.resolveConfigPath(tool.configPath);
        let existingConfig: Record<string, unknown> = {};
        if (fs.existsSync(configPath)) {
            try {
                const content = fs.readFileSync(configPath, 'utf-8');
                existingConfig = JSON.parse(content);
            } catch (e) {
                return { success: false, error: `Failed to parse config: ${e}` };
            }
        }

        const newServers: Record<string, unknown> = {};
        if (mode === 'meta-mcp') {
            newServers[META_MCP_SERVER_NAME] = this.buildServerEntry(tool, packages.metaMcpInstalled);
        } else {
            newServers['mcp-exec'] = this.buildMcpExecEntry(tool);
        }

        existingConfig[tool.configKey] = newServers;
        this.ensureServersConfig();

        const configDir = path.dirname(configPath);
        if (!fs.existsSync(configDir)) {
            fs.mkdirSync(configDir, { recursive: true });
        }

        try {
            fs.writeFileSync(configPath, JSON.stringify(existingConfig, null, 2), 'utf-8');
            return { success: true };
        } catch (e) {
            return { success: false, error: `Failed to write config: ${e}` };
        }
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
