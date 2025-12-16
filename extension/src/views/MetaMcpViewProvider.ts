import * as vscode from 'vscode';
import { createWebviewTemplate } from './webviewTemplate';
import { MessageHandler, WebviewMessage } from '../services/MessageHandler';
import { ServersConfigManager } from '../services/ServersConfigManager';
import { AIToolConfigurator } from '../services/AIToolConfigurator';
import { fetchCatalog, clearCatalogCache, CatalogServer } from '../services/GitHubCatalogService';
import { ServerConfig } from '../types';

/**
 * Server data sent to webview
 */
interface ServerListItem {
    name: string;
    // Stdio transport
    command?: string;
    args?: string[];
    env?: Record<string, string>;
    // HTTP transport
    url?: string;
    headers?: Record<string, string>;
    // Common
    disabled?: boolean;
    description?: string;
    tags?: string[];
    connected?: boolean;
}

/**
 * Webview View Provider for Meta-MCP Configurator
 */
export class MetaMcpViewProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'meta-mcp.configurator';

    private _view?: vscode.WebviewView;
    private _disposables: vscode.Disposable[] = [];
    private messageHandler: MessageHandler;
    private configManager: ServersConfigManager;
    private toolConfigurator: AIToolConfigurator;

    constructor(
        private readonly extensionUri: vscode.Uri,
        configManager?: ServersConfigManager,
        toolConfigurator?: AIToolConfigurator
    ) {
        this.configManager = configManager ?? new ServersConfigManager();
        this.toolConfigurator = toolConfigurator ?? new AIToolConfigurator();
        this.messageHandler = new MessageHandler(this.configManager, this.toolConfigurator);
    }

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        _context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken
    ): void {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this.extensionUri]
        };

        webviewView.webview.html = createWebviewTemplate(webviewView.webview, this.extensionUri);

        // Handle messages from webview
        webviewView.webview.onDidReceiveMessage(
            async (message) => {
                await this.handleWebviewMessage(message);
            },
            undefined,
            this._disposables
        );

        // Refresh on visibility change
        webviewView.onDidChangeVisibility(
            () => {
                if (webviewView.visible) {
                    this.sendServerList();
                }
            },
            undefined,
            this._disposables
        );

        // Cleanup on dispose
        webviewView.onDidDispose(() => {
            this._disposables.forEach(d => d.dispose());
            this._disposables = [];
        });

        // Send initial server list after webview is ready
        // Using setTimeout to ensure webview script has initialized
        setTimeout(() => this.sendServerList(), 50);
    }

    /**
     * Handle incoming webview messages
     */
    private async handleWebviewMessage(message: Record<string, unknown>): Promise<void> {
        const type = message.type as string;

        switch (type) {
            case 'ready':
                this.sendServerList();
                break;

            case 'refresh':
                this.sendServerList();
                break;

            case 'addServer':
                await this.handleAddServer(message);
                break;

            case 'updateServer':
                await this.handleUpdateServer(message);
                break;

            case 'deleteServer':
                await this.handleDeleteServer(message);
                break;

            case 'loadCatalog':
                await this.handleLoadCatalog(message.forceRefresh as boolean);
                break;

            case 'installFromCatalog':
                await this.handleInstallFromCatalog(message.item as CatalogServer);
                break;

            case 'loadSetup':
                await this.handleLoadSetup();
                break;

            case 'configureMetaMcp':
                await this.handleConfigureMetaMcp(message.payload as { toolId: string });
                break;
            case 'autoDetectServerPath':
                await this.handleAutoDetectServerPath();
                break;
            
            case 'installMetaMcpServer':
                await this.handleInstallMetaMcpServer();
                break;

            case 'installMcpExec':
                await this.handleInstallMcpExec();
                break;

            case 'showError':
                vscode.window.showErrorMessage(message.message as string);
                break;

            default:
                // Forward to MessageHandler for other message types
                if (typeof type === 'string') {
                    const response = await this.messageHandler.handleMessage({ type, payload: message.payload } as WebviewMessage);
                    this.postMessage(response as unknown as Record<string, unknown>);
                }
                break;
        }
    }

    /**
     * Handle load setup message - detects installed AI tools and MCP packages
     */
    private async handleLoadSetup(): Promise<void> {
        try {
            this.postMessage({ type: 'setupLoading' });

            // Try to auto-detect server path from workspace
            const detectedPath = await this.detectServerPathFromWorkspace();
            if (detectedPath) {
                this.toolConfigurator = new AIToolConfigurator(detectedPath);
            }

            const tools = this.toolConfigurator.detectInstalledTools();
            const snippets = this.toolConfigurator.generateAllSnippets();
            const genericSnippet = this.toolConfigurator.generateGenericSnippet();
            const mcpPackages = this.toolConfigurator.detectMcpPackages();

            this.postMessage({ type: 'updateSetup', tools, snippets, genericSnippet, mcpPackages });
        } catch (err) {
            const errorMsg = err instanceof Error ? err.message : String(err);
            console.error('[Meta-MCP] Failed to load setup:', errorMsg);
            this.postMessage({ type: 'showError', message: `Failed to detect tools: ${errorMsg}` });
        }
    }
    
    /**
     * Try to find dist/index.js - first in workspace, then system-wide
     */
    private async detectServerPathFromWorkspace(): Promise<string | null> {
        // 1. Check workspace folders first
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (workspaceFolders) {
            for (const folder of workspaceFolders) {
                const candidates = [
                    vscode.Uri.joinPath(folder.uri, 'dist', 'index.js'),
                    vscode.Uri.joinPath(folder.uri, 'projects', 'meta-mcp-server', 'dist', 'index.js'),
                ];

                for (const candidate of candidates) {
                    try {
                        await vscode.workspace.fs.stat(candidate);
                        return candidate.fsPath;
                    } catch {
                        // File doesn't exist, try next
                    }
                }
            }
        }

        // 2. Use Spotlight on macOS to find it anywhere
        if (process.platform === 'darwin') {
            try {
                const { execSync } = require('child_process');
                const result = execSync(
                    'mdfind -name "index.js" | grep "meta-mcp-server/dist/index.js$" | head -1',
                    { encoding: 'utf-8', timeout: 5000 }
                ).trim();
                if (result) {
                    return result;
                }
            } catch {
                // mdfind failed or timed out
            }
        }

        return null;
    }

    /**
     * Handle installing a server from the catalog
     */
    private async handleInstallFromCatalog(item: CatalogServer): Promise<void> {
        try {
            // Determine command based on serverType
            let command = 'npx';
            let args: string[] = [];
            
            if (item.serverType === 'uvx' || item.serverType === 'python') {
                command = 'uvx';
                args = [item.id];
            } else if (item.serverType === 'docker') {
                command = 'docker';
                args = ['run', '-i', '--rm', item.repoUrl];
            } else {
                // Default to npx for npm packages
                command = 'npx';
                args = ['-y', item.id];
            }

            // Convert env vars (extract default values)
            const env: Record<string, string> = {};
            if (item.env) {
                for (const [key, envVar] of Object.entries(item.env)) {
                    env[key] = envVar.default || '';
                }
            }

            const serverConfig: ServerConfig = {
                command,
                args,
                env: Object.keys(env).length > 0 ? env : undefined,
            };

            this.configManager.setServer(item.name, serverConfig);
            vscode.window.showInformationMessage(`Added "${item.name}" to backends.json`);
            
            // Refresh server list
            const servers = this.getServerList();
            this.postMessage({ type: 'updateServers', servers });
            this.postMessage({ type: 'serverSaved' });
        } catch (err) {
            const errorMsg = err instanceof Error ? err.message : String(err);
            vscode.window.showErrorMessage(`Failed to add server: ${errorMsg}`);
        }
    }

    /**
     * Install meta-mcp-server globally via npm
     */
    private async handleInstallMetaMcpServer(): Promise<void> {
        const terminal = vscode.window.createTerminal('meta-mcp-server install');
        terminal.show();
        terminal.sendText('npm install -g @justanothermldude/meta-mcp-server');

        await vscode.window.showInformationMessage(
            'Installing meta-mcp-server... Click "Refresh" when installation completes.',
            'Refresh'
        );
        // Always refresh after dialog closes (whether Refresh clicked or dismissed)
        // This ensures the button state is updated and doesn't stay stuck at "Installing..."
        await this.handleLoadSetup();
    }

    /**
     * Install mcp-exec globally via npm
     */
    private async handleInstallMcpExec(): Promise<void> {
        const terminal = vscode.window.createTerminal('mcp-exec install');
        terminal.show();
        terminal.sendText('npm install -g @justanothermldude/mcp-exec');

        await vscode.window.showInformationMessage(
            'Installing mcp-exec... Click "Refresh" when installation completes.',
            'Refresh'
        );
        // Always refresh after dialog closes (whether Refresh clicked or dismissed)
        // This ensures the button state is updated and doesn't stay stuck at "Installing..."
        await this.handleLoadSetup();
    }

    /**
     * Auto-detect and set the server path from workspace, or browse if no workspace
     */
    private async handleAutoDetectServerPath(): Promise<void> {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        
        // Try workspace detection first
        if (workspaceFolders) {
            for (const folder of workspaceFolders) {
                const candidates = [
                    vscode.Uri.joinPath(folder.uri, 'dist', 'index.js'),
                    vscode.Uri.joinPath(folder.uri, 'projects', 'meta-mcp-server', 'dist', 'index.js'),
                ];

                for (const candidate of candidates) {
                    try {
                        await vscode.workspace.fs.stat(candidate);
                        await this.setServerPath(candidate.fsPath);
                        return;
                    } catch {
                        // File doesn't exist, try next
                    }
                }
            }
        }

        // Not found - show helpful message
        const action = await vscode.window.showErrorMessage(
            'Could not find meta-mcp-server. Make sure the meta-mcp-server folder is open in this editor.',
            'Open Folder'
        );
        
        if (action === 'Open Folder') {
            await vscode.commands.executeCommand('vscode.openFolder');
        }
    }

    private async setServerPath(path: string): Promise<void> {
        await vscode.workspace.getConfiguration('meta-mcp').update(
            'serverPath',
            path,
            vscode.ConfigurationTarget.Global
        );
        vscode.window.showInformationMessage(`Server path set to: ${path}`);
        this.toolConfigurator = new AIToolConfigurator();
        await this.handleLoadSetup();
    }

    /**
     * Handle configure meta-mcp for a specific tool
     * Now also migrates existing servers to servers.json
     */
    private async handleConfigureMetaMcp(payload: { toolId: string }): Promise<void> {
        if (!payload?.toolId) {
            this.postMessage({ type: 'configureMetaMcpResponse', success: false, error: 'No tool specified' });
            return;
        }

        try {
            const result = await this.toolConfigurator.autoConfigure(payload.toolId);

            if (result.success) {
                const toolName = result.toolName || payload.toolId;

                // Build success message based on what was done
                let message = `Configured ${toolName}`;
                if (result.migratedCount > 0) {
                    message += ` and migrated ${result.migratedCount} server(s) to servers.json`;
                }
                message += `. Restart ${toolName} to apply changes.`;

                vscode.window.showInformationMessage(message);

                // Open both config files for user to review
                await this.openConfigFiles(result.configPath, result.serversConfigPath);

                // Refresh server list since we may have migrated servers
                this.sendServerList();
                await this.handleLoadSetup();
            } else {
                vscode.window.showErrorMessage(result.error || 'Configuration failed');
            }

            this.postMessage({ type: 'configureMetaMcpResponse', success: result.success, error: result.error });
        } catch (err) {
            const errorMsg = err instanceof Error ? err.message : String(err);
            console.error('[Meta-MCP] Failed to configure:', errorMsg);
            this.postMessage({ type: 'configureMetaMcpResponse', success: false, error: errorMsg });
        }
    }

    /**
     * Handle load catalog message - fetches from GitHub
     */
    private async handleLoadCatalog(forceRefresh?: boolean): Promise<void> {
        try {
            this.postMessage({ type: 'catalogLoading' });
            
            if (forceRefresh) {
                clearCatalogCache();
            }
            
            const catalog = await fetchCatalog();
            this.postMessage({ type: 'updateCatalog', catalog });
        } catch (err) {
            const errorMsg = err instanceof Error ? err.message : String(err);
            console.error('[Meta-MCP] Failed to load catalog:', errorMsg);
            this.postMessage({ type: 'catalogError', message: `Failed to load catalog: ${errorMsg}` });
        }
    }

    /**
     * Handle add server message
     */
    private async handleAddServer(message: Record<string, unknown>): Promise<void> {
        const server = message.server as Record<string, unknown>;
        if (!server?.name) {
            this.postMessage({ type: 'showError', message: 'Server name required' });
            return;
        }

        const name = server.name as string;
        const config = this.buildServerConfig(server);

        try {
            this.configManager.setServer(name, config);
            this.postMessage({ type: 'serverSaved' });
            this.sendServerList();
            vscode.window.showInformationMessage(`Server "${name}" added`);
        } catch (err) {
            const errorMsg = err instanceof Error ? err.message : String(err);
            this.postMessage({ type: 'showError', message: errorMsg });
        }
    }

    /**
     * Handle update server message
     */
    private async handleUpdateServer(message: Record<string, unknown>): Promise<void> {
        const server = message.server as Record<string, unknown>;
        const originalName = message.originalName as string | undefined;

        if (!server?.name) {
            this.postMessage({ type: 'showError', message: 'Server name required' });
            return;
        }

        const name = server.name as string;
        const config = this.buildServerConfig(server);

        try {
            // If renamed, remove old entry
            if (originalName && originalName !== name) {
                this.configManager.removeServer(originalName);
            }
            this.configManager.setServer(name, config);
            this.postMessage({ type: 'serverSaved' });
            this.sendServerList();
            vscode.window.showInformationMessage(`Server "${name}" updated`);
        } catch (err) {
            const errorMsg = err instanceof Error ? err.message : String(err);
            this.postMessage({ type: 'showError', message: errorMsg });
        }
    }

    /**
     * Handle delete server message
     */
    private async handleDeleteServer(message: Record<string, unknown>): Promise<void> {
        const name = message.name as string;
        if (!name) {
            return;
        }

        const confirm = await vscode.window.showWarningMessage(
            `Delete server "${name}"?`,
            { modal: true },
            'Delete'
        );

        if (confirm === 'Delete') {
            try {
                this.configManager.removeServer(name);
                this.postMessage({ type: 'serverDeleted', name });
                this.sendServerList();
                vscode.window.showInformationMessage(`Server "${name}" deleted`);
            } catch (err) {
                const errorMsg = err instanceof Error ? err.message : String(err);
                vscode.window.showErrorMessage(errorMsg);
            }
        }
    }

    /**
     * Build ServerConfig from webview message
     */
    private buildServerConfig(server: Record<string, unknown>): ServerConfig {
        // Check if this is a URL-based config
        if (server.url) {
            const url = server.url as string;
            const headers = server.headers as Record<string, string> | undefined;
            return {
                url,
                headers: headers && Object.keys(headers).length > 0 ? headers : undefined,
            };
        }

        // Stdio transport config
        const commandType = server.commandType as string || 'npx';
        const command = server.command as string || '';
        const args = server.args as string[] | undefined;
        const env = server.env as Record<string, string> | undefined;

        // Build full command based on type
        let fullCommand: string;
        if (commandType === 'custom') {
            fullCommand = command;
        } else {
            fullCommand = commandType;
        }

        // Build args array
        const fullArgs: string[] = [];
        if (commandType !== 'custom' && command) {
            fullArgs.push(command);
        }
        if (args && args.length > 0) {
            fullArgs.push(...args);
        }

        return {
            command: fullCommand,
            args: fullArgs.length > 0 ? fullArgs : undefined,
            env: env && Object.keys(env).length > 0 ? env : undefined,
        };
    }

    /**
     * Send current server list to webview
     */
    private sendServerList(): void {
        const servers = this.getServerList();
        console.log('[Meta-MCP] sendServerList:', servers.length, 'servers');
        this.postMessage({ type: 'updateServers', servers });
    }

    /**
     * Get server list from config
     */
    private getServerList(): ServerListItem[] {
        console.log('[Meta-MCP] getServerList - configPath:', this.configManager.getConfigPath());
        const serverNames = this.configManager.listServers();
        console.log('[Meta-MCP] getServerList - serverNames:', serverNames);
        return serverNames.map(name => {
            const config = this.configManager.getServer(name);
            // Mark as "connected" if server has valid command OR url
            const isConfigured = !!(config?.command || config?.url);
            return {
                name,
                command: config?.command,
                args: config?.args,
                env: config?.env,
                url: config?.url,
                headers: config?.headers,
                disabled: config?.disabled,
                description: config?.description,
                tags: config?.tags,
                connected: isConfigured,
            };
        });
    }

    /**
     * Post message to webview
     */
    private postMessage(message: Record<string, unknown>): void {
        this._view?.webview.postMessage(message);
    }

    /**
     * Refresh the view
     */
    public refresh(): void {
        this.sendServerList();
    }

    /**
     * Open config files in editor for user to review
     */
    private async openConfigFiles(configPath?: string, serversConfigPath?: string): Promise<void> {
        try {
            // Open servers.json first (in first column)
            if (serversConfigPath) {
                const serversDoc = await vscode.workspace.openTextDocument(serversConfigPath);
                await vscode.window.showTextDocument(serversDoc, { viewColumn: vscode.ViewColumn.One, preview: false });
            }
            
            // Open tool config second (in second column, side by side)
            if (configPath) {
                const configDoc = await vscode.workspace.openTextDocument(configPath);
                await vscode.window.showTextDocument(configDoc, { viewColumn: vscode.ViewColumn.Two, preview: false });
            }
        } catch (err) {
            console.error('[Meta-MCP] Failed to open config files:', err);
        }
    }
}
