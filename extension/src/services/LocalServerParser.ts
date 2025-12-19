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
    // Detect runtime based on file existence
    const hasPackageJson = fs.existsSync(path.join(packagePath, 'package.json'));
    const hasRequirementsTxt = fs.existsSync(path.join(packagePath, 'requirements.txt'));
    
    const runtime: 'node' | 'python' = hasPackageJson ? 'node' : 'python';
    const entryPoint = runtime === 'node' ? 'dist/index.js' : 'server.py';
    
    // Check if already built
    const isBuilt = fs.existsSync(path.join(packagePath, entryPoint));
    
    // Check if build script exists (for node projects)
    let hasBuildScript = false;
    if (hasPackageJson) {
        try {
            const pkgJson = JSON.parse(fs.readFileSync(path.join(packagePath, 'package.json'), 'utf-8'));
            hasBuildScript = pkgJson.scripts?.build !== undefined;
        } catch {
            // Ignore parse errors
        }
    }
    
    // Parse .env.example for required env vars
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
