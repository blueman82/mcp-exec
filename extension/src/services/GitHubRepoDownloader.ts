import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { execSync } from 'child_process';
import { Octokit } from '@octokit/rest';

const REPOS_DIR = path.join(os.homedir(), '.meta-mcp', 'repos');

export interface DownloadProgress {
    stage: 'authenticating' | 'downloading' | 'extracting' | 'complete' | 'error';
    message: string;
    percent?: number;
}

export type ProgressCallback = (progress: DownloadProgress) => void;

/**
 * Download and extract a GitHub repository using VS Code's GitHub authentication
 */
export async function downloadRepository(
    repoOwner: string,
    repoName: string,
    branch: string = 'main',
    onProgress?: ProgressCallback
): Promise<string> {
    // Ensure repos directory exists
    if (!fs.existsSync(REPOS_DIR)) {
        fs.mkdirSync(REPOS_DIR, { recursive: true });
    }

    const targetDir = path.join(REPOS_DIR, repoName);

    // If already exists, return it
    if (fs.existsSync(targetDir)) {
        onProgress?.({ stage: 'complete', message: 'Repository already downloaded', percent: 100 });
        return targetDir;
    }

    try {
        // Get GitHub authentication
        onProgress?.({ stage: 'authenticating', message: 'Authenticating with GitHub...', percent: 10 });
        
        const session = await vscode.authentication.getSession('github', ['repo'], { createIfNone: true });
        if (!session) {
            throw new Error('GitHub authentication required. Please sign in to GitHub.');
        }

        const octokit = new Octokit({ auth: session.accessToken });

        // Download the repository as a zip archive
        onProgress?.({ stage: 'downloading', message: `Downloading ${repoOwner}/${repoName}...`, percent: 30 });

        const response = await octokit.repos.downloadZipballArchive({
            owner: repoOwner,
            repo: repoName,
            ref: branch,
        });

        // response.data is an ArrayBuffer
        const zipData = Buffer.from(response.data as ArrayBuffer);
        
        // Write zip to temp file
        const tempZipPath = path.join(os.tmpdir(), `${repoName}-${Date.now()}.zip`);
        fs.writeFileSync(tempZipPath, zipData);

        onProgress?.({ stage: 'extracting', message: 'Extracting repository...', percent: 60 });

        // Extract using unzip command (available on macOS/Linux)
        const extractDir = path.join(os.tmpdir(), `${repoName}-extract-${Date.now()}`);
        fs.mkdirSync(extractDir, { recursive: true });

        if (process.platform === 'win32') {
            // Use PowerShell on Windows
            execSync(`powershell -command "Expand-Archive -Path '${tempZipPath}' -DestinationPath '${extractDir}'"`, {
                encoding: 'utf-8',
                timeout: 60000
            });
        } else {
            // Use unzip on macOS/Linux
            execSync(`unzip -q "${tempZipPath}" -d "${extractDir}"`, {
                encoding: 'utf-8',
                timeout: 60000
            });
        }

        // GitHub zip contains a folder like "owner-repo-sha", find and rename it
        const extractedContents = fs.readdirSync(extractDir);
        const repoFolder = extractedContents.find(f => 
            fs.statSync(path.join(extractDir, f)).isDirectory()
        );

        if (!repoFolder) {
            throw new Error('Could not find extracted repository folder');
        }

        // Move to final location
        const extractedPath = path.join(extractDir, repoFolder);
        fs.renameSync(extractedPath, targetDir);

        // Cleanup temp files
        try {
            fs.unlinkSync(tempZipPath);
            fs.rmSync(extractDir, { recursive: true, force: true });
        } catch {
            // Ignore cleanup errors
        }

        onProgress?.({ stage: 'complete', message: 'Repository downloaded successfully', percent: 100 });

        return targetDir;
    } catch (err) {
        const errorMsg = err instanceof Error ? err.message : String(err);
        onProgress?.({ stage: 'error', message: errorMsg });
        throw new Error(`Failed to download repository: ${errorMsg}`);
    }
}

/**
 * Check if a repository is already downloaded
 */
export function isRepositoryDownloaded(repoName: string): boolean {
    const targetDir = path.join(REPOS_DIR, repoName);
    return fs.existsSync(targetDir);
}

/**
 * Get the local path for a downloaded repository
 */
export function getRepositoryPath(repoName: string): string | null {
    const targetDir = path.join(REPOS_DIR, repoName);
    return fs.existsSync(targetDir) ? targetDir : null;
}

/**
 * Delete a downloaded repository
 */
export function deleteRepository(repoName: string): void {
    const targetDir = path.join(REPOS_DIR, repoName);
    if (fs.existsSync(targetDir)) {
        fs.rmSync(targetDir, { recursive: true, force: true });
    }
}

/**
 * Parse repo owner and name from a GitHub URL or repo_hint
 * Supports formats:
 * - "owner/repo"
 * - "https://github.com/owner/repo"
 * - "git@github.com:owner/repo.git"
 */
export function parseRepoIdentifier(identifier: string): { owner: string; repo: string } | null {
    // Try "owner/repo" format first
    const simpleMatch = identifier.match(/^([^/]+)\/([^/]+)$/);
    if (simpleMatch) {
        return { owner: simpleMatch[1], repo: simpleMatch[2] };
    }

    // Try GitHub URL format
    const urlMatch = identifier.match(/github\.com[/:][^/]+\/[^/.]+/);
    if (urlMatch) {
        return { owner: urlMatch[1], repo: urlMatch[2] };
    }

    return null;
}
