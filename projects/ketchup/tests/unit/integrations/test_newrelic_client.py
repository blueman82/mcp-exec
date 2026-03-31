"""Unit tests for AsyncNewRelicClient."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import orjson
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from packages.core.typed_di.service_registrations.protocols.monitoring_protocols import (
    NewRelicClientProtocol,
)
from packages.integrations.async_newrelic_client import AsyncNewRelicClient, NewRelicConfig

pytestmark = pytest.mark.unit

# Capture real orjson functions at import time to avoid mock pollution
_real_orjson_dumps = orjson.dumps


class TestAsyncNewRelicClientProtocolCompliance:
    """Verify AsyncNewRelicClient satisfies NewRelicClientProtocol."""

    def test_protocol_compliance(self):
        """AsyncNewRelicClient must implement NewRelicClientProtocol."""
        import inspect

        client = AsyncNewRelicClient(api_key="test-key", account_id="12345")

        protocol_methods = {
            name
            for name, _ in inspect.getmembers(
                NewRelicClientProtocol, predicate=inspect.isfunction
            )
            if not name.startswith("_")
        }

        service_methods = {
            name
            for name, _ in inspect.getmembers(type(client), predicate=inspect.isfunction)
            if not name.startswith("_")
        }

        assert protocol_methods.issubset(service_methods), (
            f"Missing protocol methods: {protocol_methods - service_methods}"
        )

    def test_isinstance_check(self):
        """AsyncNewRelicClient must pass isinstance check against runtime-checkable protocol."""
        client = AsyncNewRelicClient(api_key="test-key", account_id="12345")
        assert isinstance(client, NewRelicClientProtocol), (
            "AsyncNewRelicClient is not recognised as an instance of NewRelicClientProtocol"
        )


class TestExecuteNrql:
    """Tests for the execute_nrql method."""

    @pytest.fixture()
    def client(self):
        """Provide a configured client instance."""
        return AsyncNewRelicClient(api_key="nr-test-api-key", account_id="987654")

    @pytest.mark.asyncio
    async def test_graphql_url_and_method(self, client, mocker):
        """execute_nrql should POST to the GraphQL endpoint."""
        captured = {}

        async def fake_request(url, method, **kwargs):
            captured["url"] = url
            captured["method"] = method
            captured["headers"] = kwargs.get("headers", {})
            captured["json_data"] = kwargs.get("json_data", {})
            return {
                "status": 200,
                "headers": {},
                "body": _real_orjson_dumps(
                    {
                        "data": {
                            "actor": {
                                "account": {"nrql": {"results": [{"count": 42}]}}
                            }
                        }
                    }
                ),
                "content_type": "application/json",
                "url": url,
            }

        mocker.patch.object(client, "_make_api_request", AsyncMock(side_effect=fake_request))

        await client.execute_nrql("SELECT count(*) FROM Transaction")

        assert captured["url"] == "https://api.newrelic.com/graphql"
        assert captured["method"] == "POST"

    @pytest.mark.asyncio
    async def test_api_key_in_header(self, client, mocker):
        """execute_nrql must pass API-Key header."""
        captured_headers = {}

        async def fake_request(url, method, **kwargs):
            captured_headers.update(kwargs.get("headers", {}))
            return {
                "status": 200,
                "headers": {},
                "body": _real_orjson_dumps(
                    {"data": {"actor": {"account": {"nrql": {"results": []}}}}}
                ),
                "content_type": "application/json",
                "url": url,
            }

        mocker.patch.object(client, "_make_api_request", AsyncMock(side_effect=fake_request))

        await client.execute_nrql("SELECT 1")

        assert "API-Key" in captured_headers, "API-Key header is missing"
        assert captured_headers["API-Key"] == "nr-test-api-key"

    @pytest.mark.asyncio
    async def test_graphql_body_contains_account_id_and_nrql(self, client, mocker):
        """execute_nrql should embed account ID and NRQL string in the GraphQL query."""
        captured_body = {}

        async def fake_request(url, method, **kwargs):
            captured_body.update(kwargs.get("json_data", {}))
            return {
                "status": 200,
                "headers": {},
                "body": _real_orjson_dumps(
                    {"data": {"actor": {"account": {"nrql": {"results": []}}}}}
                ),
                "content_type": "application/json",
                "url": url,
            }

        mocker.patch.object(client, "_make_api_request", AsyncMock(side_effect=fake_request))

        nrql = "SELECT count(*) FROM Transaction"
        await client.execute_nrql(nrql)

        assert "query" in captured_body, "GraphQL payload must contain 'query' key"
        assert "987654" in captured_body["query"], "Account ID must appear in GraphQL query"
        assert nrql in captured_body["query"], "NRQL string must appear in GraphQL query"

    @pytest.mark.asyncio
    async def test_returns_results_list(self, client, mocker):
        """execute_nrql must return the results list from the nested GraphQL response."""
        expected_results = [{"count": 42}, {"count": 7}]

        async def fake_request(url, method, **kwargs):
            return {
                "status": 200,
                "headers": {},
                "body": _real_orjson_dumps(
                    {
                        "data": {
                            "actor": {
                                "account": {"nrql": {"results": expected_results}}
                            }
                        }
                    }
                ),
                "content_type": "application/json",
                "url": url,
            }

        mocker.patch.object(client, "_make_api_request", AsyncMock(side_effect=fake_request))

        result = await client.execute_nrql("SELECT count(*) FROM Transaction")

        assert result == expected_results, "execute_nrql should return the results list verbatim"


class TestExecuteNrqlErrorHandling:
    """Error handling tests for execute_nrql."""

    @pytest.fixture()
    def client(self):
        return AsyncNewRelicClient(api_key="nr-test-api-key", account_id="987654")

    @pytest.mark.asyncio
    async def test_unexpected_structure_returns_empty_list(self, client, mocker):
        """Unexpected response structure should return an empty list, not raise."""

        async def fake_request(url, method, **kwargs):
            return {
                "status": 200,
                "headers": {},
                "body": _real_orjson_dumps({"unexpected": "structure"}),
                "content_type": "application/json",
                "url": url,
            }

        mocker.patch.object(client, "_make_api_request", AsyncMock(side_effect=fake_request))

        result = await client.execute_nrql("SELECT count(*) FROM Transaction")

        assert result == [], "Unexpected response structure must return empty list"

    @pytest.mark.asyncio
    async def test_missing_nrql_key_returns_empty_list(self, client, mocker):
        """Missing 'nrql' key in GraphQL response should return empty list."""

        async def fake_request(url, method, **kwargs):
            return {
                "status": 200,
                "headers": {},
                "body": _real_orjson_dumps(
                    {"data": {"actor": {"account": {}}}}
                ),
                "content_type": "application/json",
                "url": url,
            }

        mocker.patch.object(client, "_make_api_request", AsyncMock(side_effect=fake_request))

        result = await client.execute_nrql("SELECT count(*) FROM Transaction")

        assert result == [], "Missing nrql key must return empty list"

    @pytest.mark.asyncio
    async def test_null_data_returns_empty_list(self, client, mocker):
        """Null data in GraphQL response should return empty list."""

        async def fake_request(url, method, **kwargs):
            return {
                "status": 200,
                "headers": {},
                "body": _real_orjson_dumps({"data": None}),
                "content_type": "application/json",
                "url": url,
            }

        mocker.patch.object(client, "_make_api_request", AsyncMock(side_effect=fake_request))

        result = await client.execute_nrql("SELECT count(*) FROM Transaction")

        assert result == [], "Null data in response must return empty list"


class TestGetActiveAlerts:
    """Tests for get_active_alerts method."""

    @pytest.fixture()
    def client(self):
        return AsyncNewRelicClient(api_key="nr-test-api-key", account_id="987654")

    @pytest.mark.asyncio
    async def test_alerts_url_and_method(self, client, mocker):
        """get_active_alerts should GET from the REST alerts endpoint."""
        captured = {}

        async def fake_request(url, method, **kwargs):
            captured["url"] = url
            captured["method"] = method
            return {
                "status": 200,
                "headers": {},
                "body": _real_orjson_dumps({"violations": []}),
                "content_type": "application/json",
                "url": url,
            }

        mocker.patch.object(client, "_make_api_request", AsyncMock(side_effect=fake_request))

        await client.get_active_alerts()

        assert captured["url"] == "https://api.newrelic.com/v2/alerts_violations.json"
        assert captured["method"] == "GET"

    @pytest.mark.asyncio
    async def test_x_api_key_in_header(self, client, mocker):
        """get_active_alerts must pass X-Api-Key header."""
        captured_headers = {}

        async def fake_request(url, method, **kwargs):
            captured_headers.update(kwargs.get("headers", {}))
            return {
                "status": 200,
                "headers": {},
                "body": _real_orjson_dumps({"violations": []}),
                "content_type": "application/json",
                "url": url,
            }

        mocker.patch.object(client, "_make_api_request", AsyncMock(side_effect=fake_request))

        await client.get_active_alerts()

        assert "X-Api-Key" in captured_headers, "X-Api-Key header is missing"
        assert captured_headers["X-Api-Key"] == "nr-test-api-key"

    @pytest.mark.asyncio
    async def test_only_open_param_is_passed(self, client, mocker):
        """get_active_alerts with only_open=True should pass only_open=true query param."""
        captured_params = {}

        async def fake_request(url, method, **kwargs):
            captured_params.update(kwargs.get("params", {}))
            return {
                "status": 200,
                "headers": {},
                "body": _real_orjson_dumps({"violations": []}),
                "content_type": "application/json",
                "url": url,
            }

        mocker.patch.object(client, "_make_api_request", AsyncMock(side_effect=fake_request))

        await client.get_active_alerts(only_open=True)

        assert captured_params.get("only_open") == "true", (
            "only_open=True must set query param only_open=true"
        )

    @pytest.mark.asyncio
    async def test_only_open_false_omits_param(self, client, mocker):
        """get_active_alerts with only_open=False should not include only_open param."""
        captured_params = {}

        async def fake_request(url, method, **kwargs):
            captured_params.update(kwargs.get("params", {}))
            return {
                "status": 200,
                "headers": {},
                "body": _real_orjson_dumps({"violations": []}),
                "content_type": "application/json",
                "url": url,
            }

        mocker.patch.object(client, "_make_api_request", AsyncMock(side_effect=fake_request))

        await client.get_active_alerts(only_open=False)

        assert "only_open" not in captured_params, (
            "only_open=False must not include only_open query param"
        )

    @pytest.mark.asyncio
    async def test_returns_violations_list(self, client, mocker):
        """get_active_alerts must return the violations list from the response."""
        expected_violations = [
            {"id": 1, "label": "High CPU"},
            {"id": 2, "label": "Memory leak"},
        ]

        async def fake_request(url, method, **kwargs):
            return {
                "status": 200,
                "headers": {},
                "body": _real_orjson_dumps({"violations": expected_violations}),
                "content_type": "application/json",
                "url": url,
            }

        mocker.patch.object(client, "_make_api_request", AsyncMock(side_effect=fake_request))

        result = await client.get_active_alerts()

        assert result == expected_violations, "get_active_alerts must return violations list"

    @pytest.mark.asyncio
    async def test_missing_violations_key_returns_empty_list(self, client, mocker):
        """Response without violations key must return empty list."""

        async def fake_request(url, method, **kwargs):
            return {
                "status": 200,
                "headers": {},
                "body": _real_orjson_dumps({}),
                "content_type": "application/json",
                "url": url,
            }

        mocker.patch.object(client, "_make_api_request", AsyncMock(side_effect=fake_request))

        result = await client.get_active_alerts()

        assert result == [], "Missing violations key must return empty list"


class TestCleanup:
    """Tests for the cleanup method."""

    @pytest.mark.asyncio
    async def test_cleanup_calls_super(self, mocker):
        """cleanup must delegate to AsyncClient.cleanup."""
        client = AsyncNewRelicClient(api_key="test-key", account_id="12345")

        super_cleanup = AsyncMock()
        mocker.patch(
            "packages.core.async_client.AsyncClient.cleanup",
            super_cleanup,
        )

        await client.cleanup()

        super_cleanup.assert_called_once()
