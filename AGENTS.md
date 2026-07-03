# AGENTS.md — Wiki Schema for mcp-exec

## Wiki location

`/Users/harrison/Github/mcp-exec-wiki/`

## Three layers

1. **Raw sources** — immutable input: the `mcp-exec` codebase, git history, commits/PRs,
   `docs/ARCHITECTURE.md`. Read from these but never modify the wiki when modifying code.
2. **Wiki** — LLM-maintained markdown at the vault path above. Claude owns this entirely —
   creates pages, updates cross-references, maintains consistency.
3. **Schema** — this file. Defines conventions and workflows, co-evolved with Gary over time.

## Page types

| Directory | Purpose |
|-----------|---------|
| `architecture/` | System components, wiring, request flow |
| `config/` | servers.json, Claude Code registration, env vars, path conventions |
| `investigations/` | Filed-back answers to Gary's queries |
| `sources/` | Ingested commit/session change records |
| `templates/` | Page skeletons — copy, don't edit |

## Page format

```yaml
---
title: ""
type: architecture | config | investigation | source
created: YYYY-MM-DD
last_updated: YYYY-MM-DD
sources: []   # file paths or URLs consulted
tags: []
---
```

Body: concise (under 2 min to read). Use `[[wiki-links]]` for cross-references. Facts and
relationships only — no narrative padding.

## Workflows

### Ingest (a commit lands, a decision is made, a change is worth recording)
Trigger: Gary says "ingest this", "add to wiki", "document this in the wiki", or a commit/PR
merges that changes architecture, config, or established behaviour.
1. Read the commit/PR diff and any session context in full.
2. Update existing wiki pages that relate to it (add cross-refs, correct stale facts).
3. Create a new `sources/YYYY-MM-DD-slug.md` page recording what changed.
4. Append an entry to `log.md`.
5. Update `index.md` if new pages were added.

### Query (Gary asks a question about the project)
1. Read `index.md` first.
2. Read relevant pages.
3. Answer from the wiki; if the answer required non-trivial synthesis, file it back as
   `investigations/YYYY-MM-DD-slug.md`.
4. Update `index.md` if a new investigations page was created.

### Lint (periodic maintenance)
- Check for contradictions between pages.
- Check for orphaned pages not linked from `index.md`.
- Check `last_updated` — flag pages not updated in 90+ days if they cover active code.

## Conventions

- `index.md` — read first, always. Update when pages are added.
- `log.md` — append only. Format: `## [YYYY-MM-DD] operation | description`.
- Wikilinks use path without extension: `[[config/servers-json]]`.
- "Not yet documented." marks known gaps in `index.md`.

## Evolution

This schema evolves with the project. When a new concern or page type is needed (e.g. a
`runbooks/` directory for operational procedures), update this file and add the new directory
and template together.
