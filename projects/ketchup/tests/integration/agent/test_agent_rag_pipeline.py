"""Integration tests for the Ketchup Agent RAG pipeline.

Tests the full RAG pipeline against a real ChromaDB instance running at localhost:8100.
This is a Tier 2 integration test that wires together real vector storage with mocked
embeddings, conversation store, and LLM API executor.

The test data is a realistic Slack conversation about production incident handling,
including timestamps, usernames, and multi-turn discussion.
"""

import os
import random
from typing import List
from unittest.mock import AsyncMock

import pytest

# All agent integration tests use mocked DynamoDB — no AWS credentials needed
pytestmark = pytest.mark.no_aws_required

# Test data: realistic Slack messages about a production incident
SAMPLE_MESSAGES = [
    {"ts": "1709000001.000001", "user": "U001", "text": "Server CPU is at 95% on prod1"},
    {
        "ts": "1709000002.000002",
        "user": "U002",
        "text": "I see the same, restarting the nginx container now",
    },
    {
        "ts": "1709000003.000003",
        "user": "U001",
        "text": "JIRA ticket CPGNCX-1234 created for the CPU spike",
    },
    {"ts": "1709000004.000004", "user": "U003", "text": "The restart fixed it, CPU back to normal"},
    {
        "ts": "1709000005.000005",
        "user": "U002",
        "text": "Root cause was a memory leak in the status updater",
    },
    {
        "ts": "1709000006.000006",
        "user": "U001",
        "text": "Deployed hotfix v2.350.100, monitoring now",
    },
    {"ts": "1709000007.000007", "user": "U003", "text": "All clear, closing the JIRA ticket"},
    {
        "ts": "1709000008.000008",
        "user": "U002",
        "text": "Next standup let's discuss adding memory limits",
    },
    {
        "ts": "1709000009.000009",
        "user": "U001",
        "text": "Agreed, I'll add it to the sprint backlog",
    },
    {
        "ts": "1709000010.000010",
        "user": "U003",
        "text": "Also need to update the runbook for this scenario",
    },
]

CHANNEL_ID = "C001CHANNEL"


@pytest.fixture
def chromadb_host():
    """Get ChromaDB host from environment, default to localhost:8100."""
    return os.environ.get("CHROMADB_HOST", "localhost")


@pytest.fixture
def chromadb_port():
    """Get ChromaDB port from environment, default to 8100."""
    return int(os.environ.get("CHROMADB_PORT", "8100"))


@pytest.fixture
async def chromadb_connection_check(chromadb_host, chromadb_port):
    """Verify ChromaDB is reachable before running tests.

    Skips all tests in this module if ChromaDB is not available.
    """
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        result = sock.connect_ex((chromadb_host, chromadb_port))
        if result != 0:
            pytest.skip(
                f"ChromaDB not reachable at {chromadb_host}:{chromadb_port}. "
                "Skipping integration tests. Start ChromaDB with: "
                "docker run -p 8100:8000 chromadb/chroma:latest"
            )
    finally:
        sock.close()


@pytest.fixture
async def chroma_vector_store(chromadb_connection_check, monkeypatch):
    """Create and initialize ChromaVectorStore connected to localhost:8100.

    Sets environment variables to override default ChromaDB host/port.
    Yields the initialized store, then cleans up the test collection after the test.
    """
    from packages.agent.embeddings.vector_store import ChromaVectorStore

    monkeypatch.setenv("CHROMADB_HOST", "localhost")
    monkeypatch.setenv("CHROMADB_PORT", "8100")

    store = ChromaVectorStore()
    await store.initialize()

    yield store

    # Teardown: delete all test data for this channel
    try:
        await store.delete_by_channel(CHANNEL_ID)
    except Exception:
        pass  # Ignore errors during cleanup


