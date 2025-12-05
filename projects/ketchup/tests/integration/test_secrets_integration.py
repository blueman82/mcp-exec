"""
Integration tests for the SecretsManager and its interactions with AWS Secrets Manager.

These tests verify the integration between SecretsManager and AWS, including error handling and edge cases.

What is being tested:
    - Successful retrieval of secrets from AWS.
    - Error handling for missing secrets and invalid JSON.
    - All major side effects (AWS calls, error propagation) are asserted.

Expected outcomes:
    - Secrets are retrieved as expected for each scenario.
    - Errors are handled gracefully and do not propagate unexpectedly.

Dependencies:
    - All external dependencies (AWS Secrets Manager) are mocked.
    - No real AWS calls are made.
    - Tests require pytest, pytest-asyncio, and pytest-mock.

Test structure:
    - Each test is fully isolated and uses fixtures for dependencies.
    - All test functions use Google-style docstrings and detailed inline comments.
    - All test logic is covered by assertions; no logic is skipped.

"""

import json

import pytest
from botocore.exceptions import ClientError
from pytest_mock import MockerFixture

from packages.secrets.manager import SecretsManager

SECRET_NAME = "TestSecretName"
MOCK_SECRET_VALUE_DICT = {"api_key": "test-key", "token": "test-token"}
MOCK_SECRET_VALUE_STRING = json.dumps(MOCK_SECRET_VALUE_DICT)


@pytest.fixture
def secrets_manager() -> SecretsManager:
    """
    Provides a standard instance of SecretsManager.

    Returns:
        SecretsManager: Instance of the secrets manager.

    Example:
        Used to inject a SecretsManager for integration tests.
    """
    # We will patch the client inside each test now
    return SecretsManager()


@pytest.mark.asyncio
async def test_get_secret_success(secrets_manager: SecretsManager, mocker: MockerFixture):
    """
    Verify successful secret retrieval and parsing.

    Args:
        secrets_manager (SecretsManager): The secrets manager under test.
        mocker (MockerFixture): The pytest-mock fixture for patching/mocking.

    Returns:
        None

    Raises:
        AssertionError: If the expected calls or results are not observed.

    Example:
        This test verifies that a valid secret is retrieved and parsed as a dict.
    """
    # Arrange
    mock_boto_client = mocker.AsyncMock()
    mock_boto_client.get_secret_value.return_value = {"SecretString": MOCK_SECRET_VALUE_STRING}

    # Patch aioboto3.Session.client to return an async context manager yielding our mock
    class AsyncContextManagerMock:
        async def __aenter__(self):
            return mock_boto_client

        async def __aexit__(self, exc_type, exc, tb):
            pass

    mocker.patch("aioboto3.Session.client", return_value=AsyncContextManagerMock())

    # Act
    secret_dict = await secrets_manager.get_secret_async(SECRET_NAME)

    # Assert
    mock_boto_client.get_secret_value.assert_awaited_once_with(SecretId=SECRET_NAME)
    assert secret_dict == MOCK_SECRET_VALUE_DICT


@pytest.mark.asyncio
async def test_get_secret_retrieval_error(secrets_manager: SecretsManager, mocker: MockerFixture):
    """
    Verify that ClientError from boto3 propagates correctly.

    Args:
        secrets_manager (SecretsManager): The secrets manager under test.
        mocker (MockerFixture): The pytest-mock fixture for patching/mocking.

    Returns:
        None

    Raises:
        ClientError: If the secret is not found or another AWS error occurs.

    Example:
        This test verifies that a missing secret raises a ClientError.
    """
    # Arrange
    mock_boto_client = mocker.AsyncMock()
    mock_error_response = {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}}
    mock_boto_client.get_secret_value.side_effect = ClientError(
        mock_error_response, "GetSecretValue"
    )

    # Patch aioboto3.Session.client to return an async context manager yielding our mock
    class AsyncContextManagerMock:
        async def __aenter__(self):
            return mock_boto_client

        async def __aexit__(self, exc_type, exc, tb):
            pass

    mocker.patch("aioboto3.Session.client", return_value=AsyncContextManagerMock())

    # Act & Assert
    with pytest.raises(ClientError) as excinfo:
        await secrets_manager.get_secret_async(SECRET_NAME)

    mock_boto_client.get_secret_value.assert_awaited_once_with(SecretId=SECRET_NAME)
    assert "ResourceNotFoundException" in str(excinfo.value)


@pytest.mark.asyncio
async def test_get_secret_parsing_error(secrets_manager: SecretsManager, mocker: MockerFixture):
    """
    Verify that JSONDecodeError is raised for invalid JSON secret string.

    Args:
        secrets_manager (SecretsManager): The secrets manager under test.
        mocker (MockerFixture): The pytest-mock fixture for patching/mocking.

    Returns:
        None

    Raises:
        JSONDecodeError: If the secret string is not valid JSON.

    Example:
        This test verifies that an invalid JSON secret raises JSONDecodeError.
    """
    # Arrange
    mock_boto_client = mocker.AsyncMock()
    mock_boto_client.get_secret_value.return_value = {"SecretString": "invalid json"}

    # Patch aioboto3.Session.client to return an async context manager yielding our mock
    class AsyncContextManagerMock:
        async def __aenter__(self):
            return mock_boto_client

        async def __aexit__(self, exc_type, exc, tb):
            pass

    mocker.patch("aioboto3.Session.client", return_value=AsyncContextManagerMock())

    # Act & Assert
    with pytest.raises(json.JSONDecodeError):
        await secrets_manager.get_secret_async(SECRET_NAME)

    mock_boto_client.get_secret_value.assert_awaited_once_with(SecretId=SECRET_NAME)


@pytest.mark.asyncio
async def test_get_secret_missing_string(secrets_manager: SecretsManager, mocker: MockerFixture):
    """
    Verify that KeyError is raised if SecretString is missing and not handled.

    Args:
        secrets_manager (SecretsManager): The secrets manager under test.
        mocker (MockerFixture): The pytest-mock fixture for patching/mocking.

    Returns:
        None

    Raises:
        KeyError: If the SecretString key is missing in the response.

    Example:
        This test verifies that a missing SecretString raises KeyError.
    """
    # Arrange
    mock_boto_client = mocker.AsyncMock()
    mock_boto_client.get_secret_value.return_value = {
        "SecretBinary": b"somebinarydata"
    }  # No SecretString

    # Patch aioboto3.Session.client to return an async context manager yielding our mock
    class AsyncContextManagerMock:
        async def __aenter__(self):
            return mock_boto_client

        async def __aexit__(self, exc_type, exc, tb):
            pass

    mocker.patch("aioboto3.Session.client", return_value=AsyncContextManagerMock())

    # Act & Assert
    with pytest.raises(KeyError) as excinfo:
        await secrets_manager.get_secret_async(SECRET_NAME)

    mock_boto_client.get_secret_value.assert_awaited_once_with(SecretId=SECRET_NAME)
    assert "SecretString" in str(excinfo.value)
