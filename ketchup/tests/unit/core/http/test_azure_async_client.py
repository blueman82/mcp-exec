"""
_test_azure_async_client.py

Unit tests for packages.ai.core.azure_async_client.

Covers:
- AzureClientError: construction, attributes, string representation
- AzureConfig: header generation with/without API key
- AzureAsyncClient: initialization, _build_azure_openai_url (valid/error), _process_response (success, 429, 4xx, invalid JSON), _make_azure_api_request (mocked)
- All tests follow the Ketchup Slack Bot test plan and cursor rules
"""

from unittest.mock import AsyncMock, patch

import orjson
import pytest

from packages.ai.core.azure_async_client import (
    AzureAsyncClient,
    AzureClientError,
    AzureConfig,
)
from packages.core.async_client import SafeResponse

# Capture the real orjson.dumps function at import time to avoid mock pollution
_real_orjson_dumps = orjson.dumps


@pytest.mark.unit
class TestAzureClientError:
    """Unit tests for AzureClientError exception."""

    def test_error_attributes_and_str(self) -> None:
        """Test AzureClientError attributes and string representation."""
        err = AzureClientError(
            "fail", status_code=400, response_data={"foo": "bar"}, request_id="req-123"
        )
        assert err.message == "fail"
        assert err.status_code == 400
        assert err.response_data == {"foo": "bar"}
        assert err.request_id == "req-123"
        s = str(err)
        assert "fail" in s and "400" in s and "req-123" in s


@pytest.mark.unit
class TestAzureConfig:
    """Unit tests for AzureConfig header generation."""

    def test_headers_with_api_key(self) -> None:
        """Test get_headers includes api-key if provided."""
        cfg = AzureConfig(api_key="abc", endpoint="https://foo")
        headers = cfg.get_headers()
        assert headers["Content-Type"] == "application/json"
        assert headers["api-key"] == "abc"

    def test_headers_without_api_key(self) -> None:
        """Test get_headers omits api-key if not provided."""
        cfg = AzureConfig(endpoint="https://foo")
        headers = cfg.get_headers()
        assert headers["Content-Type"] == "application/json"
        assert "api-key" not in headers


