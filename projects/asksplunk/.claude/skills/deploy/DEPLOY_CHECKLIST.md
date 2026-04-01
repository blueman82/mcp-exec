# Deploy Checklist

## Pre-Deploy
- [ ] All unit tests pass (`pytest tests/unit/ -v`)
- [ ] Code quality clean (`black --check`, `ruff check`, `mypy`)
- [ ] No secrets in source (`rg "xoxb-|xapp-|sk-" src/`)
- [ ] No logging violations (`rg "log.*user.*message" src/`)
- [ ] Git working tree is clean
- [ ] On correct branch (main or release branch)

## Build
- [ ] Docker build succeeds (`docker build --platform linux/amd64`)
- [ ] Image tagged with git SHA and `latest`
- [ ] Image size is reasonable (< 500MB)

## Push
- [ ] ECR login successful
- [ ] Image pushed with SHA tag
- [ ] Image pushed with `latest` tag

## Deploy
- [ ] Old container gracefully stopped (SIGTERM, wait for shutdown)
- [ ] New container started with correct env vars
- [ ] Container health check passes

## Post-Deploy Verification
- [ ] Bot responds to test query in #asksplunk
- [ ] No error logs in first 5 minutes
- [ ] DynamoDB connections working (session create/delete)
- [ ] Secrets Manager accessible (auth check)
- [ ] ChromaDB responding (retrieval check)
- [ ] New Relic metrics nominal

## Rollback Procedure
If issues detected:
1. Stop new container: `docker stop asksplunk-prod`
2. Start previous version: `docker run` with previous SHA tag
3. Verify rollback: test bot response
4. Investigate root cause before re-attempting deploy
