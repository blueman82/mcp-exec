"""
AI Service Protocols

Protocol definitions for AI-related services including Azure OpenAI integration,
prompt management, token counting, cost calculation, embeddings, and analytics.
"""

from typing import Protocol, runtime_checkable

__all__ = [
    "ApiExecutorProtocol",
    "MessagePreparerProtocol",
    "AzureConfigProtocol",
    "AIPromptTemplateServiceProtocol",
    "AIContextWindowServiceProtocol",
    "AITokenCountServiceProtocol",
    "AICostCalculationServiceProtocol",
    "AIModelSelectionServiceProtocol",
    "AIResponseCacheServiceProtocol",
    "AIStreamingServiceProtocol",
    "AIBatchProcessingServiceProtocol",
    "AIRateLimitServiceProtocol",
    "AIRetryServiceProtocol",
    "AIErrorHandlingServiceProtocol",
    "AIPerformanceMonitoringServiceProtocol",
]


@runtime_checkable
class ApiExecutorProtocol(Protocol):
    """Protocol for AI API execution operations."""

    pass


@runtime_checkable
class MessagePreparerProtocol(Protocol):
    """Protocol for message preparation operations."""

    pass


@runtime_checkable
class AzureConfigProtocol(Protocol):
    """Protocol for Azure configuration."""

    pass


@runtime_checkable
class AIPromptTemplateServiceProtocol(Protocol):
    """Protocol for AI prompt template management."""

    async def get_template(self, template_id: str) -> dict: ...
    async def save_template(self, template_id: str, content: str) -> bool: ...
    async def list_templates(self) -> list: ...


@runtime_checkable
class AIContextWindowServiceProtocol(Protocol):
    """Protocol for AI context window optimization."""

    async def optimize_context(self, content: str) -> str: ...
    async def estimate_tokens(self, content: str) -> int: ...
    async def compress_context(self, content: str) -> str: ...


@runtime_checkable
class AITokenCountServiceProtocol(Protocol):
    """Protocol for AI token counting."""

    async def count_tokens(self, text: str) -> int: ...
    async def estimate_cost(self, token_count: int) -> float: ...
    async def validate_limits(self, token_count: int) -> bool: ...


@runtime_checkable
class AICostCalculationServiceProtocol(Protocol):
    """Protocol for AI usage cost calculation."""

    async def calculate_cost(self, tokens: int, model: str) -> float: ...
    async def get_pricing(self, model: str) -> dict: ...
    async def estimate_request_cost(self, request: dict) -> float: ...


@runtime_checkable
class AIModelSelectionServiceProtocol(Protocol):
    """Protocol for AI model selection optimization."""

    async def select_model(self, task_type: str) -> str: ...
    async def get_available_models(self) -> list: ...
    async def optimize_model_for_task(self, task: dict) -> str: ...


@runtime_checkable
class AIResponseCacheServiceProtocol(Protocol):
    """Protocol for AI response caching."""

    async def get_cached_response(self, key: str): ...
    async def cache_response(self, key: str, response: dict): ...
    async def clear_cache(self): ...


@runtime_checkable
class AIStreamingServiceProtocol(Protocol):
    """Protocol for AI streaming response handling."""

    async def start_stream(self, request: dict) -> dict: ...
    async def process_stream_chunk(self, chunk: dict) -> dict: ...
    async def end_stream(self, stream_id: str) -> bool: ...


@runtime_checkable
class AIBatchProcessingServiceProtocol(Protocol):
    """Protocol for AI batch request processing."""

    async def submit_batch(self, requests: list) -> dict: ...
    async def get_batch_status(self, batch_id: str) -> str: ...
    async def get_batch_results(self, batch_id: str) -> list: ...


@runtime_checkable
class AIRateLimitServiceProtocol(Protocol):
    """Protocol for AI API rate limiting."""

    async def check_rate_limit(self, api_key: str) -> bool: ...
    async def update_usage(self, api_key: str, tokens: int): ...
    async def get_remaining_quota(self, api_key: str) -> int: ...


@runtime_checkable
class AIRetryServiceProtocol(Protocol):
    """Protocol for AI request retry logic."""

    async def retry_request(self, request: dict, max_retries: int = 3) -> dict: ...
    async def calculate_backoff(self, attempt: int) -> float: ...
    async def should_retry(self, error: dict) -> bool: ...


@runtime_checkable
class AIErrorHandlingServiceProtocol(Protocol):
    """Protocol for AI error handling service operations."""

    async def handle_error(self, error: Exception) -> dict: ...
    async def log_error(self, error: Exception, context: dict) -> None: ...
    async def recover_from_error(self, error: Exception) -> bool: ...


@runtime_checkable
class AIPerformanceMonitoringServiceProtocol(Protocol):
    """Protocol for AI performance monitoring service operations."""

    async def track_performance(self, operation: str, duration: float) -> None: ...
    async def get_metrics(self) -> dict: ...
    async def log_performance(self, metrics: dict) -> None: ...
