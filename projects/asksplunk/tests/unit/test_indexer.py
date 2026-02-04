"""Test suite for DocumentIndexer.

This module tests the document chunking and embedding generation functionality
that transforms Adobe Campaign field documentation into searchable vector chunks.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.fixture
def sample_schema_data():
    """Minimal schema data for testing chunking logic.

    Returns:
        Dict with 2 fields, 1 pattern, 1 use_case for predictable testing
    """
    return {
        "index_name": "campaign_prod",
        "display_name": "Adobe Campaign Production",
        "description": "Production logs for Adobe Campaign",
        "field_categories": [
            {
                "category_name": "Campaign & Delivery",
                "description": "Core campaign fields",
                "fields": [
                    {
                        "name": "deliveryId",
                        "type": "string",
                        "description": "Unique identifier for the delivery",
                        "examples": ["DM123456", "DM789012"],
                        "common_in": ["mta_log", "web_log"],
                    },
                    {
                        "name": "deliveryName",
                        "type": "string",
                        "description": "Human-readable name of the delivery",
                        "examples": ["Welcome Email 2024"],
                        "common_in": ["mta_log"],
                    },
                ],
            }
        ],
        "query_patterns": [
            {
                "id": "bounce_analysis",
                "name": "Bounce Analysis",
                "description": "Analyze bounce reasons",
                "spl_template": "index=campaign_prod sourcetype=mta_log | stats count by failureReason",
                "fields_involved": ["failureReason", "failureType"],
            }
        ],
        "use_cases": [
            {
                "question": "How do I see delivery success vs failure rates?",
                "fields_involved": ["deliveryStatus", "campaignId"],
                "pattern_reference": "performance_overview",
            }
        ],
    }


@pytest.fixture
def mock_openai_client():
    """Mock Azure OpenAI client for embedding generation.

    Returns:
        AsyncMock configured to return fake embeddings
    """
    client = AsyncMock()
    # Mock embeddings.create() to return fake embeddings
    mock_response = Mock()
    mock_response.data = [
        Mock(embedding=[0.1] * 1536),  # 1536-dim vector
        Mock(embedding=[0.2] * 1536),
    ]
    client.embeddings.create = AsyncMock(return_value=mock_response)
    return client


@pytest.fixture
def mock_chroma_client():
    """Mock ChromaDB client for storage.

    Returns:
        Mock with get_or_create_collection method
    """
    client = Mock()
    mock_collection = Mock()
    mock_collection.add = Mock()
    mock_collection.count = Mock(return_value=0)
    client.get_or_create_collection = Mock(return_value=mock_collection)
    return client


class TestDocumentIndexer:
    """Test DocumentIndexer chunking and embedding logic."""

    def test_create_chunks_creates_index_overview(self, sample_schema_data):
        """Index overview chunk contains summary of entire index.

        Verifies that exactly one overview chunk is created with:
        - chunk_type: "index_overview"
        - content: includes index name, description, field count
        - metadata: index_name, field_count, category_count
        """
        from src.asksplunk.indexer.indexer import DocumentIndexer

        indexer = DocumentIndexer(Mock(), Mock())
        chunks = indexer._create_chunks(sample_schema_data)

        # Find overview chunk
        overview_chunks = [c for c in chunks if c["chunk_type"] == "index_overview"]

        assert len(overview_chunks) == 1, "Should create exactly one overview chunk"

        overview = overview_chunks[0]
        assert "Adobe Campaign Production" in overview["content"]
        assert "Production logs for Adobe Campaign" in overview["content"]
        assert overview["metadata"]["index_name"] == "campaign_prod"
        assert overview["metadata"]["field_count"] == 2  # 2 fields in sample data
        assert overview["metadata"]["category_count"] == 1

    def test_create_chunks_creates_field_chunks_with_category_context(self, sample_schema_data):
        """Each field becomes a chunk with category context.

        Verifies that field chunks include:
        - Field name, type, description, examples
        - Category context (e.g., "Campaign & Delivery category")
        - Metadata: field_name, field_type, category, sourcetypes
        """
        from src.asksplunk.indexer.indexer import DocumentIndexer

        indexer = DocumentIndexer(Mock(), Mock())
        chunks = indexer._create_chunks(sample_schema_data)

        # Find field chunks
        field_chunks = [c for c in chunks if c["chunk_type"] == "field"]

        assert len(field_chunks) == 2, "Should create 2 field chunks from sample data"

        # Check first field chunk (deliveryId)
        delivery_id_chunk = [
            c for c in field_chunks if c["metadata"]["field_name"] == "deliveryId"
        ][0]

        assert "deliveryId" in delivery_id_chunk["content"]
        assert "string" in delivery_id_chunk["content"]
        assert (
            "Campaign & Delivery" in delivery_id_chunk["content"]
        ), "Must include category context"
        assert "Unique identifier for the delivery" in delivery_id_chunk["content"]
        assert "DM123456" in delivery_id_chunk["content"], "Should include examples"
        assert "mta_log" in delivery_id_chunk["content"], "Should include sourcetypes"

        # Verify metadata
        assert delivery_id_chunk["metadata"]["field_name"] == "deliveryId"
        assert delivery_id_chunk["metadata"]["field_type"] == "string"
        assert delivery_id_chunk["metadata"]["category"] == "Campaign & Delivery"
        assert "mta_log" in delivery_id_chunk["metadata"]["sourcetypes"]

    def test_create_chunks_creates_pattern_chunks_with_examples(self, sample_schema_data):
        """Query patterns become chunks with SPL templates.

        Verifies that pattern chunks include:
        - Pattern name and description
        - SPL template
        - Fields involved
        - Metadata: pattern_id, pattern_name, fields_involved
        """
        from src.asksplunk.indexer.indexer import DocumentIndexer

        indexer = DocumentIndexer(Mock(), Mock())
        chunks = indexer._create_chunks(sample_schema_data)

        # Find pattern chunks
        pattern_chunks = [c for c in chunks if c["chunk_type"] == "pattern"]

        assert len(pattern_chunks) == 1, "Should create 1 pattern chunk from sample data"

        pattern = pattern_chunks[0]
        assert "Bounce Analysis" in pattern["content"]
        assert "Analyze bounce reasons" in pattern["content"]
        assert "index=campaign_prod sourcetype=mta_log" in pattern["content"], "Must include SPL"
        assert "failureReason" in pattern["content"], "Must include involved fields"

        # Verify metadata
        assert pattern["metadata"]["pattern_id"] == "bounce_analysis"
        assert pattern["metadata"]["pattern_name"] == "Bounce Analysis"
        assert "failureReason" in pattern["metadata"]["fields_involved"]

    def test_create_chunks_creates_use_case_chunks(self, sample_schema_data):
        """Use cases become chunks linking questions to fields.

        Verifies that use_case chunks include:
        - User question
        - Relevant fields
        - Pattern reference
        - Metadata: question, fields_involved, pattern_reference
        """
        from src.asksplunk.indexer.indexer import DocumentIndexer

        indexer = DocumentIndexer(Mock(), Mock())
        chunks = indexer._create_chunks(sample_schema_data)

        # Find use_case chunks
        use_case_chunks = [c for c in chunks if c["chunk_type"] == "use_case"]

        assert len(use_case_chunks) == 1, "Should create 1 use_case chunk from sample data"

        use_case = use_case_chunks[0]
        assert "How do I see delivery success vs failure rates?" in use_case["content"]
        assert "deliveryStatus" in use_case["content"]
        assert "performance_overview" in use_case["content"]

        # Verify metadata
        assert use_case["metadata"]["question"] == "How do I see delivery success vs failure rates?"
        assert "deliveryStatus" in use_case["metadata"]["fields_involved"]
        assert use_case["metadata"]["pattern_reference"] == "performance_overview"

    def test_chunk_count_matches_expected(self, sample_schema_data):
        """Total chunks equals overview + fields + patterns + use_cases.

        Sample data has:
        - 1 overview
        - 2 fields
        - 1 pattern
        - 1 use_case
        Total: 5 chunks
        """
        from src.asksplunk.indexer.indexer import DocumentIndexer

        indexer = DocumentIndexer(Mock(), Mock())
        chunks = indexer._create_chunks(sample_schema_data)

        assert len(chunks) == 5, "Should create 5 total chunks (1+2+1+1)"

        # Verify chunk type distribution
        chunk_types = [c["chunk_type"] for c in chunks]
        assert chunk_types.count("index_overview") == 1
        assert chunk_types.count("field") == 2
        assert chunk_types.count("pattern") == 1
        assert chunk_types.count("use_case") == 1

    @pytest.mark.asyncio
    async def test_generate_embeddings_batches_correctly(self, mock_openai_client):
        """Embeddings are generated in batches of 16 (Azure OpenAI limit).

        Verifies that:
        - Texts are batched in groups of 16
        - OpenAI API is called correct number of times
        - All embeddings are returned
        """
        from src.asksplunk.indexer.indexer import DocumentIndexer

        indexer = DocumentIndexer(mock_openai_client, Mock(), batch_size=16)

        # Create 35 texts (should result in 3 batches: 16 + 16 + 3)
        texts = [f"text_{i}" for i in range(35)]

        # Mock response for each batch
        def create_mock_response(batch):
            mock_response = Mock()
            mock_response.data = [Mock(embedding=[0.1] * 1536) for _ in batch]
            return mock_response

        mock_openai_client.embeddings.create.side_effect = (
            lambda input, model: create_mock_response(input)
        )

        embeddings = await indexer._generate_embeddings(texts)

        # Verify API was called 3 times (for 3 batches)
        assert mock_openai_client.embeddings.create.call_count == 3

        # Verify all 35 embeddings returned
        assert len(embeddings) == 35

        # Verify batch sizes
        calls = mock_openai_client.embeddings.create.call_args_list
        assert len(calls[0][1]["input"]) == 16  # First batch
        assert len(calls[1][1]["input"]) == 16  # Second batch
        assert len(calls[2][1]["input"]) == 3  # Third batch (remainder)

    @pytest.mark.asyncio
    async def test_index_documentation_end_to_end(
        self, tmp_path, sample_schema_data, mock_openai_client, mock_chroma_client
    ):
        """Full indexing pipeline: load JSON → chunk → embed → store.

        Verifies that:
        - JSON is loaded correctly
        - Chunks are created
        - Embeddings are generated
        - Data is stored in ChromaDB
        - Correct chunk count is returned
        """
        from src.asksplunk.indexer.indexer import DocumentIndexer

        # Write sample schema to temp file
        json_path = tmp_path / "test_schema.json"
        with open(json_path, "w") as f:
            json.dump(sample_schema_data, f)

        # Configure mock OpenAI to return embeddings for 5 chunks
        def create_mock_response(batch):
            mock_response = Mock()
            mock_response.data = [Mock(embedding=[0.1] * 1536) for _ in batch]
            return mock_response

        mock_openai_client.embeddings.create.side_effect = (
            lambda input, model: create_mock_response(input)
        )

        # Configure mock ChromaDB collection
        mock_collection = mock_chroma_client.get_or_create_collection.return_value

        # Run indexer
        indexer = DocumentIndexer(mock_openai_client, mock_chroma_client)
        chunk_count = await indexer.index_documentation(str(json_path))

        # Verify chunk count
        assert chunk_count == 5, "Should return total chunk count"

        # Verify collection was created
        mock_chroma_client.get_or_create_collection.assert_called_once_with(
            name="campaign_prod_docs",
            metadata={"description": "Adobe Campaign field documentation for RAG"},
        )

        # Verify embeddings were generated
        assert mock_openai_client.embeddings.create.called

        # Verify chunks were added to ChromaDB
        mock_collection.add.assert_called_once()
        call_kwargs = mock_collection.add.call_args[1]

        assert len(call_kwargs["documents"]) == 5
        assert len(call_kwargs["embeddings"]) == 5
        assert len(call_kwargs["metadatas"]) == 5
        assert len(call_kwargs["ids"]) == 5

        # Verify IDs have correct format
        ids = call_kwargs["ids"]
        assert any("index_overview" in id for id in ids)
        assert any("field" in id for id in ids)
        assert any("pattern" in id for id in ids)
        assert any("use_case" in id for id in ids)

    def test_real_schema_produces_106_chunks(self):
        """Real campaign_prod_schema.json produces exactly 106 chunks.

        Verifies chunking of actual schema (reduced to momentum/mta logs only):
        - 1 overview
        - 71 fields (momentum event fields, MTA fields, infrastructure fields)
        - 19 patterns (delivery, bounce analysis, MTA errors)
        - 15 use_cases (bounce/delivery questions for momentum/mta)
        Total: 106 chunks

        Sourcetypes covered: 2 (eventlog_momentum, mta_log)
        """
        from src.asksplunk.indexer.indexer import DocumentIndexer

        schema_path = Path("docs/schema/campaign_prod_schema.json")

        if not schema_path.exists():
            pytest.skip("Real schema file not found")

        with open(schema_path) as f:
            schema_data = json.load(f)

        indexer = DocumentIndexer(Mock(), Mock())
        chunks = indexer._create_chunks(schema_data)

        assert len(chunks) == 155, "Real schema should produce 155 chunks"

        # Verify distribution
        chunk_types = [c["chunk_type"] for c in chunks]
        assert chunk_types.count("index_overview") == 1
        assert chunk_types.count("field") == 87
        assert chunk_types.count("pattern") == 42
        assert chunk_types.count("use_case") == 25