@pytest.fixture
def deterministic_embedding_client():
    """Mock AzureEmbeddingsClient that returns deterministic 1536-dim vectors.

    Uses a seeded random number generator to produce reproducible embeddings
    for the same query/text. This allows testing retrieval quality without
    hitting Azure API limits.
    """
    client = AsyncMock()

    async def make_embedding(text_or_query: str) -> List[float]:
        """Generate deterministic 1536-dim embedding from text."""
        # Use text hash as seed for reproducibility
        seed = hash(text_or_query) % (2**31)
        rng = random.Random(seed)
        # Generate 1536-dim vector normalized to ~unit length
        embedding = [rng.gauss(0, 0.1) for _ in range(1536)]
        norm = (sum(x**2 for x in embedding) ** 0.5) or 1.0
        return [x / norm for x in embedding]

    client.embed_query = AsyncMock(side_effect=make_embedding)

    async def make_embeddings(texts: List[str]) -> List[List[float]]:
        """Generate deterministic embeddings for a batch of texts."""
        return [await make_embedding(t) for t in texts]

    client.embed_texts = AsyncMock(side_effect=make_embeddings)

    return client


@pytest.fixture
def mock_conversation_store():
    """Mock ConversationStore that returns empty history.

    In integration tests, we isolate the conversation store since this test
    focuses on the retriever → context builder → LLM pipeline.
    """
    store = AsyncMock()
    store.get_history.return_value = []
    return store


@pytest.fixture
def mock_api_executor():
    """Mock ApiExecutor that returns a canned LLM response.

    Returns a realistic Azure OpenAI response structure without hitting the API.
    """
    executor = AsyncMock()
    executor.execute_request.return_value = {
        "choices": [
            {
                "message": {
                    "content": (
                        "Based on the context, the CPU spike was caused by a memory leak "
                        "in the status updater. The team restarted the nginx container to fix it, "
                        "deployed a hotfix, and is planning to add memory limits in the next sprint."
                    )
                }
            }
        ],
        "usage": {
            "prompt_tokens": 250,
            "completion_tokens": 50,
            "total_tokens": 300,
        },
    }
    return executor


class TestChromaDBConnection:
    """Test that ChromaDB is reachable and operational."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_chromadb_connection(self, chroma_vector_store):
        """Verify ChromaDB is reachable at localhost:8100.

        This test exercises the basic connection and initialization of the
        ChromaVectorStore, including collection creation/retrieval.
        """
        assert chroma_vector_store._client is not None
        assert chroma_vector_store._collection is not None

        # Verify we can get the collection
        count = await chroma_vector_store.get_document_count()
        assert count >= 0, "Collection should be queryable"


class TestEmbeddingAndStorage:
    """Test message formatting and storage in ChromaDB."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_embed_and_store_messages(
        self,
        chroma_vector_store,
        deterministic_embedding_client,
    ):
        """Format 10 sample messages and store them with embeddings in ChromaDB.

        Tests the full pipeline:
        1. Format raw Slack messages using format_messages()
        2. Generate deterministic embeddings for each message
        3. Upsert documents to ChromaDB
        4. Verify documents are stored
        """
        from packages.agent.embeddings.chunker import format_messages

        # Step 1: Format messages
        docs = format_messages(SAMPLE_MESSAGES, CHANNEL_ID)
        assert len(docs) == 10, "All 10 sample messages should be formatted"

        # Step 2: Generate embeddings for each document
        embeddings = [await deterministic_embedding_client.embed_query(doc.text) for doc in docs]
        assert len(embeddings) == 10
        assert all(len(emb) == 1536 for emb in embeddings), "All embeddings should be 1536-dim"

        # Step 3: Convert to dict format for storage
        documents = [
            {
                "id": doc.doc_id,
                "text": doc.text,
                "metadata": {
                    "channel_id": CHANNEL_ID,
                    "user_id": doc.user_id,
                    "message_ts": doc.message_ts,
                    "has_thread_replies": doc.has_thread_replies,
                },
            }
            for doc in docs
        ]

        # Step 4: Store in ChromaDB
        await chroma_vector_store.add_documents(documents, embeddings)

        # Step 5: Verify storage
        count = await chroma_vector_store.get_document_count(CHANNEL_ID)
        assert count == 10, "All 10 documents should be stored"


