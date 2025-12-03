from pathlib import Path


def test_directory_structure():
    """Verify required directories exist."""
    required_dirs = ["src/maptimize", "tests", "infrastructure", "config"]
    for dir_path in required_dirs:
        assert Path(dir_path).exists(), f"Directory {dir_path} does not exist"


def test_py_typed_exists():
    """Verify py.typed marker for type hints."""
    py_typed = Path("src/maptimize/py.typed")
    assert py_typed.exists(), "py.typed marker file does not exist"
