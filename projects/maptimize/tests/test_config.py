import pytest
import os
import json
from unittest.mock import MagicMock, patch, AsyncMock
from maptimize.config import get_slack_tokens, load_processes


class TestGetSlackTokens:
    """Test suite for get_slack_tokens function."""

    def test_get_slack_tokens_success(self, mocker):
        """Test successful token retrieval from Secrets Manager."""
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'bot_token': 'xoxb-123456',
                'app_token': 'xapp-987654',
                'signing_secret': 'test-signing-secret'
            })
        }

        mocker.patch('maptimize.config.boto3.Session').return_value.client.return_value = mock_client

        bot_token, app_token, signing_secret = get_slack_tokens()

        assert bot_token == 'xoxb-123456'
        assert app_token == 'xapp-987654'
        assert signing_secret == 'test-signing-secret'
        mock_client.get_secret_value.assert_called_once()

    def test_get_slack_tokens_with_aws_profile(self, mocker):
        """Test that AWS_PROFILE environment variable is respected."""
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'bot_token': 'xoxb-profile-token',
                'app_token': 'xapp-profile-token',
                'signing_secret': 'profile-signing-secret'
            })
        }
        mock_session.client.return_value = mock_client

        mock_boto_session = mocker.patch('maptimize.config.boto3.Session')
        mock_boto_session.return_value = mock_session

        mocker.patch.dict(os.environ, {'AWS_PROFILE': 'custom_profile'})
        bot_token, app_token, signing_secret = get_slack_tokens()

        assert bot_token == 'xoxb-profile-token'
        assert app_token == 'xapp-profile-token'
        assert signing_secret == 'profile-signing-secret'
        mock_boto_session.assert_called_once_with(profile_name='custom_profile')

    def test_get_slack_tokens_default_profile(self, mocker):
        """Test that default profile is used when AWS_PROFILE is not set."""
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'bot_token': 'xoxb-default-token',
                'app_token': 'xapp-default-token',
                'signing_secret': 'default-signing-secret'
            })
        }
        mock_session.client.return_value = mock_client

        mock_boto_session = mocker.patch('maptimize.config.boto3.Session')
        mock_boto_session.return_value = mock_session

        # Ensure AWS_PROFILE is not set
        env_dict = {k: v for k, v in os.environ.items() if k != 'AWS_PROFILE'}
        mocker.patch.dict(os.environ, env_dict, clear=True)

        bot_token, app_token, signing_secret = get_slack_tokens()

        assert bot_token == 'xoxb-default-token'
        assert app_token == 'xapp-default-token'
        assert signing_secret == 'default-signing-secret'
        mock_boto_session.assert_called_once_with()

    def test_get_slack_tokens_missing_secret(self, mocker):
        """Test error handling for missing secret."""
        mock_client = MagicMock()
        mock_client.get_secret_value.side_effect = Exception("Secret not found")

        mocker.patch('maptimize.config.boto3.Session').return_value.client.return_value = mock_client

        with pytest.raises(RuntimeError, match="Failed to fetch Slack tokens"):
            get_slack_tokens()

    def test_get_slack_tokens_custom_secret_id(self, mocker):
        """Test that SLACK_TOKENS_SECRET_ID environment variable is respected."""
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'bot_token': 'xoxb-custom-secret',
                'app_token': 'xapp-custom-secret',
                'signing_secret': 'custom-signing-secret'
            })
        }

        mocker.patch('maptimize.config.boto3.Session').return_value.client.return_value = mock_client

        mocker.patch.dict(os.environ, {'SLACK_TOKENS_SECRET_ID': 'custom/secret/path'})
        bot_token, app_token, signing_secret = get_slack_tokens()

        assert bot_token == 'xoxb-custom-secret'
        assert app_token == 'xapp-custom-secret'
        assert signing_secret == 'custom-signing-secret'
        mock_client.get_secret_value.assert_called_once_with(SecretId='custom/secret/path')

    def test_get_slack_tokens_custom_region(self, mocker):
        """Test that AWS_REGION environment variable is respected."""
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'bot_token': 'xoxb-region-token',
                'app_token': 'xapp-region-token',
                'signing_secret': 'region-signing-secret'
            })
        }
        mock_session.client.return_value = mock_client

        mock_boto_session = mocker.patch('maptimize.config.boto3.Session')
        mock_boto_session.return_value = mock_session

        mocker.patch.dict(os.environ, {'AWS_REGION': 'us-east-1'})
        bot_token, app_token, signing_secret = get_slack_tokens()

        mock_session.client.assert_called_once_with('secretsmanager', region_name='us-east-1')

    def test_get_slack_tokens_missing_bot_token_in_secret(self, mocker):
        """Test error handling when bot_token is missing from secret."""
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'app_token': 'xapp-987654'
            })
        }

        mocker.patch('maptimize.config.boto3.Session').return_value.client.return_value = mock_client

        with pytest.raises(RuntimeError, match="Failed to fetch Slack tokens"):
            get_slack_tokens()

    def test_get_slack_tokens_invalid_json(self, mocker):
        """Test error handling for invalid JSON in secret."""
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            'SecretString': 'invalid json {'
        }

        mocker.patch('maptimize.config.boto3.Session').return_value.client.return_value = mock_client

        with pytest.raises(RuntimeError, match="Failed to fetch Slack tokens"):
            get_slack_tokens()


class TestLoadProcesses:
    """Test suite for load_processes function."""

    def test_load_processes_returns_dict(self):
        """Test that load_processes returns a dictionary."""
        processes = load_processes()

        assert isinstance(processes, dict)

    def test_load_processes_has_processes_key(self):
        """Test that loaded configuration contains expected structure."""
        processes = load_processes()

        # Check that configuration has expected keys
        assert len(processes) > 0

    def test_load_processes_structure(self):
        """Test that process structure contains expected fields."""
        processes = load_processes()

        assert isinstance(processes, dict)
        # Verify it's not empty
        assert len(processes) > 0
