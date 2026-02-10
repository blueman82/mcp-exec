---
allowed-tools: Read, Glob, Grep, mcp__mcp-exec__execute_code_with_wrappers, mcp__mcp-exec__get_mcp_tool_schema
argument-hint: "<file-or-directory> [--deep] [--dry-run] [--focus=<pattern>]"
description: Reduce LOC via LSP+Semantic+Memory meta-analysis without changing behavior, public APIs, or error handling
---

# SlimCode - Intelligent LOC Reduction

Analyze code using Serena (LSP) and Theo (semantic search + memory) to identify safe refactoring opportunities that reduce lines of code without changing external behavior.

## Usage
```
/slimcode src/module.py              # Analyze single file
/slimcode src/                       # Analyze directory
/slimcode src/ --deep                # Include semantic pattern detection
/slimcode src/ --dry-run             # Report only, no suggestions
/slimcode src/ --focus=utils         # Focus on files matching pattern
```

## Core Constraints (NEVER VIOLATE)
1. **Preserve External Behavior** - Refactoring must not change what the code does
2. **Preserve Public APIs** - No changes to function signatures, class interfaces, or module exports
3. **Preserve Error Handling** - Do not simplify, remove, or alter error handling logic
4. **No Feature Changes** - This is pure structural optimization

---

## Engineering Principles

Apply these when identifying LOC reduction opportunities:

| Principle | Application to SlimCode |
|-----------|------------------------|
| **YAGNI** | Remove unused code, speculative features, dead branches |
| **KISS** | Simplify over-engineered abstractions, flatten unnecessary hierarchies |
| **DRY** | Consolidate duplicates, extract repeated patterns |
| **Fail Fast** | Keep early returns, don't simplify validation |
| **Single Source of Truth** | Merge duplicated state/config |
| **Law of Demeter** | Flag `a.b.c.d` chains but preserve if API requires |

**CODE REDUCTION**: No helpers for one-time ops, no premature abstractions, delete unused code completely (no `_unused` renames, no `# removed` comments).

---

## Language-Specific Standards

Detect language from file extensions and apply idiomatic patterns:

### Python (.py)
```
PYTHONIC: PEP 8 naming (snake_case functions, PascalCase classes), full type hints,
  EAFP over LBYL (try/except not if-checks), context managers for resources,
  f-strings over .format(), explicit imports (no star imports),
  list/dict comprehensions over loops where readable.
REDUCE: Replace verbose if/else with ternary, use walrus operator where cleaner,
  remove redundant else after return, collapse single-method classes to functions.
```

### Go (.go)
```
GO IDIOMS: Accept interfaces return structs, errors are values (handle or return),
  table-driven tests, short variable names in small scopes, package-level organization.
REDUCE: No empty structs (Type{}), no unused variables (_ = x), no TODO comments,
  use named returns for documentation, early returns over nested if/else.
```

### TypeScript (.ts, .tsx)
```
TS IDIOMS: Strict mode, explicit return types, discriminated unions over assertions,
  const assertions, exhaustive switch checks, no any.
REDUCE: Use optional chaining (?.),  nullish coalescing (??), type inference where obvious,
  object shorthand, arrow functions for callbacks.
```

---

## Phase 1: Environment Setup

### 1.1 Validate MCP Servers & Activate Project
```javascript
// Execute via mcp__mcp-exec__execute_code_with_wrappers with wrappers: ["serena", "theo"]

// Test connectivity
const [serenaConfig, theoStats] = await Promise.all([
  serena.get_current_config(),
  theo.get_index_stats()
]);
console.log("Serena (LSP):", serenaConfig ? "OK" : "UNAVAILABLE");
console.log("Theo (Semantic+Memory):", theoStats.success ? "OK" : "UNAVAILABLE");

// Activate project
await serena.activate_project({ project: process.cwd() });
const onboarded = await serena.check_onboarding_performed();
if (!onboarded.performed) console.log("Note: Serena onboarding not performed. Some features may be limited.");
```

