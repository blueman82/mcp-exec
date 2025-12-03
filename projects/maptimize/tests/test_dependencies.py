import tomllib
from pathlib import Path


def test_pyproject_valid_toml():
    """Verify pyproject.toml is valid TOML."""
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        config = tomllib.load(f)
    assert config["project"]["name"] == "maptimize"
    assert "version" in config["project"]
    assert "requires-python" in config["project"]


def test_no_version_pinning_in_dependencies():
    """Ensure no version constraints in runtime dependencies."""
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        config = tomllib.load(f)

    dependencies = config["project"].get("dependencies", [])
    for dep in dependencies:
        assert ">=" not in dep, f"Found version pinning in: {dep}"
        assert "==" not in dep, f"Found version pinning in: {dep}"
        assert "<=" not in dep, f"Found version pinning in: {dep}"
        assert "~=" not in dep, f"Found version pinning in: {dep}"


def test_no_version_pinning_in_dev_dependencies():
    """Ensure no version constraints in dev dependencies."""
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        config = tomllib.load(f)

    dev_deps = config["project"].get("optional-dependencies", {}).get("dev", [])
    for dep in dev_deps:
        assert ">=" not in dep, f"Found version pinning in dev: {dep}"
        assert "==" not in dep, f"Found version pinning in dev: {dep}"
        assert "<=" not in dep, f"Found version pinning in dev: {dep}"
        assert "~=" not in dep, f"Found version pinning in dev: {dep}"


def test_required_runtime_dependencies():
    """Verify all required runtime dependencies are listed."""
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        config = tomllib.load(f)

    dependencies = config["project"].get("dependencies", [])
    dep_names = [dep.split("[")[0] for dep in dependencies]

    required = ["slack-bolt", "aioboto3", "structlog"]
    for req in required:
        assert req in dep_names, f"Missing required dependency: {req}"


def test_build_system_configured():
    """Verify build system is properly configured."""
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        config = tomllib.load(f)

    assert "build-system" in config
    assert config["build-system"]["build-backend"] == "hatchling.build"
    assert "hatchling" in config["build-system"]["requires"]


def test_tool_configurations_present():
    """Verify tool configurations are present."""
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        config = tomllib.load(f)

    assert "tool" in config
    tools = ["pytest", "mypy", "black", "ruff"]
    for tool in tools:
        assert tool in config["tool"], f"Tool config missing for: {tool}"
