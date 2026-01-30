# Bravo Design Document (In Progress)

**Project:** Bravo - "Championing Our Data"
**Status:** Design Complete, Ready for Implementation
**Last Updated:** January 30, 2026
**Source:** Compiled from 23 Theo memories in `project:bravo` namespace

---

## 1. Project Overview

### 1.1 Goal
Help ICs log unrecorded work from Slack into Jira with minimal friction (under 1 minute).

### 1.2 Core Problem
Work in Slack doesn't surface in Jira. Solution: Poll Jira for watched assignees, detect incomplete tickets, DM engineer to add updates.

### 1.3 MVP Scope
MVP focuses on **NUDGE FLOW ONLY** (not create/update ticket flows).

Bravo is a **SCRIBE** that reduces friction - engineer talks, Bravo writes formatted Jira updates.

### 1.4 Three Core Flows (Full Vision)
1. **Create Ticket:** Slack message action → modal → Jira issue → thread+DM confirmation
2. **Update Ticket:** /bravo log or @bravo → modal → comment/field update
3. **Hygiene Nudge:** Nightly JQL scan → DM owner → "Fix now" modal → update Jira

### 1.5 MVP Definition
**MVP Done When:** Incomplete work nudges to update existing Jiras with user approval.

### 1.6 Tech Stack
- Slack + Jira only (Phase 1)
- AWS deployment
- Python + FastAPI (matches Ketchup)

### 1.7 MVP Tickets (9 total)
| Ticket | Description | Assignee | Status |
|--------|-------------|----------|--------|
| CPGNCX-63859 | Architecture + Auth | Maciej | IN PROGRESS |
| CPGNCX-63864 | Slack app foundation | Gary | Not Started |
| CPGNCX-63865 | Jira integration layer | Gary | Not Started |
| CPGNCX-63866 | Create Ticket flow | Gary | Not Started |
| CPGNCX-63877 | Update Ticket flow | Gary | Not Started |
| CPGNCX-63878 | Hygiene nudge | Mark | Not Started |
| CPGNCX-63879 | Deployment + ops | Mark | Not Started |
| CPGNCX-63891 | Missing work nudge | Maciej | Not Started |
| CPGNCX-63892 | Pilot rollout | Maciej | Not Started |

---

## 2. Architecture

### 2.1 Compute
- **Instance:** EC2 t3.xlarge (4 vCPU, 16GB RAM)
- **Rationale:** Separate from Ketchup, matches Ketchup sizing (discovered via AWS CLI query)
- **Storage:** EBS 250GB gp3
- **HA:** Single instance for MVP (upgrade to 2 for HA post-MVP)

### 2.2 Database
- **Engine:** PostgreSQL 16 in Docker container (on same EC2)
- **Volume:** Persistent Docker volume mapped to EC2 EBS
- **Backups:** Manual pg_dump to S3 (or snapshots of EBS volume)

### 2.3 Slack Integration
- **Mode:** Socket Mode (outbound WebSocket, no public endpoint needed)
- **Connection:** Bravo initiates connection to Slack

### 2.4 Services (2 containers + nginx)
| Service | Responsibility |
|---------|---------------|
| bravo-api | Handles Slack Socket Mode events |
| bravo-worker | Jira polling, LLM scoring, nudge sending |
| nginx | Reverse proxy (if needed for internal health checks) |

### 2.5 Deployment
- `./deploy` symlink to `infrastructure/deploy-bravo.sh` (Ketchup pattern)
- Manual docker-compose deployment via SSH
- `deploy-bravo.sh` script similar to Ketchup's `deploy-ketchup.sh`

### 2.6 AWS Configuration
- **Region:** eu-west-1 (same as Ketchup)
- **AWS Profile:** campaign_prod_v7 (same as Ketchup)

### 2.7 Estimated Cost
| Component | Monthly Cost |
|-----------|-------------|
| EC2 t3.xlarge | ~$120 |
| EBS 250GB gp3 | ~$25 |
| PostgreSQL (Docker) | $0 |
| **Total** | **~$145/month** |

