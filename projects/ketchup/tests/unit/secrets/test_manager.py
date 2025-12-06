"""
Unit tests for the SecretsManager class.

These tests verify the functionality of SecretsManager with mocked AWS interactions.
All external dependencies (AWS Secrets Manager) are mocked to ensure unit test isolation.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from packages.secrets.manager import SecretsManager


@pytest.fixture
def mock_secrets():
    """Fixture providing mock secret values."""
    return {
        "slack_signing_secret": "test-signing-secret",
        "authorised_users": ["user1", "user2"],
        "slack_api_token": "test-slack-token",
        "slack_user_api_token": "test-user-token",
        "slack_bot_app_id": "test-bot-id",
        "exigence_user_id": "test-exigence-id",
        "azure_openai_lb_api_key": "test-azure-key",
        "bot_slack_user_id": "test-bot-user-id",
    }


@pytest.fixture
def secrets_manager():
    """Fixture providing a SecretsManager instance."""
    return SecretsManager(region_name="test-region")


class TestSecretsManager:
    """Test suite for SecretsManager class."""

    @pytest.mark.asyncio
    async def test_init(self):
        """Test SecretsManager initialization."""
        # Test with default region
        manager = SecretsManager()
        assert manager.region_name == "eu-west-1"  # AWS_REGION default

        # Test with custom region
        manager = SecretsManager(region_name="us-east-1")
        assert manager.region_name == "us-east-1"

    @pytest.mark.asyncio
    async def test_get_secret_async_success(self, secrets_manager, mock_secrets):
        """Test successful secret retrieval from AWS Secrets Manager."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.get_secret_value.return_value = {"SecretString": json.dumps(mock_secrets)}

        mock_session = MagicMock()
        mock_session.client.return_value.__aenter__.return_value = mock_client

        with patch("aioboto3.Session", return_value=mock_session):
            # Act
            result = await secrets_manager.get_secret_async("test-secret")

            # Assert
            assert result == mock_secrets
            mock_client.get_secret_value.assert_called_once_with(SecretId="test-secret")

    @pytest.mark.asyncio
    async def test_get_secret_async_no_secret_string(self, secrets_manager):
        """Test handling when SecretString is missing from response."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.get_secret_value.return_value = {"SecretBinary": b"binary-data"}

        mock_session = MagicMock()
        mock_session.client.return_value.__aenter__.return_value = mock_client

        with patch("aioboto3.Session", return_value=mock_session):
            # Act & Assert
            with pytest.raises(KeyError) as exc_info:
                await secrets_manager.get_secret_async("test-secret")

            assert "SecretString not found in secret value response" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_secret_async_aws_error(self, secrets_manager):
        """Test handling of AWS client errors."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.get_secret_value.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": "Secret not found",
                }
            },
            "GetSecretValue",
        )

        mock_session = MagicMock()
        mock_session.client.return_value.__aenter__.return_value = mock_client

        with patch("aioboto3.Session", return_value=mock_session):
            # Act & Assert
            with pytest.raises(ClientError):
                await secrets_manager.get_secret_async("test-secret")

    @pytest.mark.asyncio
    async def test_get_secret_async_json_decode_error(self, secrets_manager):
        """Test handling of invalid JSON in secret string."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.get_secret_value.return_value = {"SecretString": "invalid-json"}

        mock_session = MagicMock()
        mock_session.client.return_value.__aenter__.return_value = mock_client

        with patch("aioboto3.Session", return_value=mock_session):
            # Act & Assert
            with pytest.raises(json.JSONDecodeError):
                await secrets_manager.get_secret_async("test-secret")

    @pytest.mark.asyncio
    async def test_get_app_secrets_success(self, secrets_manager, mock_secrets):
        """Test successful retrieval and mapping of application secrets."""
        # Arrange
        with patch.object(
            secrets_manager, "get_secret_async", return_value=mock_secrets
        ) as mock_get:
            # Act
            result = await secrets_manager.get_app_secrets()

            # Assert
            mock_get.assert_called_once_with(secrets_manager.APP_SECRETS_NAME)
            assert result["SLACK_SIGNING_SECRET"] == "test-signing-secret"
            assert result["SLACK_API_TOKEN"] == "test-slack-token"
            assert result["SLACK_USER_API_TOKEN"] == "test-user-token"
            assert result["APP_BOT_USER_ID"] == "test-bot-id"
            assert result["EXIGENCE_USER_ID"] == "test-exigence-id"
            assert result["AZURE_OPENAI_LB_API_KEY"] == "test-azure-key"
            assert result["BOT_SLACK_USER_ID"] == "test-bot-user-id"
            # Check new fields with defaults
            assert result["IMS_CLIENT_ID"] == "ketchup_prod"
            assert result["IMS_CLIENT_SECRET"] == ""
            assert result["IPAAS_USERNAME"] == "ketchup"
            assert result["AUTHORISED_SLACK_USER_IDS"] == []

    @pytest.mark.asyncio
    async def test_get_app_secrets_retrieval_error(self, secrets_manager):
        """Test error handling when secret retrieval fails."""
        # Arrange
        with patch.object(
            secrets_manager,
            "get_secret_async",
            side_effect=ClientError({"Error": {"Code": "AccessDenied"}}, "GetSecretValue"),
        ):
            # Act & Assert
            with pytest.raises(ClientError):
                await secrets_manager.get_app_secrets()

    @pytest.mark.asyncio
    async def test_get_app_secrets_missing_key(self, secrets_manager):
        """Test error handling when expected keys are missing from secrets."""
        # Arrange
        incomplete_secrets = {
            "slack_signing_secret": "test-secret",
            # Missing other required keys
        }

        with patch.object(secrets_manager, "get_secret_async", return_value=incomplete_secrets):
            # Act & Assert
            with pytest.raises(KeyError):
                await secrets_manager.get_app_secrets()

    @pytest.mark.asyncio
    async def test_get_slack_signing_secret(self, secrets_manager):
        """Test retrieval of Slack signing secret."""
        # Arrange
        mock_app_secrets = {"SLACK_SIGNING_SECRET": "test-signing-secret"}

        with patch.object(secrets_manager, "get_app_secrets", return_value=mock_app_secrets):
            # Act
            result = await secrets_manager.get_slack_signing_secret()

            # Assert
            assert result == "test-signing-secret"

    @pytest.mark.asyncio
    async def test_get_authorised_users(self, secrets_manager):
        """Test retrieval of authorised users."""
        # Arrange
        mock_app_secrets = {"AUTHORISED_USERS": ["user1", "user2"]}

        with patch.object(secrets_manager, "get_app_secrets", return_value=mock_app_secrets):
            # Act
            result = await secrets_manager.get_authorised_users()

            # Assert
            assert result == ["user1", "user2"]

    @pytest.mark.asyncio
    async def test_get_slack_api_token_async(self, secrets_manager):
        """Test retrieval of Slack API token."""
        # Arrange
        mock_app_secrets = {"SLACK_API_TOKEN": "test-api-token"}

        with patch.object(secrets_manager, "get_app_secrets", return_value=mock_app_secrets):
            # Act
            result = await secrets_manager.get_slack_api_token_async()

            # Assert
            assert result == "test-api-token"

    @pytest.mark.asyncio
    async def test_get_slack_user_api_token(self, secrets_manager):
        """Test retrieval of Slack user API token."""
        # Arrange
        mock_app_secrets = {"SLACK_USER_API_TOKEN": "test-user-token"}

        with patch.object(secrets_manager, "get_app_secrets", return_value=mock_app_secrets):
            # Act
            result = await secrets_manager.get_slack_user_api_token()

            # Assert
            assert result == "test-user-token"

    @pytest.mark.asyncio
    async def test_get_exigence_user_id_async(self, secrets_manager):
        """Test retrieval of exigence user ID."""
        # Arrange
        mock_app_secrets = {"EXIGENCE_USER_ID": "test-exigence-id"}

        with patch.object(secrets_manager, "get_app_secrets", return_value=mock_app_secrets):
            # Act
            result = await secrets_manager.get_exigence_user_id_async()

            # Assert
            assert result == "test-exigence-id"

    @pytest.mark.asyncio
    async def test_get_azure_openai_lb_api_key(self, secrets_manager):
        """Test retrieval of Azure OpenAI API key."""
        # Arrange
        mock_app_secrets = {"AZURE_OPENAI_LB_API_KEY": "test-azure-key"}

        with patch.object(secrets_manager, "get_app_secrets", return_value=mock_app_secrets):
            # Act
            result = await secrets_manager.get_azure_openai_lb_api_key()

            # Assert
            assert result == "test-azure-key"

    @pytest.mark.asyncio
    async def test_get_bot_slack_user_id_async(self, secrets_manager):
        """Test retrieval of bot Slack user ID."""
        # Arrange
        mock_app_secrets = {"BOT_SLACK_USER_ID": "test-bot-user-id"}

        with patch.object(secrets_manager, "get_app_secrets", return_value=mock_app_secrets):
            # Act
            result = await secrets_manager.get_bot_slack_user_id_async()

            # Assert
            assert result == "test-bot-user-id"

    @pytest.mark.asyncio
    async def test_logging_calls(self, secrets_manager, mock_secrets):
        """Test that appropriate logging occurs during operations."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.get_secret_value.return_value = {"SecretString": json.dumps(mock_secrets)}

        mock_session = MagicMock()
        mock_session.client.return_value.__aenter__.return_value = mock_client

        with patch("aioboto3.Session", return_value=mock_session):
            with patch("packages.secrets.manager.logger") as mock_logger:
                # Act
                await secrets_manager.get_secret_async("test-secret")

                # Assert
                mock_logger.info.assert_called_with("Starting get_secret_async function.")

    @pytest.mark.asyncio
    async def test_error_logging(self, secrets_manager):
        """Test that errors are properly logged."""
        # Arrange
        error = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "GetSecretValue",
        )

        mock_client = AsyncMock()
        mock_client.get_secret_value.side_effect = error

        mock_session = MagicMock()
        mock_session.client.return_value.__aenter__.return_value = mock_client

        with patch("aioboto3.Session", return_value=mock_session):
            with patch("packages.secrets.manager.logger") as mock_logger:
                # Act & Assert
                with pytest.raises(ClientError):
                    await secrets_manager.get_secret_async("test-secret")

                mock_logger.error.assert_called_with(
                    "Unable to retrieve secret asynchronously: %s", error
                )
