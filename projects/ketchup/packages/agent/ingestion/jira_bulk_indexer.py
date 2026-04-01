"""JIRA bulk indexer — indexes tickets from all 10 projects into ChromaDB for RCA Historian.

Fetches resolved/closed JIRA tickets from each project in VALID_JIRA_PROJECTS, formats
them into multiple embeddable documents (ticket summary, optional RCA doc, per-comment),
and stores them with deterministic IDs for idempotent re-runs.

After all projects are indexed, a second pass follows issuelinks and indexes any linked
tickets that were not already seen.

Env vars:
    KETCHUP_JIRA_INDEX_MONTHS (default "6") — default lookback window in months
    KETCHUP_JIRA_INDEX_MONTHS_CSOPM (default "12") — CSOPM-specific override
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from packages.core.jira_constants import VALID_JIRA_PROJECTS
from packages.core.logging import setup_logger

logger = setup_logger(__name__)

EMBEDDING_BATCH_SIZE = 16
INTER_BATCH_DELAY = 0.5  # seconds between embedding batches — matches existing pattern
TICKETS_PER_PAGE = 50

BOT_AUTHORS = [
    "jiradydx",
    "jira dynamics dx",
    "monserv",
    "jarvis",
    "jarvis automation",
    "snowjira",
    "jira project auto-assigner",
    "agent nexus jira prod user",
    "ketchup",
]

# All custom fields requested on every search call
_BULK_FIELDS = [
    "summary",
    "status",
    "assignee",
    "reporter",
    "priority",
    "resolution",
    "issuetype",
    "description",
    "created",
    "updated",
    "components",
    "issuelinks",
    "comment",
    "customfield_34000",  # RCA Description
    "customfield_33712",  # Corrective Actions
    "customfield_14804",  # CSO Summary
    "customfield_16201",  # Business Impact
    "customfield_29901",  # Root Cause Resolution
    "customfield_10407",  # Workaround Instructions
    "customfield_18012",  # Reproducible Steps
    "customfield_27305",  # Findings
    "customfield_15709",  # Issue Category
    "customfield_25700",  # Type of Problem
    "customfield_33706",  # RCA Category (cascading)
    "customfield_15601",  # Root Cause Enum
    "customfield_33704",  # CSO Severity
    "customfield_15901",  # Severity from CC
    "customfield_15900",  # Priority from CC
    "customfield_10803",  # Customer Name (option 1)
    "customfield_30000",  # Customer Name (option 2)
]


def _nested_get(data: dict, *keys: str) -> str | None:
    """Safely traverse nested dicts, returning the final value as a string or None."""
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    if current is None:
        return None
    return str(current)


class JiraBulkIndexer:
    """Bulk-indexes JIRA tickets from all configured projects into ChromaDB.

    Designed for the RCA Historian feature. Idempotent — deterministic doc IDs
    allow safe re-runs that overwrite stale data rather than creating duplicates.
    """

    def __init__(self, embeddings_client: Any, vector_store: Any, mcp_client: Any) -> None:
        """
        Args:
            embeddings_client: AzureEmbeddingsClient for computing embeddings.
            vector_store: ChromaVectorStore for storing documents.
            mcp_client: AsyncMCPClient for JIRA API calls.
        """
        self._embeddings_client = embeddings_client
        self._vector_store = vector_store
        self._mcp_client = mcp_client

    async def index_all_projects(self) -> dict[str, dict[str, int]]:
        """Index resolved/closed tickets from all 10 JIRA projects.

        Returns:
            Summary dict: {project: {tickets: N, documents: N, linked: N}}
        """
        default_months = int(os.environ.get("KETCHUP_JIRA_INDEX_MONTHS", "6"))
        csopm_months = int(os.environ.get("KETCHUP_JIRA_INDEX_MONTHS_CSOPM", "12"))

        summary: dict[str, dict[str, int]] = {}
        # Maps ticket_key -> fields dict for the link-following pass
        indexed_fields: dict[str, dict[str, Any]] = {}

        for project in VALID_JIRA_PROJECTS:
            months = csopm_months if project == "CSOPM" else default_months
            days = months * 30  # JIRA JQL uses -Nd (days), not -Nm (months not supported)
            jql = (
                f"project = {project} AND status IN (Resolved, Closed, Complete, Done) "
                f"AND created >= -{days}d ORDER BY updated DESC"
            )
            tickets_indexed, docs_stored = await self._index_project(project, jql, indexed_fields)
            summary[project] = {"tickets": tickets_indexed, "documents": docs_stored, "linked": 0}
            logger.info(
                "Project %s complete: %d tickets, %d documents",
                project,
                tickets_indexed,
                docs_stored,
            )

        linked_count = await self._index_linked_tickets(set(indexed_fields.keys()), indexed_fields)
        # Attribute linked tickets to a synthetic "linked" bucket in the summary
        for project in summary:
            summary[project]["linked"] = 0
        summary["_linked"] = {"tickets": linked_count, "documents": 0, "linked": linked_count}

        logger.info(
            "Bulk indexing complete: %d projects, %d linked tickets additionally indexed",
            len(VALID_JIRA_PROJECTS),
            linked_count,
        )
        return summary

    async def _index_project(
        self,
        project: str,
        jql: str,
        indexed_fields: dict[str, dict[str, Any]],
    ) -> tuple[int, int]:
        """Paginate through a JQL query and index all matching tickets.

        Args:
            project: The JIRA project key (for logging).
            jql: Full JQL query string.
            indexed_fields: Shared dict updated with each processed ticket.

        Returns:
            (tickets_indexed, documents_stored)
        """
        tickets_indexed = 0
        docs_stored = 0
        start_at = 0

        while True:
            try:
                result = await self._mcp_client.search_issues(
                    jql=jql,
                    fields=_BULK_FIELDS,
                    max_results=TICKETS_PER_PAGE,
                    start_at=start_at,
                )
            except Exception as exc:
                logger.error("Search failed for %s at offset %d: %s", project, start_at, exc)
                break

            issues = result.get("issues", [])
            total = result.get("total", 0)

            if not issues:
                break

            # Collect comments for all tickets in this page concurrently
            comment_tasks = {
                issue["key"]: self._mcp_client.get_issue_comments(issue["key"]) for issue in issues
            }
            comment_results = await asyncio.gather(*comment_tasks.values(), return_exceptions=True)
            comments_by_key: dict[str, list[dict[str, Any]]] = {}
            for key, res in zip(comment_tasks.keys(), comment_results):
                comments_by_key[key] = res if isinstance(res, list) else []

            # Format all documents from this page
            page_documents: list[dict[str, Any]] = []
            for issue in issues:
                ticket_key = issue["key"]
                fields = issue.get("fields", {})
                indexed_fields[ticket_key] = fields

                ticket_docs = self._format_ticket_documents(
                    ticket_key,
                    fields,
                    comments_by_key.get(ticket_key, []),
                )
                page_documents.extend(ticket_docs)

            stored = await self._embed_and_store(page_documents)
            tickets_indexed += len(issues)
            docs_stored += stored

            logger.info(
                "Indexed %d/%d tickets for %s (stored %d docs this page)",
                tickets_indexed,
                total,
                project,
                stored,
            )

            if start_at + len(issues) >= total:
                break
            start_at += len(issues)

        return tickets_indexed, docs_stored

    async def _index_linked_tickets(
        self,
        already_indexed: set[str],
        indexed_fields: dict[str, dict[str, Any]],
    ) -> int:
        """Follow issuelinks from indexed tickets and index any unseen ones.

        Args:
            already_indexed: Set of ticket keys already in the vector store.
            indexed_fields: Fields dicts from the primary indexing pass.

        Returns:
            Count of additionally indexed tickets.
        """
        linked_keys = {
            key
            for fields in indexed_fields.values()
            for link in fields.get("issuelinks", [])
            for direction in ("inwardIssue", "outwardIssue")
            if (key := link.get(direction, {}).get("key")) and key not in already_indexed
        }

        if not linked_keys:
            logger.info("No unindexed linked tickets found")
            return 0

        logger.info("Following %d linked tickets not yet indexed", len(linked_keys))

        all_docs: list[dict[str, Any]] = []
        fetched = 0
        for key in linked_keys:
            try:
                result = await self._mcp_client.search_issues(
                    jql=f'key = "{key}"',
                    fields=_BULK_FIELDS,
                    max_results=1,
                )
                issues = result.get("issues", [])
                if not issues:
                    continue
                issue = issues[0]
                fields = issue.get("fields", {})
                comments = await self._mcp_client.get_issue_comments(key)
                ticket_docs = self._format_ticket_documents(key, fields, comments)
                all_docs.extend(ticket_docs)
                fetched += 1
            except Exception as exc:
                logger.warning("Failed to fetch linked ticket %s: %s", key, exc)

        if all_docs:
            await self._embed_and_store(all_docs)

        logger.info("Linked ticket indexing complete: %d tickets indexed", fetched)
        return fetched

    def _format_ticket_documents(
        self,
        ticket_key: str,
        fields: dict[str, Any],
        comments: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Format a JIRA ticket and its comments into embeddable documents.

        Creates:
          - 1 ticket summary document (always)
          - 1 RCA document (CSOPM tickets only, when RCA Description is present)
          - N comment documents (one per non-bot comment)

        Args:
            ticket_key: JIRA issue key e.g. "CSOPM-1234".
            fields: The issue fields dict from the API response.
            comments: List of comment dicts from get_issue_comments.

        Returns:
            List of document dicts with keys: id, text, metadata.
        """
        documents: list[dict[str, Any]] = []
        now = int(time.time())
        project_key = ticket_key.split("-")[0]

        status = _nested_get(fields, "status", "name") or "Unknown"
        priority = _nested_get(fields, "priority", "name") or "Unknown"
        resolution = _nested_get(fields, "resolution", "name") or "Unresolved"
        assignee = _nested_get(fields, "assignee", "displayName") or "Unassigned"
        summary = fields.get("summary", "")
        description = (fields.get("description") or "")[:4000]

        # -- Document 1: Ticket summary --
        ticket_text = (
            f"[JIRA:{ticket_key}] Status: {status} | Priority: {priority} | "
            f"Resolution: {resolution} | Assignee: {assignee}\n"
            f"Summary: {summary}\n"
            f"Description: {description}"
        )

        custom_sections = [
            ("customfield_34000", "RCA Description", 6000),
            ("customfield_33712", "Corrective Actions", 4000),
            ("customfield_14804", "CSO Summary", 2000),
            ("customfield_16201", "Business Impact", 2000),
            ("customfield_29901", "Root Cause Resolution", 4000),
            ("customfield_10407", "Workaround Instructions", 2000),
            ("customfield_18012", "Reproducible Steps", 2000),
            ("customfield_27305", "Findings", 2000),
        ]
        for field_id, label, limit in custom_sections:
            value = fields.get(field_id)
            if value and isinstance(value, str) and value.strip():
                ticket_text += f"\n{label}: {value[:limit]}"

        base_metadata = _build_metadata(ticket_key, project_key, fields, now)

        documents.append(
            {
                "id": f"jira_bulk:{ticket_key}:summary",
                "text": ticket_text,
                "metadata": {**base_metadata, "jira_doc_type": "ticket"},
            }
        )

        # -- Document 2: RCA document (CSOPM only) --
        rca_description = fields.get("customfield_34000")
        if project_key == "CSOPM" and rca_description and isinstance(rca_description, str):
            corrective = (fields.get("customfield_33712") or "")[:4000]
            cso_summary = (fields.get("customfield_14804") or "")[:2000]
            rca_text = (
                f"[JIRA:{ticket_key}:rca] RCA Analysis\n"
                f"{rca_description[:6000]}\n"
                f"Corrective Actions: {corrective}\n"
                f"CSO Summary: {cso_summary}"
            )
            documents.append(
                {
                    "id": f"jira_bulk:{ticket_key}:rca",
                    "text": rca_text,
                    "metadata": {**base_metadata, "jira_doc_type": "rca"},
                }
            )

        # -- Documents 3+: Comments --
        for comment in comments:
            comment_id = comment.get("id", "unknown")
            author_raw = comment.get("author", {})
            author_name = (
                author_raw.get("displayName", "")
                if isinstance(author_raw, dict)
                else str(author_raw)
            )
            body = (comment.get("body") or "").strip()
            created = comment.get("created", "")

            if not body:
                continue
            if any(bot in author_name.lower() for bot in BOT_AUTHORS):
                continue

            comment_text = f"[JIRA:{ticket_key}:comment] {author_name} ({created}): {body[:4000]}"
            documents.append(
                {
                    "id": f"jira_bulk:{ticket_key}:c:{comment_id}",
                    "text": comment_text,
                    "metadata": {**base_metadata, "jira_doc_type": "comment"},
                }
            )

        return documents

    async def _embed_and_store(self, documents: list[dict[str, Any]]) -> int:
        """Embed a list of documents in batches and store them in the vector store.

        Args:
            documents: Documents with id, text, metadata keys.

        Returns:
            Number of documents stored.
        """
        if not documents:
            return 0

        texts = [d["text"] for d in documents]
        all_embeddings: list[list[float]] = []

        batches = [
            texts[i : i + EMBEDDING_BATCH_SIZE] for i in range(0, len(texts), EMBEDDING_BATCH_SIZE)
        ]
        for batch_idx, batch in enumerate(batches):
            embeddings = await self._embeddings_client.embed_texts(batch)
            all_embeddings.extend(embeddings)
            if batch_idx < len(batches) - 1:
                await asyncio.sleep(INTER_BATCH_DELAY)

        await self._vector_store.add_documents(documents, all_embeddings)
        return len(documents)


