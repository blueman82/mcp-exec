---
allowed-tools: Bash(~/.claude/scripts/push.sh*)
argument-hint: [commit message]
description: Add, commit, push changes and create PR with reviewers
---

Execute the push workflow script:

```bash
~/.claude/scripts/push.sh "$ARGUMENTS"
```

The script handles:
1. Staging all changes
2. Creating commit (with provided message or auto-generated)
3. Checking if repository requires PR reviewers
4. Pushing branch to origin
5. Creating or updating Pull Request
6. Adding reviewers if required by branch protection

Report the PR URL when complete.
