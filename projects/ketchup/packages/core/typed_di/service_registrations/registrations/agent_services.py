"""
Agent Service Registrations.

Registers all Ketchup Agent services via ServiceSpec for:
- Embeddings client (Azure OpenAI ada-002)
- Vector store (ChromaDB)
- Conversation store (DynamoDB)
- RAG pipeline (retriever, context builder, engine)
- Ingestion (real-time + backfill)
- Slack interface (handler, thread manager, isolation filter)

All services are registered as singletons and gated behind
the KETCHUP_AGENT_ENABLED feature flag at runtime.
"""

import os
from typing import List

from packages.core.logging import setup_logger
from packages.core.typed_di.service_registrations.manager import (
    ServiceRegistrationManager,
)
from packages.core.typed_di.service_spec import ServiceSpec, register_from_specs

logger = setup_logger(__name__)


def _get_agent_specs() -> List[ServiceSpec]:
    """Build the list of agent ServiceSpecs."""
    # Import concrete implementations
    from packages.agent.conversation.store import ConversationStore
    from packages.agent.embeddings.azure_embeddings_client import (
        AzureEmbeddingsClient,
    )
    from packages.agent.embeddings.vector_store import ChromaVectorStore
    from packages.agent.ingestion.backfill_ingestor import BackfillIngestor
    from packages.agent.ingestion.jira_backfill import JiraBackfillIngestor
    from packages.agent.ingestion.realtime_ingestor import RealtimeIngestor
    from packages.agent.rag.context_builder import ContextBuilder
    from packages.agent.rag.engine import AgentEngine
    from packages.agent.rag.retriever import Retriever
    from packages.agent.slack.handler import AgentSlackHandler
    from packages.agent.slack.isolation import AgentThreadFilter
    from packages.agent.slack.thread_manager import AgentThreadManager
    from packages.core.typed_di.service_registrations.protocols import (
        AgentBackfillIngestorProtocol,
        AgentContextBuilderProtocol,
        AgentConversationStoreProtocol,
        AgentEmbeddingsClientProtocol,
        AgentEngineProtocol,
        AgentJiraBackfillIngestorProtocol,
        AgentRealtimeIngestorProtocol,
        AgentRetrieverProtocol,
        AgentSlackHandlerProtocol,
        AgentThreadFilterProtocol,
        AgentThreadManagerProtocol,
        AgentVectorStoreProtocol,
        DynamoDBAsyncClientProtocol,
        JIRADataExtractorProtocol,
        SecretsManagerProtocol,
        SlackPostingHandlerProtocol,
    )
    from packages.core.typed_di.service_registrations.protocols.ai_protocols import (
        ApiExecutorProtocol,
    )

    return [
        # ── Layer 1: No agent deps (foundation) ──────────────────
        ServiceSpec(
            protocol=AgentEmbeddingsClientProtocol,
            concrete=AzureEmbeddingsClient,
            deps={"secrets_manager": SecretsManagerProtocol},
        ),
        ServiceSpec(
            protocol=AgentVectorStoreProtocol,
            concrete=ChromaVectorStore,
            deps={},
        ),
        ServiceSpec(
            protocol=AgentConversationStoreProtocol,
            concrete=ConversationStore,
            deps={"dynamodb_client": DynamoDBAsyncClientProtocol},
        ),
        # ── Layer 2: Depends on Layer 1 ──────────────────────────
        ServiceSpec(
            protocol=AgentRetrieverProtocol,
            concrete=Retriever,
            deps={
                "embeddings_client": AgentEmbeddingsClientProtocol,
                "vector_store": AgentVectorStoreProtocol,
            },
        ),
        ServiceSpec(
            protocol=AgentContextBuilderProtocol,
            concrete=ContextBuilder,
            deps={"conversation_store": AgentConversationStoreProtocol},
        ),
        ServiceSpec(
            protocol=AgentThreadFilterProtocol,
            concrete=AgentThreadFilter,
            deps={"conversation_store": AgentConversationStoreProtocol},
        ),
        ServiceSpec(
            protocol=AgentThreadManagerProtocol,
            concrete=AgentThreadManager,
            deps={
                "conversation_store": AgentConversationStoreProtocol,
                "posting_handler": SlackPostingHandlerProtocol,
            },
        ),
        # ── Layer 2b: Ingestion (depends on Layer 1 + bot_user_id from secrets) ──
        ServiceSpec(
            protocol=AgentRealtimeIngestorProtocol,
            concrete=RealtimeIngestor,
            deps={
                "embeddings_client": AgentEmbeddingsClientProtocol,
                "vector_store": AgentVectorStoreProtocol,
                "conversation_store": AgentConversationStoreProtocol,
                "secrets_manager": SecretsManagerProtocol,
            },
            factory=_create_realtime_ingestor,
        ),
        ServiceSpec(
            protocol=AgentJiraBackfillIngestorProtocol,
            concrete=JiraBackfillIngestor,
            deps={
                "embeddings_client": AgentEmbeddingsClientProtocol,
                "vector_store": AgentVectorStoreProtocol,
                "jira_data_extractor": (JIRADataExtractorProtocol, True),
            },
        ),
        ServiceSpec(
            protocol=AgentBackfillIngestorProtocol,
            concrete=BackfillIngestor,
            deps={
                "embeddings_client": AgentEmbeddingsClientProtocol,
                "vector_store": AgentVectorStoreProtocol,
                "conversation_store": AgentConversationStoreProtocol,
                "posting_handler": SlackPostingHandlerProtocol,
                "secrets_manager": SecretsManagerProtocol,
                "jira_backfill_ingestor": (AgentJiraBackfillIngestorProtocol, True),
            },
            factory=_create_backfill_ingestor,
        ),
        # ── Layer 3: Agent Engine (depends on retriever + context builder) ──
        # AgentEngine has a custom factory because it needs the system prompt
        ServiceSpec(
            protocol=AgentEngineProtocol,
            concrete=AgentEngine,
            deps={
                "retriever": AgentRetrieverProtocol,
                "context_builder": AgentContextBuilderProtocol,
                "conversation_store": AgentConversationStoreProtocol,
                "api_executor": ApiExecutorProtocol,
            },
            factory=_create_agent_engine,
        ),
        # ── Layer 4: Slack Handler (depends on engine + thread manager + backfill) ──
        ServiceSpec(
            protocol=AgentSlackHandlerProtocol,
            concrete=AgentSlackHandler,
            deps={
                "agent_engine": AgentEngineProtocol,
                "conversation_store": AgentConversationStoreProtocol,
                "thread_manager": AgentThreadManagerProtocol,
                "posting_handler": SlackPostingHandlerProtocol,
                "secrets_manager": SecretsManagerProtocol,
                "backfill_ingestor": (AgentBackfillIngestorProtocol, True),
            },
        ),
    ]


