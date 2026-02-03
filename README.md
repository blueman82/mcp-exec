# camp-ops-emea

A monorepo containing internal tools and Slack applications for Adobe Campaign Operations EMEA teams.

## Overview

This repository houses multiple related projects that share common infrastructure patterns, deployment pipelines, and operational knowledge. By keeping them together:

- **Shared learnings**: Patterns proven in one project can be applied to others
- **Consistent tooling**: Same CI/CD, linting, and deployment approaches
- **Easier maintenance**: Single place for cross-cutting updates

## Projects

| Project | Description | Status | Documentation |
|---------|-------------|--------|---------------|
| [Bravo](./projects/bravo) | Slack bot for nudging engineers to log unrecorded Jira work with minimal friction | Design | [Design Doc](./projects/bravo/docs/bravo_design_doc.md) |
| [Ketchup](./projects/ketchup) | Multi-service Slack app for CSO warroom summarization, JIRA integration, and channel management | Production | [README](./projects/ketchup/README.md) |
| [Maptimize](./projects/maptimize) | Slack bot for task mapping, process optimization, and team collaboration | Alpha | [README](./projects/maptimize/README.md) |
| [Meta-MCP](./projects/meta-mcp-server) | MCP server wrapper for token-efficient tool discovery via lazy loading | Production | [README](./projects/meta-mcp-server/README.md) |

## Repository Structure

```
camp-ops-emea/
├── .gitignore              # Shared gitignore for all projects
├── README.md               # This file
├── projects/
│   ├── bravo/              # Jira hygiene nudge bot
│   │   └── docs/           # Design documentation
│   │
│   ├── ketchup/            # CSO summarization Slack app
│   │   ├── README.md
│   │   ├── CLAUDE.md       # AI assistant guidelines
│   │   ├── packages/       # Shared Python packages
│   │   ├── ketchup-app/    # Main FastAPI service
│   │   ├── infrastructure/ # Docker, deployment scripts
│   │   ├── tests/          # Test suite
│   │   └── docs/           # Technical documentation
│   │
│   ├── maptimize/          # Task mapping Slack bot
│   │   ├── README.md
│   │   ├── CLAUDE.md
│   │   ├── src/            # Source code
│   │   ├── infrastructure/ # Docker, deployment scripts
│   │   └── tests/          # Test suite
│   │
│   └── meta-mcp-server/    # MCP server wrapper
│       ├── README.md
│       ├── src/            # TypeScript source
│       │   ├── pool/       # Connection pool with LRU eviction
│       │   ├── registry/   # Server manifest loader
│       │   └── tools/      # MCP tools (list, get, call)
│       └── tests/          # Vitest test suite
│
└── logs/                   # Local development logs (gitignored content)
```

## Getting Started

### Prerequisites

- Git 2.20+ (for worktree support)
- Python 3.12
- Docker & Docker Compose
- AWS CLI (configured with appropriate profile)

### Clone the Repository

```bash
git clone https://github.com/OneAdobe/camp-ops-emea.git
cd camp-ops-emea
```

Then navigate to the project you want to work on:

```bash
cd projects/ketchup    # For Ketchup
cd projects/maptimize  # For Maptimize
```

See each project's README for specific setup instructions.

---

## Working with Multiple Projects (Git Worktrees)

### The Problem

Imagine this scenario:

> You're working on a feature for **Ketchup** on branch `feature/ketchup-new-command`.
> A colleague asks you to review something in **Maptimize**, which needs its own branch.
>
> In a normal git workflow, you'd have to:
> 1. Stash or commit your Ketchup work
> 2. Switch branches
> 3. Work on Maptimize
> 4. Switch back and unstash
>
> This is tedious and error-prone.

**Git Worktrees** solve this by letting you have multiple branches checked out at the same time, in separate folders.

### What is a Git Worktree?

Think of it like having **multiple desks in the same office**:

- Your main desk (`camp-ops-emea/`) has your Ketchup work
- A second desk (`camp-ops-emea-maptimize/`) has your Maptimize work
- Both desks share the same filing cabinet (`.git` history)
- Changes at either desk are tracked in the same repository

```
Your computer
├── camp-ops-emea/                  # Main checkout (your Ketchup branch)
│   └── .git/                       # The "filing cabinet" - shared git history
│
└── camp-ops-emea-maptimize/        # Worktree (your Maptimize branch)
    └── .git  (file, not folder)    # Points back to main .git
```

### Why We Need This for Our Monorepo

Since Ketchup and Maptimize live in the same repository:

