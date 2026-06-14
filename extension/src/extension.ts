import * as vscode from 'vscode';
import { MetaMcpViewProvider } from './views';
import { ServersConfigManager } from './services/ServersConfigManager';

let outputChannel: vscode.OutputChannel | undefined;

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  outputChannel = vscode.window.createOutputChannel('MCP-Exec');
  outputChannel.appendLine('MCP-Exec activating...');

  try {
    const configManager = new ServersConfigManager();
    configManager.init();
    outputChannel.appendLine(`Config initialized at: ${configManager.getConfigPath()}`);
  } catch (err) {
    outputChannel.appendLine(`Failed to initialize config: ${err instanceof Error ? err.message : String(err)}`);
  }

  const provider = new MetaMcpViewProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider('mcp-exec-view', provider)
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('mcp-exec.openView', () => {
      vscode.commands.executeCommand('mcp-exec-view.focus');
    })
  );

  outputChannel.appendLine('MCP-Exec activated');
}

export function deactivate(): void {
  outputChannel?.dispose();
}
