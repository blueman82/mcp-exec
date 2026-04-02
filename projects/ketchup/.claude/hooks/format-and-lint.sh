#!/usr/bin/env bash
# format-and-lint.sh — PostToolUse hook for Write|Edit|MultiEdit
#
# Phase 1: Auto-format with black, isort, ruff --fix (silent)
# Phase 2: Lint check with ruff (exit 2 if non-auto-fixable errors remain)
#
# Runs BEFORE auto_commit.py — ensures committed code is always clean.

set -uo pipefail

# Read hook payload from stdin
PAYLOAD=$(cat)
FILE_PATH=$(echo "$PAYLOAD" | jq -r '.tool_input.file_path // empty')

# Skip if no file path
if [[ -z "$FILE_PATH" ]]; then
    exit 0
fi

# Only process Python files
if [[ "$FILE_PATH" != *.py ]]; then
    exit 0
fi

# Skip if file doesn't exist (deleted files)
if [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

# Resolve project root for tool discovery
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}"
VENV_BIN="${PROJECT_DIR}/.venv/bin"

# Find tools: prefer test venv, fall back to PATH
find_tool() {
    if [[ -x "${VENV_BIN}/$1" ]]; then
        echo "${VENV_BIN}/$1"
    elif command -v "$1" &>/dev/null; then
        command -v "$1"
    else
        echo ""
    fi
}

BLACK=$(find_tool black)
ISORT=$(find_tool isort)
RUFF=$(find_tool ruff)

# Phase 1: Auto-format (silent, non-blocking)
if [[ -n "$BLACK" ]]; then
    "$BLACK" --quiet "$FILE_PATH" 2>/dev/null || true
fi

if [[ -n "$ISORT" ]]; then
    "$ISORT" --quiet "$FILE_PATH" 2>/dev/null || true
fi

if [[ -n "$RUFF" ]]; then
    "$RUFF" check --fix --quiet "$FILE_PATH" 2>/dev/null || true
fi

# Phase 2: Lint check (blocking if errors remain)
if [[ -n "$RUFF" ]]; then
    LINT_OUTPUT=$("$RUFF" check "$FILE_PATH" 2>&1)
    LINT_EXIT=$?

    if [[ $LINT_EXIT -ne 0 && -n "$LINT_OUTPUT" ]]; then
        # Send errors to stderr for Claude to see and self-correct
        echo "$LINT_OUTPUT" >&2
        echo "" >&2
        echo "Fix these lint errors before continuing." >&2
        exit 2
    fi
fi

# All clean — exit 0, auto_commit.py will fire next
exit 0
