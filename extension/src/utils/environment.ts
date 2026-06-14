import * as vscode from 'vscode';
import * as path from 'path';
import * as os from 'os';

export type EditorType = 'vscode' | 'cursor';

/**
 * Detects whether running in VS Code or Cursor
 */
export function detectEnvironment(): EditorType {
    const appName = vscode.env.appName?.toLowerCase() ?? '';
    return appName.includes('cursor') ? 'cursor' : 'vscode';
}

/**
 * Gets the config directory name for the current editor
 */
export function getConfigDirName(): string {
    return detectEnvironment() === 'cursor' ? '.cursor' : '.vscode';
}

/**
 * Gets MCP config paths for project and global locations
 */
export function getMcpConfigPaths(): { project: string; global: string } {
    const configDir = getConfigDirName();
    const homeDir = os.homedir();
    const workspaceFolders = vscode.workspace.workspaceFolders;

    const project = workspaceFolders?.[0]
        ? path.join(workspaceFolders[0].uri.fsPath, configDir, 'mcp.json')
        : '';
    const global = path.join(homeDir, configDir, 'mcp.json');

    return { project, global };
}

/**
 * Gets the servers.json config path
 * Priority: extension setting > default location
 */
export function getServersConfigPath(): string {
    const setting = vscode.workspace
        .getConfiguration('mcp-exec')
        .get<string>('serversConfigPath');

    if (setting?.trim()) {
        return setting;
    }

    return path.join(os.homedir(), '.meta-mcp', 'servers.json');
}
