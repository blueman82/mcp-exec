import * as vscode from 'vscode';
import { MetaMcpViewProvider } from './views';
import { ServersConfigManager } from './services/ServersConfigManager';

let outputChannel: vscode.OutputChannel | undefined;

async function migrateLegacySettings(): Promise<void> {
  try {
    const legacy = vscode.workspace.getConfiguration('meta-mcp');
    const current = vscode.workspace.getConfiguration('mcp-exec');

    const keys: Array<'serversConfigPath' | 'mcpExecPath'> = ['serversConfigPath', 'mcpExecPath'];
    for (const key of keys) {
      const legacyInspect = legacy.inspect<string>(key);
      const currentInspect = current.inspect<string>(key);

      const legacyValue = legacyInspect?.globalValue;
      const currentValue = currentInspect?.globalValue;

      if (legacyValue && !currentValue) {
        await current.update(key, legacyValue, vscode.ConfigurationTarget.Global);
        await legacy.update(key, undefined, vscode.ConfigurationTarget.Global);
        outputChannel?.appendLine(`Migrated meta-mcp.${key} → mcp-exec.${key}: ${legacyValue}`);
      }
    }
  } catch (err) {
    outputChannel?.appendLine(`Settings migration failed (non-fatal): ${err instanceof Error ? err.message : String(err)}`);
  }
}

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  outputChannel = vscode.window.createOutputChannel('MCP-Exec');
  outputChannel.appendLine('MCP-Exec activating...');

  await migrateLegacySettings();

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
