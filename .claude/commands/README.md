# Commands

Project-level slash commands for Claude Code. Invoke with `/<name>`.

| Command | What it does | Example |
|---------|-------------|---------|
| `/cook` | Interactive design session — asks questions one-at-a-time to refine an idea into a validated design, then generates an implementation plan | `/cook "Slack bot that posts daily summaries"` |
| `/merge` | Merge an approved PR, switch to main, pull latest. Checks branch protection and approval status | `/merge 42` or `/merge auto` |
| `/push` | Stage all changes, commit, push, and create/update a PR with reviewers | `/push "fix: resolve timeout in poller"` |
| `/slimcode` | Analyse code with LSP + semantic search to find safe LOC reduction opportunities without changing behaviour or public APIs | `/slimcode src/ --deep` |
| `/sync-docs` | Audit documentation against codebase reality. Detects drift, missing docs, outdated diagrams. Use `--semantic` for deep AI-powered discovery | `/sync-docs --check` |

> **Note:** `/push` and `/merge` delegate to shell scripts in `~/.claude/scripts/`. `/cook` invokes `/doc` after design approval.