class TestQueryAndRetrieval:
    """Test semantic search and retrieval from ChromaDB."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_query_returns_relevant_results(
        self,
        chroma_vector_store,
        deterministic_embedding_client,
    ):
        """Store messages, then query and verify results come back with correct structure.

        Tests that ChromaDB's semantic search returns results matching the query
        with proper metadata and distance scores.
        """
        from packages.agent.embeddings.chunker import format_messages

        # Setup: Store sample messages
        docs = format_messages(SAMPLE_MESSAGES, CHANNEL_ID)
        embeddings = [await deterministic_embedding_client.embed_query(doc.text) for doc in docs]
        documents = [
            {
                "id": doc.doc_id,
                "text": doc.text,
                "metadata": {
                    "channel_id": CHANNEL_ID,
                    "user_id": doc.user_id,
                    "message_ts": doc.message_ts,
                },
            }
            for doc in docs
        ]
        await chroma_vector_store.add_documents(documents, embeddings)

        # Test: Query for CPU-related context
        query = "What caused the CPU spike?"
        query_embedding = await deterministic_embedding_client.embed_query(query)

        results = await chroma_vector_store.query(
            query_embedding=query_embedding,
            channel_id=CHANNEL_ID,
            top_k=5,
        )

        # Assertions
        assert len(results) > 0, "Query should return results"
        assert len(results) <= 5, "Should not exceed top_k"

        for result in results:
            assert "id" in result, "Result should have id"
            assert "text" in result, "Result should have text"
            assert "metadata" in result, "Result should have metadata"
            assert "distance" in result, "Result should have distance score"
            assert 0.0 <= result["distance"] <= 2.0, "Distance should be in cosine range"
            assert result["metadata"]["channel_id"] == CHANNEL_ID


class TestRetrieverIntegration:
    """Test the Retriever component with real ChromaDB and mock embeddings."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_retriever_end_to_end(
        self,
        chroma_vector_store,
        deterministic_embedding_client,
    ):
        """Wire up Retriever with mock embeddings client and real ChromaVectorStore.

        Tests that the Retriever correctly:
        1. Embeds user queries using the embeddings client
        2. Queries the vector store by channel
        3. Converts raw distance scores to similarity scores
        4. Returns results in the expected format
        """
        from packages.agent.embeddings.chunker import format_messages
        from packages.agent.rag.retriever import Retriever

        # Setup: Store test messages
        docs = format_messages(SAMPLE_MESSAGES, CHANNEL_ID)
        embeddings = [await deterministic_embedding_client.embed_query(doc.text) for doc in docs]
        documents = [
            {
                "id": doc.doc_id,
                "text": doc.text,
                "metadata": {
                    "channel_id": CHANNEL_ID,
                    "user_id": doc.user_id,
                    "message_ts": doc.message_ts,
                },
            }
            for doc in docs
        ]
        await chroma_vector_store.add_documents(documents, embeddings)

        # Create retriever
        retriever = Retriever(
            embeddings_client=deterministic_embedding_client,
            vector_store=chroma_vector_store,
        )

        # Test: Retrieve with a query
        query = "What was the root cause and how was it fixed?"
        results = await retriever.retrieve(
            query=query,
            channel_id=CHANNEL_ID,
            top_k=15,
        )

        # Assertions
        assert len(results) > 0, "Retriever should return results"
        assert len(results) <= 15, "Should not exceed top_k"

        # Check result structure
        for result in results:
            assert "id" in result, "Result should have id"
            assert "text" in result, "Result should have text"
            assert "metadata" in result, "Result should have metadata"
            assert "score" in result, "Result should have similarity score"
            assert 0.0 <= result["score"] <= 1.0, "Similarity score should be 0-1"

        # Verify similarity scores are sorted (descending)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True), "Results should be sorted by score"

        # Verify embeddings client was called
        deterministic_embedding_client.embed_query.assert_called_with(query)


