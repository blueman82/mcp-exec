"""
Agent Service Registrations.

Two-tier architecture for managing ChromaDB and Agent services:

Layer 1 - ChromaDB Foundation (gated by KETCHUP_CHROMADB_ENABLED or KETCHUP_AGENT_ENABLED):
- Embeddings client (Azure OpenAI ada-002)
- Vector store (ChromaDB)
- Conversation store (DynamoDB)
- Realtime ingestor (data ingestion during conversations)

Layer 2 - Agent Chat/RAG (gated by KETCHUP_AGENT_ENABLED):
- Retriever, context builder, engine (RAG pipeline)
- JIRA backfill, backfill ingestor (historical data ingestion)
- Slack handler, thread manager, thread filter (Slack interface)

The two-tier split allows features like handover summaries to use
ChromaDB foundation services independently of the agent chat feature.
All services are registered as singletons.
"""

import os

from packages.core.logging import setup_logger
from packages.core.typed_di.service_registrations.manager import (
    ServiceRegistrationManager,
)
from packages.core.typed_di.service_spec import ServiceSpec, register_from_specs

logger = setup_logger(__name__)


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


def _get_chromadb_specs() -> list[ServiceSpec]:
    """Build the list of ChromaDB foundation ServiceSpecs.

    These form the data layer used by both agent chat and handover summary features:
    - Layer 1: Embeddings client, vector store, conversation store (foundation)
    - Layer 1b: Realtime ingestor (depends only on foundation + secrets)
    """
    # Import concrete implementations
    from packages.agent.conversation.store import ConversationStore
    from packages.agent.embeddings.azure_embeddings_client import (
        AzureEmbeddingsClient,
    )
    from packages.agent.embeddings.vector_store import ChromaVectorStore
    from packages.agent.ingestion.realtime_ingestor import RealtimeIngestor
    from packages.core.typed_di.service_registrations.protocols import (
        AgentConversationStoreProtocol,
        AgentEmbeddingsClientProtocol,
        AgentRealtimeIngestorProtocol,
        AgentVectorStoreProtocol,
        DynamoDBAsyncClientProtocol,
        SecretsManagerProtocol,
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
        # ── Layer 1b: Realtime ingestor (depends on Layer 1 + bot_user_id from secrets) ──
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
    ]


