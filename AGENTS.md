# AGENTS.md — Meta-MCP LLM Wiki Schema

## Wiki location

**Vault**: `/Users/harrison/Documents/Github/camp-ops-emea/projects/meta-mcp-server-wiki/`

**Raw sources** (immutable): This repo — `packages/`, `extension/`, `docs/`. Read for truth; do not edit the wiki when changing product code unless the task is explicitly wiki maintenance.

## Three layers

1. **Raw sources**: Codebase and official docs in `meta-mcp-server/`.
2. **The wiki**: Markdown in the vault path above. The LLM creates and updates pages, cross-links, and the log.
3. **This file**: Single schema for structure, conventions, and ingest/query/lint workflows. Do not copy this file into the vault.

## Page types

| Type | Directory | Purpose |
|------|-----------|---------|
| concept | `concepts/` | Cross-cutting patterns, request flows, token/pooling ideas |
| package | `packages/` | One page per npm workspace package (`core`, `mcp-exec`) |
| extension | `extension/` | VS Code/Cursor extension structure and key surfaces |
| investigation | `investigations/` | Durable answers filed back from chat (queries, RCAs, decisions) |
| source | `sources/` | Summaries of ingested PRs, articles, or external writeups |

Shared folders: `templates/` (skeletons), `assets/` (charts, images).

## Page format

Every page has YAML frontmatter:

- `title`, `type`, `created`, `last_updated`, `sources`, `tags`

Body uses `[[wiki-links]]` to related pages. Flag contradictions inline:

`> ⚠️ CONTRADICTION: ...`

Aim for under ~2 minutes read; one main idea per page unless it is an index-style page.

## Operations

### Ingest

1. Read the new source (diff, doc, article).
2. Note only what is **new and non-obvious** relative to existing wiki pages.
3. Add or update `sources/<name>.md` when ingesting a discrete artifact.
4. Update affected concept/package/extension pages and cross-links (often many files).
5. Update [[index.md]].
6. Append to [[log.md]] with prefix `## [YYYY-MM-DD] ingest | …` (or `query |`, `lint |`, `maintenance |`).

### Query

1. Read [[index.md]] first.
2. Open linked pages; synthesize with citations to wiki paths.
3. If the wiki is silent, read the codebase or `docs/`, then optionally **file** non-obvious findings under `investigations/`.

### Lint

When the user asks: check contradictions, stale `last_updated`, orphan pages (no inbound `[[links]]`), missing pages for major concepts, weak cross-references, and gaps that need new sources or code reading.

## Conventions

- Tags: lowercase, hyphenated (e.g. `mcp`, `pool`, `mcp-exec`).
- Prefer linking to a canonical page over duplicating long explanations.
- Do not automate lint or silent bulk ingest; the human directs emphasis early on.

## Evolution

Adjust this schema as the project and wiki grow; update [[index.md]] when page types or workflows change.
