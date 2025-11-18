"""Comprehensive AWS mocking fixtures for testing."""

import json
import boto3
import pytest
from moto import mock_aws
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any


@pytest.fixture
def mock_aws_services():
    """Mock all AWS services with real AWS infrastructure setup."""
    with mock_aws():
        # Create DynamoDB table
        dynamodb = boto3.resource("dynamodb", region_name="eu-west-1")
        table = dynamodb.create_table(
            TableName="ketchup_channel_information",
            KeySchema=[{"AttributeName": "channel_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "channel_id", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Create Secrets Manager secret
        secrets_client = boto3.client("secretsmanager", region_name="eu-west-1")
        secret_value = {
            "slack_token": "xoxb-test-token",
            "slack_app_token": "xapp-test-token",
            "slack_signing_secret": "test-signing-secret",
            "jira_api_token": "test-jira-token",
            "azure_openai_api_key": "test-azure-key",
        }
        secrets_client.create_secret(
            Name="Ketchup_Token_Secrets", SecretString=json.dumps(secret_value)
        )

        # Create SQS queue
        sqs = boto3.client("sqs", region_name="eu-west-1")
        queue_url = sqs.create_queue(QueueName="ketchup-events-queue")["QueueUrl"]

        yield {
            "dynamodb_table": table,
            "secrets_client": secrets_client,
            "sqs_queue_url": queue_url,
        }


@pytest.fixture
def mock_secrets_manager():
    """Mock AWS Secrets Manager with test credentials."""
    manager = AsyncMock()
    secret_data = {
        "slack_token": "xoxb-test-token",
        "slack_app_token": "xapp-test-token",
        "slack_signing_secret": "test-signing-secret",
        "jira_api_token": "test-jira-token",
        "azure_openai_api_key": "test-azure-key",
    }
    manager.get_secret.return_value = secret_data
    manager.get_secret_value.return_value = secret_data
    manager.get_slack_api_token_async.return_value = "xoxb-test-token"
    manager.get_app_secrets.return_value = secret_data
    manager.get_secret_async.return_value = {"SecretString": json.dumps(secret_data)}
    return manager


@pytest.fixture
def mock_dynamodb_client():
    """Mock DynamoDB client with common operations."""
    client = AsyncMock()

    # Default responses for common operations
    client.get_item.return_value = {
        "Item": {
            "channel_id": {"S": "C1234567890"},
            "channel_name": {"S": "test-channel"},
            "is_private": {"BOOL": False},
            "member_count": {"N": "10"},
        }
    }

    client.put_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
    client.update_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
    client.delete_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}

    client.scan.return_value = {
        "Items": [
            {
                "channel_id": {"S": "C1234567890"},
                "channel_name": {"S": "test-channel-1"},
            },
            {
                "channel_id": {"S": "C0987654321"},
                "channel_name": {"S": "test-channel-2"},
            },
        ],
        "Count": 2,
        "ScannedCount": 2,
    }

    return client


@pytest.fixture
def mock_sqs_client():
    """Mock SQS client for event queue operations."""
    client = AsyncMock()

    client.send_message.return_value = {
        "MessageId": "test-message-id-12345",
        "MD5OfBody": "test-md5-hash",
        "ResponseMetadata": {"HTTPStatusCode": 200},
    }

    client.receive_message.return_value = {
        "Messages": [
            {
                "MessageId": "test-message-id-12345",
                "ReceiptHandle": "test-receipt-handle",
                "Body": json.dumps(
                    {
                        "type": "channel_created",
                        "channel": {"id": "C1234567890", "name": "test-channel"},
                    }
                ),
            }
        ]
    }

    client.delete_message.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}

    return client


@pytest.fixture
def mock_slack_client():
    """Mock Slack WebClient for API operations."""
    client = AsyncMock()

    # Common Slack API responses
    client.conversations_info.return_value = {
        "ok": True,
        "channel": {
            "id": "C1234567890",
            "name": "test-channel",
            "is_private": False,
            "num_members": 10,
        },
    }

    client.conversations_list.return_value = {
        "ok": True,
        "channels": [
            {"id": "C1234567890", "name": "test-channel-1", "is_private": False},
            {"id": "C0987654321", "name": "test-channel-2", "is_private": True},
        ],
    }

    client.chat_postMessage.return_value = {
        "ok": True,
        "channel": "C1234567890",
        "ts": "1234567890.123456",
        "message": {"text": "Test message", "user": "U1234567890"},
    }

    client.users_info.return_value = {
        "ok": True,
        "user": {
            "id": "U1234567890",
            "name": "testuser",
            "real_name": "Test User",
            "profile": {"email": "test@adobe.com"},
        },
    }

    return client


@pytest.fixture
def mock_azure_openai_client():
    """Mock Azure OpenAI client for AI operations."""
    client = AsyncMock()

    # Mock chat completion response
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content="This is a test AI response for channel analysis."
            )
        )
    ]
    mock_response.usage = MagicMock(
        prompt_tokens=50, completion_tokens=25, total_tokens=75
    )

    client.chat.completions.create.return_value = mock_response

    return client


@pytest.fixture
def mock_jira_client():
    """Mock JIRA client for issue operations."""
    client = AsyncMock()

    client.search_issues.return_value = [
        MagicMock(
            key="TEST-123",
            fields=MagicMock(
                summary="Test JIRA Issue",
                status=MagicMock(name="In Progress"),
                assignee=MagicMock(displayName="Test Assignee"),
            ),
        )
    ]

    client.create_issue.return_value = MagicMock(key="TEST-124", id="12345")

    return client


@pytest.fixture
def mock_environment_variables(monkeypatch):
    """Set up mock environment variables for testing."""
    env_vars = {
        "AWS_REGION": "eu-west-1",
        "DYNAMODB_TABLE_NAME": "ketchup_channel_information",
        "AWS_SECRET_NAME": "Ketchup_Token_Secrets",
        "LOG_LEVEL": "WARNING",
        "PYTHONPATH": "/app",
        "USE_IPAAS": "true",
        "PORT": "8081",
        "KETCHUP_STATUS_UPDATER_FEATURE": "true",
        "KETCHUP_NLP_FEATURE": "true",
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    return env_vars


class MockHTTPResponse:
    """Mock HTTP response for testing HTTP clients."""

    def __init__(self, json_data: Dict[str, Any], status_code: int = 200):
        self.json_data = json_data
        self.status_code = status_code
        self.status = status_code
        self.headers = {"Content-Type": "application/json"}

    async def json(self):
        """Return JSON data."""
        return self.json_data

    async def text(self):
        """Return text representation."""
        return json.dumps(self.json_data)

    async def read(self):
        """Return bytes representation."""
        return json.dumps(self.json_data).encode()


@pytest.fixture
def mock_http_client():
    """Mock HTTP client for external API calls."""
    client = AsyncMock()

    # Default successful response
    client.get.return_value = MockHTTPResponse({"status": "ok", "data": []})
    client.post.return_value = MockHTTPResponse({"status": "created", "id": "12345"})
    client.put.return_value = MockHTTPResponse({"status": "updated"})
    client.delete.return_value = MockHTTPResponse({"status": "deleted"})

    return client


@pytest.fixture(autouse=True)
def auto_mock_aws_credentials(monkeypatch):
    """Automatically mock AWS credentials for all tests."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