### 1.2 Index Codebase & Load Patterns
```javascript
// Execute via mcp__mcp-exec__execute_code_with_wrappers with wrappers: ["theo"]

const targetPath = "$ARGUMENTS".split(" ")[0] || ".";

// Index for semantic search
const indexStats = await theo.index_directory({ dir_path: targetPath, recursive: true });
console.log(`Indexed ${indexStats.data?.files_indexed || 0} files`);

// Recall past refactoring patterns
const patterns = await theo.memory_recall({
  query: "refactoring patterns LOC reduction code simplification",
  n_results: 10,
  memory_type: "pattern",
  include_related: true,
  max_depth: 2
});
if (patterns.data?.memories?.length > 0) {
  console.log(`Found ${patterns.data.memories.length} relevant patterns from memory`);
}
```

---

## Phase 2: Multi-Layer Analysis

### 2.1 Serena LSP Analysis (Structural)
For each target file, extract structural information:

```javascript
// Execute via mcp__mcp-exec__execute_code_with_wrappers with wrappers: ["serena"]

const symbols = await serena.get_symbols_overview({ relative_path: "TARGET_FILE_PATH" });
const refactorCandidates = [];

for (const symbol of symbols.classes || []) {
  const [refs, details] = await Promise.all([
    serena.find_referencing_symbols({ name_path: symbol.name }),
    serena.find_symbol({ name: symbol.name, depth: 2 })
  ]);
  refactorCandidates.push({
    symbol: symbol.name, type: 'class',
    references: refs.length, children: details.children?.length || 0, loc: details.location
  });
}
```

**Identify via LSP:**
- Unused private methods (zero internal references)
- Single-use helper functions (candidates for inlining)
- Classes with only one method (candidate for function conversion)
- Deeply nested symbol hierarchies
- Overly verbose property accessors

### 2.2 Theo Semantic Analysis (Patterns)
Search for duplicate/similar code patterns:

```javascript
// Execute via mcp__mcp-exec__execute_code_with_wrappers with wrappers: ["theo"]

const duplicatePatterns = await Promise.all([
  theo.search({ query: "function method implementation logic processing", n_results: 20 }),
  theo.search({ query: "class definition initialization constructor setup", n_results: 15 }),
  theo.search({ query: "try catch exception error handling recovery", n_results: 10 })
]);

// Find near-duplicates (>85% similarity)
const highSimilarity = duplicatePatterns.flatMap(r => r.data?.results || [])
  .filter(result => result.score > 0.85);
```

**Identify via Semantic Search:**
- Near-duplicate code blocks (high semantic similarity)
- Similar utility functions across files
- Repeated patterns that could be abstracted
- Copy-paste code with minor variations

### 2.3 Theo Memory Analysis (Historical)
Leverage past refactoring knowledge:

```javascript
// Execute via mcp__mcp-exec__execute_code_with_wrappers with wrappers: ["theo"]

const [codebaseContext, successfulRefactors, warnings] = await Promise.all([
  theo.memory_context({ query: "refactoring code structure optimization patterns", token_budget: 2000 }),
  theo.memory_recall({ query: "successful refactoring reduced lines simplified code", memory_type: "decision", min_importance: 0.7 }),
  theo.memory_recall({ query: "refactoring failed broke caused issues regression", memory_type: "pattern", n_results: 5 })
]);
```

**Identify via Memory:**
- Past successful refactoring patterns in similar code
- Known anti-patterns to avoid
- User preferences for code style
- Previously identified opportunities not yet addressed

---

## Phase 3: Cross-Reference & Validate