1. **Isolated branches**: Work on `feature/ketchup-x` and `feature/maptimize-y` simultaneously
2. **No context switching**: Keep your IDE open on both projects
3. **Independent PRs**: Each project's changes stay in their own branch
4. **No accidental mixing**: Can't accidentally commit Ketchup changes to a Maptimize PR

### Quick Start

```bash
# From your main repo directory
cd /path/to/camp-ops-emea

# Create a worktree for Maptimize work
git worktree add ../camp-ops-emea-maptimize -b feature/maptimize-my-feature

# Now you have two directories, each on different branches!
```

### Step-by-Step Guide

#### 1. Create a Worktree for a New Branch

```bash
# Syntax: git worktree add <path> -b <new-branch-name> [base-branch]

# Example: Create a worktree for new Maptimize feature (based on main)
git worktree add ../camp-ops-emea-maptimize -b feature/maptimize-new-feature main
```

This creates:
- A new folder `../camp-ops-emea-maptimize`
- A new branch `feature/maptimize-new-feature`
- The folder is a full working copy on that branch

#### 2. Create a Worktree for an Existing Branch

```bash
# If the branch already exists
git worktree add ../camp-ops-emea-maptimize feature/maptimize-existing-branch
```

#### 3. Work in Your Worktree

```bash
# Navigate to the worktree
cd ../camp-ops-emea-maptimize

# Work normally - all git commands work as expected
git status
git add .
git commit -m "Your changes"
git push -u origin feature/maptimize-new-feature
```

#### 4. List All Worktrees

```bash
git worktree list
```

Output:
```
/Users/you/camp-ops-emea                main
/Users/you/camp-ops-emea-maptimize      feature/maptimize-new-feature
```

#### 5. Remove a Worktree When Done

```bash
# First, merge your PR and delete the remote branch

# Then remove the worktree
git worktree remove ../camp-ops-emea-maptimize

# Or if you just want to delete it manually:
rm -rf ../camp-ops-emea-maptimize
git worktree prune  # Clean up the worktree registry
```

### Naming Convention

We recommend naming worktree directories to indicate their purpose:

| Pattern | Example | Use Case |
|---------|---------|----------|
| `{repo}-{project}` | `camp-ops-emea-maptimize` | General work on a specific project |
| `{repo}-{feature}` | `camp-ops-emea-auth-fix` | Specific feature spanning projects |
| `{repo}-review` | `camp-ops-emea-review` | Code review checkout |

### Important Notes

1. **One branch per worktree**: You cannot check out the same branch in multiple worktrees
2. **Shared history**: Commits made in any worktree are visible to all others
3. **Independent staging**: Each worktree has its own staging area and working directory
4. **IDE support**: Open each worktree folder as a separate project/window in your IDE

### Common Issues

**"Branch is already checked out"**
```bash
# This means the branch is active in another worktree
git worktree list  # Find where it's checked out
```

**"Worktree folder already exists"**
```bash
# The directory exists but isn't registered
rm -rf ../camp-ops-emea-maptimize  # Remove the folder
git worktree prune                  # Clean the registry
# Now try again
```

---

## Contributing

### Branch Naming

Use prefixes to indicate the type and scope of work:

```
feature/ketchup-new-command     # New feature for Ketchup
feature/maptimize-jira-sync     # New feature for Maptimize
fix/ketchup-status-bug          # Bug fix for Ketchup
chore/update-dependencies       # Maintenance work
docs/ketchup-api-reference      # Documentation updates
```

### Pull Request Process

1. Create a feature branch (use a worktree if working on multiple projects)
2. Make your changes
3. Run tests (`make test-unit` in the project's test directory)
4. Run linting (`make pylint`)
5. Create a PR with a clear description
6. Get review and approval
7. Merge and clean up your worktree if used

---

## Documentation

### Bravo
- [Design Document](./projects/bravo/docs/bravo_design_doc.md) - Architecture and implementation plan

### Ketchup
- [README](./projects/ketchup/README.md) - Quick start and overview
- [CLAUDE.md](./projects/ketchup/CLAUDE.md) - Development guidelines
- [Technical Docs](./projects/ketchup/docs/) - Architecture, diagrams, and deep-dives
- [Wiki](https://wiki.corp.adobe.com/display/neolane/Ketchup) - Confluence documentation

### Maptimize
- [README](./projects/maptimize/README.md) - Quick start and overview
- [CLAUDE.md](./projects/maptimize/CLAUDE.md) - Development guidelines
- [Deployment Guide](./projects/maptimize/docs/DEPLOYMENT.md)
- [AWS Setup](./projects/maptimize/docs/AWS_SETUP.md)

### Meta-MCP Server
- [README](./projects/meta-mcp-server/README.md) - Quick start and configuration
