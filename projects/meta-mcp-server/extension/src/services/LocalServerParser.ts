import * as fs from 'fs';
import * as path from 'path';

export interface EnvVar {
    key: string;
    placeholder: string;
    optional: boolean;
    description?: string;
}

export interface LocalServerMeta {
    envVars: EnvVar[];
    runtime: 'node' | 'python';
    entryPoint: string;
    isBuilt: boolean;
    hasBuildScript: boolean;
}

/**
 * Parse a local MCP server package to extract configuration metadata
 * from existing structured files (.env.example, package.json, etc.)
 */
export async function parseLocalServer(packagePath: string): Promise<LocalServerMeta> {
    const hasPackageJson = fs.existsSync(path.join(packagePath, 'package.json'));
    const runtime: 'node' | 'python' = hasPackageJson ? 'node' : 'python';
    const entryPoint = runtime === 'node' ? 'dist/index.js' : findPythonEntryPoint(packagePath);

    const isBuilt = fs.existsSync(path.join(packagePath, entryPoint));

    let hasBuildScript = false;
    if (hasPackageJson) {
        try {
            const pkgJson = JSON.parse(fs.readFileSync(path.join(packagePath, 'package.json'), 'utf-8'));
            hasBuildScript = pkgJson.scripts?.build !== undefined;
        } catch {
            // Ignore parse errors
        }
    }

    const envVars = parseEnvExample(path.join(packagePath, '.env.example'));

    return {
        envVars,
        runtime,
        entryPoint,
        isBuilt,
        hasBuildScript
    };
}

/**
 * Find the Python entry point by checking common locations in order.
 */
function findPythonEntryPoint(packagePath: string): string {
    const dirName = path.basename(packagePath);
    const candidates = [
        'server.py',
        'src/server.py',
        '__main__.py',
        `src/${dirName}/server.py`,
    ];

    // Also scan src/*/server.py for nested package layouts (e.g. src/firefly_mcp/server.py)
    try {
        const srcDir = path.join(packagePath, 'src');
        if (fs.existsSync(srcDir) && fs.statSync(srcDir).isDirectory()) {
            for (const entry of fs.readdirSync(srcDir)) {
                const nested = path.join('src', entry, 'server.py');
                if (!candidates.includes(nested) && fs.existsSync(path.join(packagePath, nested))) {
                    candidates.push(nested);
                }
            }
        }
    } catch {
        // Ignore read errors
    }

    return candidates.find(c => fs.existsSync(path.join(packagePath, c))) ?? 'server.py';
}

/**
 * Parse .env.example file to extract environment variable definitions
 * Detects required vs optional based on comment sections
 */
function parseEnvExample(filePath: string): EnvVar[] {
    if (!fs.existsSync(filePath)) {
        return [];
    }
    
    const content = fs.readFileSync(filePath, 'utf-8');
    const vars: EnvVar[] = [];
    let isOptionalSection = false;
    let lastComment = '';
    
    for (const line of content.split('\n')) {
        const trimmedLine = line.trim();
        
        // Track section headers
        const lowerLine = trimmedLine.toLowerCase();
        if (lowerLine.includes('# optional') || lowerLine.includes('#optional')) {
            isOptionalSection = true;
            continue;
        }
        if (lowerLine.includes('# required') || lowerLine.includes('#required')) {
            isOptionalSection = false;
            continue;
        }
        
        // Capture inline comments as descriptions
        if (trimmedLine.startsWith('#') && !trimmedLine.toLowerCase().includes('optional') && !trimmedLine.toLowerCase().includes('required')) {
            lastComment = trimmedLine.replace(/^#\s*/, '');
            continue;
        }
        
        // Parse KEY=value lines
        const match = trimmedLine.match(/^([A-Z][A-Z0-9_]*)=(.*)$/);
        if (match) {
            vars.push({
                key: match[1],
                placeholder: match[2] || '',
                optional: isOptionalSection,
                description: lastComment || undefined
            });
            lastComment = '';
        }
    }
    
    return vars;
}

/**
 * Check if a server package needs to be built
 */
export function needsBuild(meta: LocalServerMeta): boolean {
    return !meta.isBuilt && meta.hasBuildScript;
}
