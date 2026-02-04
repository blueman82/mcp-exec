"""Pytest configuration for project root.

Adds src/ directory to Python path so tests can import asksplunk package.
Loads AWS profile from .env.test for integration tests.
"""

import os
import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Load .env.test for integration tests
env_test = Path(__file__).parent / ".env.test"
if env_test.exists():
    with open(env_test) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()
