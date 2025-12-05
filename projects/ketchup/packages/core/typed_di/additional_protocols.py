# Additional protocols for new TypedDI service registrations
# Manual protocol definitions for services beyond the generated protocol files

from contextlib import asynccontextmanager
from typing import Any, AsyncContextManager, Dict, List, Optional, Protocol


# Monitoring and metrics protocols
class AccessRequestMonitorProtocol(Protocol):
    """Protocol for AccessRequestMonitor service."""

    def record_access_request_error(self, error_type: str, details: Dict[str, Any]) -> None: ...

    def record_access_request_success(self, action: str, details: Dict[str, Any]) -> None: ...

    async def send_alert_if_needed(self, metric_type: str, count: int) -> None: ...

    def get_hourly_stats(self) -> Dict[str, int]: ...


class DistributedLockProtocol(Protocol):
    """Protocol for DistributedLock service."""

    @asynccontextmanager
    async def acquire_lock(
        self, resource_id: str, timeout_seconds: Optional[int] = None
    ) -> AsyncContextManager[bool]: ...

    async def is_locked(self, resource_id: str) -> bool: ...

    async def release_lock(self, resource_id: str) -> bool: ...


# Slack command and routing protocols
class CommandRouterProtocol(Protocol):
    """Protocol for CommandRouter service."""

    async def route_command(self, command_data: Dict[str, Any]) -> Dict[str, Any]: ...

    def register_handler(self, command_type: str, handler: Any) -> None: ...

    def get_supported_commands(self) -> List[str]: ...


class BaseCommandHandlerProtocol(Protocol):
    """Protocol for BaseCommandHandler service."""

    async def handle_command(self, command_params: Any) -> Dict[str, Any]: ...

    def get_command_type(self) -> str: ...

    async def validate_command(self, command_data: Dict[str, Any]) -> bool: ...


class SlackMessageFormatterProtocol(Protocol):
    """Protocol for SlackMessageFormatter service."""

    def format_channel_summary(self, channel_data: Dict[str, Any]) -> str: ...

    def format_user_list(self, users: List[Dict[str, Any]]) -> str: ...

    def format_error_message(self, error: str, context: Dict[str, Any]) -> str: ...


# Configuration and feature protocols
class FeatureFlagsProtocol(Protocol):
    """Protocol for FeatureFlags service."""

    def is_enabled(self, feature_name: str) -> bool: ...

    def get_feature_value(self, feature_name: str, default: Any = None) -> Any: ...

    def refresh_flags(self) -> None: ...


class CodeQualityValidatorProtocol(Protocol):
    """Protocol for CodeQualityValidator service."""

    async def validate_code(self, code: str, language: str) -> Dict[str, Any]: ...

    def get_supported_languages(self) -> List[str]: ...

    async def check_style(self, code: str, language: str) -> List[Dict[str, Any]]: ...


# AI and token management protocols
class TokenManagerProtocol(Protocol):
    """Protocol for TokenManager service."""

    def count_tokens(self, text: str, model: str) -> int: ...

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float: ...

    def get_token_limits(self, model: str) -> Dict[str, int]: ...


# Infrastructure and performance protocols
class TypedServiceRegistryProtocol(Protocol):
    """Protocol for TypedServiceRegistry service."""

    def register_service(
        self, service_type: type, instance: Any, qualifier: Optional[str] = None
    ) -> None: ...

    def get_service(self, service_type: type, qualifier: Optional[str] = None) -> Any: ...

    def has_service(self, service_type: type, qualifier: Optional[str] = None) -> bool: ...

    def unregister_service(self, service_type: type, qualifier: Optional[str] = None) -> bool: ...


class PerformanceMonitorProtocol(Protocol):
    """Protocol for PerformanceMonitor service."""

    def start_timing(self, operation_name: str) -> str: ...

    def end_timing(self, timing_id: str) -> float: ...

    def record_metric(
        self, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None
    ) -> None: ...

    def get_metrics_summary(self) -> Dict[str, Any]: ...


class BackoffStrategyProtocol(Protocol):
    """Protocol for BackoffStrategy service."""

    def next_delay(self, attempt: int) -> float: ...

    def reset(self) -> None: ...

    def should_retry(self, attempt: int, max_attempts: int) -> bool: ...


class ExponentialBackoffStrategyProtocol(BackoffStrategyProtocol):
    """Protocol for ExponentialBackoffStrategy service."""

    def set_backoff_factor(self, factor: float) -> None: ...

    def set_max_delay(self, max_delay: float) -> None: ...


# Slack operations protocols
class ChannelEligibilityServiceProtocol(Protocol):
    """Protocol for ChannelEligibilityService."""

    async def is_channel_eligible(self, channel_id: str, operation: str) -> bool: ...

    async def get_eligibility_reason(self, channel_id: str, operation: str) -> str: ...

    def get_supported_operations(self) -> List[str]: ...


class BatchSizeManagerProtocol(Protocol):
    """Protocol for BatchSizeManager service."""

    def get_batch_size(self, operation_type: str) -> int: ...

    def adjust_batch_size(self, operation_type: str, performance_data: Dict[str, Any]) -> None: ...

    def get_optimal_batch_size(self, operation_type: str, data_size: int) -> int: ...


class EventProcessorProtocol(Protocol):
    """Protocol for EventProcessor service."""

    async def process_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]: ...

    def get_supported_event_types(self) -> List[str]: ...

    def register_event_handler(self, event_type: str, handler: Any) -> None: ...


class SlackEventHandlerProtocol(Protocol):
    """Protocol for SlackEventHandler service."""

    async def handle_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]: ...

    async def handle_channel_event(self, event_data: Dict[str, Any]) -> None: ...

    async def handle_user_event(self, event_data: Dict[str, Any]) -> None: ...


# Slack command handlers
class SlackListCommandProtocol(Protocol):
    """Protocol for SlackListCommand service."""

    async def handle_list_command(self, command_params: Any) -> Dict[str, Any]: ...

    async def generate_channel_list(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]: ...


class SlackQueryHandlerProtocol(Protocol):
    """Protocol for SlackQueryHandler service."""

    async def handle_query(self, query_params: Any) -> Dict[str, Any]: ...

    async def search_channels(
        self, search_term: str, filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]: ...


class SlackSummaryHandlerProtocol(Protocol):
    """Protocol for SlackSummaryHandler service."""

    async def handle_summary_command(self, command_params: Any) -> Dict[str, Any]: ...

    async def generate_summary(self, channel_id: str, summary_type: str) -> Dict[str, Any]: ...


class SlackReportsProtocol(Protocol):
    """Protocol for SlackReports service."""

    async def handle_report_command(self, command_params: Any) -> Dict[str, Any]: ...

    async def generate_status_report(self, report_type: str) -> Dict[str, Any]: ...

    async def get_available_reports(self) -> List[str]: ...


class AccessCommandProtocol(Protocol):
    """Protocol for AccessCommand service."""

    async def handle_access_command(self, command_params: Any) -> Dict[str, Any]: ...

    async def process_access_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]: ...

    async def check_access_permissions(self, user_id: str, channel_id: str) -> bool: ...
