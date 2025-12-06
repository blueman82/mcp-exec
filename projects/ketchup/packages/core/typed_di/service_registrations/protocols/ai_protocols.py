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
    "AIEmbeddingServiceProtocol",
    "AISimilarityServiceProtocol",
    "AIClassificationServiceProtocol",
    "AISummarizationServiceProtocol",
    "AITranslationServiceProtocol",
    "AISentimentServiceProtocol",
    "AIKeywordServiceProtocol",
    "AIConversationServiceProtocol",
    "AIPersonalityServiceProtocol",
    "AIAnalyticsServiceProtocol",
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
class AIEmbeddingServiceProtocol(Protocol):
    """Protocol for text embedding generation."""

    async def generate_embedding(self, text: str) -> list: ...
    async def batch_embeddings(self, texts: list) -> list: ...
    async def similarity_search(self, query_embedding: list, embeddings: list) -> list: ...


@runtime_checkable
class AISimilarityServiceProtocol(Protocol):
    """Protocol for semantic similarity calculation."""

    async def calculate_similarity(self, text1: str, text2: str) -> float: ...
    async def find_similar_texts(self, query: str, corpus: list) -> list: ...
    async def cluster_texts(self, texts: list) -> dict: ...


@runtime_checkable
class AIClassificationServiceProtocol(Protocol):
    """Protocol for content classification."""

    async def classify_text(self, text: str, categories: list) -> str: ...
    async def detect_intent(self, text: str) -> str: ...
    async def categorize_content(self, content: dict) -> dict: ...


@runtime_checkable
class AISummarizationServiceProtocol(Protocol):
    """Protocol for content summarization."""

    async def summarize_text(self, text: str, max_length: int = 100) -> str: ...
    async def extract_key_points(self, text: str) -> list: ...
    async def generate_abstract(self, content: dict) -> str: ...


@runtime_checkable
class AITranslationServiceProtocol(Protocol):
    """Protocol for multi-language translation."""

    async def translate_text(self, text: str, target_lang: str) -> str: ...
    async def detect_language(self, text: str) -> str: ...
    async def batch_translate(self, texts: list, target_lang: str) -> list: ...


@runtime_checkable
class AISentimentServiceProtocol(Protocol):
    """Protocol for sentiment analysis."""

    async def analyze_sentiment(self, text: str) -> dict: ...
    async def batch_sentiment_analysis(self, texts: list) -> list: ...
    async def get_emotion_analysis(self, text: str) -> dict: ...


@runtime_checkable
class AIKeywordServiceProtocol(Protocol):
    """Protocol for keyword extraction."""

    async def extract_keywords(self, text: str, max_keywords: int = 10) -> list: ...
    async def generate_tags(self, content: dict) -> list: ...
    async def analyze_topics(self, text: str) -> dict: ...


@runtime_checkable
class AIConversationServiceProtocol(Protocol):
    """Protocol for conversation flow management."""

    async def start_conversation(self, user_id: str) -> dict: ...
    async def add_message(self, conversation_id: str, message: dict): ...
    async def get_conversation_history(self, conversation_id: str) -> list: ...


@runtime_checkable
class AIPersonalityServiceProtocol(Protocol):
    """Protocol for AI personality configuration."""

    async def set_personality(self, personality_config: dict): ...
    async def get_personality_prompt(self, personality_id: str) -> str: ...
    async def list_personalities(self) -> list: ...


@runtime_checkable
class AIAnalyticsServiceProtocol(Protocol):
    """Protocol for AI usage analytics."""

    async def track_usage(self, usage_data: dict): ...
    async def generate_usage_report(self, period: str) -> dict: ...
    async def get_cost_breakdown(self, period: str) -> dict: ...


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