### 3.1 Merge Analysis Results
```javascript
const findings = {
  structural: {           // From Serena (LSP)
    unusedSymbols: [],        // Private methods with 0 references
    singleUseFunctions: [],   // Functions called only once
    trivialClasses: [],       // Classes with single method
    verboseAccessors: []      // Getters/setters that just proxy
  },
  semantic: {             // From Theo Search
    nearDuplicates: [],       // Code blocks with >85% similarity
    similarUtilities: [],     // Similar functions in different files
    repeatedPatterns: []      // Patterns that could be abstracted
  },
  historical: {           // From Theo Memory
    knownPatterns: [],        // Previously successful refactorings
    warnings: [],             // Things to avoid
    preferences: []           // User style preferences
  }
};
```

### 3.2 Safety Validation
For each candidate refactoring, validate safety:

```javascript
// Execute via mcp__mcp-exec__execute_code_with_wrappers with wrappers: ["serena"]

async function validateSafety(candidate) {
  const symbol = await serena.find_symbol({ name: candidate.name });
  const refs = await serena.find_referencing_symbols({ name_path: candidate.name });
  const body = symbol.body || '';

  return {
    isPublic: symbol.visibility === 'public' || !symbol.name.startsWith('_') || symbol.exported,
    isErrorHandling: /try|catch|except|throw|raise|Error/.test(body),
    referenceCount: refs.length,
    hasSideEffects: false // Requires deeper analysis
  };
}
```

**Discard candidates that:**
- Are part of public API (exported/public visibility)
- Contain error handling logic
- Would change external behavior
- Have side effects affecting state outside their scope

---

## Phase 4: Generate Report

Output structured report with:
- **Summary table**: Category, count, estimated LOC saved
- **Safe opportunities**: Location, symbol, confidence (HIGH/MEDIUM/LOW), LOC saved
- **Excluded items**: Location + reason (Public API, Error handling, etc.)
- **Historical context**: Relevant patterns from Theo memory

Each opportunity format:
```
**Location**: `file.py:123` | **Symbol**: `_unused_helper()` | **Confidence**: HIGH | **LOC**: ~15
```

---

## Phase 5: Store Learnings (Optional)

If significant patterns were discovered and not `--dry-run`:

```javascript
// Execute via mcp__mcp-exec__execute_code_with_wrappers with wrappers: ["theo"]

await theo.memory_store({
  content: `SlimCode analysis of [target] identified [X] LOC reduction opportunities. Key patterns: [list]. Safe candidates: [list]. Excluded due to API/error handling: [list].`,
  memory_type: "pattern",
  namespace: "project:" + process.cwd().split('/').pop(),
  importance: 0.6,
  metadata: { tool: "slimcode", target: "$ARGUMENTS", date: new Date().toISOString() }
});
```

---

## Tool Reference

### Serena (LSP) - Structural Analysis
| Tool | Purpose |
|------|---------|
| `activate_project` | Initialize LSP for codebase |
| `get_symbols_overview` | Get all symbols in a file |
| `find_symbol` | Get symbol details and body |
| `find_referencing_symbols` | Find all references to a symbol |
| `search_for_pattern` | Regex search across codebase |

### Theo - Semantic Search + Memory
| Tool | Purpose |
|------|---------|
| `index_directory` | Build vector index of codebase |
| `search` | Semantic similarity search |
| `search_with_budget` | Token-limited semantic search |
| `get_index_stats` | Check indexing status |
| `memory_recall` | Search past patterns/decisions |
| `memory_context` | Get formatted context |
| `memory_store` | Store new patterns |

---

## Flags
| Flag | Description |
|------|-------------|
| `--deep` | Enable full semantic analysis (slower, more thorough) |
| `--dry-run` | Report only, skip storing learnings |
| `--focus=<pattern>` | Filter files by glob pattern |

## Notes
- **Safety First**: When in doubt, exclude the candidate
- **Incremental**: Run multiple times after applying suggestions
- **Verify**: Always run tests after applying refactorings
- **LSP Priority**: Trust Serena findings over heuristics
- **Semantic Confirmation**: Use Theo search to confirm duplicates before suggesting consolidation
- **Learn**: Theo memory stores patterns to improve future analyses
