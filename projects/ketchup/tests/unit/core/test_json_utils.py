"""Tests for json_utils module."""

from unittest.mock import AsyncMock

import orjson
import pytest

from packages.core.json_utils import parse_json_response

# Capture the real orjson.dumps function at import time to avoid mock pollution
_real_orjson_dumps = orjson.dumps


class TestJsonUtils:
    """Test cases for JSON parsing utilities."""

    @pytest.mark.asyncio
    async def test_parse_json_response_simple(self):
        """Test parsing simple JSON response."""
        # Mock response
        mock_response = AsyncMock()
        test_data = {"status": "ok", "data": [1, 2, 3]}
        mock_response.read.return_value = orjson.dumps(test_data)

        # Parse
        result = await parse_json_response(mock_response)

        # Verify
        assert result == test_data
        mock_response.read.assert_called_once()

    @pytest.mark.asyncio
    async def test_parse_json_response_large(self):
        """Test parsing large JSON response (performance scenario)."""
        # Create large test data similar to Slack channel history
        large_data = {
            "ok": True,
            "messages": [
                {
                    "text": f"Message {i}",
                    "user": f"U{i:06d}",
                    "ts": f"1234567890.{i:06d}",
                    "reactions": [{"name": "thumbsup", "count": i % 5}],
                }
                for i in range(1000)
            ],
        }

        mock_response = AsyncMock()
        mock_response.read.return_value = _real_orjson_dumps(large_data)

        result = await parse_json_response(mock_response)

        assert result["ok"] is True
        assert len(result["messages"]) == 1000
        assert result["messages"][0]["text"] == "Message 0"

    @pytest.mark.asyncio
    async def test_parse_json_response_empty_object(self):
        """Test parsing empty JSON object."""
        mock_response = AsyncMock()
        mock_response.read.return_value = b"{}"

        result = await parse_json_response(mock_response)
        assert result == {}

    @pytest.mark.asyncio
    async def test_parse_json_response_unicode(self):
        """Test parsing JSON with unicode characters."""
        mock_response = AsyncMock()
        test_data = {"message": "Hello 👋 世界", "status": "✅"}
        mock_response.read.return_value = orjson.dumps(test_data)

        result = await parse_json_response(mock_response)
        assert result == test_data
        assert result["message"] == "Hello 👋 世界"
        assert result["status"] == "✅"

    @pytest.mark.asyncio
    async def test_parse_json_response_nested(self):
        """Test parsing deeply nested JSON structures."""
        nested_data = {"level1": {"level2": {"level3": {"items": ["a", "b", "c"], "count": 3}}}}

        mock_response = AsyncMock()
        mock_response.read.return_value = _real_orjson_dumps(nested_data)

        result = await parse_json_response(mock_response)
        assert result["level1"]["level2"]["level3"]["items"] == ["a", "b", "c"]
        assert result["level1"]["level2"]["level3"]["count"] == 3

    @pytest.mark.asyncio
    async def test_parse_json_response_null_values(self):
        """Test parsing JSON with null values."""
        test_data = {"name": "test", "value": None, "items": [1, None, 3]}

        mock_response = AsyncMock()
        mock_response.read.return_value = orjson.dumps(test_data)

        result = await parse_json_response(mock_response)
        assert result["name"] == "test"
        assert result["value"] is None
        assert result["items"] == [1, None, 3]

    @pytest.mark.asyncio
    async def test_parse_json_response_boolean_values(self):
        """Test parsing JSON with boolean values."""
        test_data = {"success": True, "error": False, "flags": [True, False, True]}

        mock_response = AsyncMock()
        mock_response.read.return_value = orjson.dumps(test_data)

        result = await parse_json_response(mock_response)
        assert result["success"] is True
        assert result["error"] is False
        assert result["flags"] == [True, False, True]

    @pytest.mark.asyncio
    async def test_parse_json_response_number_types(self):
        """Test parsing JSON with various number types."""
        test_data = {
            "integer": 42,
            "float": 3.14159,
            "negative": -100,
            "exponential": 1.23e-4,
            "large": 999999999999999,
        }

        mock_response = AsyncMock()
        mock_response.read.return_value = orjson.dumps(test_data)

        result = await parse_json_response(mock_response)
        assert result["integer"] == 42
        assert result["float"] == 3.14159
        assert result["negative"] == -100
        assert result["exponential"] == 1.23e-4
        assert result["large"] == 999999999999999

    @pytest.mark.asyncio
    async def test_parse_json_response_invalid_json(self):
        """Test parsing invalid JSON raises appropriate error."""
        mock_response = AsyncMock()
        mock_response.read.return_value = b"not valid json"

        with pytest.raises(orjson.JSONDecodeError):
            await parse_json_response(mock_response)

    @pytest.mark.asyncio
    async def test_parse_json_response_empty_response(self):
        """Test parsing empty response."""
        mock_response = AsyncMock()
        mock_response.read.return_value = b""

        with pytest.raises(orjson.JSONDecodeError):
            await parse_json_response(mock_response)

    @pytest.mark.asyncio
    async def test_parse_json_response_array(self):
        """Test parsing JSON array response."""
        mock_response = AsyncMock()
        test_data = [{"id": 1, "name": "item1"}, {"id": 2, "name": "item2"}]
        mock_response.read.return_value = orjson.dumps(test_data)

        result = await parse_json_response(mock_response)
        assert result == test_data
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["name"] == "item2"

    @pytest.mark.asyncio
    async def test_parse_json_response_empty(self):
        """Test parsing empty JSON object (alias for existing test)."""
        mock_response = AsyncMock()
        mock_response.read.return_value = b"{}"

        result = await parse_json_response(mock_response)
        assert result == {}

    @pytest.mark.asyncio
    async def test_parse_json_response_null(self):
        """Test parsing JSON with null values (alias for existing test)."""
        test_data = {"name": "test", "value": None, "items": [1, None, 3]}

        mock_response = AsyncMock()
        mock_response.read.return_value = orjson.dumps(test_data)

        result = await parse_json_response(mock_response)
        assert result["name"] == "test"
        assert result["value"] is None
        assert result["items"] == [1, None, 3]

    @pytest.mark.asyncio
    async def test_parse_json_response_numbers(self):
        """Test parsing JSON with various number types (alias for existing test)."""
        test_data = {
            "integer": 42,
            "float": 3.14159,
            "negative": -100,
            "exponential": 1.23e-4,
            "large": 999999999999999,
        }

        mock_response = AsyncMock()
        mock_response.read.return_value = orjson.dumps(test_data)

        result = await parse_json_response(mock_response)
        assert result["integer"] == 42
        assert result["float"] == 3.14159
        assert result["negative"] == -100
        assert result["exponential"] == 1.23e-4
        assert result["large"] == 999999999999999

    @pytest.mark.asyncio
    async def test_parse_json_response_invalid(self):
        """Test parsing invalid JSON raises appropriate error (alias for existing test)."""
        mock_response = AsyncMock()
        mock_response.read.return_value = b"not valid json"

        with pytest.raises(orjson.JSONDecodeError):
            await parse_json_response(mock_response)

    @pytest.mark.asyncio
    async def test_parse_json_response_connection_error(self):
        """Test handling connection error (alias for existing test)."""
        import aiohttp

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.url = "https://api.example.com/test"
        mock_response.headers = {"x-request-id": "test-123"}
        mock_response.read.side_effect = aiohttp.ClientConnectionError("Connection closed")

        with pytest.raises(aiohttp.ClientConnectionError) as exc_info:
            await parse_json_response(mock_response)

        assert "Connection closed after receiving 200 response" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_parse_json_response_connection_closed(self):
        """Test handling connection closed error."""
        import aiohttp

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.url = "https://api.example.com/test"
        mock_response.headers = {"x-request-id": "test-123"}
        mock_response.read.side_effect = aiohttp.ClientConnectionError("Connection closed")

        with pytest.raises(aiohttp.ClientConnectionError) as exc_info:
            await parse_json_response(mock_response)

        assert "Connection closed after receiving 200 response" in str(exc_info.value)
