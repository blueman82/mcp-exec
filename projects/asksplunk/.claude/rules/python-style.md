---
paths:
  - "src/**/*.py"
  - "tests/**/*.py"
---
# Python Style

## Type Hints
- Full annotations on all function signatures (args + return)
- Builtin generics: `list[int]` not `List[int]`, `dict[str, Any]` not `Dict[str, Any]`
- Union syntax: `str | None` not `Optional[str]`
- Must pass mypy strict mode (check_untyped_defs, no_implicit_optional, strict_equality)

## Idioms
- **EAFP over LBYL**: `try/except` not `if`-checks for existence/validity
- **Context managers**: `async with` for all resources (AWS clients, files, connections)
- **f-strings only**: No `.format()` or `%` string formatting
- **Comprehensions**: Over explicit loops where readable
- **No mutable default args**: Use `None` sentinel and assign in body
- **Guard clauses**: Early returns over nested conditionals 3+ deep
- **Walrus operator** (`:=`): Where it reduces redundancy in conditions
- **Allowlist > blocklist**: `if status not in KNOWN_GOOD` over `if status == "error"` — fail-closed prevents silent failures

## Reduction Patterns
- Ternary assignments over 4-line if/else blocks for simple values
- `enumerate()`/`zip()` over manual indexing
- `any()`/`all()` over loop-with-break booleans
- `collections.Counter`/`defaultdict` over manual counting
- `"".join(parts)` over string concatenation in loops
- Dict dispatch over long if/elif chains (5+ branches)
- Collapse single-method classes to functions

## Imports
- Explicit imports only (no star imports)
- `from __future__ import annotations` in all modules
- No `TYPE_CHECKING` blocks — fix circular imports at architecture level
