"""Tests for Dockerfile configuration and structure."""

from pathlib import Path


def test_dockerfile_exists():
    """Verify Dockerfile exists."""
    dockerfile = Path("infrastructure/Dockerfile")
    assert dockerfile.exists(), "Dockerfile should exist at infrastructure/Dockerfile"


def test_dockerfile_multi_stage():
    """Verify Dockerfile uses multi-stage build."""
    with open("infrastructure/Dockerfile", "r") as f:
        content = f.read()

    from_count = content.count("FROM")
    assert from_count >= 2, (
        f"Dockerfile should use multi-stage build with at least 2 FROM "
        f"statements, found {from_count}"
    )


def test_dockerfile_non_root_user():
    """Verify non-root user is used."""
    with open("infrastructure/Dockerfile", "r") as f:
        content = f.read()

    assert "USER" in content, "Dockerfile should specify a USER"

    # Get the USER line after all other configuration
    user_lines = [line.strip() for line in content.split("\n") if line.strip().startswith("USER")]
    assert len(user_lines) > 0, "Dockerfile should have a USER directive"

    # Verify non-root user
    final_user = user_lines[-1]
    assert (
        "root" not in final_user or "1000" in final_user
    ), "Dockerfile should use non-root user (UID 1000)"


def test_dockerfile_healthcheck():
    """Verify HEALTHCHECK is present."""
    with open("infrastructure/Dockerfile", "r") as f:
        content = f.read()

    assert "HEALTHCHECK" in content, "Dockerfile should include HEALTHCHECK directive"
