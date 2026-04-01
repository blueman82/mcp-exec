#!/bin/bash
# Stop hook: Run tests before allowing Claude to finish
# Purpose: Validate code changes with automated test suite

# Parse JSON payload from stdin
payload=$(cat)
stop_hook_active=$(echo "$payload" | jq -r '.stop_hook_active // false')
cwd=$(echo "$payload" | jq -r '.cwd // empty')

# CRITICAL: Prevent infinite loop - if hook is already active, exit immediately
if [[ "$stop_hook_active" == "true" ]]; then
    exit 0
fi

# Use CLAUDE_PROJECT_DIR if available, otherwise use payload cwd
project_dir="${CLAUDE_PROJECT_DIR:-$cwd}"
if [[ -z "$project_dir" ]]; then
    exit 0
fi

# Check if any relevant files were modified in recent git history
code_changed=$(git diff --name-only HEAD~10 2>/dev/null | grep -E '^(packages/|ketchup_)' | head -1)

# If no relevant files changed, skip tests
if [[ -z "$code_changed" ]]; then
    exit 0
fi

# Run tests from the test directory
test_dir="$project_dir/tests/setup"
if [[ ! -d "$test_dir" ]]; then
    exit 0
fi

# Execute tests
cd "$test_dir" || exit 0
test_output=$(make test-fast 2>&1)
test_exit_code=$?

# Report results
if [[ $test_exit_code -eq 0 ]]; then
    # Tests passed - return success with system message
    echo "{\"systemMessage\": \"All tests passed\", \"suppressOutput\": false}"
    exit 0
else
    # Tests failed - show output to Claude for fixing
    echo "$test_output" >&2
    exit 2
fi
