"""
feature_flags.py

Feature flags for configurable features.
"""

import os
from typing import Any, Dict

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class FeatureFlags:
    """Manages feature flags for the application."""

    @staticmethod
    def is_message_analysis_enabled() -> bool:
        """
        Check if message analysis is enabled (legacy).

        Returns:
            True if message analysis is enabled, False otherwise
        """
        value = os.environ.get("ENABLE_MESSAGE_ANALYSIS", "false").lower()
        return value == "true"

    @staticmethod
    def is_status_updater_enabled() -> bool:
        """
        Check if status updater feature is enabled.

        Returns:
            True if status updater is enabled, False otherwise
        """
        value = os.environ.get("KETCHUP_STATUS_UPDATER_FEATURE", "false").lower()
        return value == "true"

    @staticmethod
    def is_status_updater_global() -> bool:
        """
        Check if status updater is enabled globally for all channels.

        Returns:
            True if status updater is enabled globally, False otherwise
        """
        value = os.environ.get("KETCHUP_STATUS_UPDATER_GLOBAL", "false").lower()
        return value == "true"

    @staticmethod
    def is_jira_reporter_enabled() -> bool:
        """
        Check if JIRA reporter feature is enabled.

        Returns:
            True if JIRA reporter is enabled, False otherwise
        """
        value = os.environ.get("KETCHUP_JIRA_REPORTER_FEATURE", "false").lower()
        return value == "true"

    @staticmethod
    def is_jira_reporter_global() -> bool:
        """
        Check if JIRA reporter is enabled globally for all channels.

        Returns:
            True if JIRA reporter is enabled globally, False otherwise
        """
        value = os.environ.get("KETCHUP_JIRA_REPORTER_GLOBAL", "false").lower()
        return value == "true"

    @staticmethod
    def is_trust_endorsement_enabled() -> bool:
        """
        Check if trust endorsement feature is enabled.

        Returns:
            True if trust endorsement is enabled, False otherwise
        """
        value = os.environ.get("KETCHUP_TRUST_ENDORSEMENT_FEATURE", "false").lower()
        return value == "true"

    @staticmethod
    def is_trust_endorsement_global() -> bool:
        """
        Check if trust endorsement is enabled globally for all channels.

        Returns:
            True if trust endorsement is enabled globally, False otherwise
        """
        value = os.environ.get("KETCHUP_TRUST_ENDORSEMENT_GLOBAL", "false").lower()
        return value == "true"

    @staticmethod
    def is_access_request_automation_enabled() -> bool:
        """
        Check if access request automation feature is enabled.

        Returns:
            True if access request automation is enabled, False otherwise
        """
        value = os.environ.get("KETCHUP_ACCESS_REQUEST_AUTOMATION_FEATURE", "false").lower()
        return value == "true"

    @staticmethod
    def is_access_request_automation_global() -> bool:
        """
        Check if access request automation is enabled globally for all users.

        Returns:
            True if access request automation is enabled globally, False otherwise
        """
        value = os.environ.get("KETCHUP_ACCESS_REQUEST_AUTOMATION_GLOBAL", "false").lower()
        return value == "true"

    @staticmethod
    def is_user_join_notifications_enabled() -> bool:
        """
        Check if user join notifications feature is enabled.

        Returns:
            True if user join notifications is enabled, False otherwise
        """
        value = os.environ.get("KETCHUP_USER_JOIN_NOTIFICATIONS_FEATURE", "false").lower()
        return value == "true"

    @staticmethod
    def is_user_join_notifications_global() -> bool:
        """
        Check if user join notifications is enabled globally for all channels.

        Returns:
            True if user join notifications is enabled globally, False otherwise
        """
        value = os.environ.get("KETCHUP_USER_JOIN_NOTIFICATIONS_GLOBAL", "false").lower()
        return value == "true"

    @staticmethod
    def is_keepalive_tuning_enabled() -> bool:
        """
        Check if optimized keep-alive settings are enabled for HTTP connections.

        When enabled, uses extended connection keep-alive timeouts and DNS caching
        to reduce TCP handshake overhead and improve response times by 2-3%.

        Returns:
            True if keep-alive tuning is enabled, False otherwise

        Example:
            >>> os.environ['KETCHUP_KEEPALIVE_ENABLED'] = 'true'
            >>> FeatureFlags.is_keepalive_tuning_enabled()
            True
        """
        value = os.environ.get("KETCHUP_KEEPALIVE_ENABLED", "false").lower()
        return value == "true"

    @staticmethod
    def get_keepalive_timeout() -> int:
        """
        Get the keep-alive timeout in seconds for HTTP connections.

        Returns the duration to keep idle connections alive before closing them.
        Default is 60 seconds (vs aiohttp default of 15 seconds).

        Returns:
            Keep-alive timeout in seconds

        Example:
            >>> os.environ['KETCHUP_KEEPALIVE_TIMEOUT'] = '120'
            >>> FeatureFlags.get_keepalive_timeout()
            120
        """
        return int(os.environ.get("KETCHUP_KEEPALIVE_TIMEOUT", "60"))

    @staticmethod
    def get_dns_cache_ttl() -> int:
        """
        Get the DNS cache TTL (time-to-live) in seconds.

        Returns the duration to cache DNS lookup results before refreshing.
        Default is 300 seconds (5 minutes vs aiohttp default of 10 seconds).
        Longer TTL reduces DNS lookup overhead for stable endpoints.

        Returns:
            DNS cache TTL in seconds

        Example:
            >>> os.environ['KETCHUP_DNS_CACHE_TTL'] = '600'
            >>> FeatureFlags.get_dns_cache_ttl()
            600
        """
        return int(os.environ.get("KETCHUP_DNS_CACHE_TTL", "300"))

    @staticmethod
    def is_httpx_enabled() -> bool:
        """
        Check if httpx is enabled instead of aiohttp.

        When enabled, the application uses httpx.AsyncClient with HTTP/2 support
        for improved performance through connection multiplexing.

        Returns:
            True if httpx is enabled, False otherwise (uses aiohttp)
        """
        value = os.environ.get("KETCHUP_USE_HTTPX", "false").lower()
        return value == "true"

    @staticmethod
    def is_http2_enabled() -> bool:
        """
        Check if HTTP/2 is enabled (requires httpx to be enabled).

        HTTP/2 provides connection multiplexing, header compression, and improved
        performance over HTTP/1.1. Only takes effect when httpx is enabled.

        Returns:
            True if HTTP/2 is enabled, False otherwise
        """
        value = os.environ.get("KETCHUP_HTTP2_ENABLED", "true").lower()
        return value == "true"

    @staticmethod
    def get_httpx_pool_limits() -> int:
        """
        Get max connections for httpx connection pool.

        Controls the maximum number of concurrent connections in the httpx
        connection pool. Higher values allow more concurrent requests but
        consume more resources.

        Returns:
            Maximum number of connections (default: 50)
        """
        value = os.environ.get("KETCHUP_HTTPX_POOL_LIMITS", "50")
        try:
            return int(value)
        except ValueError:
            logger.warning(f"Invalid KETCHUP_HTTPX_POOL_LIMITS value: {value}, using default 50")
            return 50

    @staticmethod
    def is_structured_json_output_enabled() -> bool:
        """
        Check if structured JSON output is enabled for OpenAI responses.

        When enabled, OpenAI returns responses in JSON format instead of prose,
        which improves generation speed by 10-20% (industry benchmark).

        The JSON response contains a 'response_text' field with the complete
        formatted response. This text is extracted and passed to existing
        BlockKit handlers, resulting in identical Slack message output.

        Returns:
            True if JSON output is enabled, False otherwise

        Environment Variable:
            KETCHUP_STRUCTURED_JSON_OUTPUT: Set to 'true' to enable

        Example:
            >>> os.environ['KETCHUP_STRUCTURED_JSON_OUTPUT'] = 'true'
            >>> FeatureFlags.is_structured_json_output_enabled()
            True
        """
        value = os.environ.get("KETCHUP_STRUCTURED_JSON_OUTPUT", "false").lower()
        return value == "true"

    @staticmethod
    def is_chromadb_enabled() -> bool:
        """
        Check if ChromaDB data layer is enabled independently of the agent.

        When enabled, registers ChromaDB foundation services (embeddings, vector store,
        conversation store, realtime ingestor) for use by features like handover summary
        without requiring the full agent chat/RAG stack.

        Returns:
            True if ChromaDB is enabled, False otherwise
        """
        value = os.environ.get("KETCHUP_CHROMADB_ENABLED", "false").lower()
        return value == "true"

    @staticmethod
    def get_all_flags() -> Dict[str, Any]:
        """
        Get all feature flags and their current values.

        Returns:
            Dictionary of all feature flags
        """
        return {
            "message_analysis_enabled": FeatureFlags.is_message_analysis_enabled(),
            "status_updater_enabled": FeatureFlags.is_status_updater_enabled(),
            "status_updater_global": FeatureFlags.is_status_updater_global(),
            "jira_reporter_enabled": FeatureFlags.is_jira_reporter_enabled(),
            "jira_reporter_global": FeatureFlags.is_jira_reporter_global(),
            "trust_endorsement_enabled": FeatureFlags.is_trust_endorsement_enabled(),
            "trust_endorsement_global": FeatureFlags.is_trust_endorsement_global(),
            "access_request_automation_enabled": FeatureFlags.is_access_request_automation_enabled(),
            "access_request_automation_global": FeatureFlags.is_access_request_automation_global(),
            "user_join_notifications_enabled": FeatureFlags.is_user_join_notifications_enabled(),
            "user_join_notifications_global": FeatureFlags.is_user_join_notifications_global(),
            "keepalive_tuning_enabled": FeatureFlags.is_keepalive_tuning_enabled(),
            "keepalive_timeout": FeatureFlags.get_keepalive_timeout(),
            "dns_cache_ttl": FeatureFlags.get_dns_cache_ttl(),
            "httpx_enabled": FeatureFlags.is_httpx_enabled(),
            "http2_enabled": FeatureFlags.is_http2_enabled(),
            "httpx_pool_limits": FeatureFlags.get_httpx_pool_limits(),
            "structured_json_output_enabled": FeatureFlags.is_structured_json_output_enabled(),
            "chromadb_enabled": FeatureFlags.is_chromadb_enabled(),
            # async_mcp_enabled removed - always True (consolidated to AsyncMCPClient)
        }
