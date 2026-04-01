#!/usr/bin/env python3
"""One-off script to run the JIRA bulk indexer locally.

Usage:
    cd projects/ketchup
    AWS_PROFILE=campaign_prod_v7 uv run scripts/run_jira_indexer.py

    # Override time windows:
    KETCHUP_JIRA_INDEX_MONTHS=1 KETCHUP_JIRA_INDEX_MONTHS_CSOPM=1 uv run scripts/run_jira_indexer.py

    # Single project only:
    uv run scripts/run_jira_indexer.py --project CSOPM

    # Dry run (count tickets only, no embedding):
    uv run scripts/run_jira_indexer.py --dry-run

Requires:
    - uv sync (project dependencies installed)
    - AWS credentials (for Secrets Manager)
    - MCP JIRA service running (docker-compose.local.yml)
    - ChromaDB running (docker-compose.local.yml)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import packages.core.jira_constants as jc
from packages.agent.embeddings.azure_embeddings_client import AzureEmbeddingsClient
from packages.agent.embeddings.vector_store import ChromaVectorStore
from packages.agent.ingestion.jira_bulk_indexer import JiraBulkIndexer
from packages.core.jira_constants import VALID_JIRA_PROJECTS
from packages.core.logging import setup_logger
from packages.integrations.async_ims_token_manager import AsyncIMSTokenManager
from packages.integrations.async_mcp_client import AsyncMCPClient
from packages.secrets.manager import SecretsManager

logger = setup_logger("run_jira_indexer")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run JIRA bulk indexer")
    parser.add_argument(
        "--project",
        choices=VALID_JIRA_PROJECTS,
        help="Index a single project only (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch tickets but skip embedding and storage",
    )
    args = parser.parse_args()

    months = int(os.environ.get("KETCHUP_JIRA_INDEX_MONTHS", "1"))
    csopm_months = int(os.environ.get("KETCHUP_JIRA_INDEX_MONTHS_CSOPM", "1"))

    logger.info("=== JIRA Bulk Indexer ===")
    logger.info("Index window: %s months (CSOPM: %s months)", months, csopm_months)
    logger.info("Projects: %s", args.project or "all")
    logger.info("Dry run: %s", args.dry_run)

    # Resolve secrets
    secrets = SecretsManager()

    # Init MCP client
    mcp_base_url = os.environ.get("MCP_JIRA_URL", "http://localhost:8081")

    token_manager = AsyncIMSTokenManager(secrets_manager=secrets)
    mcp_client = AsyncMCPClient(base_url=mcp_base_url, token_manager=token_manager)

    if args.dry_run:
        # Dry run: just count tickets per project
        logger.info("--- DRY RUN: counting tickets only ---")
        for project in ([args.project] if args.project else VALID_JIRA_PROJECTS):
            m = csopm_months if project == "CSOPM" else months
            days = m * 30
            jql = (
                f"project = {project} AND status IN (Resolved, Closed, Complete, Done) "
                f"AND created >= -{days}d ORDER BY updated DESC"
            )
            try:
                result = await mcp_client.search_issues(jql=jql, fields=["summary"], max_results=1)
                total = result.get("total", 0)
                logger.info("  %s: %d tickets in last %s months", project, total, m)
            except Exception as exc:
                logger.error("  %s: FAILED - %s", project, exc)
        await mcp_client.cleanup()
        return

    # Init embeddings client
    embeddings_client = AzureEmbeddingsClient(secrets_manager=secrets)
    await embeddings_client.initialize()

    # Init vector store
    vector_store = ChromaVectorStore()
    await vector_store.initialize()

    # Build indexer
    indexer = JiraBulkIndexer(
        embeddings_client=embeddings_client,
        vector_store=vector_store,
        mcp_client=mcp_client,
    )

    # If single project, temporarily override VALID_JIRA_PROJECTS

    original_projects = jc.VALID_JIRA_PROJECTS
    if args.project:
        jc.VALID_JIRA_PROJECTS = [args.project]

    start = time.time()
    try:
        summary = await indexer.index_all_projects()
    finally:
        jc.VALID_JIRA_PROJECTS = original_projects

    elapsed = time.time() - start

    # Print results
    logger.info("=== Indexing Complete (%.1fs) ===", elapsed)
    total_tickets = 0
    total_docs = 0
    for project, stats in summary.items():
        logger.info(
            "  %s: %d tickets, %d documents, %d linked",
            project,
            stats["tickets"],
            stats["documents"],
            stats["linked"],
        )
        total_tickets += stats["tickets"]
        total_docs += stats["documents"]

    logger.info("Total: %d tickets, %d documents", total_tickets, total_docs)

    # Verify ChromaDB count
    doc_count = await vector_store.get_document_count()
    logger.info("ChromaDB total document count: %d", doc_count)

    # Cleanup
    await embeddings_client.cleanup()
    await mcp_client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
