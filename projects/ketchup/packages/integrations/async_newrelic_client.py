"""Async New Relic client for NRQL queries and alert data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import orjson

from packages.core.async_client import AsyncClient
from packages.core.logging import setup_logger

logger = setup_logger(__name__)


@dataclass
class NewRelicConfig:
    """Configuration for New Relic API access."""

    api_key: str
    account_id: str
    graphql_url: str = "https://api.newrelic.com/graphql"
    alerts_url: str = "https://api.newrelic.com/v2/alerts_violations.json"


class AsyncNewRelicClient(AsyncClient[NewRelicConfig, Dict[str, Any]]):
    """Async New Relic client using NRQL via GraphQL and REST alerts API."""

    def __init__(
        self,
        api_key: str,
        account_id: str,
        max_concurrent_requests: int = 5,
        request_timeout: int = 30,
    ) -> None:
        """Initialise the New Relic async client.

        Args:
            api_key: New Relic API key for authentication.
            account_id: New Relic account ID for NRQL queries.
            max_concurrent_requests: Maximum concurrent outbound requests.
            request_timeout: Timeout for individual requests in seconds.
        """
        config = NewRelicConfig(api_key=api_key, account_id=account_id)
        super().__init__(
            config=config,
            max_concurrent_requests=max_concurrent_requests,
            request_timeout=request_timeout,
        )

    async def execute_nrql(self, nrql: str) -> List[Dict[str, Any]]:
        """Execute a NRQL query via New Relic GraphQL API.

        Args:
            nrql: The NRQL query string.

        Returns:
            List of result rows from the query.
        """
        graphql_query = {
            "query": (
                '{ actor { account(id: %s) { nrql(query: "%s") { results } } } }'
                % (self.config.account_id, nrql.replace('"', '\\"'))
            )
        }

        response = await self._make_api_request(
            url=self.config.graphql_url,
            method="POST",
            headers={
                "API-Key": self.config.api_key,
                "Content-Type": "application/json",
            },
            json_data=graphql_query,
        )

        data = orjson.loads(response["body"])

        # Navigate the GraphQL response structure
        try:
            results = data["data"]["actor"]["account"]["nrql"]["results"]
        except (KeyError, TypeError):
            logger.error("Unexpected NRQL response structure: %s", data)
            return []

        return results

    async def get_active_alerts(self, only_open: bool = True) -> List[Dict[str, Any]]:
        """Get active alert violations from New Relic REST API.

        Args:
            only_open: If True, only return open violations.

        Returns:
            List of alert violation dictionaries.
        """
        params: Dict[str, str] = {}
        if only_open:
            params["only_open"] = "true"

        response = await self._make_api_request(
            url=self.config.alerts_url,
            method="GET",
            headers={"X-Api-Key": self.config.api_key},
            params=params,
        )

        data = orjson.loads(response["body"])
        return data.get("violations", [])

    async def cleanup(self) -> None:
        """Close the HTTP session."""
        await super().cleanup()
