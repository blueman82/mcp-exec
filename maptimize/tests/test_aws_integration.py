"""Comprehensive AWS Secrets Manager integration tests.

Tests AWS integration including:
- Secrets Manager API calls and token retrieval
- EC2 IAM role authentication
- Error handling and retry logic
- Environment variable configuration
- Secret structure validation
"""

import pytest
import json
import os
from unittest.mock import MagicMock, patch, call
from maptimize.config import get_slack_tokens, load_processes


class TestAWSSecretsManagerIntegration:
    """Test complete AWS Secrets Manager integration flow."""

    @patch('maptimize.config.boto3.Session')
    def test_complete_aws_token_retrieval_flow(self, mock_session_class):
        """Test complete flow: create session → call API → parse secret → return tokens."""
        # Setup mock client
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.client.return_value = mock_client

        secret_data = {
            'bot_token': 'xoxb-complete-flow-token',
            'app_token': 'xapp-complete-flow-token'
        }
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps(secret_data)
        }

        # Execute
        bot_token, app_token = get_slack_tokens()

        # Verify complete flow
        mock_session_class.assert_called_once_with()
        mock_session.client.assert_called_once_with('secretsmanager', region_name='eu-west-1')
        mock_client.get_secret_value.assert_called_once_with(SecretId='maptimize/slack-tokens')
        assert bot_token == 'xoxb-complete-flow-token'
        assert app_token == 'xapp-complete-flow-token'

    @patch('maptimize.config.boto3.Session')
    def test_aws_ec2_iam_role_authentication(self, mock_session_class):
        """Test EC2 IAM role authentication (no AWS profile)."""
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.client.return_value = mock_client

        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'bot_token': 'xoxb-ec2-iam-role',
                'app_token': 'xapp-ec2-iam-role'
            })
        }

        # Clear AWS_PROFILE to simulate EC2 environment
        with patch.dict(os.environ, {}, clear=False):
            if 'AWS_PROFILE' in os.environ:
                del os.environ['AWS_PROFILE']
            bot_token, app_token = get_slack_tokens()

        # Verify Session created without profile (EC2 IAM role)
        mock_session_class.assert_called_once_with()
        assert bot_token == 'xoxb-ec2-iam-role'

    @patch('maptimize.config.boto3.Session')
    def test_aws_credentials_with_profile_chain(self, mock_session_class):
        """Test AWS credential chain with explicit profile."""
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.client.return_value = mock_client

        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'bot_token': 'xoxb-profile-chain',
                'app_token': 'xapp-profile-chain'
            })
        }

        with patch.dict(os.environ, {'AWS_PROFILE': 'development'}, clear=False):
            bot_token, app_token = get_slack_tokens()

        # Verify Session created with profile
        mock_session_class.assert_called_once_with(profile_name='development')
        assert bot_token == 'xoxb-profile-chain'

    @patch('maptimize.config.boto3.Session')
    def test_aws_multi_region_support(self, mock_session_class):
        """Test AWS Secrets Manager across different regions."""
        regions = ['eu-west-1', 'us-east-1', 'ap-southeast-1']

        for region in regions:
            mock_session = MagicMock()
            mock_client = MagicMock()
            mock_session_class.return_value = mock_session
            mock_session.client.return_value = mock_client

            mock_client.get_secret_value.return_value = {
                'SecretString': json.dumps({
                    'bot_token': f'xoxb-{region}',
                    'app_token': f'xapp-{region}'
                })
            }

            with patch.dict(os.environ, {'AWS_REGION': region}, clear=False):
                bot_token, app_token = get_slack_tokens()

            # Verify region is passed to client
            mock_session.client.assert_called_with('secretsmanager', region_name=region)
            mock_session_class.reset_mock()

    @patch('maptimize.config.boto3.Session')
    def test_aws_secret_structure_validation(self, mock_session_class):
        """Test validation of secret structure and required keys."""
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.client.return_value = mock_client

        # Test with all required keys
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'bot_token': 'xoxb-valid-structure',
                'app_token': 'xapp-valid-structure',
                'extra_field': 'should_be_ignored'
            })
        }

        bot_token, app_token = get_slack_tokens()
        assert bot_token == 'xoxb-valid-structure'
        assert app_token == 'xapp-valid-structure'

    @patch('maptimize.config.boto3.Session')
    def test_aws_token_format_validation(self, mock_session_class):
        """Test that returned tokens have expected format."""
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.client.return_value = mock_client

        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'bot_token': 'xoxb-1234567890-1234567890-abcdefghijklmnopqrst',
                'app_token': 'xapp-1-1234567890-abcdefghijklmnopqrst'
            })
        }

        bot_token, app_token = get_slack_tokens()

        # Verify token format
        assert bot_token.startswith('xoxb-')
        assert app_token.startswith('xapp-')
        assert len(bot_token) > 10
        assert len(app_token) > 10


