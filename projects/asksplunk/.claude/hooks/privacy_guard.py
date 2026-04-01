#!/usr/bin/env python3
"""PreToolUse hook: block writes containing secrets, PII, or logging violations.

Scans tool_input for Write/Edit/MultiEdit operations and exits with code 2
to block execution if dangerous patterns are found.

Exit codes:
  0 — content is clean, allow the operation
  2 — violation found, BLOCK the operation (Claude receives stderr for self-correction)
"""
from __future__ import annotations

import json
import os
import re
import sys

# --- Pattern definitions ---

# Hardcoded secrets/tokens (tightened formats from code review)
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Slack bot token", re.compile(r"xoxb-[0-9A-Za-z\-]{20,}")),
    ("Slack app token", re.compile(r"xapp-[0-9A-Za-z\-]{20,}")),
    ("Slack user token", re.compile(r"xoxp-[0-9A-Za-z\-]{20,}")),
    ("OpenAI API key", re.compile(r"sk-[0-9A-Za-z]{20,}")),
    ("OpenAI project key", re.compile(r"sk-proj-[0-9A-Za-z]{20,}")),
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    (
        "AWS secret key",
        re.compile(
            r"aws_secret_access_key\s*=\s*['\"]?[A-Za-z0-9/+=]{20,}['\"]?",
            re.IGNORECASE,
        ),
    ),
]

# Logging violations: logger calls with user content as keyword arguments.
# Uses word boundary + equals to avoid false positives like message_count=5.
_LOGGING_VIOLATIONS: list[tuple[str, re.Pattern[str]]] = [
    (
        "User message in log",
        re.compile(r"logger?\.\w+\(.*\bmessage\s*=\s*[^0-9]", re.IGNORECASE),
    ),
    (
        "User question in log",
        re.compile(r"logger?\.\w+\(.*\bquestion\s*=", re.IGNORECASE),
    ),
    (
        "User content in log",
        re.compile(r"logger?\.\w+\(.*\bcontent\s*=", re.IGNORECASE),
    ),
    (
        "User text in log",
        re.compile(r"logger?\.\w+\(.*\btext\s*=\s*[^0-9]", re.IGNORECASE),
    ),
    (
        "User query in log",
        re.compile(r"logger?\.\w+\(.*\bquery\s*=\s*[^0-9]", re.IGNORECASE),
    ),
]

# Slack mention injection in string literals
_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("@channel injection", re.compile(r"<!channel>")),
    ("@here injection", re.compile(r"<!here>")),
    ("@everyone injection", re.compile(r"<!everyone>")),
]

# Paths to skip — use os.sep-aware checks, not bare substring matching.
# Only skip test files and documentation, NOT .claude/ (hooks should be scanned too).
_SKIP_PREFIXES: list[str] = [
    "tests/",
    "docs/",
]
_SKIP_FILENAME_PREFIXES: list[str] = [
    "test_",
    "conftest",
]


def _extract_content(tool_input: dict, tool_name: str) -> str:
    """Extract the text content being written from the tool input."""
    if tool_name == "Write":
        return tool_input.get("content", "")
    if tool_name == "Edit":
        return tool_input.get("new_string", "")
    if tool_name == "MultiEdit":
        edits = tool_input.get("edits", [])
        parts = []
        for edit in edits:
            if isinstance(edit, dict):
                parts.append(edit.get("new_string", ""))
        return "\n".join(parts)
    return ""


def _should_skip(file_path: str) -> bool:
    """Check if this file should be skipped from scanning.

    Uses path-prefix matching (not substring) to avoid over-broad skipping.
    """
    # Normalize to relative path for prefix checks
    basename = os.path.basename(file_path)

    # Skip test files by filename prefix
    for prefix in _SKIP_FILENAME_PREFIXES:
        if basename.startswith(prefix):
            return True

    # Skip by directory prefix (check if any path component matches)
    for prefix in _SKIP_PREFIXES:
        if f"/{prefix}" in file_path or file_path.startswith(prefix):
            return True

    return False


def _scan_content(content: str) -> list[str]:
    """Scan content for violations. Scans line-by-line to avoid ReDoS on large inputs."""
    violations: list[str] = []
    seen: set[str] = set()

    for line in content.split("\n"):
        # Skip comment lines (reduce false positives)
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue

        for name, pattern in _SECRET_PATTERNS:
            if name not in seen and pattern.search(line):
                violations.append(f"Hardcoded secret: {name}")
                seen.add(name)

        for name, pattern in _LOGGING_VIOLATIONS:
            if name not in seen and pattern.search(line):
                violations.append(f"Logging violation: {name}")
                seen.add(name)

        for name, pattern in _INJECTION_PATTERNS:
            if name not in seen and pattern.search(line):
                violations.append(f"Slack injection: {name}")
                seen.add(name)

    return violations


def main() -> None:
    """Read tool input from stdin, scan for violations, exit 2 to block."""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            sys.exit(0)

        input_data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        # Can't parse input — don't block, let it through
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    if tool_name not in ("Write", "Edit", "MultiEdit"):
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    if _should_skip(file_path):
        sys.exit(0)

    content = _extract_content(tool_input, tool_name)
    if not content:
        sys.exit(0)

    violations = _scan_content(content)
    if violations:
        violation_list = "\n".join(f"  - {v}" for v in violations)
        msg = (
            f"BLOCKED: Privacy/security violation in {file_path}:\n"
            f"{violation_list}\n"
            f"Fix the content and retry."
        )
        print(msg, file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