*Note: RDS removed in favor of PostgreSQL in Docker for MVP. Can migrate to RDS later if needed.*

---

## 3. Data Model (PostgreSQL)

### 3.1 Tables

#### 3.1.1 watched_tickets
Main tracking table: ticket state, full snapshot (encrypted), nudge state, LLM scores.

#### 3.1.2 nudge_events
Audit log: every nudge sent, full message content, response, Jira comment posted.

#### 3.1.3 watched_assignees
Who we monitor + preferences (quiet hours, snooze defaults).

#### 3.1.4 project_configs
Per-project gate thresholds (G2 stale hours, G3 response hours, LLM threshold).

### 3.2 Key Design Decisions
- **Full snapshot storage** (summary, description, comments) - enables rich context without re-fetching
- **Store full message content** in nudge_events for audit trail
- **Per-user preferences from day 1** (quiet hours, default snooze time)
- **Per-project configurable thresholds** (different SLAs per project)
- **Encryption at rest** for ticket data (EBS volume encryption)

### 3.3 State Machine (watched_tickets.status)
```
ACQUIRED → ACTIVE → SNOOZED ↔ ACTIVE → RESOLVED (terminal)
```

### 3.4 Indexes
- status
- project
- assignee_jira_id
- snoozed_until (partial index)

---

## 4. Polling Design

### 4.1 JQL Query
```sql
project IN (CPGNCX, AMSE, CPGNREQ, CPGNPROV, CAMP, NEO, PLATIR, CPGNTT)
AND (assignee IN membersOf(ORG-VALLET-ALL) OR assignee IN membersOf(ORG-BRONSHTE-ALL) OR assignee IN membersOf(ORG-OMEARA-ALL))
AND resolution IS EMPTY
AND updated >= '{cursor}'
ORDER BY updated ASC
```

### 4.2 Configuration
| Setting | Value |
|---------|-------|
| Cursor | updatedDate timestamp, stored in poll_state table |
| Frequency | 60 minutes (24 polls/day) |
| Backfill | None - start tracking from first poll forward |
| Pagination | Fetch all pages (50 tickets/request) until exhausted |

### 4.3 Fields Fetched
```
key, summary, description, status, assignee, updated, created, comment,
project, issuetype, priority, labels, components
```

### 4.4 HTTP Client
- aiohttp with connection pooling (match Ketchup pattern)
- Exponential backoff on 429/5xx errors
- MAX_CONCURRENT_REQUESTS configurable

### 4.5 Poll Flow
1. Read last cursor from DB (or "now - 60 min" on first run)
2. Execute JQL with `updated >= cursor`
3. For each ticket:
   - **New:** INSERT into watched_tickets (status=ACQUIRED)
   - **Existing:** UPDATE snapshot, check gate violations
4. Store new cursor timestamp
5. Trigger nudge evaluation for gate failures

### 4.6 Volume Estimate
~35K tickets across orgs, but with cursor only fetches changes since last poll.

### 4.7 Jira-First Polling Model
**Core Loop:**
1. Poll Jira every N mins (15/30/60 configurable) for assignee IN (watched_list) AND unresolved
2. NEW ticket → Store as ACQUIRED, snapshot fields (summary, description, comments, customfields)
3. KNOWN ticket → Diff against last snapshot
4. No assignee activity since last check → Trigger NUDGE via Slack DM

---

## 5. Heuristic Gates

### 5.1 Gate Definitions (Pass/Fail)

| Gate | Name | Threshold | Description |
|------|------|-----------|-------------|
| G1 | Assignee Comment Exists | Boolean | At least 1 comment where author = assignee (exclude automation: Jarvis, JIRA Dynamics DX) |
| G2 | No Stale Ticket | 4 HOURS | Since last assignee comment (was G3 before renumbering) |
| G3 | Response Obligation | 24 HOURS | To reply to questions from others (was G4 before renumbering) |
| G4 | Resolution Comment | 24 HOURS | Within 24 hours of ticket closure (was G5 before renumbering) |

