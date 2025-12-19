import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import { execSync } from 'child_process';

/**
 * Auto-detect the location of a repository (e.g., adobe-mcp-servers)
 * Uses multiple strategies: VS Code workspace, Spotlight (macOS), find command
 */
export async function findRepository(repoName: string): Promise<string | null> {
    // 1. Check VS Code workspace folders first (most reliable if user has it open)
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (workspaceFolders) {
        for (const folder of workspaceFolders) {
            if (folder.uri.fsPath.includes(repoName)) {
                return folder.uri.fsPath;
            }
            // Also check if it's a subfolder
            const subPath = path.join(folder.uri.fsPath, repoName);
            if (fs.existsSync(subPath)) {
                return subPath;
            }
        }
    }
    
    // 2. macOS Spotlight search (instant, indexed)
    if (process.platform === 'darwin') {
        try {
            const result = execSync(
                `mdfind -name "${repoName}" -onlyin ~ 2>/dev/null | grep -E "/${repoName}$" | head -1`,
                { encoding: 'utf-8', timeout: 3000 }
            ).trim();
            if (result && fs.existsSync(result)) {
                return result;
            }
        } catch {
            // Spotlight search failed, continue to fallback
        }
    }
    
    // 3. Fast find with depth limit (works on all platforms)
    const homeDir = process.env.HOME || process.env.USERPROFILE || '~';
    try {
        const result = execSync(
            `find "${homeDir}" -maxdepth 5 -type d -name "${repoName}" 2>/dev/null | head -1`,
            { encoding: 'utf-8', timeout: 10000 }
        ).trim();
        if (result && fs.existsSync(result)) {
            return result;
        }
    } catch {
        // Find command failed
    }
    
    return null;
}

/**
 * Prompt user to select a repository folder
 */
export async function promptForRepository(repoName: string): Promise<string | null> {
    const selected = await vscode.window.showOpenDialog({
        canSelectFolders: true,
        canSelectFiles: false,
        canSelectMany: false,
        title: `Select ${repoName} repository folder`,
        openLabel: 'Select Repository'
    });
    
    if (!selected || selected.length === 0) {
        return null;
    }
    
    return selected[0].fsPath;
}

/**
 * Find repository with fallback to user prompt
 */
export async function findOrPromptForRepository(repoName: string): Promise<string | null> {
    // Try auto-detection first
    const autoDetected = await findRepository(repoName);
    
    if (autoDetected) {
        // Confirm with user
        const useDetected = await vscode.window.showInformationMessage(
            `Found ${repoName} at: ${autoDetected}`,
            'Use This',
            'Choose Different'
        );
        
        if (useDetected === 'Use This') {
            return autoDetected;
        }
    }
    
    // Fall back to manual selection
    return promptForRepository(repoName);
}

/**
 * Validate that a path contains the expected package
 */
export function validatePackagePath(repoPath: string, packagePath: string): boolean {
    const fullPath = path.join(repoPath, packagePath);
    return fs.existsSync(fullPath);
}
