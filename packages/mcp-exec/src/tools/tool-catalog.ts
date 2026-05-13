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
import { listServers } from '@justanothermldude/meta-mcp-core';

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
  types?: Record<string, string>;
  description?: string;
}

interface ToolCatalog {
  servers: Record<string, CatalogEntry[]>;
  updatedAt: string;
}

const CATALOG_PATH = join(homedir(), '.meta-mcp', 'tool-catalog.json');

/**
 * Generate a compact type hint for a single JSON Schema property.
 * Returns null for primitives (string, number, boolean) since AI guesses those correctly.
 * Returns compact notation for objects, typed arrays, and enums.
 */
function compactTypeHint(propSchema: Record<string, unknown>): string | null {
  // Handle enum values
  if (Array.isArray(propSchema.enum)) {
    const vals = propSchema.enum as unknown[];
    if (vals.length <= 6) {
      return vals.map(v => typeof v === 'string' ? `'${v}'` : String(v)).join('|');
    }
    return 'enum';
  }

  // Handle anyOf/oneOf (common for nullable types like string | null)
  const variants = (propSchema.anyOf ?? propSchema.oneOf) as Record<string, unknown>[] | undefined;
  if (variants) {
    const nonNull = variants.filter(v => v.type !== 'null');
    if (nonNull.length === 1) return compactTypeHint(nonNull[0]);
  }

  const type = propSchema.type as string | undefined;

  // Primitives — AI defaults correctly, no hint needed
  if (type === 'string' || type === 'number' || type === 'integer' || type === 'boolean') {
    return null;
  }

  // Object with defined properties — show required/optional sub-keys one level deep
  if (type === 'object' && propSchema.properties) {
    const props = propSchema.properties as Record<string, Record<string, unknown>>;
    const required = (propSchema.required as string[]) || [];
    const keys = Object.keys(props);
    if (keys.length === 0) return 'object';
    const PRIM = new Set(['string', 'number', 'integer', 'boolean']);
    const parts = keys.map(k => {
      const sub = props[k]?.type as string | undefined;
      const sfx = required.includes(k) ? '' : '?';
      return PRIM.has(sub ?? '') ? `${k}${sfx}:${sub}` : `${k}${sfx}`;
    });
    return `{${parts.join(', ')}}`;
  }

  // Freeform object — AI must call get_mcp_tool_schema before using
  if (type === 'object') {
    return 'object';
  }

  // Array with typed items
  if (type === 'array' && propSchema.items) {
    const items = propSchema.items as Record<string, unknown>;
    if (items.type === 'object' && items.properties) {
      const props = items.properties as Record<string, Record<string, unknown>>;
      const required = (items.required as string[]) || [];
      const keys = Object.keys(props);
      const PRIM = new Set(['string', 'number', 'integer', 'boolean']);
      const parts = keys.map(k => {
        const sub = props[k]?.type as string | undefined;
        const sfx = required.includes(k) ? '' : '?';
        return PRIM.has(sub ?? '') ? `${k}${sfx}:${sub}` : `${k}${sfx}`;
      });
      return `[{${parts.join(', ')}}]`;
    }
    // Simple typed arrays (string[], number[]) — usually obvious
    return null;
  }

  return null;
}

/**
 * Format a single tool as a compact signature: toolName({required, optional?})
 * Inlines type hints for non-primitive params: comment:{body, visibility?}
 * Single source of truth — used by catalog, FuzzyProxy help, and wrapper-generator.
 */
export function formatToolSignature(t: ToolLike): string {
  const allProps = Object.keys(t.inputSchema?.properties ?? {});
  const req = t.inputSchema?.required ?? [];
  const props = t.inputSchema?.properties as Record<string, Record<string, unknown>> | undefined;

  const formatParam = (name: string, optional: boolean): string => {
    const suffix = optional ? '?' : '';
    if (props?.[name]) {
      const hint = compactTypeHint(props[name]);
      if (hint) return `${name}${suffix}:${hint}`;
    }
    return `${name}${suffix}`;
  };

  const params = [
    ...req.map(k => formatParam(k, false)),
    ...allProps.filter(k => !req.includes(k)).map(k => formatParam(k, true)),
  ];
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

    // Extract type hints for non-primitive parameters
    const types: Record<string, string> = {};
    if (t.inputSchema?.properties) {
      const props = t.inputSchema.properties as Record<string, Record<string, unknown>>;
      for (const [key, schema] of Object.entries(props)) {
        const hint = compactTypeHint(schema);
        if (hint) types[key] = hint;
      }
    }

    return {
      name: t.name,
      required: req,
      optional: allProps.filter(k => !req.includes(k)),
      ...(Object.keys(types).length > 0 ? { types } : {}),
      description: t.description || undefined,
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

  // Prune and persist servers no longer in servers.json
  try {
    const active = new Set(listServers().map(s => s.name));
    if (active.size > 0) {
      let pruned = false;
      for (const key of Object.keys(catalog.servers)) {
        if (!active.has(key)) {
          delete catalog.servers[key];
          pruned = true;
        }
      }
      if (pruned) saveCatalog(catalog);
    }
  } catch {
    // Non-fatal
  }

  const servers = Object.entries(catalog.servers);
  if (servers.length === 0) return '';

  const lines: string[] = [
    '',
    '',
    'Tool API Reference (use EXACT names and parameters):',
  ];
  for (const [server, tools] of servers) {
    const toolStrs = tools.map(t => {
      const formatParam = (name: string, optional: boolean): string => {
        const suffix = optional ? '?' : '';
        const hint = t.types?.[name];
        if (hint) return `${name}${suffix}:${hint}`;
        return `${name}${suffix}`;
      };
      const params = [
        ...t.required.map(k => formatParam(k, false)),
        ...t.optional.map(k => formatParam(k, true)),
      ];
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
