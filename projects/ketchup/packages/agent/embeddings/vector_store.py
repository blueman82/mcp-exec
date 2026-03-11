"""ChromaDB vector store for Ketchup Agent RAG pipeline.

All ChromaDB client calls are synchronous (uses requests internally).
We wrap them in asyncio.to_thread() to avoid blocking the event loop
during backfill upserts and query operations.
"""

import asyncio
import os
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings

from packages.core.logging import setup_logger

logger = setup_logger(__name__)

COLLECTION_NAME = "ketchup_messages"


class ChromaVectorStore:
    """Manages document embeddings in ChromaDB for RAG retrieval."""

    def __init__(self):
        self._client: Optional[chromadb.HttpClient] = None
        self._collection = None

    async def initialize(self) -> None:
        """Connect to ChromaDB and get/create the collection."""
        host = os.environ.get("CHROMADB_HOST", "chromadb")
        port = int(os.environ.get("CHROMADB_PORT", "8000"))

        self._client = chromadb.HttpClient(
            host=host,
            port=port,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = await asyncio.to_thread(
            self._client.get_or_create_collection,
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        count = await asyncio.to_thread(self._collection.count)
        logger.info(
            "ChromaVectorStore connected to %s:%d, collection=%s (count=%d)",
            host,
            port,
            COLLECTION_NAME,
            count,
        )

    async def _ensure_collection(self) -> None:
        """Re-create collection if it was deleted externally (stale cached ref)."""
        self._collection = await asyncio.to_thread(
            self._client.get_or_create_collection,
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Re-acquired ChromaDB collection: %s", COLLECTION_NAME)

    async def add_documents(
        self,
        documents: List[Dict[str, Any]],
        embeddings: List[List[float]],
    ) -> None:
        """Add documents with pre-computed embeddings.

        Args:
            documents: List of dicts with keys: id, text, metadata
            embeddings: Corresponding embedding vectors
        """
        if not documents:
            return
        if not self._collection:
            raise RuntimeError("Vector store not initialized")

        ids = [doc["id"] for doc in documents]
        texts = [doc["text"] for doc in documents]
        metadatas = [doc["metadata"] for doc in documents]

        try:
            await asyncio.to_thread(
                self._collection.upsert,
                ids=ids,
                documents=texts,
                embeddings=embeddings,
                metadatas=metadatas,
            )
        except Exception as e:
            if "does not exist" in str(e):
                logger.warning("Collection gone, re-creating: %s", e)
                await self._ensure_collection()
                await asyncio.to_thread(
                    self._collection.upsert,
                    ids=ids,
                    documents=texts,
                    embeddings=embeddings,
                    metadatas=metadatas,
                )
            else:
                raise
        logger.info("Upserted %d documents to ChromaDB", len(documents))

    async def query(
        self,
        query_embedding: List[float],
        channel_id: str,
        top_k: int = 15,
    ) -> List[Dict[str, Any]]:
        """Query for similar documents filtered by channel_id.

        Args:
            query_embedding: The query embedding vector.
            channel_id: Filter results to this channel.
            top_k: Number of results to return.

        Returns:
            List of result dicts with keys: id, text, metadata, distance
        """
        if not self._collection:
            raise RuntimeError("Vector store not initialized")

        try:
            results = await asyncio.to_thread(
                self._collection.query,
                query_embeddings=[query_embedding],
                where={"channel_id": channel_id},
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            if "does not exist" in str(e):
                logger.warning("Collection gone during query, re-creating: %s", e)
                await self._ensure_collection()
                results = await asyncio.to_thread(
                    self._collection.query,
                    query_embeddings=[query_embedding],
                    where={"channel_id": channel_id},
                    n_results=top_k,
                    include=["documents", "metadatas", "distances"],
                )
            else:
                raise

        output = []
        if results and results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                output.append(
                    {
                        "id": doc_id,
                        "text": results["documents"][0][i] if results["documents"] else "",
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else 0.0,
                    }
                )

        return output

    async def delete_by_channel(self, channel_id: str) -> None:
        """Delete all documents for a specific channel.

        Args:
            channel_id: The channel whose documents should be deleted.
        """
        if not self._collection:
            raise RuntimeError("Vector store not initialized")

        try:
            await asyncio.to_thread(self._collection.delete, where={"channel_id": channel_id})
        except Exception as e:
            if "does not exist" in str(e):
                logger.warning("Collection gone during delete, re-creating: %s", e)
                await self._ensure_collection()
                await asyncio.to_thread(self._collection.delete, where={"channel_id": channel_id})
            else:
                raise
        logger.info("Deleted all ChromaDB documents for channel %s", channel_id)

    async def get_document_count(self, channel_id: Optional[str] = None) -> int:
        """Get the number of documents, optionally filtered by channel.

        Args:
            channel_id: Optional channel filter.

        Returns:
            Document count.
        """
        if not self._collection:
            return 0

        try:
            if channel_id:
                results = await asyncio.to_thread(
                    self._collection.get,
                    where={"channel_id": channel_id},
                    include=[],
                )
                return len(results["ids"]) if results["ids"] else 0
            return await asyncio.to_thread(self._collection.count)
        except Exception as e:
            if "does not exist" in str(e):
                logger.warning("Collection gone during count, re-creating: %s", e)
                await self._ensure_collection()
                if channel_id:
                    results = await asyncio.to_thread(
                        self._collection.get,
                        where={"channel_id": channel_id},
                        include=[],
                    )
                    return len(results["ids"]) if results["ids"] else 0
                return await asyncio.to_thread(self._collection.count)
            raise

    async def cleanup(self) -> None:
        """Clean up ChromaDB connection."""
        logger.info("ChromaVectorStore cleanup complete")
