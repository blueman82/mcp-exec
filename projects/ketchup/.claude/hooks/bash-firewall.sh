#!/bin/bash
# PreToolUse hook: blocks dangerous bash commands
# Input: JSON from stdin with structure {"tool_name": "Bash", "tool_input": {"command": "..."}}
# Exit codes: 0 (safe), 2 (blocked)

set -u

# Extract command from JSON input (read stdin first)
PAYLOAD=$(cat)
COMMAND=$(echo "$PAYLOAD" | jq -r '.tool_input.command // empty' 2>/dev/null)

if [[ -z "$COMMAND" ]]; then
    exit 0  # Empty or malformed input, let it through
fi

# Helper function to check for dangerous patterns
block_command() {
    local reason="$1"
    echo "❌ Command blocked by firewall: $reason" >&2
    echo "Command: $COMMAND" >&2
    exit 2
}

# Block: git push --force (any branch), but allow --force-with-lease (safe)
if [[ "$COMMAND" =~ git[[:space:]]+push[[:space:]].*(--force|-f) && ! "$COMMAND" =~ --force-with-lease ]]; then
    block_command "git push --force is destructive and requires explicit approval (use --force-with-lease instead)"
fi

# Block: git reset --hard
if [[ "$COMMAND" =~ git[[:space:]]+reset[[:space:]]+--hard ]]; then
    block_command "git reset --hard discards local changes and requires explicit approval"
fi

# Block: catastrophic rm operations
if [[ "$COMMAND" =~ rm[[:space:]]+-rf[[:space:]]+/?~?[[:space:]]*$ ]]; then
    block_command "rm -rf / or rm -rf ~ would destroy system directories"
fi
if [[ "$COMMAND" =~ rm[[:space:]]+-rf[[:space:]]+\./[[:space:]]*$ ]]; then
    block_command "rm -rf ./ in root directory would destroy project"
fi

# Block: docker-compose down (production containers)
if [[ "$COMMAND" =~ docker-compose[[:space:]]+(down|stop)[[:space:]]* ]]; then
    block_command "docker-compose down/stop would halt production services"
fi

# Block: docker stop (production containers)
if [[ "$COMMAND" =~ docker[[:space:]]+stop[[:space:]]+ ]]; then
    block_command "docker stop would halt running containers"
fi

# SSH to production servers — allowed (read-only commands are common for monitoring/verification)

# Block: SQL destructive operations (case insensitive)
if [[ "$COMMAND" =~ [Dd][Rr][Oo][Pp][[:space:]]+(TABLE|DATABASE) ]]; then
    block_command "DROP TABLE/DATABASE is destructive and requires explicit approval"
fi
if [[ "$COMMAND" =~ [Dd][Ee][Ll][Ee][Tt][Ee][[:space:]]+[Ff][Rr][Oo][Mm] ]]; then
    block_command "DELETE FROM is destructive and requires explicit approval"
fi

# Block: ./deploy (deployment should be explicit)
if [[ "$COMMAND" =~ ^\./deploy([[:space:]]|$) ]]; then
    block_command "deployment must be an explicit, conscious action"
fi

# Safe command
exit 0