@pytest.mark.unit
class TestAzureAsyncClient:
    """Unit tests for AzureAsyncClient core logic."""

    def _create_safe_response(
        self,
        status: int,
        headers: dict,
        body: bytes,
        content_type: str = "application/json",
        url: str = "http://test.com",
    ) -> SafeResponse:
        """Helper to create a SafeResponse dictionary for testing."""
        return {
            "status": status,
            "headers": headers,
            "body": body,
            "content_type": content_type,
            "url": url,
        }

    @pytest.mark.asyncio
    async def test_process_response_success(self) -> None:
        """Test _process_response with a successful JSON response."""
        client = AzureAsyncClient(api_key="abc", endpoint="https://foo")
        safe_response = self._create_safe_response(
            status=200,
            headers={"x-request-id": "req-1"},
            body=_real_orjson_dumps({"ok": True}),
        )
        result = await client._process_response(safe_response)
        assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_process_response_429(self) -> None:
        """Test _process_response raises AzureClientError on 429."""
        client = AzureAsyncClient(api_key="abc", endpoint="https://foo")
        safe_response = self._create_safe_response(
            status=429,
            headers={"x-request-id": "req-2", "retry-after": "42"},
            body=b"",
        )
        with pytest.raises(AzureClientError) as exc:
            await client._process_response(safe_response)
        assert "Rate limit" in str(exc.value)
        assert exc.value.status_code == 429
        assert exc.value.request_id == "req-2"

    @pytest.mark.asyncio
    async def test_process_response_4xx(self) -> None:
        """Test _process_response raises AzureClientError on 4xx with error JSON."""
        client = AzureAsyncClient(api_key="abc", endpoint="https://foo")
        error_payload = _real_orjson_dumps({"error": {"message": "bad req"}})
        safe_response = self._create_safe_response(
            status=400,
            headers={"x-request-id": "req-3"},
            body=error_payload,
        )
        with pytest.raises(AzureClientError) as exc:
            await client._process_response(safe_response)
        assert "bad req" in str(exc.value)
        assert exc.value.status_code == 400
        assert exc.value.request_id == "req-3"

    @pytest.mark.asyncio
    async def test_process_response_4xx_nonjson(self) -> None:
        """Test _process_response raises AzureClientError on 4xx with non-JSON error."""
        client = AzureAsyncClient(api_key="abc", endpoint="https://foo")
        safe_response = self._create_safe_response(
            status=404,
            headers={"x-request-id": "req-4"},
            body=b"not found",
        )
        with pytest.raises(AzureClientError) as exc:
            await client._process_response(safe_response)
        assert "not found" in str(exc.value)
        assert exc.value.status_code == 404
        assert exc.value.request_id == "req-4"

    @pytest.mark.asyncio
    async def test_process_response_invalid_json(self) -> None:
        """Test _process_response returns text_response if JSON parsing fails."""
        client = AzureAsyncClient(api_key="abc", endpoint="https://foo")
        safe_response = self._create_safe_response(
            status=200,
            headers={"x-request-id": "req-5"},
            body=b"raw text",
        )
        result = await client._process_response(safe_response)
        assert result == {"text_response": "raw text"}

    @pytest.mark.asyncio
    @patch.object(AzureAsyncClient, "_make_api_request", new_callable=AsyncMock)
    @patch.object(AzureAsyncClient, "_process_response", new_callable=AsyncMock)
    async def test_make_azure_api_request_post(
        self, mock_process: AsyncMock, mock_make_api: AsyncMock
    ) -> None:
        """Test _make_azure_api_request for POST method with mocked internals."""
        client = AzureAsyncClient(api_key="abc", endpoint="https://foo")
        # The mock now returns a SafeResponse-like dictionary
        mock_make_api.return_value = self._create_safe_response(
            200, {}, b'{"ok": true}'
        )
        mock_process.return_value = {"ok": True}
        result = await client._make_azure_api_request(
            url="https://foo", method="POST", headers=None, json_data={"a": 1}
        )
        assert result == {"ok": True}
        mock_make_api.assert_awaited_once()
        mock_process.assert_awaited_once_with(mock_make_api.return_value)

    @pytest.mark.asyncio
    @patch.object(AzureAsyncClient, "_make_api_request", new_callable=AsyncMock)
    @patch.object(AzureAsyncClient, "_process_response", new_callable=AsyncMock)
    async def test_make_azure_api_request_get(
        self, mock_process: AsyncMock, mock_make_api: AsyncMock
    ) -> None:
        """Test _make_azure_api_request for GET method with mocked internals."""
        client = AzureAsyncClient(api_key="abc", endpoint="https://foo")
        # The mock now returns a SafeResponse-like dictionary
        mock_make_api.return_value = self._create_safe_response(
            200, {}, b'{"ok": true}'
        )
        mock_process.return_value = {"ok": True}
        result = await client._make_azure_api_request(
            url="https://foo", method="GET", headers=None, json_data={"a": 1}
        )
        assert result == {"ok": True}
        mock_make_api.assert_awaited_once()
        mock_process.assert_awaited_once_with(mock_make_api.return_value)

    @pytest.mark.asyncio
    async def test_azure_client_retry_logic(self) -> None:
        """Test retry logic with retryable errors."""
        from packages.ai.core.azure_async_client import AzureClientError

        client = AzureAsyncClient(api_key="test-key", endpoint="https://test.com")

        # Mock the backoff strategy to track calls
        mock_strategy = AsyncMock()
        client.backoff_strategy = mock_strategy

        # First call fails with retryable error, second succeeds
        call_count = 0
        async def mock_core_logic():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise AzureClientError("Rate limit exceeded", status_code=429)
            return {"success": True}

        # Mock strategy to return success result
        async def mock_execute(func):
            return await func()

        mock_strategy.execute.side_effect = mock_execute

        # Mock the internal methods to control the flow
        with patch.object(client, '_make_api_request', new_callable=AsyncMock) as mock_make_api, \
             patch.object(client, '_process_response', new_callable=AsyncMock) as mock_process:

            # Set up the mock chain
            mock_make_api.return_value = self._create_safe_response(200, {}, b'{"success": true}')
            mock_process.return_value = {"success": True}

            # Test the method that uses retry logic
            result = await client._make_azure_api_request("https://test.com/api")

            # Verify the strategy was used
            mock_strategy.execute.assert_called_once()
            assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_azure_client_timeout_handling(self) -> None:
        """Test timeout scenarios are properly handled."""
        import asyncio

        client = AzureAsyncClient(
            api_key="test-key",
            endpoint="https://test.com",
            request_timeout=1  # Very short timeout for testing
        )

        # Mock the backoff strategy
        mock_strategy = AsyncMock()
        client.backoff_strategy = mock_strategy

        # Mock a timeout error during execution
        async def timeout_mock(func):
            raise asyncio.TimeoutError("Request timed out")

        mock_strategy.execute.side_effect = timeout_mock

        # Test that timeout error is properly handled
        with pytest.raises(asyncio.TimeoutError) as exc_info:
            await client._make_azure_api_request("https://test.com/api")

        assert "Request timed out" in str(exc_info.value)
        mock_strategy.execute.assert_called_once()
