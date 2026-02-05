"""CLI tool for testing document retrieval interactively.

Interactive test tool that prompts for queries and displays retrieved chunks
with relevance scores. Useful for validating RAG quality during development.

Usage:
    export AZURE_OPENAI_API_KEY="your-key"
    python -m src.asksplunk.cli.test_retrieval

Try example queries:
    - "bounce rate fields"
    - "how to track campaigns"
    - "recipient email address"
    - "delivery failures"
"""

import asyncio
import os
import sys

import chromadb
from openai import AsyncAzureOpenAI

from asksplunk.retriever.retriever import DocumentRetriever


async def main():  # noqa: C901
    """Run interactive retrieval testing.

    Prompts user for queries and displays retrieved chunks with relevance scores.
    Useful for validating RAG quality during development.
    """
    # Check for API key
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    if not api_key:
        print("Error: AZURE_OPENAI_API_KEY environment variable not set")
        print("\nUsage:")
        print('  export AZURE_OPENAI_API_KEY="your-api-key"')
        print("  python -m src.asksplunk.cli.test_retrieval")
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
        chunk_count = collection.count()
        print(f"✓ Connected to ChromaDB (collection has {chunk_count} chunks)")
    except Exception as e:
        print("Error: Collection 'campaign_prod_docs' not found")
        print(f"Details: {e}")
        print("\nRun indexer first:")
        print("  python -m src.asksplunk.indexer.indexer")
        sys.exit(1)

    # Initialize retriever
    retriever = DocumentRetriever(openai_client, chroma_client)

    # Interactive loop
    print("\n" + "=" * 70)
    print("Document Retrieval Test Tool")
    print("=" * 70)
    print("Enter queries to test retrieval (Ctrl+C or 'exit' to quit)")
    print("\nExample queries:")
    print('  - "bounce rate fields"')
    print('  - "how to track campaigns"')
    print('  - "recipient email address"')
    print('  - "delivery failures"')
    print()

    while True:
        try:
            # Prompt for query
            query = input("\nQuery: ").strip()

            # Check for exit
            if query.lower() in ["exit", "quit", "q"]:
                print("Exiting...")
                break

            if not query:
                continue

            # Retrieve documents
            print(f"\nRetrieving for: '{query}'...\n")
            docs = await retriever.retrieve(query, top_k=5)

            # Display results
            print(f"Found {len(docs)} chunks:\n")
            for i, doc in enumerate(docs, 1):
                print(f"{i}. [{doc['chunk_type']}] Score: {doc['relevance_score']:.3f}")
                print(f"   {doc['content'][:150]}...")

                # Show category if available
                if "category" in doc["metadata"]:
                    print(f"   Category: {doc['metadata']['category']}")

                print()

            print("-" * 70)

        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
        except Exception as e:
            print(f"\nError: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
