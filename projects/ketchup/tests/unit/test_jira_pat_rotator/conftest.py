"""Shared fixtures for PAT rotator tests."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure AWS region is set for all tests in this module
os.environ.setdefault("AWS_DEFAULT_REGION", "eu-west-1")
os.environ.setdefault("AWS_REGION", "eu-west-1")
os.environ.setdefault("AWS_SECRET_NAME", "test-secret")
os.environ.setdefault("DYNAMODB_TABLE_NAME", "test-table")


@pytest.fixture(autouse=True)
def mock_aws_services():
    """
    Auto-mock AWS services to prevent real AWS calls during unit tests.
    
    This fixture mocks both sync (boto3) and async (aioboto3) AWS SDK calls.
    """
    # Comprehensive secrets JSON matching production structure
    secrets_json = (
        "{"
        '"slack_signing_secret": "test-sign",'
        '"slack_api_token": "xoxb-test",'
        '"slack_user_api_token": "xoxp-test",'
        '"slack_bot_app_id": "BTEST123",'
        '"exigence_user_id": "UTEST123",'
        '"azure_openai_lb_api_key": "test-azure-key",'
        '"bot_slack_user_id": "UTESTBOT",'
        '"ketchup_jira_pat": "test-pat-token",'
        '"ketchup_jira_pat_id": "test-pat-456",'
        '"JIRA_PAT": "test-pat",'
        '"JIRA_PAT_EXPIRY": "2025-12-31T00:00:00Z"'
        "}"
    )
    
    # Mock aioboto3.Session for async AWS calls
    with patch("aioboto3.Session") as mock_aioboto3_session:
        # Create mock async session
        mock_session = MagicMock()
        mock_aioboto3_session.return_value = mock_session
        
        # Mock async client context manager
        mock_async_client = AsyncMock()
        mock_async_client.__aenter__.return_value = mock_async_client
        mock_async_client.__aexit__.return_value = None
        
        # Mock async AWS operations
        mock_async_client.get_secret_value.return_value = {"SecretString": secrets_json}
        mock_async_client.update_secret.return_value = {}
        mock_async_client.put_item.return_value = {}
        mock_async_client.update_item.return_value = {}
        mock_async_client.get_item.return_value = {}
        mock_async_client.send_message.return_value = {"MessageId": "test-msg-id"}
        
        mock_session.client.return_value = mock_async_client
        
        # Mock boto3.client for sync AWS calls
        with patch("boto3.client") as mock_boto3_client:
            # Create sync client mocks
            mock_sync_secrets_client = MagicMock()
            mock_sync_secrets_client.get_secret_value.return_value = {"SecretString": secrets_json}
            mock_sync_secrets_client.update_secret.return_value = {}
            
            mock_sync_sqs_client = MagicMock()
            mock_sync_sqs_client.send_message.return_value = {"MessageId": "test-msg-id"}
            
            mock_sync_dynamodb_client = MagicMock()
            mock_sync_dynamodb_client.put_item.return_value = {}
            mock_sync_dynamodb_client.get_item.return_value = {}
            
            def get_mock_client(service_name, **kwargs):
                if service_name == "secretsmanager":
                    return mock_sync_secrets_client
                elif service_name == "sqs":
                    return mock_sync_sqs_client
                elif service_name == "dynamodb":
                    return mock_sync_dynamodb_client
                return MagicMock()
            
            mock_boto3_client.side_effect = get_mock_client
            
            # Mock boto3.Session as well
            with patch("boto3.Session") as mock_boto3_session:
                mock_boto3_session.return_value.client.side_effect = get_mock_client
                
                yield {
                    "async_client": mock_async_client,
                    "sync_secrets_client": mock_sync_secrets_client,
                    "sync_sqs_client": mock_sync_sqs_client,
                    "sync_dynamodb_client": mock_sync_dynamodb_client,
                }


@pytest.fixture(autouse=True)
async def reset_container():
    """Reset the global TypedServiceRegistry between tests."""
    # Clear the global container before each test
    from packages.core import typed_di_integration
    typed_di_integration._typed_registry = None
    
    yield
    
    # Clean up after test
    typed_di_integration._typed_registry = None


@pytest.fixture
def mock_rotation_service():
    """Mock PAT rotation service."""
    return AsyncMock()


@pytest.fixture
def mock_health_service():
    """Mock health status service."""
    return MagicMock()