async def _create_realtime_ingestor(resolver):
    """Custom factory for RealtimeIngestor — resolves bot_user_id from secrets."""
    from packages.agent.ingestion.realtime_ingestor import RealtimeIngestor
    from packages.core.typed_di.service_registrations.protocols import (
        AgentConversationStoreProtocol,
        AgentEmbeddingsClientProtocol,
        AgentVectorStoreProtocol,
        SecretsManagerProtocol,
    )

    embeddings_client = await resolver.aget(AgentEmbeddingsClientProtocol)
    vector_store = await resolver.aget(AgentVectorStoreProtocol)
    conversation_store = await resolver.aget(AgentConversationStoreProtocol)
    secrets_manager = await resolver.aget(SecretsManagerProtocol)
    bot_user_id = await secrets_manager.get_bot_slack_user_id_async()

    return RealtimeIngestor(
        embeddings_client=embeddings_client,
        vector_store=vector_store,
        conversation_store=conversation_store,
        bot_user_id=bot_user_id,
    )


async def _create_backfill_ingestor(resolver):
    """Custom factory for BackfillIngestor — resolves bot_user_id from secrets."""
    from packages.agent.ingestion.backfill_ingestor import BackfillIngestor
    from packages.core.typed_di.service_registrations.protocols import (
        AgentConversationStoreProtocol,
        AgentEmbeddingsClientProtocol,
        AgentJiraBackfillIngestorProtocol,
        AgentVectorStoreProtocol,
        SecretsManagerProtocol,
        SlackPostingHandlerProtocol,
    )

    embeddings_client = await resolver.aget(AgentEmbeddingsClientProtocol)
    vector_store = await resolver.aget(AgentVectorStoreProtocol)
    conversation_store = await resolver.aget(AgentConversationStoreProtocol)
    posting_handler = await resolver.aget(SlackPostingHandlerProtocol)
    secrets_manager = await resolver.aget(SecretsManagerProtocol)
    bot_user_id = await secrets_manager.get_bot_slack_user_id_async()

    # JIRA backfill is optional — degrades gracefully if unavailable
    jira_backfill = None
    try:
        jira_backfill = await resolver.aget(AgentJiraBackfillIngestorProtocol)
    except Exception:
        logger.info("JiraBackfillIngestor not available — JIRA backfill disabled")

    return BackfillIngestor(
        embeddings_client=embeddings_client,
        vector_store=vector_store,
        conversation_store=conversation_store,
        posting_handler=posting_handler,
        bot_user_id=bot_user_id,
        jira_backfill_ingestor=jira_backfill,
    )


async def _create_agent_engine(resolver):
    """Custom factory for AgentEngine — injects system prompt."""
    from packages.agent.prompts.agent_system import AGENT_SYSTEM_PROMPT
    from packages.agent.rag.engine import AgentEngine
    from packages.core.typed_di.service_registrations.protocols import (
        AgentContextBuilderProtocol,
        AgentConversationStoreProtocol,
        AgentRetrieverProtocol,
    )
    from packages.core.typed_di.service_registrations.protocols.ai_protocols import (
        ApiExecutorProtocol,
    )

    logger.info("Creating AgentEngine instance via TypedDI (custom factory)")

    retriever = await resolver.aget(AgentRetrieverProtocol)
    context_builder = await resolver.aget(AgentContextBuilderProtocol)
    conversation_store = await resolver.aget(AgentConversationStoreProtocol)
    api_executor = await resolver.aget(ApiExecutorProtocol)

    return AgentEngine(
        retriever=retriever,
        context_builder=context_builder,
        conversation_store=conversation_store,
        api_executor=api_executor,
        system_prompt=AGENT_SYSTEM_PROMPT,
    )


def register_agent_services(manager: ServiceRegistrationManager) -> int:
    """Register all agent services if the feature is enabled.

    Services are always registered (for DI graph completeness) but
    gated at runtime by the KETCHUP_AGENT_ENABLED feature flag.

    Args:
        manager: The ServiceRegistrationManager instance.

    Returns:
        Number of services registered.
    """
    enabled = os.environ.get("KETCHUP_AGENT_ENABLED", "false").lower() == "true"

    if not enabled:
        logger.info("Agent feature disabled — skipping agent service registration")
        return 0

    specs = _get_agent_specs()
    count = register_from_specs(manager, specs, "agent_services")
    logger.info("Registered %d agent services", count)
    return count
