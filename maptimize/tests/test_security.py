"""Security tests for Slack bot authentication and verification.

Tests request signature verification and secure token handling.
"""

import json
from unittest.mock import MagicMock, patch

import pytest


class TestSlackTokensWithSigningSecret:
    """Tests for Slack token retrieval including signing secret."""

    @patch("maptimize.config.boto3.Session")
    def test_get_slack_tokens_returns_signing_secret(self, mock_session):
        """Test that get_slack_tokens returns bot_token, app_token, and signing_secret.

        Verifies the config module retrieves all three required credentials
        from AWS Secrets Manager needed for request signature verification.
        """
        from maptimize.config import get_slack_tokens

        # Setup mock
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(
                {
                    "bot_token": "xoxb-test-token",
                    "app_token": "xapp-test-token",
                    "signing_secret": "test-signing-secret",
                }
            )
        }

        # Execute
        bot_token, app_token, signing_secret = get_slack_tokens()

        # Verify
        assert bot_token == "xoxb-test-token"
        assert app_token == "xapp-test-token"
        assert signing_secret == "test-signing-secret"

    @patch("maptimize.config.boto3.Session")
    def test_get_slack_tokens_raises_on_missing_signing_secret(self, mock_session):
        """Test that get_slack_tokens raises RuntimeError if signing_secret missing.

        Ensures critical security credential is present in AWS Secrets Manager.
        """
        from maptimize.config import get_slack_tokens

        # Setup mock with missing signing_secret
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(
                {
                    "bot_token": "xoxb-test-token",
                    "app_token": "xapp-test-token",
                    # Missing signing_secret
                }
            )
        }

        # Execute & verify raises
        with pytest.raises(RuntimeError) as exc_info:
            get_slack_tokens()

        assert "signing_secret" in str(exc_info.value).lower()


class TestTokenVerificationEnabled:
    """Tests for request signature verification in Slack app."""

    def test_bot_module_uses_signing_secret(self):
        """Test that bot.py code includes signing_secret parameter.

        Verifies the bot initialization code contains the signing_secret
        parameter which is required for request signature verification.
        """
        # Read bot.py source and verify it includes signing_secret
        with open("src/maptimize/bot.py", "r") as f:
            bot_source = f.read()

        # Verify signing_secret is extracted from get_slack_tokens
        assert (
            "SIGNING_SECRET = " in bot_source
        ), "bot.py must unpack SIGNING_SECRET from get_slack_tokens()"

        # Verify signing_secret is passed to App initialization
        assert (
            "signing_secret=SIGNING_SECRET" in bot_source
        ), "signing_secret parameter must be passed to App()"

        # Verify token_verification_enabled=True
        assert (
            "token_verification_enabled=True" in bot_source
        ), "token_verification_enabled must be explicitly set to True"

    def test_config_returns_three_values(self):
        """Test that get_slack_tokens returns bot_token, app_token, and signing_secret.

        The three-tuple return is required for secure request verification.
        """
        # Read config.py source and verify return statement
        with open("src/maptimize/config.py", "r") as f:
            config_source = f.read()

        # Verify signing_secret is extracted from secret
        assert (
            'signing_secret = secret["signing_secret"]' in config_source
        ), "signing_secret must be extracted from AWS secret"

        # Verify all three values are returned
        assert (
            "return bot_token, app_token, signing_secret" in config_source
        ), "Function must return all three credentials as tuple"
