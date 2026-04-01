#!/usr/bin/env bash
# PostToolUse hook: auto-format Python files after Write/Edit/MultiEdit.
#
# Exit codes:
#   0 — success or not applicable (non-blocking)
#   1 — formatter error (non-blocking, logged)
#
# Never exits 2 — formatting failures should not block the operation
# since the tool has already completed.

set -euo pipefail

# Read JSON from stdin
INPUT=$(cat)

# Extract file path from tool_input
FILE_PATH=$(echo "$INPUT" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get('tool_input', {}).get('file_path', ''))
except Exception:
    print('')
" 2>/dev/null)

# Skip if no file path or not a Python file
if [[ -z "$FILE_PATH" || "$FILE_PATH" != *.py ]]; then
    exit 0
fi

# Skip if file doesn't exist (might have been deleted)
if [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

# Find project root (look for pyproject.toml)
DIR=$(dirname "$FILE_PATH")
PROJECT_ROOT=""
SEARCH_DIR="$DIR"
while [[ "$SEARCH_DIR" != "/" ]]; do
    if [[ -f "$SEARCH_DIR/pyproject.toml" ]]; then
        PROJECT_ROOT="$SEARCH_DIR"
        break
    fi
    SEARCH_DIR=$(dirname "$SEARCH_DIR")
done

# Default to file's directory if no project root found
if [[ -z "$PROJECT_ROOT" ]]; then
    PROJECT_ROOT="$DIR"
fi

# Run black (quiet mode, ignore errors)
if command -v black &>/dev/null; then
    black --quiet "$FILE_PATH" 2>/dev/null || true
fi

# Run ruff fix (quiet mode, ignore errors)
if command -v ruff &>/dev/null; then
    ruff check --fix --quiet "$FILE_PATH" 2>/dev/null || true
fi

exit 0
