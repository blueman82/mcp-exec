import * as vscode from 'vscode';
import { MetaMcpViewProvider } from './views';
import { ServersConfigManager } from './services/ServersConfigManager';

let outputChannel: vscode.OutputChannel | undefined;

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  outputChannel = vscode.window.createOutputChannel('Meta-MCP');
  outputChannel.appendLine('Meta-MCP activating...');

  // Initialize backends.json config file if it doesn't exist
  try {
    const configManager = new ServersConfigManager();
    configManager.init();
    outputChannel.appendLine(`Config initialized at: ${configManager.getConfigPath()}`);
  } catch (err) {
    outputChannel.appendLine(`Failed to initialize config: ${err instanceof Error ? err.message : String(err)}`);
  }

  // Register webview provider (lazy - won't initialize until view is opened)
  const provider = new MetaMcpViewProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider('meta-mcp-view', provider)
  );

  // Register open command
  context.subscriptions.push(
    vscode.commands.registerCommand('meta-mcp.openView', () => {
      vscode.commands.executeCommand('meta-mcp-view.focus');
    })
  );

  outputChannel.appendLine('Meta-MCP activated');
}

export function deactivate(): void {
  outputChannel?.dispose();
}
