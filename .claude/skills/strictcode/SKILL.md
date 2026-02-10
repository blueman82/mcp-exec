---
name: strictcode
description: Enforce engineering principles (YAGNI, KISS, DRY, Fail Fast, SSOT, Law of Demeter) and language-specific coding standards (Python/Go/TypeScript) on code being written or modified. Uses Serena LSP for call site analysis and Theo semantic search for duplicate detection. Use PROACTIVELY when writing, modifying, or reviewing code. Triggers on code changes, "enforce standards", "check principles", "apply standards", "code quality", or explicit /strictcode command.
allowed-tools: Read, Write, Edit, Glob, Grep, Skill, mcp__mcp-exec__*
---

# StrictCode - Engineering Principles & Language Standards

**Version:** 3.0.0
**Purpose:** Proactively enforce engineering principles and language-specific idioms. Uses LSP (Serena) for structural verification and semantic search (Theo) for pattern detection. **Dispatches to language-specific skills for idiom enforcement.**

## When to Activate

**Proactively** (without user asking):
- After writing or modifying code in any file
- When reviewing code changes before commit
- When implementing features or fixing bugs

**Explicitly** (user invokes `/strictcode`):
- Point at a file or directory to audit and fix

---

## PHASE 0: Language Detection & Dispatch (MANDATORY)

**Before any analysis, detect the language and invoke the appropriate sub-skill:**

| File Extension | Invoke Skill |
|----------------|--------------|
| `.go` | Execute `strictcode-go` skill |
| `.py` | Execute `strictcode-python` skill |
| `.ts`, `.tsx` | Execute `strictcode-ts` skill |

**The language-specific skill provides idioms, patterns, and examples. This coordinator provides universal principles and MCP analysis.**

---

## Phase 1: MCP Environment Setup

Before analysis, activate Serena and Theo for the current project.

```javascript
// Execute via mcp__mcp-exec__execute_code_with_wrappers with wrappers: ["serena", "theo"]

// Test connectivity
const [serenaConfig, theoStats] = await Promise.all([
  serena.get_current_config(),
  theo.get_index_stats()
]);

const hasSerena = !!serenaConfig;
const hasTheo = theoStats?.success;

console.log("Serena (LSP):", hasSerena ? "OK" : "UNAVAILABLE - falling back to static analysis");
console.log("Theo (Semantic):", hasTheo ? "OK" : "UNAVAILABLE - skipping duplicate detection");

// Activate Serena project if available
if (hasSerena) {
  await serena.activate_project({ project: process.cwd() });
}
```

**Graceful degradation:** If MCPs are unavailable, fall back to file-level static analysis using Read/Grep/Glob. Serena and Theo enhance but are not required.

---

## Phase 2: Structural Analysis via Serena (LSP)

Use Serena to get precise structural data for principle enforcement.

### 2.1 Symbol Overview

```javascript
// Execute via mcp__mcp-exec__execute_code_with_wrappers with wrappers: ["serena"]

const symbols = await serena.get_symbols_overview({ relative_path: "TARGET_FILE" });

// Collect all symbols for analysis
const allSymbols = [
  ...(symbols.classes || []),
  ...(symbols.functions || []),
  ...(symbols.methods || [])
];
```

### 2.2 Reference Counting (YAGNI Detection)

```javascript
async function checkYAGNI(symbolName) {
  const refs = await serena.find_referencing_symbols({ name_path: symbolName });
  return {
    symbol: symbolName,
    referenceCount: refs.length || 0,
    isDeadCode: (refs.length || 0) === 0,
  };
}
```

**YAGNI rule:** If `referenceCount === 0` and symbol is not exported/public, flag for deletion.

### 2.3 Symbol Depth Analysis (Law of Demeter)

```javascript
async function checkDemeter(symbolName) {
  const detail = await serena.find_symbol({ name: symbolName, depth: 3 });
  const body = detail.body || '';

  // Detect a.b.c.d chains (3+ dots)
  const chainPattern = /\w+(?:\.\w+){3,}/g;
  const chains = body.match(chainPattern) || [];

  return { symbol: symbolName, demeterViolations: chains };
}
```

### 2.4 Class Structure Analysis (KISS)

```javascript
async function checkKISS(className) {
  const detail = await serena.find_symbol({ name: className, depth: 2 });
  const children = detail.children || [];
  const methods = children.filter(c => c.kind === 'method' || c.kind === 'function');

  return {
    className,
    methodCount: methods.length,
    isTrivialClass: methods.length === 1,
    hasDeepHierarchy: (detail.bases || []).length > 2,
  };
}
```

---

## Phase 3: Semantic Analysis via Theo

### 3.1 DRY Violation Detection

