# JIRA Indexing Schema for RCA Historian

**Date**: 2026-03-31
**Status**: Design — informs RCA Historian implementation in feat/rca-historian branch

## Context

The RCA Historian needs cross-project JIRA search to find similar past incidents. Currently, `jira_backfill.py` only indexes per-channel (the ticket associated with a specific Slack channel). This schema defines what fields to bulk-index into ChromaDB across all 10 JIRA projects Ketchup monitors.

Research was conducted by querying actual tickets from each project via corp-jira MCP.

---

## Project Priority for Indexing

| Priority | Project | Resolved Tickets | RCA Value | Why |
|---|---|---|---|---|
| **1st** | CSOPM | 67,889 | Critical | Structured RCA fields: root cause, corrective actions, timelines, service paths |
| **2nd** | NEO | 71,588 | High | Rich technical descriptions with logs, error codes, stack traces |
| **3rd** | CPGNREQ | 123,661 | High | Structured problem descriptions + human investigation comments |
| **4th** | PLATIR | 46,343 | High | Only project with structured Root Cause enum (customfield_15601) |
| **5th** | CPGNPROV | 17,753 | Medium | Provisioning requests — resolution steps in comments |
| **6th** | CPGNCX | 18,040 | Medium | Ops knowledge capture — Slack transcript style |
| **7th** | CAMP | 44,437 | Medium | Product bugs — deeper engineering context |
| **8th** | AMSE | 29,666 | Medium | Managed services — migration + infrastructure |
| **9th** | CPGNCC | 2,683 | Low | 75% bot noise (Jarvis alerts), thin human content |
| **10th** | CPGNTT | 62,002 | Low | 85% bot noise, best for aggregate patterns only |

**Recommended initial scope**: CSOPM + NEO + CPGNREQ (top 3, ~262K tickets, ~1.8M docs, ~12GB)

---

## Fields to Embed (ChromaDB document text)

| Field | ID | Projects | Truncation | Notes |
|---|---|---|---|---|
| summary | standard | All | None (~200 chars) | Always present |
| description | standard | All | 4,000 chars | Increase from 2K — NEO/CPGNREQ descriptions are rich |
| RCA Description | customfield_34000 | CSOPM (primary) | 6,000 chars | Structured: executive summary + timeline + root cause |
| Corrective Actions | customfield_33712 | CSOPM | 4,000 chars | Action items with linked JIRAs |
| CSO Summary | customfield_14804 | CSOPM | 2,000 chars | Executive impact statement |
| Business Impact | customfield_16201 | PLATIR | 2,000 chars | Free-text impact narrative |
| Root Cause Resolution | customfield_29901 | Cross-project | 4,000 chars | Actual fix description — when populated, most directly useful for "what fixed it" |
| Workaround Instructions | customfield_10407 | CPGNREQ | 2,000 chars | Immediate remediation steps |
| Reproducible Steps | customfield_18012 | CPGNREQ | 2,000 chars | Symptom description — what similarity search matches on |
| Findings | customfield_27305 | CAMP | 2,000 chars | Investigation conclusions |
| Human comments | standard | All | 4,000 chars/comment | Increase from 2K — some 10K+ investigation details |
| resolution | standard | All | None | "Fixed", "Won't Fix" etc. |

---

## Fields to Store as Metadata (filterable, not embedded)

| Field | ID | Projects | Use |
|---|---|---|---|
| Issue Category | customfield_15709 | CPGNREQ | Filter: "SFTP Issues", "Deliveries - Error" |
| Type of Problem | customfield_25700 | NEO | Filter: "Database", "Configuration" |
| RCA Category | customfield_33706 | CSOPM | Filter: "Architecture - Back End > Database" |
| Root Cause (enum) | customfield_15601 | PLATIR | Filter: "Bug", "Eng/Backend correction" |
| CSO Severity | customfield_33704 | CSOPM | Filter: "Sev 1", "Sev 2" |
| Priority from CC | customfield_15900 | CPGNREQ, CPGNTT, CPGNPROV, PLATIR | Filter: "P1 - Relationship is at risk", "P2 - Relationship affected" |
| Severity from CC | customfield_15901 | CPGNREQ, CPGNTT, CPGNPROV, PLATIR | Filter: "S1 - Services unavailable", "S2 - Significantly degraded" |
| Customer Name | customfield_10803 / customfield_30000 | All | Filter by customer |
| Customer ID (IMS Org) | customfield_29900 | Cross-project | Unique customer identifier for cross-ticket correlation |
| Support Tickets | customfield_10802 | Cross-project | Cross-reference to Exigence E-numbers |
| Customers Impacted | customfield_14803 | CAMP | Impact scope |
| Severity (standalone) | customfield_15700 | Cross-project | Different from Severity from CC — internal severity rating |
| Escalation Level | customfield_35300 | CPGNREQ | Incident escalation path |
| RCA Status | customfield_30801 | CSOPM | "RCA found - Permanent fix available" vs "RCA not found" |
| Solution (product) | customfield_17100 | PLATIR | Required product area: "AJO", "RTCDP", "AEP" |
| Product Area | customfield_15325 | PLATIR | Product taxonomy |
| Type of Request | customfield_29601 | PLATIR | "Bug" vs other classifications |
| Instance URL | customfield_22302 | CPGNREQ, CPGNPROV | Identifies which server — pattern matching |
| Remediation Date | customfield_22902 | CSOPM | When the fix was applied |
| Service Path | customfield_38301 | CSOPM | Filter: "ACC Email Execution" |
| Regression | customfield_14301 | NEO | Flag: yes/no |
| Recurring | customfield_33710 | CSOPM | Flag: yes/no |
| Impact Start/End | customfield_25904 / customfield_25905 | CSOPM | Duration calculation |
| components | standard | All | Product area signal |
| labels | standard | All (filter SLA labels in PLATIR) | Categorization |
| project | standard | All | Project key for filtering |
| issuetype | standard | All | "CSO RCA", "Bug", "Customer Request" |
| created/updated/resolved | standard | All | Time-range queries |

