#!/usr/bin/env bash
# PreToolUse hook: block dangerous bash commands.
#
# Exit codes:
#   0 — command is safe, allow execution
#   2 — command is dangerous, BLOCK execution
#
# IMPORTANT: Exit 2 is the ONLY code that blocks. Exit 1 is non-blocking.
#
# All pattern matching uses bash [[ =~ ]] to avoid piping untrusted
# content through shell utilities.

set -euo pipefail

# Read JSON from stdin
INPUT=$(cat)

# Extract the command from tool_input using Python for safe JSON parsing
COMMAND=$(printf '%s' "$INPUT" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get('tool_input', {}).get('command', ''))
except Exception:
    print('')
" 2>/dev/null)

# If no command extracted, allow
if [[ -z "$COMMAND" ]]; then
    exit 0
fi

# --- Dangerous patterns ---
# All checks use [[ "$COMMAND" =~ pattern ]] instead of echo | grep
# to avoid shell injection via piped untrusted content.

# Destructive file operations on critical directories
# Catches: rm -rf, rm -f, rm --force on protected dirs
if [[ "$COMMAND" =~ rm[[:space:]].*(-rf|-fr|-f|--force)[[:space:]].*(/infrastructure|/src/|/\.claude/) ]] ||
   [[ "$COMMAND" =~ rm[[:space:]]+(-rf|-fr)[[:space:]]+(infrastructure|src/|\.claude/) ]]; then
    echo "BLOCKED: Destructive rm on protected directory" >&2
    exit 2
fi

# Force push (any variant)
if [[ "$COMMAND" =~ git[[:space:]]+push[[:space:]]+.*--force ]] ||
   [[ "$COMMAND" =~ git[[:space:]]+push[[:space:]]+-f[[:space:]] ]] ||
   [[ "$COMMAND" =~ git[[:space:]]+push[[:space:]]+-f$ ]]; then
    echo "BLOCKED: git push --force is not allowed" >&2
    exit 2
fi

# Hard reset
if [[ "$COMMAND" =~ git[[:space:]]+reset[[:space:]]+--hard ]]; then
    echo "BLOCKED: git reset --hard is not allowed" >&2
    exit 2
fi

# AWS destructive operations
if [[ "$COMMAND" =~ aws[[:space:]]+dynamodb[[:space:]]+delete-table ]]; then
    echo "BLOCKED: aws dynamodb delete-table is not allowed" >&2
    exit 2
fi

if [[ "$COMMAND" =~ aws[[:space:]]+ec2[[:space:]]+terminate-instances ]]; then
    echo "BLOCKED: aws ec2 terminate-instances is not allowed" >&2
    exit 2
fi

if [[ "$COMMAND" =~ aws[[:space:]]+ecr[[:space:]]+delete-repository ]]; then
    echo "BLOCKED: aws ecr delete-repository is not allowed" >&2
    exit 2
fi

# Docker force-removing containers
if [[ "$COMMAND" =~ docker[[:space:]]+(rm|container[[:space:]]+rm)[[:space:]]+-f ]]; then
    echo "BLOCKED: Force removing Docker containers is not allowed" >&2
    exit 2
fi

# Commands containing real token patterns (data exfiltration risk)
# Require minimum length to avoid matching test placeholders
if [[ "$COMMAND" =~ xoxb-[0-9A-Za-z-]{20,} ]] ||
   [[ "$COMMAND" =~ xapp-[0-9A-Za-z-]{20,} ]] ||
   [[ "$COMMAND" =~ xoxp-[0-9A-Za-z-]{20,} ]] ||
   [[ "$COMMAND" =~ AKIA[A-Z0-9]{16} ]]; then
    echo "BLOCKED: Command contains what appears to be a real token/secret" >&2
    exit 2
fi

# curl/wget — block only when piping to shell (RCE risk).
# Token detection above already catches secret exfiltration.
if [[ "$COMMAND" =~ (curl|wget)[[:space:]].*\|[[:space:]]*(bash|sh|zsh|exec|source|eval) ]]; then
    echo "BLOCKED: Piping curl/wget output to shell is not allowed" >&2
    exit 2
fi

# SQL destructive operations
if [[ "$COMMAND" =~ [Dd][Rr][Oo][Pp][[:space:]]+[Tt][Aa][Bb][Ll][Ee] ]] ||
   [[ "$COMMAND" =~ [Tt][Rr][Uu][Nn][Cc][Aa][Tt][Ee][[:space:]]+[Tt][Aa][Bb][Ll][Ee] ]]; then
    echo "BLOCKED: DROP TABLE / TRUNCATE TABLE is not allowed" >&2
    exit 2
fi

# If none of the patterns matched, allow the command
exit 0
