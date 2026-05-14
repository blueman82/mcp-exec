import * as vscode from 'vscode';
import { createWebviewTemplate } from './webviewTemplate';
import { MessageHandler, WebviewMessage } from '../services/MessageHandler';
import { ServersConfigManager } from '../services/ServersConfigManager';
import { AIToolConfigurator } from '../services/AIToolConfigurator';
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
 * Webview View Provider for MCP-Exec
 */
export class MetaMcpViewProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'mcp-exec.configurator';

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

            case 'loadSetup':
                await this.handleLoadSetup();
                break;

            case 'configureMetaMcp':
                await this.handleConfigureMetaMcp(message.payload as { toolId: string });
                break;
            case 'autoDetectServerPath':
                await this.handleAutoDetectServerPath();
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

            this.toolConfigurator = new AIToolConfigurator();

            const tools = this.toolConfigurator.detectInstalledTools();
            const snippets = this.toolConfigurator.generateAllSnippets();
            const genericSnippet = this.toolConfigurator.generateGenericSnippet();
            const mcpPackages = this.toolConfigurator.detectMcpPackages();

            this.postMessage({ type: 'updateSetup', tools, snippets, genericSnippet, mcpPackages });
        } catch (err) {
            const errorMsg = err instanceof Error ? err.message : String(err);
            console.error('[mcp-exec-oss] Failed to load setup:', errorMsg);
            this.postMessage({ type: 'showError', message: `Failed to detect tools: ${errorMsg}` });
        }
    }
    

    /**
     * Install mcp-exec globally via npm
     */
    private async handleInstallMcpExec(): Promise<void> {
        const terminal = vscode.window.createTerminal('mcp-exec install');
        terminal.show();
        terminal.sendText('npm install -g @justanothermldude/mcp-exec-oss');

        await vscode.window.showInformationMessage(
            'Installing mcp-exec... Click "Refresh" when installation completes.',
            'Refresh'
        );
        // Always refresh after dialog closes (whether Refresh clicked or dismissed)
        // This ensures the button state is updated and doesn't stay stuck at "Installing..."
        await this.handleLoadSetup();
    }


    /**
     * Auto-detect and set mcp-exec path from workspace
     */
    private async handleAutoDetectServerPath(): Promise<void> {
        const workspaceFolders = vscode.workspace.workspaceFolders;

        // Try workspace detection first
        if (workspaceFolders) {
            for (const folder of workspaceFolders) {
                const candidates = [
                    vscode.Uri.joinPath(folder.uri, 'packages', 'mcp-exec', 'dist', 'index.js'),
                ];

                for (const candidate of candidates) {
                    try {
                        await vscode.workspace.fs.stat(candidate);
                        await this.setMcpExecPath(candidate.fsPath);
                        return;
                    } catch {
                        // File doesn't exist, try next
                    }
                }
            }
        }

        // Not found - show helpful message
        const action = await vscode.window.showErrorMessage(
            'Could not find mcp-exec. Make sure the mcp-exec folder is open in this editor.',
            'Open Folder'
        );

        if (action === 'Open Folder') {
            await vscode.commands.executeCommand('vscode.openFolder');
        }
    }

    private async setMcpExecPath(path: string): Promise<void> {
        await vscode.workspace.getConfiguration('mcp-exec').update(
            'mcpExecPath',
            path,
            vscode.ConfigurationTarget.Global
        );
        vscode.window.showInformationMessage(`mcp-exec path set to: ${path}`);
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
            console.error('[mcp-exec-oss] Failed to configure:', errorMsg);
            this.postMessage({ type: 'configureMetaMcpResponse', success: false, error: errorMsg });
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
        console.log('[mcp-exec-oss] sendServerList:', servers.length, 'servers');
        this.postMessage({ type: 'updateServers', servers });
    }

    /**
     * Get server list from config
     */
    private getServerList(): ServerListItem[] {
        console.log('[mcp-exec-oss] getServerList - configPath:', this.configManager.getConfigPath());
        const serverNames = this.configManager.listServers();
        console.log('[mcp-exec-oss] getServerList - serverNames:', serverNames);
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
            console.error('[mcp-exec-oss] Failed to open config files:', err);
        }
    }
}
