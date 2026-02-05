"""Document retriever for semantic search over Adobe Campaign documentation.

This module performs vector similarity search in ChromaDB to find relevant
documentation chunks for user queries, supporting optional filtering by
category and chunk type.
"""

import asyncio
from typing import Any

import structlog

logger = structlog.get_logger()


class DocumentRetriever:
    """Retrieves relevant documentation chunks from ChromaDB via semantic search.

    Performs vector similarity search over Adobe Campaign field documentation
    to find chunks relevant to user queries. Supports optional filtering by
    category and chunk type.

    Args:
        openai_client: Azure OpenAI async client for query embedding
        chroma_client: ChromaDB HTTP client
        collection_name: ChromaDB collection to query (default: "campaign_prod_docs")

    Example:
        from openai import AsyncAzureOpenAI
        import chromadb

        openai_client = AsyncAzureOpenAI(
            azure_endpoint="https://asksplunk.cognitiveservices.azure.com/openai",
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version="2023-05-15"
        )
        chroma_client = chromadb.HttpClient(host="localhost", port=8000)

        retriever = DocumentRetriever(openai_client, chroma_client)
        chunks = await retriever.retrieve("bounce rate fields", top_k=5)
        print(f"Found {len(chunks)} relevant chunks")
    """

    def __init__(
        self,
        openai_client,
        chroma_client,
        collection_name: str = "campaign_prod_docs",
    ):
        """Initialize the document retriever.

        Args:
            openai_client: Azure OpenAI async client
            chroma_client: ChromaDB HTTP client
            collection_name: ChromaDB collection name
        """
        self.openai_client = openai_client
        self.chroma_client = chroma_client
        self.collection_name = collection_name

    async def _generate_query_embedding(self, query: str) -> list[float]:
        """Generate embedding vector for user query.

        Uses Azure OpenAI text-embedding-ada-002 model to convert the query
        text into a 1536-dimensional vector for semantic search.

        Args:
            query: Natural language query string

        Returns:
            1536-dimensional embedding vector

        Raises:
            openai.OpenAIError: If embedding generation fails

        Example:
            embedding = await retriever._generate_query_embedding("bounce fields")
            # Returns [0.1, 0.2, ..., 0.5] (1536 floats)
        """
        response = await self.openai_client.embeddings.create(
            input=query, model="text-embedding-ada-002"
        )

        embedding: list[float] = list(response.data[0].embedding)

        logger.info("query_embedding_generated", embedding_dim=len(embedding))

        return embedding

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filter_category: str | None = None,
        filter_chunk_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve relevant documentation chunks via semantic search.

        Generates an embedding for the user query and performs vector similarity
        search in ChromaDB. Optionally filters results by category and/or chunk type.
        Returns chunks sorted by relevance score (descending).

        Args:
            query: Natural language query (e.g., "bounce rate fields")
            top_k: Number of results to return (default: 5)
            filter_category: Optional category filter (e.g., "Campaign & Delivery")
            filter_chunk_type: Optional chunk type filter (e.g., "field", "pattern")

        Returns:
            List of dicts with keys:
                - content (str): Chunk text
                - chunk_type (str): "field", "pattern", "use_case", "index_overview"
                - metadata (dict): Chunk metadata (field_name, category, etc.)
                - relevance_score (float): 0.0-1.0 similarity score

        Raises:
            chromadb.errors.ChromaError: If ChromaDB connection fails
            openai.OpenAIError: If embedding generation fails

        Example:
            # Basic retrieval
            chunks = await retriever.retrieve("delivery failures", top_k=3)

            # With category filter
            chunks = await retriever.retrieve(
                "bounce fields",
                filter_category="Campaign & Delivery"
            )

            # Get only pattern chunks
            chunks = await retriever.retrieve(
                "query examples",
                filter_chunk_type="pattern"
            )
        """
        logger.info("retrieval_started", query_length=len(query), top_k=top_k)

        # 1. Generate query embedding
        query_embedding = await self._generate_query_embedding(query)

        # 2. Build where clause for filters
        where_clause = {}
        if filter_category:
            where_clause["category"] = filter_category
        if filter_chunk_type:
            where_clause["chunk_type"] = filter_chunk_type

        # 3. Query ChromaDB (wrap in asyncio.to_thread - ChromaDB is sync)
        collection = await asyncio.to_thread(
            self.chroma_client.get_collection, self.collection_name
        )

        results = await asyncio.to_thread(
            collection.query,
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_clause if where_clause else None,
            include=["documents", "metadatas", "distances"],
        )

        # 4. Format results
        chunks = []
        for i in range(len(results["documents"][0])):
            # Convert distance to similarity score (1.0 = perfect match, 0.0 = no match)
            # ChromaDB returns L2 distance, convert to similarity
            distance = results["distances"][0][i]
            relevance_score = 1.0 / (1.0 + distance)  # Normalize to 0-1 range

            chunk = {
                "content": results["documents"][0][i],
                "chunk_type": results["metadatas"][0][i].get("chunk_type", "unknown"),
                "metadata": results["metadatas"][0][i],
                "relevance_score": relevance_score,
            }
            chunks.append(chunk)

        # Calculate avg relevance for logging
        avg_relevance = sum(c["relevance_score"] for c in chunks) / len(chunks) if chunks else 0.0

        logger.info(
            "retrieval_complete", chunks_found=len(chunks), avg_relevance=round(avg_relevance, 3)
        )

        return chunks


# CLI interface for testing retrieval (can be run standalone)
if __name__ == "__main__":
    import os
    import sys

    import chromadb
    from openai import AsyncAzureOpenAI  # type: ignore[import-not-found]

    async def main():
        """CLI entry point for testing document retrieval.

        Usage:
            export AZURE_OPENAI_API_KEY="your-key"
            python -m src.asksplunk.retriever.retriever "bounce fields"

        Args from command line:
            query: Search query (default: "delivery failures")
        """
        # Check for API key
        api_key = os.environ.get("AZURE_OPENAI_API_KEY")
        if not api_key:
            print("Error: AZURE_OPENAI_API_KEY environment variable not set")
            print("\nUsage:")
            print('  export AZURE_OPENAI_API_KEY="your-api-key"')
            print('  python -m src.asksplunk.retriever.retriever "bounce fields"')
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

        # Verify collection exists
        try:
            collection = chroma_client.get_collection("campaign_prod_docs")
            print(f"✓ Found collection with {collection.count()} chunks\n")
        except Exception as e:
            print("Error: Collection 'campaign_prod_docs' not found")
            print(f"Details: {e}")
            print("\nRun indexer first:")
            print("  python -m src.asksplunk.indexer.indexer")
            sys.exit(1)

        # Get query from args or use default
        query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "delivery failures"

        # Run retrieval
        print(f"Query: '{query}'")
        print("Retrieving top 5 chunks...\n")

        retriever = DocumentRetriever(openai_client, chroma_client)

        try:
            chunks = await retriever.retrieve(query, top_k=5)

            print(f"Found {len(chunks)} relevant chunks:\n")
            for i, chunk in enumerate(chunks, 1):
                print(f"{i}. [{chunk['chunk_type']}] Score: {chunk['relevance_score']:.3f}")
                print(f"   {chunk['content'][:150]}...")
                print()

        except Exception as e:
            print(f"\n✗ Error during retrieval: {e}")
            import traceback

            traceback.print_exc()
            sys.exit(1)

    asyncio.run(main())
