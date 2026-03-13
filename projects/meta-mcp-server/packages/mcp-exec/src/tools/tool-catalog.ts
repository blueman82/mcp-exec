/**
 * Disk-persisted tool catalog for MCP servers.
 * Caches tool names + parameter signatures so the LLM sees exact API
 * in the tool description before writing any code.
 *
 * Updated as a side-effect of every execute_code_with_wrappers call.
 * Loaded on startup — stale data is better than no data.
 */
import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { homedir } from 'os';

/** Minimal tool shape used for signature formatting */
export interface ToolLike {
  name: string;
  description?: string;
  inputSchema?: { required?: string[]; properties?: Record<string, unknown> };
}

interface CatalogEntry {
  name: string;
  required: string[];
  optional: string[];
  description?: string;
}

interface ToolCatalog {
  servers: Record<string, CatalogEntry[]>;
  updatedAt: string;
}

const CATALOG_PATH = join(homedir(), '.meta-mcp', 'tool-catalog.json');

/**
 * Format a single tool as a compact signature: toolName({required, optional?})
 * Single source of truth — used by catalog, FuzzyProxy help, and wrapper-generator.
 */
export function formatToolSignature(t: ToolLike): string {
  const allProps = Object.keys(t.inputSchema?.properties ?? {});
  const req = t.inputSchema?.required ?? [];
  const params = [...req, ...allProps.filter(k => !req.includes(k)).map(p => p + '?')];
  return `${t.name}(${params.length > 0 ? '{' + params.join(', ') + '}' : ''})`;
}

/**
 * Load catalog from disk. Returns empty catalog if file doesn't exist or is corrupt.
 */
function loadCatalog(): ToolCatalog {
  try {
    const data = readFileSync(CATALOG_PATH, 'utf-8');
    return JSON.parse(data);
  } catch {
    return { servers: {}, updatedAt: new Date().toISOString() };
  }
}

/**
 * Write catalog to disk. Non-fatal on failure — catalog is best-effort.
 */
function saveCatalog(catalog: ToolCatalog): void {
  try {
    mkdirSync(dirname(CATALOG_PATH), { recursive: true });
    writeFileSync(CATALOG_PATH, JSON.stringify(catalog, null, 2), 'utf-8');
  } catch {
    // Non-fatal
  }
}

/**
 * Update the catalog for a single server after tool discovery.
 * Called as a side-effect of execute_code_with_wrappers.
 */
export function updateCatalogForServer(serverName: string, tools: ToolLike[]): void {
  const catalog = loadCatalog();
  catalog.servers[serverName] = tools.map(t => {
    const allProps = Object.keys(t.inputSchema?.properties ?? {});
    const req = t.inputSchema?.required ?? [];
    return {
      name: t.name,
      required: req,
      optional: allProps.filter(k => !req.includes(k)),
      description: t.description ? t.description.slice(0, 60) : undefined,
    };
  });
  catalog.updatedAt = new Date().toISOString();
  saveCatalog(catalog);
}

/**
 * Build compact catalog string for embedding in the tool description.
 * Format: server: tool1({param1, param2?}), tool2(), ...
 */
export function buildCatalogString(): string {
  const catalog = loadCatalog();
  const servers = Object.entries(catalog.servers);
  if (servers.length === 0) return '';

  const lines: string[] = [
    '',
    '',
    'Tool API Reference (use EXACT names and parameters):',
  ];
  for (const [server, tools] of servers) {
    const toolStrs = tools.map(t => {
      const params = [...t.required, ...t.optional.map(p => p + '?')];
      return `${t.name}(${params.length > 0 ? '{' + params.join(', ') + '}' : ''})`;
    });
    lines.push(`  ${server}: ${toolStrs.join(', ')}`);
  }
  lines.push('');
  lines.push('IMPORTANT: Use ONLY the exact tool and parameter names above. Do NOT guess.');
  lines.push('Inside this sandbox, use serverName.toolName({params}) or mcp["server-name"].toolName({params}).');
  lines.push('Do NOT use mcp__server__tool() syntax — that is the protocol layer, not the sandbox API.');
  return lines.join('\n');
}
