import * as vscode from 'vscode';
import { ServersConfigManager } from './ServersConfigManager';
import { AIToolConfigurator } from './AIToolConfigurator';
import { ServerConfig } from '../types';

/**
 * Message types from webview
 */
export type MessageType =
    | 'getServers'
    | 'addServer'
    | 'removeServer'
    | 'updateServer'
    | 'configureMetaMcp'
    | 'detectTools'
    | 'getConfigSnippet';

/**
 * Incoming message from webview
 */
export interface WebviewMessage {
    type: MessageType;
    payload?: unknown;
}

/**
 * Response message to webview
 */
export interface WebviewResponse {
    type: string;
    success: boolean;
    data?: unknown;
    error?: string;
}

/**
 * Payload types for messages
 */
export interface AddServerPayload {
    name: string;
    config: ServerConfig;
}

export interface UpdateServerPayload {
    name: string;
    config: ServerConfig;
}

export interface RemoveServerPayload {
    name: string;
}

export interface ConfigureMetaMcpPayload {
    toolId: string;
}

export interface GetConfigSnippetPayload {
    toolId: string;
}

/**
 * Message Handler Service - Dispatches webview messages to appropriate handlers
 */
export class MessageHandler {
    private configManager: ServersConfigManager;
    private toolConfigurator: AIToolConfigurator;

    constructor(
        configManager?: ServersConfigManager,
        toolConfigurator?: AIToolConfigurator
    ) {
        this.configManager = configManager ?? new ServersConfigManager();
        this.toolConfigurator = toolConfigurator ?? new AIToolConfigurator();
    }

    /**
     * Handle incoming webview message and return response
     */
    async handleMessage(message: WebviewMessage): Promise<WebviewResponse> {
        try {
            switch (message.type) {
                case 'getServers':
                    return this.handleGetServers();

                case 'addServer':
                    return this.handleAddServer(message.payload as AddServerPayload);

                case 'removeServer':
                    return this.handleRemoveServer(message.payload as RemoveServerPayload);

                case 'updateServer':
                    return this.handleUpdateServer(message.payload as UpdateServerPayload);

                case 'configureMetaMcp':
                    return await this.handleConfigureMetaMcp(
                        message.payload as ConfigureMetaMcpPayload
                    );

                case 'detectTools':
                    return this.handleDetectTools();

                case 'getConfigSnippet':
                    return this.handleGetConfigSnippet(
                        message.payload as GetConfigSnippetPayload
                    );

                default:
                    return {
                        type: `${message.type}Response`,
                        success: false,
                        error: `Unknown message type: ${message.type}`,
                    };
            }
        } catch (err) {
            return {
                type: `${message.type}Response`,
                success: false,
                error: err instanceof Error ? err.message : String(err),
            };
        }
    }

    /**
     * Setup message listener for a webview
     */
    setupWebviewListener(
        webview: vscode.Webview,
        disposables: vscode.Disposable[]
    ): void {
        webview.onDidReceiveMessage(
            async (message: WebviewMessage) => {
                const response = await this.handleMessage(message);
                webview.postMessage(response);
            },
            undefined,
            disposables
        );
    }

    private handleGetServers(): WebviewResponse {
        const servers = this.configManager.listServers();
        const serverData: Record<string, ServerConfig> = {};

        for (const name of servers) {
            const config = this.configManager.getServer(name);
            if (config) {
                serverData[name] = config;
            }
        }

        return {
            type: 'getServersResponse',
            success: true,
            data: { servers: serverData, configPath: this.configManager.getConfigPath() },
        };
    }

    private handleAddServer(payload: AddServerPayload): WebviewResponse {
        if (!payload?.name || !payload?.config) {
            return {
                type: 'addServerResponse',
                success: false,
                error: 'Missing name or config',
            };
        }

        const existing = this.configManager.getServer(payload.name);
        if (existing) {
            return {
                type: 'addServerResponse',
                success: false,
                error: `Server "${payload.name}" already exists`,
            };
        }

        this.configManager.setServer(payload.name, payload.config);

        return {
            type: 'addServerResponse',
            success: true,
            data: { name: payload.name },
        };
    }

    private handleRemoveServer(payload: RemoveServerPayload): WebviewResponse {
        if (!payload?.name) {
            return {
                type: 'removeServerResponse',
                success: false,
                error: 'Missing server name',
            };
        }

        const removed = this.configManager.removeServer(payload.name);

        if (!removed) {
            return {
                type: 'removeServerResponse',
                success: false,
                error: `Server "${payload.name}" not found`,
            };
        }

        return {
            type: 'removeServerResponse',
            success: true,
            data: { name: payload.name },
        };
    }

    private handleUpdateServer(payload: UpdateServerPayload): WebviewResponse {
        if (!payload?.name || !payload?.config) {
            return {
                type: 'updateServerResponse',
                success: false,
                error: 'Missing name or config',
            };
        }

        this.configManager.setServer(payload.name, payload.config);

        return {
            type: 'updateServerResponse',
            success: true,
            data: { name: payload.name },
        };
    }

    private async handleConfigureMetaMcp(
        payload: ConfigureMetaMcpPayload
    ): Promise<WebviewResponse> {
        if (!payload?.toolId) {
            return {
                type: 'configureMetaMcpResponse',
                success: false,
                error: 'Missing toolId',
            };
        }

        const result = await this.toolConfigurator.autoConfigure(payload.toolId);

        if (!result.success) {
            return {
                type: 'configureMetaMcpResponse',
                success: false,
                error: result.error,
            };
        }

        return {
            type: 'configureMetaMcpResponse',
            success: true,
            data: { toolId: payload.toolId, backupPath: result.backupPath },
        };
    }

    private handleDetectTools(): WebviewResponse {
        const tools = this.toolConfigurator.detectInstalledTools();

        return {
            type: 'detectToolsResponse',
            success: true,
            data: { tools },
        };
    }

    private handleGetConfigSnippet(payload: GetConfigSnippetPayload): WebviewResponse {
        if (!payload?.toolId) {
            return {
                type: 'getConfigSnippetResponse',
                success: false,
                error: 'Missing toolId',
            };
        }

        const snippet = this.toolConfigurator.generateSnippet(payload.toolId);

        if (!snippet) {
            return {
                type: 'getConfigSnippetResponse',
                success: false,
                error: `Unknown tool: ${payload.toolId}`,
            };
        }

        return {
            type: 'getConfigSnippetResponse',
            success: true,
            data: snippet,
        };
    }
}
