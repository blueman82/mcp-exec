# camp-ops-emea

Internal tools and Slack applications for Adobe Campaign Operations EMEA teams.

## Projects

| Project | Description | Status | Documentation |
|---------|-------------|--------|---------------|
| [Bravo](./projects/bravo) | Slack bot for nudging engineers to log unrecorded Jira work with minimal friction | Design | [Design Doc](./projects/bravo/docs/bravo_design_doc.md) |
| [Ketchup](./projects/ketchup) | Multi-service Slack app for CSO warroom summarization, JIRA integration, and channel management | Production | [README](./projects/ketchup/README.md) |
| [Maptimize](./projects/maptimize) | Slack bot for task mapping, process optimization, and team collaboration | Alpha | [README](./projects/maptimize/README.md) |
| [Meta-MCP](./projects/meta-mcp-server) | MCP server wrapper for token-efficient tool discovery via lazy loading | Production | [README](./projects/meta-mcp-server/README.md) |

## Getting Started

**Prerequisites:** Git 2.20+, Python 3.12, Docker & Docker Compose, AWS CLI

```bash
git clone https://github.com/OneAdobe/camp-ops-emea.git
cd camp-ops-emea/projects/ketchup  # or maptimize, bravo, meta-mcp-server
```

See each project's README for setup instructions.

## Git Worktrees

Use worktrees to work on multiple projects/branches simultaneously without stashing.

```bash
# Create worktree for feature work
git worktree add ../camp-ops-emea-{project}-{feature} -b feature/{project}-{feature} main

# List worktrees
git worktree list

# Remove when done (after PR merged)
git worktree remove ../camp-ops-emea-{worktree-name}
```

**Naming:** `camp-ops-emea-{project}` (project work), `camp-ops-emea-{feature}` (cross-project), `camp-ops-emea-review` (code review)

## Contributing

### Branch Naming

```
feature/{project}-{name}    # New feature
fix/{project}-{name}        # Bug fix
docs/{project}-{name}       # Documentation
chore/{description}         # Maintenance
```

### PR Process

1. Create feature branch (use worktree if needed)
2. Make changes, run tests
3. Create PR, get approval, merge