---

## Fields to Skip

| Field | ID | Why |
|---|---|---|
| Rank | customfield_15200, customfield_39738 | Internal sorting values |
| Dev Status | customfield_30400 | Bitbucket PR metadata blob |
| SLA Timer/Start | customfield_11902, customfield_11901 | Encoded timer strings |
| Sprint | customfield_11002 | Workflow metadata |
| Contract dates | customfield_18028, customfield_18029 | Business metadata |
| Localization fields | customfield_27200, customfield_31800, customfield_35400-35402 | CAMP only, noise |

---

## Bot Comment Filtering

All bot comments should be skipped during indexing. Update `jira_data_extractor.py` bot list as part of the RCA Historian PR (feat/rca-historian branch).

| Bot Author (displayName) | Projects | Content | Action |
|---|---|---|---|
| **ketchup Generic** | All (Ketchup posts to) | AI-generated incident summaries | **Skip** — re-indexing our own output creates feedback loop |
| jiradydx / JIRA Dynamics DX | CPGNREQ, NEO, PLATIR | "Dynamics CRM is Watching this ticket" (48 chars) | Skip |
| jarvis / Jarvis Automation | CPGNTT, CPGNCC | JSON metadata, Rundeck links, automation | Skip |
| monserv | CPGNTT | Automated monitoring updates | Skip |
| snowjira | CSOPM | RCA instruction templates | Skip |
| JIRA Project Auto-Assigner | CPGNPROV | Assignment notifications | Skip |
| Agent Nexus Jira Prod User | PLATIR | AutoCloserBot messages | Skip |

**Current bot list** (`jira_data_extractor.py:189`): `["jiradydx", "monserv", "jarvis"]`

**Expanded list for RCA indexer** (in the feat/rca-historian PR):
```python
BOT_AUTHORS = [
    "jiradydx", "jira dynamics dx",
    "monserv",
    "jarvis", "jarvis automation",
    "snowjira",
    "jira project auto-assigner",
    "agent nexus jira prod user",
    "ketchup",  # Our own AI-generated summaries — prevent feedback loop
]
```

Match using: `author_name.lower()` contains any bot substring.

---

## Chunking Strategy

| Document Type | Content | Est. Size | Doc ID Pattern |
|---|---|---|---|
| Ticket summary | summary + description + resolution + classification fields | 500-5,000 chars | `{project}:{ticket_key}:summary` |
| RCA document (CSOPM) | RCA Description + Corrective Actions + CSO Summary | 2,000-12,000 chars | `{project}:{ticket_key}:rca` |
| Comment (per human) | Author + timestamp + body | 100-4,000 chars | `{project}:{ticket_key}:c:{comment_id}` |

---

## Storage Estimates

| Scope | Tickets | Total Docs | Storage |
|---|---|---|---|
| Top 3 (CSOPM + NEO + CPGNREQ) | ~262K | ~1.8M | ~12GB |
| All 10 projects | ~422K | ~2.9M | ~20GB |

**Embedding cost** (ada-002, one-time): ~$58 for all projects, ~$25 for top 3.

---

## Key Finding

**RCA Description (customfield_34000) is only reliably populated in CSOPM.** In all other projects, RCA-valuable content lives in human comments, not structured fields. The indexing strategy must prioritize comment quality (longer truncation, better bot filtering) over field completeness.

**PLATIR is uniquely valuable** for its `customfield_15601` (Root Cause enum) — the only project with structured root cause classification on nearly every ticket.