```javascript
// Execute via mcp__mcp-exec__execute_code_with_wrappers with wrappers: ["theo"]

await theo.index_directory({ dir_path: "TARGET_PATH", recursive: true });

const duplicates = await theo.search({
  query: "PASTE_FUNCTION_BODY_OR_SIGNATURE_HERE",
  n_results: 10
});

const dryViolations = (duplicates.data?.results || [])
  .filter(r => r.score > 0.85 && r.file_path !== "CURRENT_FILE");
```

**DRY rule:** If similarity > 85% across different files, flag as duplicate candidate.

### 3.2 Recall Past Patterns

```javascript
const [pastPatterns, pastWarnings] = await Promise.all([
  theo.memory_recall({
    query: "strictcode enforcement refactoring pattern decision",
    n_results: 5,
    memory_type: "pattern",
    include_related: true
  }),
  theo.memory_recall({
    query: "refactoring failed broke regression avoid",
    n_results: 3,
    memory_type: "pattern"
  })
]);
```

### 3.3 Store Learnings

```javascript
await theo.memory_store({
  content: `StrictCode on [file]: Fixed [N] violations. [summary]. Flagged [M] issues.`,
  memory_type: "pattern",
  namespace: "project:" + process.cwd().split('/').pop(),
  importance: 0.5,
  metadata: { tool: "strictcode", date: new Date().toISOString() }
});
```

---

## Core Principles (Universal)

Every code change MUST be checked against these six principles:

| # | Principle | What to Look For | Serena/Theo Tool |
|---|-----------|-------------------|------------------|
| 1 | **YAGNI** | Unused code, speculative features, dead branches | `find_referencing_symbols` → 0 refs = dead code |
| 2 | **KISS** | Over-engineered abstractions, trivial classes | `find_symbol` depth → single-method classes |
| 3 | **DRY** | Duplicated logic across files | `theo.search` → >85% similarity |
| 4 | **Fail Fast** | Late validation, deep nesting before error checks | `find_symbol` body → nesting depth |
| 5 | **SSOT** | Duplicated state/config | `theo.search` → config patterns |
| 6 | **Law of Demeter** | `a.b.c.d` chains | `find_symbol` body → chain regex |

### Code Reduction Rules

- No helpers for one-time operations
- No premature abstractions (3 similar lines > a premature abstraction)
- Delete unused code completely (no `_unused` renames, no `# removed` comments)
- No backwards-compatibility shims when you can just change the code
- No feature flags for unreleased features

---

## Enforcement Process

### Step 1: Detect Language & Dispatch
Read the file extension. **Invoke the matching language skill:**
- `.go` → `strictcode-go`
- `.py` → `strictcode-python`
- `.ts`/`.tsx` → `strictcode-ts`

### Step 2: Analyze with MCP Tools
- **If Serena available:** Run symbol overview, reference counting, depth analysis (Phase 2)
- **If Theo available:** Run duplicate detection, recall past patterns (Phase 3)
- **If neither available:** Fall back to file-level static analysis via Read/Grep

### Step 3: Fix or Flag

**Fix directly** (LSP-confirmed safe):
- Naming convention violations
- Missing type hints
- Redundant `else` after `return`
- Verbose patterns with idiomatic replacements
- Unused imports

**Flag to user** (need confirmation):
- Removing functions with 0 references
- Collapsing single-method class
- Extracting duplicated code
- Breaking `a.b.c.d` chains

### Step 4: Report

```
StrictCode: <filename>
  Language: Go → invoked strictcode-go
  Fixed: 3 violations
    - Removed redundant else after return (L45)
    - Wrapped error with context (L23)
    - Used early return pattern (L12, L18)
  Flagged: 2 issues (LSP-verified)
    - _format_helper() has 0 references [YAGNI] - delete? (L67)
    - Similar to utils.go:78 [DRY] - consolidate? (Theo)
  Memory: Stored enforcement pattern
```

---

## Rules

- Never change external behavior or public APIs
- Never remove or simplify error handling
- Always preserve test coverage
- When in doubt, flag instead of fix
- Apply the minimum change needed
- Don't add features, comments, or docstrings beyond what's needed
- Trust LSP data (Serena) over heuristics
- Use semantic search (Theo) to confirm duplicates
- **Always invoke language-specific skill for idioms**
- Store learnings after enforcement

---

## Integration with SlimCode

- **SlimCode** (`/slimcode`): Deep LSP + semantic analysis for LOC reduction. Read-only report.
- **StrictCode** (`/strictcode`): Proactive enforcement of principles and standards. Makes changes.

They complement each other: StrictCode ensures new code follows standards. SlimCode finds deeper structural improvements.
