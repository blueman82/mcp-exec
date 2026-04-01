---
name: deploy
description: Build, test, and deploy AskSplunk to AWS ECR and EC2. Use when deploying, pushing to ECR, or releasing to production. Triggers on "deploy", "push to ECR", "release to prod", or explicit /deploy.
allowed-tools: Read, Bash, Grep, Glob
---
# Deploy AskSplunk

Use the existing deployment script at `infrastructure/deploy-build-push.sh`. It handles validation, semantic versioning, Docker build, ECR push, and SSH deploy to EC2.

## Standard Deploy

```bash
./infrastructure/deploy-build-push.sh
```

This runs the full pipeline: validate → version bump → build → ECR push → SSH deploy to `asksplunk-prod`.

## Common Variants

```bash
# Skip validation (if already verified)
./infrastructure/deploy-build-push.sh --skip-validation

# Preview without making changes
./infrastructure/deploy-build-push.sh --dry-run

# Build and push only, don't deploy to server
./infrastructure/deploy-build-push.sh --no-deploy

# Force re-index ChromaDB (after schema changes)
./infrastructure/deploy-build-push.sh --reindex

# Build without Docker cache
./infrastructure/deploy-build-push.sh --no-cache
```

## What the Script Does

1. **Pre-flight checks**: Docker, AWS CLI, profile `campaign_prod_v7`, Dockerfile, validate.sh
2. **Validation gate**: Runs `validate.sh` (pytest, ruff, black) — skip with `--skip-validation`
3. **Version management**: Fetches latest tag from ECR, auto-increments (feat commits → minor, else → patch)
4. **Docker build**: `docker buildx build --platform linux/amd64`
5. **ECR push**: Authenticates and pushes version tag + `latest`
6. **EC2 deploy**: SSH to `asksplunk-prod`, pulls image, restarts container via docker compose
7. **ChromaDB indexer**: Runs `run-indexer.py` in container (checks existing index, skips if current)

## Post-Deploy Verification

```bash
# View live logs
ssh asksplunk-prod 'cd /opt/asksplunk && docker compose logs -f'

# Check container status
ssh asksplunk-prod 'docker ps'

# Restart if needed
ssh asksplunk-prod 'cd /opt/asksplunk && docker compose restart'
```

- Verify bot responds in #asksplunk
- Monitor structlog for errors in first 5 minutes
- Check New Relic metrics are nominal

Reference @DEPLOY_CHECKLIST.md for the complete checklist.
