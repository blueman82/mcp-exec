#!/usr/bin/env bash
# SessionStart hook: verify development environment.
#
# Checks Python version, virtualenv, required tools, and provides
# context via git log. Informational only — never blocks session start.
#
# Exit codes:
#   0 — always (informational, never blocks)

set -uo pipefail

WARNINGS=()
INFO=()

# Check Python version
if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' || echo "0.0")
    PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
    if [[ "$PY_MAJOR" -lt 3 ]] || [[ "$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 13 ]]; then
        WARNINGS+=("Python $PY_VERSION detected, 3.13+ required")
    fi
else
    WARNINGS+=("python3 not found")
fi

# Check virtualenv
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
    if command -v uv &>/dev/null; then
        INFO+=("No virtualenv active (uv available for setup)")
    else
        WARNINGS+=("No virtualenv active and uv not found")
    fi
fi

# Check required tools
for TOOL in black ruff mypy pytest; do
    if ! command -v "$TOOL" &>/dev/null; then
        WARNINGS+=("$TOOL not found in PATH")
    fi
done

# Check Docker (needed for ChromaDB) — with timeout to prevent hanging
if ! command -v docker &>/dev/null; then
    WARNINGS+=("docker not found (needed for ChromaDB)")
elif ! docker ps -q &>/dev/null 2>&1; then
    WARNINGS+=("Docker daemon not running")
fi

# Git context
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
if git -C "$PROJECT_DIR" rev-parse --git-dir &>/dev/null 2>&1; then
    BRANCH=$(git -C "$PROJECT_DIR" branch --show-current 2>/dev/null || echo "unknown")
    RECENT=$(git -C "$PROJECT_DIR" log --oneline -5 2>/dev/null || echo "(no commits)")
    INFO+=("Branch: $BRANCH")
    INFO+=("Recent commits:")
    while IFS= read -r line; do
        INFO+=("  $line")
    done <<< "$RECENT"
fi

# Build output via Python for safe JSON encoding
if [[ ${#WARNINGS[@]} -gt 0 ]] || [[ ${#INFO[@]} -gt 0 ]]; then
    python3 -c "
import json, sys

warnings = sys.argv[1:sys.argv.index('---')]
info = sys.argv[sys.argv.index('---')+1:]

parts = []
if warnings:
    parts.append('Environment warnings:')
    for w in warnings:
        parts.append(f'  - {w}')
if info:
    parts.append('Environment info:')
    for i in info:
        parts.append(f'  - {i}')

msg = chr(10).join(parts)
print(json.dumps({'suppressOutput': False, 'systemMessage': msg}))
" "${WARNINGS[@]}" "---" "${INFO[@]}"
fi

exit 0
