---
name: strictcode-python
description: Python-specific coding standards and idioms. Invoked by strictcode coordinator or directly for Python files.
allowed-tools: Read, Write, Edit, Glob, Grep, mcp__mcp-exec__*
---

# StrictCode Python - Language-Specific Standards

**Version:** 1.0.0
**Purpose:** Enforce Python idioms and patterns on `.py` files.

---

## Python Idioms (MANDATORY)

### Naming & Structure (PEP 8)
- `snake_case` for functions and variables
- `PascalCase` for classes
- `UPPER_CASE` for constants
- Full type hints on ALL function signatures and class attributes (must pass Pyright strict)

### Imports
- Explicit imports (no star imports)
- No lazy imports
- No `TYPE_CHECKING` blocks — fix architecture if circular imports exist
- Use `from __future__ import annotations` for forward references

### Idioms
- **EAFP over LBYL** — `try/except` not `if`-checks for existence/validity
- **Context managers** for all resources (`with open(...)`, `async with ...`)
- **f-strings** over `.format()` or `%`
- **List/dict comprehensions** over explicit loops where readable
- **No mutable default arguments** — use `None` and check

### Documentation
- PEP 257 docstrings for public APIs only
- No docstrings for private methods unless complex

---

## Reduction Patterns (APPLY)

| Pattern | Before | After |
|---------|--------|-------|
| Ternary | `if x: y = a else: y = b` | `y = a if x else b` |
| Walrus | `m = re.match(...); if m:` | `if (m := re.match(...)):` |
| No redundant else | `if x: return a else: return b` | `if x: return a; return b` |
| Builtin generics | `List[int]`, `Dict[str, int]` | `list[int]`, `dict[str, int]` |
| Union syntax | `Optional[str]`, `Union[int, str]` | `str \| None`, `int \| str` |
| Comprehension | `for x in items: result.append(f(x))` | `[f(x) for x in items]` |
| Single-method class | `class X: def do(self): ...` | `def do(): ...` |

---

## Example: Before/After

```python
# BEFORE (violations: KISS, naming, type hints, redundant else, old generics)
from typing import List, Dict, Optional

class DataProcessor:
    def process(self, items):
        result = []
        for item in items:
            if item is not None:
                processed = item.strip().lower()
                result.append(processed)
        return result

    def get_first(self, items):
        if len(items) > 0:
            return items[0]
        else:
            return None
```

```python
# AFTER (all violations fixed)
class DataProcessor:
    def process(self, items: list[str | None]) -> list[str]:
        return [item.strip().lower() for item in items if item is not None]

    def get_first(self, items: list[str]) -> str | None:
        if len(items) > 0:
            return items[0]
        return None
```

---

## Type Hints Template

```python
from collections.abc import Callable, Iterable, Mapping, Sequence

def process_data(
    items: list[str],
    callback: Callable[[str], bool],
    config: dict[str, int] | None = None,
) -> tuple[list[str], int]:
    """Process items with callback and optional config."""
    config = config or {}
    results = [item for item in items if callback(item)]
    return results, len(results)
```

---

## Context Manager Pattern

```python
# File handling
with open("file.txt", encoding="utf-8") as f:
    content = f.read()

# Multiple resources
with (
    open("input.txt", encoding="utf-8") as infile,
    open("output.txt", "w", encoding="utf-8") as outfile,
):
    outfile.write(infile.read())

# Async resources
async with aiohttp.ClientSession() as session:
    async with session.get(url) as response:
        data = await response.json()
```

---

## EAFP Pattern

```python
# LBYL (Look Before You Leap) - AVOID
if key in dictionary:
    value = dictionary[key]
else:
    value = default

# EAFP (Easier to Ask Forgiveness) - PREFER
try:
    value = dictionary[key]
except KeyError:
    value = default

# Or even better for dicts:
value = dictionary.get(key, default)
```

---

## Checklist

Before completing Python code changes:

- [ ] All functions have full type hints (args and return)
- [ ] No `List`, `Dict`, `Optional` from typing — use builtins
- [ ] No star imports
- [ ] No mutable default arguments
- [ ] f-strings used (not `.format()` or `%`)
- [ ] Context managers for resources
- [ ] EAFP pattern (try/except not if-checks)
- [ ] No redundant else after return
- [ ] Comprehensions where readable
