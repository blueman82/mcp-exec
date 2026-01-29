import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { createWebviewTemplate } from './webviewTemplate';
import { MessageHandler, WebviewMessage } from '../services/MessageHandler';
import { ServersConfigManager } from '../services/ServersConfigManager';
import { AIToolConfigurator } from '../services/AIToolConfigurator';
import { fetchCatalog, clearCatalogCache, CatalogServer } from '../services/GitHubCatalogService';
import { parseLocalServer } from '../services/LocalServerParser';
import { findRepository } from '../services/RepoDetector';
import { downloadRepository, getRepositoryPath } from '../services/GitHubRepoDownloader';
import { ServerConfig } from '../types';

/**
 * Data for local server setup completion
 */
interface LocalServerSetupData {
    serverName: string;
    repoPath: string;
    packagePath: string;
    entryPoint: string;
    runtime: 'node' | 'python';
    env: Record<string, string>;
}

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

            case 'localServerSetupComplete':
                await this.handleLocalServerSetupComplete(message.data as LocalServerSetupData);
                break;

            case 'runLocalServerBuild':
                await this.handleRunLocalServerBuild(message.data as { packagePath: string; serverName: string });
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

            case 'switchActivePackage':
                await this.handleSwitchActivePackage(
                    message.payload as { toolId: string; mode: 'meta-mcp' | 'mcp-exec' }
                );
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

            const activePackages: Record<string, string> = {};
            for (const t of tools) {
                activePackages[t.tool.id] = this.toolConfigurator.getActivePackage(t.tool);
            }

            this.postMessage({ type: 'updateSetup', tools, snippets, genericSnippet, mcpPackages, activePackages });
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
            // For Internal servers, check if available locally (should be downloaded when catalog opened)
            if (item.serverType === 'Internal') {
                const localServerPath = await this.findLocalServer(item.id);
                if (localServerPath) {
                    await this.handleInstallLocalServer(item, localServerPath);
                    return;
                } else {
                    // Repo not downloaded yet - trigger download and retry
                    await this.ensureInternalRepoDownloaded();
                    const retryPath = await this.findLocalServer(item.id);
                    if (retryPath) {
                        await this.handleInstallLocalServer(item, retryPath);
                        return;
                    }
                    vscode.window.showErrorMessage(`Could not find ${item.name} in adobe-mcp-servers. Make sure the repository downloaded successfully.`);
                    return;
                }
            }

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
            vscode.window.showInformationMessage(`Added "${item.name}" to servers.json`);
            
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
     * Find a server in local repos (auto-detected or downloaded)
     * Returns the full path to the server package if found, null otherwise
     */
    private async findLocalServer(serverId: string): Promise<{ repoPath: string; packagePath: string } | null> {
        // Check common locations for the server
        const possiblePaths = [
            `src/${serverId}`,
            `packages/${serverId}`,
            serverId,
        ];

        // 1. Try auto-detected adobe-mcp-servers repo first
        const autoDetectedRepo = await findRepository('adobe-mcp-servers');
        if (autoDetectedRepo) {
            for (const packagePath of possiblePaths) {
                const fullPath = path.join(autoDetectedRepo, packagePath);
                if (fs.existsSync(fullPath) && (
                    fs.existsSync(path.join(fullPath, 'package.json')) ||
                    fs.existsSync(path.join(fullPath, 'requirements.txt'))
                )) {
                    return { repoPath: autoDetectedRepo, packagePath };
                }
            }
        }

        // 2. Try downloaded repo in ~/.meta-mcp/repos/
        const downloadedRepo = getRepositoryPath('adobe-mcp-servers');
        if (downloadedRepo) {
            for (const packagePath of possiblePaths) {
                const fullPath = path.join(downloadedRepo, packagePath);
                if (fs.existsSync(fullPath) && (
                    fs.existsSync(path.join(fullPath, 'package.json')) ||
                    fs.existsSync(path.join(fullPath, 'requirements.txt'))
                )) {
                    return { repoPath: downloadedRepo, packagePath };
                }
            }
        }
        
        return null;
    }

    /**
     * Handle installing a local/internal server (not on npm)
     */
    private async handleInstallLocalServer(item: CatalogServer, localServer: { repoPath: string; packagePath: string }): Promise<void> {
        try {
            const { repoPath, packagePath } = localServer;
            const fullPackagePath = path.join(repoPath, packagePath);
            
            // Parse server metadata from existing files
            const meta = await parseLocalServer(fullPackagePath);
            
            // Send to webview for UI setup dialog
            this.postMessage({
                type: 'showLocalServerSetup',
                data: {
                    serverName: item.name,
                    repoPath,
                    packagePath,
                    ...meta
                }
            });
        } catch (err) {
            const errorMsg = err instanceof Error ? err.message : String(err);
            vscode.window.showErrorMessage(`Failed to setup local server: ${errorMsg}`);
        }
    }

    /**
     * Handle running build for a local server
     */
    private async handleRunLocalServerBuild(data: { packagePath: string; serverName: string }): Promise<void> {
        // Many servers have build scripts that expect .env to exist
        // Auto-create from .env.example if missing
        const envPath = path.join(data.packagePath, '.env');
        const envExamplePath = path.join(data.packagePath, '.env.example');
        if (!fs.existsSync(envPath) && fs.existsSync(envExamplePath)) {
            fs.copyFileSync(envExamplePath, envPath);
        }
        
        const terminal = vscode.window.createTerminal({
            name: `Build: ${data.serverName}`,
            cwd: data.packagePath
        });
        
        terminal.show();
        // Use --ignore-scripts to prevent "prepare" script from running build during install
        terminal.sendText('npm install --ignore-scripts && NODE_OPTIONS="--max-old-space-size=8192" npm run build');
        
        const entryPoint = path.join(data.packagePath, 'dist', 'index.js');
        
        // Poll for build completion (check every 2 seconds for up to 2 minutes)
        const maxAttempts = 60;
        let attempts = 0;
        
        const checkBuild = async (): Promise<boolean> => {
            while (attempts < maxAttempts) {
                await new Promise(resolve => setTimeout(resolve, 2000));
                attempts++;
                
                if (fs.existsSync(entryPoint)) {
                    // Check if file was modified in the last 30 seconds (freshly built)
                    const stats = fs.statSync(entryPoint);
                    const age = Date.now() - stats.mtimeMs;
                    if (age < 30000) {
                        return true;
                    }
                }
            }
            return false;
        };
        
        // Start polling in background
        checkBuild().then(success => {
            if (success) {
                this.postMessage({ type: 'localServerBuildComplete', success: true });
                vscode.window.showInformationMessage(`${data.serverName} built successfully!`);
            }
        });
        
        // Also show manual option
        const result = await vscode.window.showInformationMessage(
            `Building ${data.serverName}... Will auto-detect when done, or click "Check Now" to verify.`,
            'Check Now',
            'Cancel'
        );
        
        if (result === 'Check Now') {
            if (fs.existsSync(entryPoint)) {
                this.postMessage({ type: 'localServerBuildComplete', success: true });
                vscode.window.showInformationMessage('Build completed successfully!');
            } else {
                vscode.window.showWarningMessage('Build not complete yet - dist/index.js not found. Wait for build to finish.');
            }
        } else if (result === 'Cancel') {
            this.postMessage({ type: 'localServerBuildComplete', success: false });
        }
    }

    /**
     * Handle completion of local server setup (from webview dialog)
     */
    private async handleLocalServerSetupComplete(data: LocalServerSetupData): Promise<void> {
        try {
            const fullEntryPath = path.join(data.repoPath, data.packagePath, data.entryPoint);
            
            // Verify entry point exists
            if (!fs.existsSync(fullEntryPath)) {
                vscode.window.showErrorMessage(
                    `Entry point not found: ${fullEntryPath}. Did you build the server?`
                );
                return;
            }
            
            const config: ServerConfig = {
                command: data.runtime,
                args: [fullEntryPath],
                env: Object.keys(data.env).length > 0 ? data.env : undefined,
            };
            
            this.configManager.setServer(data.serverName, config);
            vscode.window.showInformationMessage(`Added "${data.serverName}" to servers.json`);
            
            // Refresh server list
            const servers = this.getServerList();
            this.postMessage({ type: 'updateServers', servers });
            this.postMessage({ type: 'serverSaved' });
        } catch (err) {
            const errorMsg = err instanceof Error ? err.message : String(err);
            vscode.window.showErrorMessage(`Failed to save server config: ${errorMsg}`);
        }
    }

    /**
     * Install meta-mcp-server globally via npm
     */
    private async handleInstallMetaMcpServer(): Promise<void> {
        const terminal = vscode.window.createTerminal('meta-mcp-server install');
        terminal.show();

        // On macOS/Linux, check if npm global prefix is writable
        if (process.platform === 'darwin' || process.platform === 'linux') {
            const { execSync } = require('child_process');
            try {
                const prefix = execSync('npm config get prefix', { encoding: 'utf-8' }).trim();
                // Check if we can write to the prefix directory
                try {
                    fs.accessSync(prefix, fs.constants.W_OK);
                } catch {
                    // Can't write - auto-configure user-level npm global
                    const shellRc = process.env.SHELL?.includes('zsh') ? '~/.zshrc' : '~/.bashrc';
                    terminal.sendText('mkdir -p ~/.npm-global');
                    terminal.sendText('npm config set prefix ~/.npm-global');
                    terminal.sendText(`echo 'export PATH=~/.npm-global/bin:$PATH' >> ${shellRc}`);
                    terminal.sendText(`source ${shellRc}`);
                    vscode.window.showInformationMessage('Configured npm to use ~/.npm-global to avoid permission issues.');
                }
            } catch {
                // npm config failed - proceed anyway
            }
        }

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
     * Handle switching active MCP package for a tool
     */
    private async handleSwitchActivePackage(
        payload: { toolId: string; mode: 'meta-mcp' | 'mcp-exec' }
    ): Promise<void> {
        if (!payload?.toolId || !payload?.mode) {
            this.postMessage({ type: 'switchActivePackageResponse', success: false, error: 'Missing toolId or mode' });
            return;
        }

        try {
            const result = await this.toolConfigurator.switchActivePackage(payload.toolId, payload.mode);
            if (result.success) {
                vscode.window.showInformationMessage(
                    `Switched to ${payload.mode}. Restart your AI tool to apply.`
                );
                await this.handleLoadSetup();
            } else {
                vscode.window.showErrorMessage(result.error || 'Failed to switch package');
            }
            this.postMessage({
                type: 'switchActivePackageResponse',
                success: result.success,
                error: result.error
            });
        } catch (err) {
            const errorMsg = err instanceof Error ? err.message : String(err);
            this.postMessage({ type: 'switchActivePackageResponse', success: false, error: errorMsg });
        }
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
     * Handle load catalog message - fetches from GitHub and auto-downloads internal repos
     */
    private async handleLoadCatalog(forceRefresh?: boolean): Promise<void> {
        try {
            this.postMessage({ type: 'catalogLoading' });
            
            if (forceRefresh) {
                clearCatalogCache();
            }
            
            // Auto-download adobe-mcp-servers repo in background if not present
            this.ensureInternalRepoDownloaded();
            
            const catalog = await fetchCatalog();
            this.postMessage({ type: 'updateCatalog', catalog });
        } catch (err) {
            const errorMsg = err instanceof Error ? err.message : String(err);
            console.error('[Meta-MCP] Failed to load catalog:', errorMsg);
            this.postMessage({ type: 'catalogError', message: `Failed to load catalog: ${errorMsg}` });
        }
    }

    /**
     * Auto-download adobe-mcp-servers repo if not already present
     * Runs in background without blocking catalog load
     */
    private async ensureInternalRepoDownloaded(): Promise<void> {
        // Check if already exists (auto-detected or downloaded)
        const autoDetected = await findRepository('adobe-mcp-servers');
        const downloaded = getRepositoryPath('adobe-mcp-servers');
        
        if (autoDetected || downloaded) {
            return; // Already have it
        }

        // Download in background with progress notification
        vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: 'Downloading internal MCP servers repository',
            cancellable: false
        }, async (progress) => {
            try {
                await downloadRepository('Adobe-AIFoundations', 'adobe-mcp-servers', 'main', (downloadProgress) => {
                    progress.report({ 
                        message: downloadProgress.message,
                        increment: downloadProgress.percent ? downloadProgress.percent / 4 : undefined
                    });
                });
                vscode.window.showInformationMessage('Internal MCP servers repository downloaded successfully');
            } catch (err) {
                const errorMsg = err instanceof Error ? err.message : String(err);
                console.error('[Meta-MCP] Failed to download internal repo:', errorMsg);
                // Don't show error - user can still use public servers
            }
        });
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
        // Only add command to args if it's different from commandType
        // This prevents duplicate 'npx' when editing servers (command='npx', commandType='npx')
        if (commandType !== 'custom' && command && command !== commandType) {
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