class TestContextBuilder:
    """Test the ContextBuilder component with retrieved chunks."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_context_builder_assembles_messages(
        self,
        mock_conversation_store,
    ):
        """Given retrieved chunks, verify ContextBuilder produces proper message list.

        Tests that ContextBuilder correctly:
        1. Includes the system prompt
        2. Includes retrieved context as a user message
        3. Includes conversation history (empty in this test)
        4. Ends with the current user question
        5. Respects token budget constraints
        """
        from packages.agent.rag.context_builder import ContextBuilder

        builder = ContextBuilder(conversation_store=mock_conversation_store)

        # Sample retrieved chunks
        chunks = [
            {
                "id": "C001CHANNEL:1709000001.000001",
                "text": "[1709000001] <@U001>: Server CPU is at 95% on prod1",
                "metadata": {"channel_id": CHANNEL_ID},
                "score": 0.92,
            },
            {
                "id": "C001CHANNEL:1709000005.000005",
                "text": "[1709000005] <@U002>: Root cause was a memory leak in the status updater",
                "metadata": {"channel_id": CHANNEL_ID},
                "score": 0.88,
            },
            {
                "id": "C001CHANNEL:1709000006.000006",
                "text": "[1709000006] <@U001>: Deployed hotfix v2.350.100, monitoring now",
                "metadata": {"channel_id": CHANNEL_ID},
                "score": 0.85,
            },
        ]

        system_prompt = "You are a helpful Slack bot that analyzes incidents."
        question = "What happened with the CPU spike and how was it resolved?"

        messages = await builder.build_context(
            question=question,
            channel_id=CHANNEL_ID,
            thread_ts="1234.5678",
            retrieved_chunks=chunks,
            system_prompt=system_prompt,
            max_history_turns=10,
        )

        # Assertions
        assert len(messages) >= 2, "Should have at least system prompt + question"
        assert messages[0]["role"] == "system", "First message should be system prompt"
        assert system_prompt in messages[0]["content"], "System prompt should be included"

        # Verify context is included
        context_found = False
        for msg in messages:
            if "relevant context" in msg.get("content", "").lower():
                context_found = True
                assert msg["role"] == "user", "Context block should be user role"
                break
        assert context_found, "Retrieved context should be in the message list"

        # Verify question is at the end
        assert messages[-1]["role"] == "user", "Last message should be user question"
        assert question in messages[-1]["content"], "Question should be at the end"


class TestAgentEnginePipeline:
    """Test the full AgentEngine pipeline from question to answer."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_pipeline_answer(
        self,
        chroma_vector_store,
        deterministic_embedding_client,
        mock_conversation_store,
        mock_api_executor,
    ):
        """Wire up AgentEngine and verify full end-to-end flow.

        Tests the complete RAG pipeline:
        1. Store sample messages in ChromaDB
        2. Create AgentEngine with real retriever and mock LLM
        3. Ask a question
        4. Verify retrieval, context building, LLM call, and response
        5. Verify conversation turns are stored
        """
        from packages.agent.embeddings.chunker import format_messages
        from packages.agent.rag.context_builder import ContextBuilder
        from packages.agent.rag.engine import AgentEngine
        from packages.agent.rag.retriever import Retriever

        # Setup: Store test messages
        docs = format_messages(SAMPLE_MESSAGES, CHANNEL_ID)
        embeddings = [await deterministic_embedding_client.embed_query(doc.text) for doc in docs]
        documents = [
            {
                "id": doc.doc_id,
                "text": doc.text,
                "metadata": {
                    "channel_id": CHANNEL_ID,
                    "user_id": doc.user_id,
                    "message_ts": doc.message_ts,
                },
            }
            for doc in docs
        ]
        await chroma_vector_store.add_documents(documents, embeddings)

        # Create pipeline components
        retriever = Retriever(
            embeddings_client=deterministic_embedding_client,
            vector_store=chroma_vector_store,
        )
        context_builder = ContextBuilder(conversation_store=mock_conversation_store)

        system_prompt = "You are a Ketchup incident analysis bot."
        engine = AgentEngine(
            retriever=retriever,
            context_builder=context_builder,
            conversation_store=mock_conversation_store,
            api_executor=mock_api_executor,
            system_prompt=system_prompt,
        )

        # Test: Ask a question
        question = "What caused the production incident and how was it resolved?"
        response = await engine.answer(
            question=question,
            channel_id=CHANNEL_ID,
            thread_ts="1709000001.000001",
            user_id="U456",
        )

        # Assertions
        assert isinstance(response, str), "Response should be a string"
        assert len(response) > 0, "Response should not be empty"
        assert (
            "memory leak" in response.lower() or "hotfix" in response.lower()
        ), "Response should reference retrieved context"

        # Verify retriever was used
        deterministic_embedding_client.embed_query.assert_called()

        # Verify LLM was called
        mock_api_executor.execute_request.assert_called_once()
        call_kwargs = mock_api_executor.execute_request.call_args[1]
        assert "payload" in call_kwargs, "Executor should receive payload with messages"
        assert "messages" in call_kwargs["payload"], "Payload should have messages"

        # Verify conversation turns were stored
        assert (
            mock_conversation_store.store_turn.call_count == 2
        ), "Should store both user and assistant turns"

        # Verify first turn is user's question
        first_turn_call = mock_conversation_store.store_turn.call_args_list[0]
        user_turn = first_turn_call[0][0]
        assert user_turn.role == "user", "First turn should be user"
        assert user_turn.content == question, "First turn should contain the question"
        assert user_turn.channel_id == CHANNEL_ID, "Turn should reference the channel"
        assert user_turn.user_id == "U456", "Turn should reference the user"

        # Verify second turn is assistant's response
        second_turn_call = mock_conversation_store.store_turn.call_args_list[1]
        assistant_turn = second_turn_call[0][0]
        assert assistant_turn.role == "assistant", "Second turn should be assistant"
        assert assistant_turn.content == response, "Second turn should contain the response"


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_retriever_handles_no_results(
        self,
        chroma_vector_store,
        deterministic_embedding_client,
    ):
        """Verify retriever gracefully handles no matching results.

        Tests that querying an empty or non-matching channel returns empty results
        without errors.
        """
        from packages.agent.rag.retriever import Retriever

        retriever = Retriever(
            embeddings_client=deterministic_embedding_client,
            vector_store=chroma_vector_store,
        )

        # Query a channel with no documents
        results = await retriever.retrieve(
            query="What happened?",
            channel_id="C_NONEXISTENT",
            top_k=20,
        )

        assert results == [], "Should return empty list for non-existent channel"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_context_builder_handles_empty_chunks(
        self,
        mock_conversation_store,
    ):
        """Verify ContextBuilder works with no retrieved chunks.

        Tests that the system gracefully handles queries with no semantic matches.
        """
        from packages.agent.rag.context_builder import ContextBuilder

        builder = ContextBuilder(conversation_store=mock_conversation_store)

        messages = await builder.build_context(
            question="Why is the sky blue?",
            channel_id=CHANNEL_ID,
            thread_ts="1234.5678",
            retrieved_chunks=[],
            system_prompt="You are helpful.",
        )

        # Should still have system prompt and question
        assert len(messages) >= 2, "Should have at least system + question"
        assert messages[0]["role"] == "system"
        assert messages[-1]["role"] == "user"
        assert "Why is the sky blue?" in messages[-1]["content"]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_agent_engine_fallback_on_empty_lm_response(
        self,
        chroma_vector_store,
        deterministic_embedding_client,
        mock_conversation_store,
    ):
        """Verify AgentEngine returns fallback message when LLM response is empty.

        Tests resilience to empty or missing LLM responses.
        """
        from packages.agent.embeddings.chunker import format_messages
        from packages.agent.rag.context_builder import ContextBuilder
        from packages.agent.rag.engine import AgentEngine
        from packages.agent.rag.retriever import Retriever

        # Setup messages
        docs = format_messages(SAMPLE_MESSAGES, CHANNEL_ID)
        embeddings = [await deterministic_embedding_client.embed_query(doc.text) for doc in docs]
        documents = [
            {
                "id": doc.doc_id,
                "text": doc.text,
                "metadata": {
                    "channel_id": CHANNEL_ID,
                    "user_id": doc.user_id,
                    "message_ts": doc.message_ts,
                },
            }
            for doc in docs
        ]
        await chroma_vector_store.add_documents(documents, embeddings)

        # Create components with mock that returns empty response
        retriever = Retriever(
            embeddings_client=deterministic_embedding_client,
            vector_store=chroma_vector_store,
        )
        context_builder = ContextBuilder(conversation_store=mock_conversation_store)

        api_executor = AsyncMock()
        api_executor.execute_request.return_value = {"choices": []}

        engine = AgentEngine(
            retriever=retriever,
            context_builder=context_builder,
            conversation_store=mock_conversation_store,
            api_executor=api_executor,
            system_prompt="You are helpful.",
        )

        response = await engine.answer(
            question="What happened?",
            channel_id=CHANNEL_ID,
            thread_ts="1234.5678",
        )

        # Should return fallback message, not empty string
        assert len(response) > 0, "Should return fallback message"
        assert "wasn't able to generate" in response.lower()
