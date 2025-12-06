"""
Integration tests conftest.py - AWS configuration and fixtures.

AWS configuration is loaded from .env.test in the project root by the
root conftest.py. This file provides fixtures for integration tests
that require AWS connectivity.
"""

import os

import pytest


def _is_aws_configured() -> bool:
    """Check if AWS is properly configured for integration tests."""
    return bool(os.environ.get("AWS_PROFILE") or os.environ.get("AWS_ACCESS_KEY_ID"))


@pytest.fixture(scope="session")
def aws_profile() -> str:
    """
    Get the AWS profile from environment.

    Skips test if AWS is not configured.
    The profile is loaded from .env.test by the root conftest.py.
    """
    if not _is_aws_configured():
        pytest.skip(
            "AWS not configured. Create .env.test from .env.test.example "
            "or set AWS_PROFILE environment variable."
        )
    return os.environ.get("AWS_PROFILE", "default")


@pytest.fixture(scope="session")
def aws_region() -> str:
    """Get the AWS region from environment."""
    return os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "eu-west-1"))


@pytest.fixture(autouse=True)
def skip_without_aws(request):
    """
    Auto-skip integration tests if AWS is not configured.

    Tests can opt-out by using the @pytest.mark.no_aws_required marker.
    """
    # Check if test has the no_aws_required marker
    if request.node.get_closest_marker("no_aws_required"):
        return

    # Check if this is in the integration directory
    if "integration" in str(request.fspath):
        if not _is_aws_configured():
            pytest.skip(
                "AWS not configured. Create .env.test from .env.test.example "
                "or set AWS_PROFILE environment variable."
            )