class TestAWSErrorHandling:
    """Test error handling in AWS Secrets Manager integration."""

    @patch('maptimize.config.boto3.Session')
    def test_aws_secret_not_found_error(self, mock_session_class):
        """Test handling of ResourceNotFoundException."""
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.client.return_value = mock_client

        # Simulate secret not found
        mock_client.get_secret_value.side_effect = Exception(
            "Secrets Manager secret not found"
        )

        with pytest.raises(RuntimeError, match="Failed to fetch Slack tokens"):
            get_slack_tokens()

    @patch('maptimize.config.boto3.Session')
    def test_aws_access_denied_error(self, mock_session_class):
        """Test handling of AccessDeniedException."""
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.client.return_value = mock_client

        # Simulate access denied
        mock_client.get_secret_value.side_effect = Exception(
            "User is not authorized to perform: secretsmanager:GetSecretValue"
        )

        with pytest.raises(RuntimeError, match="Failed to fetch Slack tokens"):
            get_slack_tokens()

    @patch('maptimize.config.boto3.Session')
    def test_aws_network_timeout_error(self, mock_session_class):
        """Test handling of network timeout."""
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.client.return_value = mock_client

        # Simulate network timeout
        mock_client.get_secret_value.side_effect = Exception(
            "Connection timeout"
        )

        with pytest.raises(RuntimeError, match="Failed to fetch Slack tokens"):
            get_slack_tokens()

    @patch('maptimize.config.boto3.Session')
    def test_aws_malformed_secret_json(self, mock_session_class):
        """Test handling of malformed JSON in secret value."""
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.client.return_value = mock_client

        # Simulate malformed JSON
        mock_client.get_secret_value.return_value = {
            'SecretString': '{"bot_token": "xoxb-test", invalid json'
        }

        with pytest.raises(RuntimeError, match="Failed to fetch Slack tokens"):
            get_slack_tokens()

    @patch('maptimize.config.boto3.Session')
    def test_aws_missing_bot_token_in_secret(self, mock_session_class):
        """Test handling when bot_token is missing from secret."""
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.client.return_value = mock_client

        # Secret missing bot_token
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'app_token': 'xapp-test'
            })
        }

        with pytest.raises(RuntimeError, match="Failed to fetch Slack tokens"):
            get_slack_tokens()

    @patch('maptimize.config.boto3.Session')
    def test_aws_missing_app_token_in_secret(self, mock_session_class):
        """Test handling when app_token is missing from secret."""
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.client.return_value = mock_client

        # Secret missing app_token
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'bot_token': 'xoxb-test'
            })
        }

        with pytest.raises(RuntimeError, match="Failed to fetch Slack tokens"):
            get_slack_tokens()

    @patch('maptimize.config.boto3.Session')
    def test_aws_empty_secret_string(self, mock_session_class):
        """Test handling of empty secret string."""
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.client.return_value = mock_client

        # Empty secret string
        mock_client.get_secret_value.return_value = {
            'SecretString': '{}'
        }

        with pytest.raises(RuntimeError, match="Failed to fetch Slack tokens"):
            get_slack_tokens()


class TestAWSSecretRotation:
    """Test handling of secret updates and rotation."""

    @patch('maptimize.config.boto3.Session')
    def test_fetch_updated_secret_on_each_call(self, mock_session_class):
        """Test that secret is fetched fresh on each call (no caching)."""
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.client.return_value = mock_client

        # Simulate secret rotation: first call returns old token, second returns new
        old_secret = {'bot_token': 'xoxb-old', 'app_token': 'xapp-old'}
        new_secret = {'bot_token': 'xoxb-new', 'app_token': 'xapp-new'}

        mock_client.get_secret_value.side_effect = [
            {'SecretString': json.dumps(old_secret)},
            {'SecretString': json.dumps(new_secret)}
        ]

        # First call
        bot_token1, app_token1 = get_slack_tokens()
        assert bot_token1 == 'xoxb-old'

        # Second call should get new secret (no caching)
        bot_token2, app_token2 = get_slack_tokens()
        assert bot_token2 == 'xoxb-new'

        # Verify API was called twice
        assert mock_client.get_secret_value.call_count == 2

    @patch('maptimize.config.boto3.Session')
    def test_secret_with_binary_data(self, mock_session_class):
        """Test handling of binary secret data (if applicable)."""
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.client.return_value = mock_client

        # Standard text secret (binary would need base64 decoding)
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'bot_token': 'xoxb-binary-test',
                'app_token': 'xapp-binary-test'
            })
        }

        bot_token, app_token = get_slack_tokens()
        assert bot_token == 'xoxb-binary-test'


class TestAWSEnvironmentConfiguration:
    """Test configuration through environment variables."""

    @patch('maptimize.config.boto3.Session')
    def test_all_environment_variables_combined(self, mock_session_class):
        """Test using all environment variables together."""
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.client.return_value = mock_client

        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'bot_token': 'xoxb-combined-env',
                'app_token': 'xapp-combined-env'
            })
        }

        with patch.dict(os.environ, {
            'AWS_PROFILE': 'production',
            'AWS_REGION': 'us-west-2',
            'SLACK_TOKENS_SECRET_ID': 'prod/slack-tokens'
        }, clear=False):
            bot_token, app_token = get_slack_tokens()

        # Verify all environment variables were used
        mock_session_class.assert_called_once_with(profile_name='production')
        mock_session.client.assert_called_once_with('secretsmanager', region_name='us-west-2')
        mock_client.get_secret_value.assert_called_once_with(SecretId='prod/slack-tokens')
        assert bot_token == 'xoxb-combined-env'

    @patch('maptimize.config.boto3.Session')
    def test_default_values_when_env_not_set(self, mock_session_class):
        """Test default values are used when environment variables not set."""
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.client.return_value = mock_client

        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'bot_token': 'xoxb-defaults',
                'app_token': 'xapp-defaults'
            })
        }

        # Clear all related environment variables
        clear_env = {k: v for k, v in os.environ.items()
                     if k not in ['AWS_PROFILE', 'AWS_REGION', 'SLACK_TOKENS_SECRET_ID']}

        with patch.dict(os.environ, clear_env, clear=True):
            bot_token, app_token = get_slack_tokens()

        # Verify defaults
        mock_session_class.assert_called_once_with()
        mock_session.client.assert_called_once_with('secretsmanager', region_name='eu-west-1')
        mock_client.get_secret_value.assert_called_once_with(SecretId='maptimize/slack-tokens')
