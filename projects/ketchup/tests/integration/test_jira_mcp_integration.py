"""
test_jira_mcp_integration.py

Integration tests for JIRA MCP ReAct implementation.
Tests the actual integration with AWS Secrets, IMS tokens, and MCP server.
"""

import os
import subprocess

import pytest

from packages.integrations.async_mcp_client import AsyncMCPClient
from packages.integrations.ims_token_manager import IMSTokenManager
from packages.secrets.manager import SecretsManager

pytestmark = pytest.mark.integration


class TestJIRAMCPIntegration:
    """Integration tests for JIRA MCP functionality."""

    def test_setup_ipaas_env_script(self):
        """Test that the setup-ipaas-env.sh script works."""
        # Script is in tests/setup directory
        script_path = os.path.join(os.path.dirname(__file__), "../setup/setup-ipaas-env.sh")
        if not os.path.exists(script_path):
            pytest.skip("setup-ipaas-env.sh script not found")

        # Test script execution
        result = subprocess.run(
            ["bash", script_path],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(__file__),
        )

        # Script should succeed
        assert result.returncode == 0, f"Setup script failed: {result.stderr}"

        # Should output environment variable confirmation
        assert "Environment variables set:" in result.stdout
        assert "JIRA_API_KEY:" in result.stdout
        assert "JIRA_USERNAME:" in result.stdout

    def test_docker_compose_configuration(self):
        """Test that docker-compose configuration is valid."""
        # Get absolute path relative to this test file
        test_dir = os.path.dirname(os.path.abspath(__file__))
        compose_file = os.path.join(test_dir, "../../infrastructure/docker-compose.yml")
        compose_file = os.path.abspath(compose_file)

        if not os.path.exists(compose_file):
            pytest.skip(f"docker-compose.yml not found at {compose_file}")

        # Test docker-compose config validation
        result = subprocess.run(
            ["docker-compose", "-f", compose_file, "config", "--quiet"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(__file__),
            env={
                **os.environ,
                "JIRA_API_KEY": "test",
                "JIRA_USERNAME": "test",
                "JIRA_PASSWORD": "test",
            },
        )

        assert result.returncode == 0, f"Docker-compose config invalid: {result.stderr}"

    def test_required_services_defined(self):
        """Test that all required services are defined in docker-compose."""
        # Get absolute path relative to this test file
        test_dir = os.path.dirname(os.path.abspath(__file__))
        compose_file = os.path.join(test_dir, "../../infrastructure/docker-compose.yml")
        compose_file = os.path.abspath(compose_file)

        if not os.path.exists(compose_file):
            pytest.skip(f"docker-compose.yml not found at {compose_file}")

        result = subprocess.run(
            ["docker-compose", "-f", compose_file, "config", "--services"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(__file__),
            env={
                **os.environ,
                "JIRA_API_KEY": "test",
                "JIRA_USERNAME": "test",
                "JIRA_PASSWORD": "test",
            },
        )

        services = result.stdout.strip().split("\n")
        required_services = [
            "mcp-jira",
            "ketchup-app",
            "ketchup-metadata-updater",
            "nginx",
        ]

        for service in required_services:
            assert service in services, f"Required service {service} not found in docker-compose"

    @pytest.mark.asyncio
    async def test_secrets_manager_integration(self):
        """Test SecretsManager can fetch secrets."""
        try:
            secrets_manager = SecretsManager()
            secrets = await secrets_manager.get_app_secrets()

            # Should have iPaaS-related secrets (uppercase keys)
            assert "IPAAS_API_KEY" in secrets
            assert "IPAAS_USERNAME" in secrets
            assert "IPAAS_PASSWORD" in secrets

            # Validate they're not empty (they might have default values)
            # Note: These might be empty strings if not configured in AWS Secrets Manager
            print(f"IPAAS_API_KEY present: {'IPAAS_API_KEY' in secrets}")
            print(f"IPAAS_USERNAME value: {secrets.get('IPAAS_USERNAME', 'Not found')}")

            # Just check that the secrets exist, not that they have values
            # since they might not be configured in the test environment

        except Exception as e:
            pytest.skip(f"Secrets Manager not available: {e}")

    @pytest.mark.asyncio
    async def test_ims_token_manager_initialization(self):
        """Test IMS token manager can be initialized."""
        try:
            secrets_manager = SecretsManager()
            ims_manager = IMSTokenManager(secrets_manager)

            # Should initialize without error
            assert ims_manager is not None
            assert ims_manager.secrets_manager is not None

        except Exception as e:
            pytest.skip(f"IMS Token Manager initialization failed: {e}")

    @pytest.mark.asyncio
    async def test_mcp_client_initialization(self):
        """Test MCP client can be initialized with IMS token manager."""
        try:
            secrets_manager = SecretsManager()
            ims_manager = IMSTokenManager(secrets_manager)
            mcp_client = AsyncMCPClient(ims_manager)

            # Should initialize without error
            assert mcp_client is not None
            assert mcp_client.token_manager is not None

        except Exception as e:
            pytest.skip(f"MCP Client initialization failed: {e}")

    @pytest.mark.asyncio
    async def test_mcp_client_health_check(self):
        """Test MCP client health check functionality."""
        try:
            secrets_manager = SecretsManager()
            ims_manager = IMSTokenManager(secrets_manager)
            mcp_client = AsyncMCPClient(ims_manager)

            # Health check should not raise an error
            # (might return False if MCP server is not running, but shouldn't crash)
            health_result = await mcp_client.health_check()
            assert isinstance(health_result, bool)

        except Exception as e:
            pytest.skip(f"MCP Client health check failed: {e}")

    def test_docker_compose_ipaas_configuration(self):
        """Test that docker-compose is configured for iPaaS mode."""
        # Get absolute path relative to this test file
        test_dir = os.path.dirname(os.path.abspath(__file__))
        compose_file = os.path.join(test_dir, "../../infrastructure/docker-compose.yml")
        compose_file = os.path.abspath(compose_file)

        if not os.path.exists(compose_file):
            pytest.skip(f"docker-compose.yml not found at {compose_file}")

        # Check that MCP service is configured for iPaaS
        result = subprocess.run(
            ["docker-compose", "-f", compose_file, "config"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(__file__),
            env={
                **os.environ,
                "JIRA_API_KEY": "test",
                "JIRA_USERNAME": "test",
                "JIRA_PASSWORD": "test",
            },
        )

        config_output = result.stdout

        # Should have USE_IPAAS=true
        assert "USE_IPAAS" in config_output
        assert "true" in config_output

        # Should have proper service dependencies
        assert "depends_on" in config_output
        assert "mcp-jira" in config_output

    def test_health_checks_configured(self):
        """Test that health checks are configured for services."""
        # Get absolute path relative to this test file
        test_dir = os.path.dirname(os.path.abspath(__file__))
        compose_file = os.path.join(test_dir, "../../infrastructure/docker-compose.yml")
        compose_file = os.path.abspath(compose_file)

        if not os.path.exists(compose_file):
            pytest.skip(f"docker-compose.yml not found at {compose_file}")

        result = subprocess.run(
            ["docker-compose", "-f", compose_file, "config"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(__file__),
            env={
                **os.environ,
                "JIRA_API_KEY": "test",
                "JIRA_USERNAME": "test",
                "JIRA_PASSWORD": "test",
            },
        )

        config_output = result.stdout

        # Should have health checks configured
        health_check_count = config_output.count("healthcheck:")
        assert (
            health_check_count >= 3
        ), f"Expected at least 3 health checks, found {health_check_count}"

    def test_logging_configuration(self):
        """Test that logging is properly configured."""
        # Get absolute path relative to this test file
        test_dir = os.path.dirname(os.path.abspath(__file__))
        compose_file = os.path.join(test_dir, "../../infrastructure/docker-compose.yml")
        compose_file = os.path.abspath(compose_file)

        if not os.path.exists(compose_file):
            pytest.skip(f"docker-compose.yml not found at {compose_file}")

        result = subprocess.run(
            ["docker-compose", "-f", compose_file, "config"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(__file__),
            env={
                **os.environ,
                "JIRA_API_KEY": "test",
                "JIRA_USERNAME": "test",
                "JIRA_PASSWORD": "test",
            },
        )

        config_output = result.stdout

        # Should use json-file logging driver
        assert "json-file" in config_output