def _get_agent_specs() -> list[ServiceSpec]:
    """Build the list of agent chat/RAG ServiceSpecs.

    These depend on ChromaDB foundation services and form the agent feature:
    - Layer 2: Retriever, context builder, thread manager, thread filter
    - Layer 2b: JIRA backfill, backfill ingestor
    - Layer 3: Agent engine
    - Layer 4: Slack handler
    """
    # Import concrete implementations
    from packages.agent.ingestion.backfill_ingestor import BackfillIngestor
    from packages.agent.ingestion.jira_backfill import JiraBackfillIngestor
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
        AgentRetrieverProtocol,
        AgentSlackHandlerProtocol,
        AgentThreadFilterProtocol,
        AgentThreadManagerProtocol,
        AgentVectorStoreProtocol,
        JIRADataExtractorProtocol,
        SecretsManagerProtocol,
        SlackPostingHandlerProtocol,
    )
    from packages.core.typed_di.service_registrations.protocols.ai_protocols import (
        ApiExecutorProtocol,
    )

    return [
        # ── Layer 2: Depends on ChromaDB foundation ──────────────────
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
        # ── Layer 2b: Backfill ingestion ──────────────────────────────
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


async def _create_rca_tool_executor(resolver):
    """Custom factory for RCAToolExecutor — resolves retriever, MCP client, NewRelic client."""
    from packages.agent.rca.tool_executor import RCAToolExecutor
    from packages.core.typed_di.service_registrations.protocols.agent_protocols import (
        AgentRetrieverProtocol,
        RCAToolExecutorProtocol,  # noqa: F401 — imported for type reference
    )
    from packages.core.typed_di.service_registrations.protocols.mcp_protocols import (
        MCPAsyncClientProtocol,
    )
    from packages.core.typed_di.service_registrations.protocols.monitoring_protocols import (
        NewRelicClientProtocol,
    )

    retriever = await resolver.aget(AgentRetrieverProtocol)
    mcp_client = await resolver.aget(MCPAsyncClientProtocol)
    newrelic_client = await resolver.aget(NewRelicClientProtocol)

    return RCAToolExecutor(
        retriever=retriever,
        mcp_client=mcp_client,
        newrelic_client=newrelic_client,
    )


async def _create_agent_engine(resolver):
    """Custom factory for AgentEngine — injects system prompt and optional RCA tools."""
    import os

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

    rca_enabled = os.environ.get("KETCHUP_RCA_HISTORIAN_ENABLED", "false").lower() == "true"

    if rca_enabled:
        from packages.agent.prompts.rca_system import RCA_SYSTEM_PROMPT
        from packages.agent.rca.tools import RCA_TOOLS
        from packages.core.typed_di.service_registrations.protocols.agent_protocols import (
            RCAToolExecutorProtocol,
        )

        tool_executor = await resolver.aget(RCAToolExecutorProtocol)
        system_prompt = RCA_SYSTEM_PROMPT
        tools = RCA_TOOLS
    else:
        from packages.agent.prompts.agent_system import AGENT_SYSTEM_PROMPT

        system_prompt = AGENT_SYSTEM_PROMPT
        tools = None
        tool_executor = None

    return AgentEngine(
        retriever=retriever,
        context_builder=context_builder,
        conversation_store=conversation_store,
        api_executor=api_executor,
        system_prompt=system_prompt,
        tools=tools,
        tool_executor=tool_executor,
    )


def register_chromadb_services(manager: ServiceRegistrationManager) -> int:
    """Register ChromaDB foundation services if KETCHUP_CHROMADB_ENABLED or KETCHUP_AGENT_ENABLED.

    Registers: embeddings client, vector store, conversation store, and realtime ingestor.
    These form the data layer used by both the agent chat and handover summary features.

    Args:
        manager: The ServiceRegistrationManager instance.

    Returns:
        Number of services registered.
    """
    chromadb_enabled = os.environ.get("KETCHUP_CHROMADB_ENABLED", "false").lower() == "true"
    agent_enabled = os.environ.get("KETCHUP_AGENT_ENABLED", "false").lower() == "true"

    if not chromadb_enabled and not agent_enabled:
        logger.info("ChromaDB disabled — skipping chromadb service registration")
        return 0

    specs = _get_chromadb_specs()
    count = register_from_specs(manager, specs, "chromadb_services")
    logger.info("Registered %d chromadb services", count)
    return count


async def _create_newrelic_client(resolver):
    """Custom factory for AsyncNewRelicClient — resolves secrets."""
    # Resolve SecretsManagerProtocol via local import to avoid barrel import
    from packages.core.typed_di.service_registrations.protocols.core_protocols import (
        SecretsManagerProtocol,
    )
    from packages.integrations.async_newrelic_client import AsyncNewRelicClient

    secrets_manager = await resolver.aget(SecretsManagerProtocol)
    api_key = await secrets_manager.get_new_relic_api_key()
    account_id = await secrets_manager.get_new_relic_account_id()

    client = AsyncNewRelicClient(api_key=api_key, account_id=account_id)
    await client.setup()
    return client


def register_rca_services(manager: ServiceRegistrationManager) -> int:
    """Register RCA Historian services if the feature is enabled.

    Currently registers: NewRelicClient
    Phase 3 will add: RCAToolExecutor

    Args:
        manager: The ServiceRegistrationManager instance.

    Returns:
        Number of services registered.
    """
    enabled = os.environ.get("KETCHUP_RCA_HISTORIAN_ENABLED", "false").lower() == "true"

    if not enabled:
        logger.info("RCA Historian disabled — skipping RCA service registration")
        return 0

    from packages.core.typed_di.service_registrations.protocols.monitoring_protocols import (
        NewRelicClientProtocol,
    )
    from packages.integrations.async_newrelic_client import AsyncNewRelicClient

    specs = [
        ServiceSpec(
            protocol=NewRelicClientProtocol,
            concrete=AsyncNewRelicClient,
            deps={},
            factory=_create_newrelic_client,
        ),
    ]

    count = register_from_specs(manager, specs, "rca_services")
    logger.info("Registered %d RCA services", count)
    return count


def register_agent_services(manager: ServiceRegistrationManager) -> int:
    """Register agent chat/RAG services if the feature is enabled.

    Assumes chromadb foundation services are already registered via
    register_chromadb_services() in the role maps.

    Args:
        manager: The ServiceRegistrationManager instance.

    Returns:
        Number of services registered.
    """
    enabled = os.environ.get("KETCHUP_AGENT_ENABLED", "false").lower() == "true"

    if not enabled:
        logger.info("Agent feature disabled — skipping agent chat service registration")
        return 0

    specs = _get_agent_specs()
    count = register_from_specs(manager, specs, "agent_services")
    logger.info("Registered %d agent chat services", count)
    return count
