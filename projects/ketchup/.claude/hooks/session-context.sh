#!/bin/bash
# SessionStart hook: outputs live project context
# Output: JSON object with systemMessage field
# Always exits 0 (never blocks session)

set -u

CLAUDE_PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"

# Resolve to absolute path if relative
if [[ "$CLAUDE_PROJECT_DIR" != /* ]]; then
    CLAUDE_PROJECT_DIR="$(cd "$CLAUDE_PROJECT_DIR" 2>/dev/null && pwd)" || CLAUDE_PROJECT_DIR="."
fi

# Read feature flags from both env files
read_flags() {
    local file="$1"
    grep -E "(ENABLED|FEATURE)" "$file" 2>/dev/null || true
}

FEATURES=$(read_flags "$CLAUDE_PROJECT_DIR/infrastructure/features.env")
AGENT=$(read_flags "$CLAUDE_PROJECT_DIR/infrastructure/agent.env")

# Get git info (with fallback for non-git repos)
BRANCH=$(cd "$CLAUDE_PROJECT_DIR" && git branch --show-current 2>/dev/null || echo "unknown")
COMMITS=$(cd "$CLAUDE_PROJECT_DIR" && git log --oneline -5 2>/dev/null || echo "N/A")
CHANGES=$(cd "$CLAUDE_PROJECT_DIR" && git status --porcelain 2>/dev/null | wc -l || echo "0")

# Build context message
read -r -d '' CONTEXT << EOM || true
Ketchup Project Context

Current Branch: $BRANCH
Uncommitted Changes: $CHANGES

Recent Commits:
$COMMITS

Feature Flags (features.env):
$FEATURES

Agent Configuration (agent.env):
$AGENT

Services Deployed: prod1 (7 containers, all services + singletons), prod2 (5 containers, core services only)
Singleton Services: ketchup-unified-scheduler, ketchup-csopm-notifier (prod1 only)
EOM

# Output JSON with proper escaping
printf '{"systemMessage":%s,"suppressOutput":false}' "$(jq -Rs . <<<"$CONTEXT")"
exit 0