def _build_metadata(
    ticket_key: str,
    project_key: str,
    fields: dict[str, Any],
    ingested_at: int,
) -> dict[str, Any]:
    """Build the shared metadata dict for all documents from a ticket.

    Args:
        ticket_key: JIRA issue key.
        project_key: Extracted project prefix.
        fields: Raw fields dict from the API.
        ingested_at: Unix timestamp of ingestion.

    Returns:
        Metadata dict (jira_doc_type is added by the caller).
    """
    components_list = fields.get("components") or []
    components = ",".join(
        c["name"] for c in components_list if isinstance(c, dict) and c.get("name")
    )

    # Customer name: try customfield_10803 (plain string) then customfield_30000 (nested)
    customer_name = (
        fields.get("customfield_10803") or _nested_get(fields, "customfield_30000", "value") or ""
    )

    # RCA Category is a cascading select — join parent + child
    rca_raw = fields.get("customfield_33706")
    rca_category = ""
    if isinstance(rca_raw, dict):
        parent = rca_raw.get("value", "")
        child_raw = rca_raw.get("child", {})
        child = child_raw.get("value", "") if isinstance(child_raw, dict) else ""
        rca_category = f"{parent}/{child}" if child else parent

    def _select_value(field_id: str) -> str:
        val = fields.get(field_id)
        if isinstance(val, dict):
            return val.get("value", "")
        return ""

    return {
        "source": "jira_bulk",
        "jira_ticket_id": ticket_key,
        "jira_project": project_key,
        "ingested_at": ingested_at,
        "issue_category": _select_value("customfield_15709"),
        "type_of_problem": _select_value("customfield_25700"),
        "rca_category": rca_category,
        "root_cause_enum": _select_value("customfield_15601"),
        "cso_severity": _select_value("customfield_33704"),
        "severity_from_cc": _select_value("customfield_15901"),
        "priority_from_cc": _select_value("customfield_15900"),
        "customer_name": str(customer_name) if customer_name else "",
        "components": components,
        "resolution": _nested_get(fields, "resolution", "name") or "",
        "issuetype": _nested_get(fields, "issuetype", "name") or "",
    }
