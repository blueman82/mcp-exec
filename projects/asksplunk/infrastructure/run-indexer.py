#!/usr/bin/env python3
"""Standalone indexer script for deployment.

Checks if ChromaDB collection exists and indexes if missing.
Designed to be run inside the bot container.

Usage:
  python run-indexer.py           # Index only if collection is empty
  python run-indexer.py --force   # Clear collection and re-index
"""

import argparse
import asyncio
import json
import sys

sys.path.insert(0, "/app/src")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Index schema to ChromaDB")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-index by clearing existing collection",
    )
    return parser.parse_args()


async def run_indexer(force: bool = False):
    """Check collection and run indexer if needed."""
    import chromadb

    chroma_client = chromadb.HttpClient(host="localhost", port=8000)

    # Handle --force flag: delete existing collection
    if force:
        print("Force flag detected. Clearing existing collection...")
        try:
            chroma_client.delete_collection("campaign_prod_docs")
            print("Collection 'campaign_prod_docs' deleted.")
        except Exception as e:
            print(f"Collection deletion skipped (may not exist): {e}")

    # Check if collection exists
    try:
        collections = chroma_client.list_collections()
        collection_names = [c.name for c in collections]
        if "campaign_prod_docs" in collection_names:
            collection = chroma_client.get_collection("campaign_prod_docs")
            count = collection.count()
            if count > 0:
                print(f"Collection exists with {count} chunks. Skipping indexer.")
                return
    except Exception as e:
        print(f"Collection check failed: {e}")

    print("Collection not found or empty. Running indexer...")

    from asksplunk.secrets import SecretsManager
    from openai import AsyncAzureOpenAI

    async with SecretsManager() as sm:
        config = await sm.get_azure_openai_config()

    openai_client = AsyncAzureOpenAI(
        azure_endpoint=config["endpoint"],
        api_key=config["api_key"],
        api_version=config.get("api_version", "2024-02-15-preview"),
    )
    
    embedding_model = config.get("embedding_deployment", "text-embedding-ada-002")
    print(f"Using embedding deployment: {embedding_model}")

    with open("/app/docs/schema/campaign_prod_schema.json") as f:
        docs = json.load(f)

    print(f"Loaded: {docs['index_name']}")

    chunks = []
    field_count = sum(len(cat["fields"]) for cat in docs["field_categories"])

    # Overview chunk
    chunks.append(
        {
            "content": f"{docs['display_name']}: {docs['description']}. Contains {field_count} fields.",
            "chunk_type": "index_overview",
            "metadata": {"index_name": docs["index_name"], "field_count": field_count},
        }
    )

    # Field chunks
    for cat in docs["field_categories"]:
        for field in cat["fields"]:
            chunks.append(
                {
                    "content": f"Field: {field['name']} ({field['type']}). Category: {cat['category_name']}. {field['description']}. Found in: {', '.join(field['common_in'])}.",
                    "chunk_type": "field",
                    "metadata": {
                        "field_name": field["name"],
                        "field_type": field["type"],
                        "category": cat["category_name"],
                        "sourcetypes": ",".join(field["common_in"]),
                    },
                }
            )

    # Pattern chunks
    for p in docs["query_patterns"]:
        chunks.append(
            {
                "content": f"Query Pattern: {p['pattern_name']}. {p.get('description', p.get('use_case', ''))}. SPL: {p['spl_template']}",
                "chunk_type": "pattern",
                "metadata": {"pattern_name": p["pattern_name"], "fields_involved": ""},
            }
        )

    # Use case chunks
    for uc in docs.get("use_cases", []):
        pattern_ref = uc.get("pattern_reference") or ""
        chunks.append(
            {
                "content": f"Use Case: {uc['question']}. Fields: {', '.join(uc['fields_involved'])}. Pattern: {pattern_ref}.",
                "chunk_type": "use_case",
                "metadata": {
                    "question": uc["question"],
                    "fields_involved": ",".join(uc["fields_involved"]),
                    "pattern_reference": pattern_ref,
                },
            }
        )

    print(f"Created {len(chunks)} chunks")

    # Generate embeddings
    texts = [c["content"] for c in chunks]
    embeddings = []
    batch_size = 16
    total_batches = (len(texts) + batch_size - 1) // batch_size

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        batch_num = i // batch_size + 1
        print(f"Embedding batch {batch_num}/{total_batches}")
        resp = await openai_client.embeddings.create(
            input=batch, model=embedding_model
        )
        embeddings.extend([d.embedding for d in resp.data])

    print(f"Generated {len(embeddings)} embeddings")

    # Store in ChromaDB
    collection = chroma_client.get_or_create_collection(
        name="campaign_prod_docs", metadata={"description": "Adobe Campaign docs"}
    )

    ids = [f"chunk_{i}" for i in range(len(chunks))]
    metadatas = [c["metadata"] for c in chunks]

    collection.add(
        documents=texts, embeddings=embeddings, metadatas=metadatas, ids=ids
    )

    print(f"SUCCESS: Stored {collection.count()} chunks in ChromaDB")


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run_indexer(force=args.force))