### 5.2 Automation Accounts to Exclude
- Jarvis Automation
- JIRA Dynamics DX
- Ketchup

---

## 6. LLM Scoring

### 6.1 Scoring Criteria (1-5 each)

| Criterion | Question |
|-----------|----------|
| Clarity | Would someone unfamiliar understand what happened? |
| Completeness | Is the full story told (problem → investigation → resolution)? |
| Root Cause | Is the underlying cause identified or hypothesized? |
| Actionability | Could this help prevent/solve future similar issues? |

### 6.2 Nudge Trigger
Average LLM score < 3/5 triggers a nudge for more detail.

### 6.3 Hybrid Approach Flow
1. Poll 8 projects for watched assignees
2. Run heuristic gates → failure = immediate nudge
3. Gates pass → run LLM scoring → score < 3 = nudge for more detail

---

## 7. Nudge Flow

### 7.1 Initial Nudge Contains
- Greeting
- Ticket key + full Jira link
- LLM-generated summary (3-4 bullets)
- Comment summary (who said what)
- Three buttons:
  - `[Yes, I have updates]`
  - `[No updates yet]`
  - `[Snooze dropdown: 1hr, 4hr, Tomorrow 9am]`

### 7.2 Snooze Behavior
In-place button replacement with `[Unsnooze]` option (like Ketchup CSOPM pattern).

### 7.3 "No Updates" Response
Acknowledge, check back in 4 hours (matches G2 threshold).

### 7.4 "Yes Updates" Flow
1. Prompt for freeform description
2. LLM formats into structured update with: findings, status, next steps
3. Preview with attribution "Posted by Bravo on behalf of @user"
4. Buttons: `[Post to Jira]` `[Edit]` `[Cancel]`

### 7.5 Edit Options
- `[Open editor]` modal
- `[Tell me what to change]` conversational re-prompt

### 7.6 Post Confirmation
Confirm success with `[View in Jira]` link, update internal state.

### 7.7 Nudge Conversation Flow Summary
```
Summarize ticket (4 bullets max from summary+description)
    ↓
Show comment summary (who said what)
    ↓
Ask: "Any progress to add?"
    ↓
NO → Track internally (don't spam Jira with "no news")
YES → Engineer describes work → Bravo formats → Engineer approves → Post to Jira
```

---

## 8. Configuration (FINAL)

### 8.1 Projects Watched
| Project Key |
|-------------|
| CPGNCX |
| AMSE |
| CPGNREQ |
| CPGNPROV |
| CAMP |
| NEO |
| PLATIR |
| CPGNTT |

### 8.2 Organization Groups
| Group |
|-------|
| ORG-VALLET-ALL |
| ORG-BRONSHTE-ALL |
| ORG-OMEARA-ALL |
| ORG-ADCAIN-ALL |

### 8.3 Assignees
**Derived automatically from Organization Groups via JQL `membersOf()`.**

No manual list required. The `watched_assignees` table is auto-populated when a user is first encountered, storing:
- Jira ID → Slack ID mapping (for DMs)
- Per-user preferences (quiet hours, snooze defaults)
- Nudge history tracking

### 8.4 Approach
Hybrid (Heuristics + LLM) from day 1.

### 8.5 Polling Frequency
Configurable: 15/30/60 mins (MVP: 60 mins).

---

## 9. API Contracts

### 9.1 Tech Stack
- Python + FastAPI (matches Ketchup)
- OpenAPI 3.1 spec at `docs/openapi.yaml`

### 9.2 API Categories (16 endpoints total)

#### 9.2.1 Health (2 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Basic health check |
| `/health/detailed` | GET | Detailed health with component status |

#### 9.2.2 Admin (5 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/stats` | GET | Dashboard metrics |
| `/admin/config` | GET | Get current configuration |
| `/admin/config` | PATCH | Runtime config changes |
| `/admin/poll/trigger` | POST | Manual poll for debugging |
| `/admin/logs` | GET | Recent logs access |

#### 9.2.3 Polling (2 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/polling/state` | GET | Get current poll state |
| `/polling/history` | GET | Get poll history |

