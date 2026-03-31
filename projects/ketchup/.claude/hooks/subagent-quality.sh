#!/bin/bash
# SubagentStop hook: Check for lint errors in modified Python files
# Purpose: Ensure subagents don't leave code quality issues

# Parse JSON payload from stdin
payload=$(cat)
cwd=$(echo "$payload" | jq -r '.cwd // empty')

# Use CLAUDE_PROJECT_DIR if available, otherwise use payload cwd
project_dir="${CLAUDE_PROJECT_DIR:-$cwd}"
if [[ -z "$project_dir" ]]; then
    echo "Error: Could not determine project directory" >&2
    exit 2
fi

# Change to project directory
cd "$project_dir" || {
    echo "Error: Could not cd to $project_dir" >&2
    exit 2
}

# Find modified Python files (both staged and unstaged)
# git diff --name-only returns paths relative to the git root, which may differ
# from $project_dir when working in a subdirectory (e.g. a worktree under a monorepo).
# Resolve each path against the git root so ruff receives valid absolute paths.
git_root=$(git rev-parse --show-toplevel 2>/dev/null)
modified_files=$(
    (git diff --name-only --diff-filter=ACMR 2>/dev/null; \
     git diff --cached --name-only --diff-filter=ACMR 2>/dev/null) | \
    grep '\.py$' | sort -u | \
    while IFS= read -r f; do
        abs="$git_root/$f"
        if [[ -f "$abs" ]]; then
            echo "$abs"
        fi
    done
)

# If no modified Python files, exit silently
if [[ -z "$modified_files" ]]; then
    exit 0
fi

# Locate ruff binary
ruff_bin="${CLAUDE_PROJECT_DIR}/tests/setup/.venv/bin/ruff"
if [[ ! -x "$ruff_bin" ]]; then
    ruff_bin=$(command -v ruff)
fi

if [[ -z "$ruff_bin" ]] || [[ ! -x "$ruff_bin" ]]; then
    echo "Warning: ruff not found, skipping lint check" >&2
    exit 0
fi

# Run ruff check on modified files
errors=$("$ruff_bin" check $modified_files 2>&1)
exit_code=$?

if [[ $exit_code -ne 0 ]]; then
    echo "Lint errors found in modified files:" >&2
    echo "$errors" >&2
    exit 2
fi

exit 0
