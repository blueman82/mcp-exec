"""Document indexer for Adobe Campaign field documentation.

This module chunks JSON documentation into semantic units, generates embeddings
via Azure OpenAI, and stores them in ChromaDB for RAG retrieval.
"""

import json
import time
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()


class DocumentIndexer:
    """Chunks documentation and generates embeddings for RAG retrieval.

    This indexer transforms the Adobe Campaign field documentation JSON into
    semantic chunks optimized for vector search. Each chunk represents a
    discrete piece of knowledge (field, pattern, or use case) with rich
    contextual metadata.

    Chunking Strategy:
        1. Index Overview: High-level summary of the entire index
        2. Field Chunks: One per field with category context (287 total)
        3. Pattern Chunks: Query patterns with SPL examples (6 total)
        4. Use Case Chunks: Common questions mapped to fields (12 total)

    Args:
        openai_client: Azure OpenAI client for embedding generation
        chroma_client: ChromaDB client for vector storage
        collection_name: Name of ChromaDB collection (default: "campaign_prod_docs")
        batch_size: Embedding batch size (default: 16, Azure OpenAI limit)

    Example:
        from openai import AsyncAzureOpenAI
        import chromadb

        openai_client = AsyncAzureOpenAI(
            azure_endpoint="https://asksplunk.cognitiveservices.azure.com/openai",
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version="2023-05-15"
        )
        chroma_client = chromadb.HttpClient(host="localhost", port=8000)

        indexer = DocumentIndexer(openai_client, chroma_client)
        count = await indexer.index_documentation("docs/schema/campaign_prod_schema.json")
        print(f"Indexed {count} chunks")
    """

    def __init__(
        self,
        openai_client,
        chroma_client,
        collection_name: str = "campaign_prod_docs",
        batch_size: int = 16,
    ):
        """Initialize the document indexer.

        Args:
            openai_client: Azure OpenAI async client
            chroma_client: ChromaDB HTTP client
            collection_name: ChromaDB collection name
            batch_size: Maximum texts per embedding API call (Azure limit: 16)
        """
        self.openai_client = openai_client
        self.chroma_client = chroma_client
        self.collection_name = collection_name
        self.batch_size = batch_size

    def _create_chunks(self, docs: dict[str, Any]) -> list[dict[str, Any]]:
        """Chunk documentation into semantic units.

        Creates four types of chunks:
        1. Index overview: High-level summary (1 chunk)
        2. Field chunks: One per field with category context (287 chunks)
        3. Pattern chunks: Query patterns with SPL examples (6 chunks)
        4. Use case chunks: Questions mapped to fields (12 chunks)

        Args:
            docs: Parsed JSON schema dictionary

        Returns:
            List of chunk dictionaries with keys:
                - content (str): Searchable text content
                - chunk_type (str): "index_overview", "field", "pattern", "use_case"
                - metadata (dict): Chunk-specific metadata for filtering

        Example:
            chunks = indexer._create_chunks(schema_data)
            # Returns 306 chunks for full Adobe Campaign schema
        """
        chunks = []

        # Count fields and categories for overview
        field_count = sum(len(category["fields"]) for category in docs["field_categories"])
        category_count = len(docs["field_categories"])

        # 1. Create index overview chunk
        overview = {
            "content": (
                f"{docs['display_name']}: {docs['description']}. "
                f"Contains {field_count} fields across {category_count} categories."
            ),
            "chunk_type": "index_overview",
            "metadata": {
                "index_name": docs["index_name"],
                "field_count": field_count,
                "category_count": category_count,
            },
        }
        chunks.append(overview)

        # 2. Create field chunks (287 total for full schema)
        for category in docs["field_categories"]:
            category_name = category["category_name"]

            for field in category["fields"]:
                # Convert examples to strings (some may be integers)
                examples_str = ", ".join(str(ex) for ex in field["examples"])

                field_chunk = {
                    "content": (
                        f"Field: {field['name']} ({field['type']}). "
                        f"Category: {category_name}. "
                        f"Description: {field['description']}. "
                        f"Examples: {examples_str}. "
                        f"Found in: {', '.join(field['common_in'])}."
                    ),
                    "chunk_type": "field",
                    "metadata": {
                        "field_name": field["name"],
                        "field_type": field["type"],
                        "category": category_name,
                        "sourcetypes": ",".join(field["common_in"]),  # ChromaDB requires string
                    },
                }
                chunks.append(field_chunk)

        # 3. Create pattern chunks (6 total for full schema)
        for pattern in docs["query_patterns"]:
            # Handle both test data and real schema (different key names)
            pattern_name = pattern.get("name") or pattern.get("pattern_name", "Unknown")
            pattern_id = pattern.get("id") or pattern.get("pattern_name", "unknown")
            description = pattern.get("description") or pattern.get("use_case", "")
            fields_involved = pattern.get("fields_involved", [])

            # Build fields text (may not be in all schemas)
            fields_text = f"Fields: {', '.join(fields_involved)}." if fields_involved else ""

            pattern_chunk = {
                "content": (
                    f"Query Pattern: {pattern_name}. "
                    f"{description}. "
                    f"SPL: {pattern['spl_template']}. "
                    f"{fields_text}"
                ).strip(),
                "chunk_type": "pattern",
                "metadata": {
                    "pattern_id": pattern_id,
                    "pattern_name": pattern_name,
                    "fields_involved": ",".join(fields_involved),  # ChromaDB requires string
                },
            }
            chunks.append(pattern_chunk)

        # 4. Create use case chunks (12 total for full schema)
        # Handle both "use_cases" and "common_use_cases" keys
        use_cases = docs.get("use_cases") or docs.get("common_use_cases", [])
        for use_case in use_cases:
            use_case_chunk = {
                "content": (
                    f"Use Case: {use_case['question']}. "
                    f"Relevant fields: {', '.join(use_case['fields_involved'])}. "
                    f"Pattern: {use_case['pattern_reference']}."
                ),
                "chunk_type": "use_case",
                "metadata": {
                    "question": use_case["question"],
                    "fields_involved": ",".join(
                        use_case["fields_involved"]
                    ),  # ChromaDB requires string
                    "pattern_reference": use_case["pattern_reference"],
                },
            }
            chunks.append(use_case_chunk)

        logger.info(
            "chunks_created",
            total=len(chunks),
            overview=1,
            fields=field_count,
            patterns=len(docs["query_patterns"]),
            use_cases=len(use_cases),
        )

        return chunks

    async def _generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for texts in batches.

        Batches texts into groups of batch_size (default 16) to comply with
        Azure OpenAI API limits. Uses text-embedding-ada-002 model which
        produces 1536-dimensional vectors.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors (1536 dimensions each)

        Raises:
            openai.OpenAIError: If embedding generation fails

        Example:
            texts = ["Field: deliveryId", "Field: campaignId"]
            embeddings = await indexer._generate_embeddings(texts)
            # Returns [[0.1, 0.2, ...], [0.3, 0.4, ...]]
        """
        embeddings = []

        # Process in batches of batch_size (Azure OpenAI limit)
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]

            logger.info(
                "generating_embeddings",
                batch_num=i // self.batch_size + 1,
                batch_size=len(batch),
                total_batches=(len(texts) + self.batch_size - 1) // self.batch_size,
            )

            response = await self.openai_client.embeddings.create(
                input=batch, model="text-embedding-ada-002"
            )

            # Extract embeddings from response
            batch_embeddings = [data.embedding for data in response.data]
            embeddings.extend(batch_embeddings)

        logger.info("embeddings_generated", count=len(embeddings))

        return embeddings

    async def index_documentation(self, json_path: str) -> int:
        """Index documentation from JSON file into ChromaDB.

        Main entry point for the indexing pipeline:
        1. Load JSON documentation
        2. Chunk into semantic units
        3. Generate embeddings via Azure OpenAI
        4. Store in ChromaDB collection

        Args:
            json_path: Path to JSON schema file

        Returns:
            Total number of chunks indexed

        Raises:
            FileNotFoundError: If json_path doesn't exist
            json.JSONDecodeError: If JSON is malformed
            openai.OpenAIError: If embedding generation fails
            chromadb.errors.ChromaError: If storage fails

        Example:
            count = await indexer.index_documentation("docs/schema/campaign_prod_schema.json")
            print(f"Indexed {count} chunks")  # Should print 306 for full schema
        """
        start_time = time.time()

        logger.info("indexing_started", json_path=json_path)

        # 1. Load JSON documentation
        with open(json_path) as f:
            docs = json.load(f)

        logger.info("json_loaded", index_name=docs.get("index_name"))

        # 2. Create chunks
        chunks = self._create_chunks(docs)
        chunk_count = len(chunks)

        # 3. Generate embeddings for all chunk contents
        texts = [chunk["content"] for chunk in chunks]
        embeddings = await self._generate_embeddings(texts)

        # 4. Store in ChromaDB
        collection = self.chroma_client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "Adobe Campaign field documentation for RAG"},
        )

        logger.info("storing_in_chromadb", collection=self.collection_name, chunk_count=chunk_count)

        # Generate unique IDs for each chunk
        ids = [f"{chunk['chunk_type']}_{i}" for i, chunk in enumerate(chunks)]

        # Add all chunks to collection
        collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=[chunk["metadata"] for chunk in chunks],
            ids=ids,
        )

        elapsed = time.time() - start_time

        logger.info(
            "indexing_complete",
            chunks=chunk_count,
            duration_seconds=round(elapsed, 2),
            collection=self.collection_name,
        )

        return chunk_count


# CLI interface for running indexer standalone
if __name__ == "__main__":
    import asyncio
    import os
    import sys

    import chromadb
    from openai import AsyncAzureOpenAI

    async def main():
        """CLI entry point for document indexer.

        Usage:
            export AZURE_OPENAI_API_KEY="your-key"
            python -m src.asksplunk.indexer.indexer [json_path]

        Args from command line:
            json_path: Path to schema JSON (default: docs/schema/campaign_prod_schema.json)
        """
        # Check for API key
        api_key = os.environ.get("AZURE_OPENAI_API_KEY")
        if not api_key:
            print("Error: AZURE_OPENAI_API_KEY environment variable not set")
            print("\nUsage:")
            print("  export AZURE_OPENAI_API_KEY='your-api-key'")
            print("  python -m src.asksplunk.indexer.indexer [json_path]")
            sys.exit(1)

        # Initialize OpenAI client
        openai_client = AsyncAzureOpenAI(
            azure_endpoint="https://asksplunk.cognitiveservices.azure.com/openai",
            api_key=api_key,
            api_version="2023-05-15",
        )

        # Initialize ChromaDB client
        try:
            chroma_client = chromadb.HttpClient(host="localhost", port=8000)
            # Test connection
            chroma_client.heartbeat()
        except Exception as e:
            print("Error: Cannot connect to ChromaDB at localhost:8000")
            print(f"Details: {e}")
            print("\nMake sure ChromaDB is running:")
            print("  docker-compose up -d chromadb")
            sys.exit(1)

        # Get JSON path from args or use default
        json_path = sys.argv[1] if len(sys.argv) > 1 else "docs/schema/campaign_prod_schema.json"

        if not Path(json_path).exists():
            print(f"Error: File not found: {json_path}")
            sys.exit(1)

        # Run indexer
        print(f"Indexing {json_path}...")
        print("This may take a few minutes for 306 chunks...")

        indexer = DocumentIndexer(openai_client, chroma_client)

        try:
            count = await indexer.index_documentation(json_path)
            print(f"\n✓ Successfully indexed {count} chunks into ChromaDB")
            print("  Collection: campaign_prod_docs")
            print("  Endpoint: http://localhost:8000")

            # Verify storage
            collection = chroma_client.get_collection("campaign_prod_docs")
            stored_count = collection.count()
            print(f"\n✓ Verification: {stored_count} chunks stored in ChromaDB")

        except Exception as e:
            print(f"\n✗ Error during indexing: {e}")
            import traceback

            traceback.print_exc()
            sys.exit(1)

    asyncio.run(main())