#### 9.2.4 Tickets (4 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/tickets` | GET | List watched tickets |
| `/tickets/{ticket_key}` | GET | Get ticket details |
| `/tickets/{ticket_key}` | DELETE | Stop watching a ticket |
| `/tickets/{ticket_key}/evaluate` | POST | Manually evaluate ticket for nudge |

#### 9.2.5 Nudge (3 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/nudge` | GET | List nudge events |
| `/nudge/{nudge_id}` | GET | Get nudge event details |
| `/nudge/send` | POST | Manually send a nudge |

#### 9.2.6 Assignees (2 endpoints)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/assignees` | GET | List watched assignees |
| `/assignees/{jira_id}` | GET | Get assignee details |
| `/assignees/{jira_id}` | PATCH | Update assignee preferences |

### 9.3 Key Schemas

**Note:** Slack events arrive via Socket Mode (WebSocket), not HTTP endpoints. No REST API needed for Slack integration.

#### 9.3.1 TicketStatus
```
ACQUIRED → ACTIVE → SNOOZED ↔ ACTIVE → RESOLVED
```

#### 9.3.2 NudgeStatus
```
SENT → ACKNOWLEDGED/SNOOZED → RESPONDED → POSTED
```

#### 9.3.3 Gate Results
```json
{
  "g1_passed": boolean,
  "g2_passed": boolean,
  "g3_passed": boolean,
  "g4_passed": boolean
}
```

#### 9.3.4 LLM Scores
```json
{
  "clarity": 1-5,
  "completeness": 1-5,
  "root_cause": 1-5,
  "actionability": 1-5
}
```

### 9.4 OpenAPI Spec File
`/projects/bravo/docs/openapi.yaml`

---

## 10. Design Artifacts Created

| File | Description |
|------|-------------|
| `/projects/bravo/.gitignore` | Git ignore file |
| `/projects/bravo/docs/openapi.yaml` | OpenAPI 3.1 specification |
| `/projects/bravo/docs/complete_field_metadata_v2.json` | RAG source for Jira fields (gitignored, 30MB) |

---

## 11. Implementation Next Steps

1. Create project scaffolding (FastAPI + uv)
2. Set up database migrations (alembic)
3. Implement Jira poller service
4. Implement Slack Socket Mode handler
5. Implement gate evaluation logic
6. Implement LLM scoring
7. Implement nudge sending
8. Create Docker infrastructure
9. Deploy to EC2

---

## 12. Design Session History

### Session 1: Nudge Flow + Data Model
- Nudge flow completed and locked
- Key decisions: snooze with unsnooze (Ketchup pattern), LLM summary, preview before post, attribution line, edit via modal or conversational
- Data model design (PostgreSQL, 4 tables)

### Session 2: Architecture + Polling + API (January 30, 2026)
- Architecture - EC2 t3.xlarge, PostgreSQL in Docker, Socket Mode, 2 Docker services
- Polling design - 60-min JQL poll with membersOf groups, cursor-based incremental
- API contracts - FastAPI + OpenAPI spec with full admin API
- Gate numbering corrected G1/G2/G3/G4 (original G2 dropped, renumbered)
- JQL validated against live Jira (35K tickets found)
- EC2 instance type discovered via AWS CLI (matches Ketchup t3.xlarge)

---

## 13. Memory Graph Structure

Four core linked memories:
- **Overview** (9c9df9fc): MVP = Nudge flow only
- **Gates** (e3817289): G1, G2, G3, G4 (original G2 dropped as gameable)
- **LLM Scoring** (a2c005e3): Clarity, Completeness, Root Cause, Actionability - threshold <3/5
- **Config** (6ea5cb42): 8 projects, hybrid approach, assignees TBD

Valid relation types in Theo: `relates_to`, `supersedes`, `caused_by`, `contradicts`.

---

## 14. Resume Command

To resume Bravo design work:
```
/recall Bravo design session
```

---

*Document compiled from 23 Theo memories in `project:bravo` namespace.*
