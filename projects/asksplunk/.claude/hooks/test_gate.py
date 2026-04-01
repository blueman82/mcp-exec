#!/usr/bin/env python3
"""Stop hook: block Claude from stopping if unit tests fail.

Runs pytest on the unit test suite and exits with code 2 to block
if tests fail. Includes stop_hook_active loop prevention.

Exit codes:
  0 — tests pass or not applicable, allow stop
  2 — tests fail, BLOCK stop (Claude must fix before stopping)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _find_project_root() -> Path | None:
    """Find the AskSplunk project root by looking for pyproject.toml."""
    candidates = [
        os.environ.get("CLAUDE_PROJECT_DIR"),
        os.environ.get("CLAUDE_WORKING_DIR"),
    ]

    for candidate in candidates:
        if candidate:
            p = Path(candidate)
            if (p / "pyproject.toml").exists():
                return p

    # Walk up from cwd
    current = Path.cwd()
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent

    return None


def _has_python_changes(project_root: Path) -> bool:
    """Check if there are any Python files in recent changes worth testing.

    Uses git log with a safe fallback if there aren't enough commits.
    """
    try:
        # First check how many commits exist
        count_result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=project_root,
        )
        if count_result.returncode != 0:
            return True  # Can't determine, run tests

        commit_count = int(count_result.stdout.strip())
        lookback = min(commit_count, 10)
        if lookback == 0:
            return True  # New repo, run tests

        result = subprocess.run(
            ["git", "diff", "--name-only", f"HEAD~{lookback}", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=project_root,
        )
        if result.returncode == 0:
            return any(
                line.strip().endswith(".py")
                for line in result.stdout.strip().split("\n")
                if line.strip()
            )
    except (subprocess.TimeoutExpired, OSError, ValueError):
        pass
    # If we can't determine, run tests anyway to be safe
    return True


def main() -> None:
    """Run unit tests and block stop if they fail."""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            sys.exit(0)

        input_data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    # Prevent infinite loops: if this is the second stop attempt, allow it.
    # stop_hook_active is set by the Claude Code hook system, not user input.
    if input_data.get("stop_hook_active", False):
        output = {"suppressOutput": True}
        print(json.dumps(output))
        sys.exit(0)

    project_root = _find_project_root()
    if not project_root:
        output = {
            "suppressOutput": False,
            "systemMessage": "Test gate: could not find project root, allowing stop",
        }
        print(json.dumps(output))
        sys.exit(0)

    test_dir = project_root / "tests" / "unit"
    if not test_dir.exists():
        output = {
            "suppressOutput": False,
            "systemMessage": "Test gate: no tests/unit/ directory found, allowing stop",
        }
        print(json.dumps(output))
        sys.exit(0)

    # Skip if no Python changes in recent commits
    if not _has_python_changes(project_root):
        output = {
            "suppressOutput": False,
            "systemMessage": "Test gate: no Python changes detected, allowing stop",
        }
        print(json.dumps(output))
        sys.exit(0)

    # Find the right Python/pytest to use.
    # Prefer the project venv, fall back to PATH pytest, then sys.executable.
    venv_pytest = project_root / ".venv" / "bin" / "pytest"
    if venv_pytest.exists():
        pytest_cmd = [str(venv_pytest)]
    else:
        # Try PATH-based pytest (works if venv is activated)
        which_result = subprocess.run(
            ["which", "pytest"], capture_output=True, text=True, timeout=5
        )
        if which_result.returncode == 0 and which_result.stdout.strip():
            pytest_cmd = [which_result.stdout.strip()]
        else:
            pytest_cmd = [sys.executable, "-m", "pytest"]

    # Run pytest
    try:
        result = subprocess.run(
            [
                *pytest_cmd,
                str(test_dir),
                "-x",
                "-q",
                "--tb=short",
                "--no-header",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=project_root,
            env={**os.environ, "PYTHONPATH": str(project_root / "src")},
        )
    except subprocess.TimeoutExpired:
        # Timeout might indicate hanging test — block to be safe
        msg = "BLOCKED: pytest timed out after 120s. A test may be hanging — investigate before stopping."
        print(msg, file=sys.stderr)
        sys.exit(2)
    except OSError as e:
        output = {
            "suppressOutput": False,
            "systemMessage": f"Test gate: could not run pytest: {e}",
        }
        print(json.dumps(output))
        sys.exit(0)

    if result.returncode == 0:
        # Extract summary line (last non-empty line)
        lines = [line for line in result.stdout.strip().split("\n") if line.strip()]
        summary = lines[-1] if lines else "all passed"
        output = {
            "suppressOutput": False,
            "systemMessage": f"Test gate PASSED: {summary}",
        }
        print(json.dumps(output))
        sys.exit(0)

    # Tests failed — block stop
    # Show last 20 lines of output for context
    stdout_lines = result.stdout.strip().split("\n")
    stderr_lines = result.stderr.strip().split("\n") if result.stderr.strip() else []
    all_lines = stdout_lines + stderr_lines
    tail = "\n".join(all_lines[-20:])

    msg = (
        f"BLOCKED: Unit tests failed. Fix the failures before stopping.\n\n"
        f"Test output (last 20 lines):\n{tail}"
    )
    print(msg, file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
