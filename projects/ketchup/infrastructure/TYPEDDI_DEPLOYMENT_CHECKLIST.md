# TypedDI Deployment Checklist - v2.360.130

## Pre-Deployment Requirements

### ✅ Code Fixes Applied
- [x] UserStore compatibility bridge mapping implemented
- [x] TypedDI smoke checks aligned to 6 essential services only
- [x] aget() method implementation completed
- [x] Fallback mechanism enhanced for resilience

### 🔧 Pre-Deployment Tests (Run These First)

#### 1. Unit Test Validation
```bash
cd /Users/harrison/Documents/Github/camp-ops-emea/projects/ketchup/tests/setup
make test-unit
```
**Expected**: All tests pass, especially TypedDI compatibility tests

#### 2. Pylint Code Quality Check
```bash
cd /Users/harrison/Documents/Github/camp-ops-emea/projects/ketchup/tests/setup
make pylint
```
**Expected**: No linting errors, code quality standards met

#### 3. TypedDI Smoke Check Validation
```bash
python -m pytest tests/unit/core/typed_di/test_service_batch_smoke_checks.py -v
```
**Expected**: All 6 essential services pass smoke tests

## Deployment Configuration

### Environment Variables for v2.360.130

#### Initial Safe Deployment (Recommended)
```yaml
KETCHUP_USE_TYPED_DI=false                # Start disabled, enable after validation
KETCHUP_TYPED_DI_FALLBACK=true           # Keep fallback enabled for safety
```

#### Post-Validation Enablement
```yaml
KETCHUP_USE_TYPED_DI=true                # Enable after successful validation
KETCHUP_TYPED_DI_FALLBACK=true           # Keep fallback for production safety
```

### Docker Image Version
- **All Services**: `v2.360.130`
- **Registry**: `483013340174.dkr.ecr.eu-west-1.amazonaws.com`

## Deployment Sequence

### Phase 1: Deploy with TypedDI Disabled
1. **Target Server**: Start with ketchup-prod2 only
2. **Command**:
   ```bash
   ./deploy-ketchup.sh prod2
   ```
3. **Validation**: Verify all services healthy with legacy DI
4. **Duration**: Allow 10 minutes for full service startup

### Phase 2: Enable TypedDI (After Phase 1 Success)
1. **SSH to prod2**: `ssh ketchup-prod2`
2. **Update Environment**:
   ```bash
   sudo sed -i 's/KETCHUP_USE_TYPED_DI=false/KETCHUP_USE_TYPED_DI=true/' /opt/ketchup/docker-compose.yml
   ```
3. **Restart Services**:
   ```bash
   cd /opt/ketchup
   sudo docker-compose down
   sudo docker-compose up -d
   ```
4. **Monitor Startup**: Watch logs for TypedDI initialization

### Phase 3: Full Production Deployment (After Phase 2 Success)
1. **Deploy to prod1**:
   ```bash
   ./deploy-ketchup.sh prod1
   ```
2. **Enable TypedDI on prod1** (repeat Phase 2 steps)

## Post-Deployment Validation

### 1. Service Health Checks
```bash
# Check all containers are running
ssh ketchup-prod2 'sudo docker ps --format "table {{.Names}}\t{{.Status}}"'

# Verify health endpoints
curl -f http://10.30.165.228/health        # Nginx health
curl -f http://10.30.165.228:8081/health   # MCP-JIRA health
```

### 2. TypedDI Smoke Tests (When Enabled)
- **Check Logs**: Look for "TypedDI initialization successful"
- **Verify Services**: Confirm 6 essential services initialized
- **Test UserStore**: Verify no "UserStore not available" errors

### 3. Critical User Flows
#### Home Tab Test
1. Open Slack app home tab
2. **Expected**: No 500 errors, home tab loads successfully
3. **Previous Issue**: "Service 'user_store' not available" error

#### Status Command Test
1. Run `/ketchup status` in any channel
2. **Expected**: Command executes successfully
3. **Previous Issue**: 500 error due to UserStore resolution failure

### 4. Monitoring (First 30 Minutes)
- **CloudWatch Logs**: Monitor for TypedDI errors
- **Health Endpoints**: Verify consistent health responses
- **Slack Activity**: Test various commands and interactions

## Rollback Procedure

### Immediate Rollback (If Issues Occur)

#### Option 1: Disable TypedDI Only
```bash
ssh ketchup-prod2
sudo sed -i 's/KETCHUP_USE_TYPED_DI=true/KETCHUP_USE_TYPED_DI=false/' /opt/ketchup/docker-compose.yml
cd /opt/ketchup && sudo docker-compose restart ketchup-app
```

#### Option 2: Full Version Rollback
```bash
ssh ketchup-prod2
cd /opt/ketchup
sudo sed -i 's/v2.360.130/v2.360.114/g' docker-compose.yml
sudo docker-compose down
sudo docker-compose pull
sudo docker-compose up -d
```

### Rollback Decision Matrix
| Issue | Action |
|-------|--------|
| TypedDI UserStore errors | Disable TypedDI (Option 1) |
| Service startup failures | Full rollback (Option 2) |
| Performance degradation | Disable TypedDI, monitor |
| Any 500 errors in production | Immediate Option 1 |

## Success Criteria

### ✅ Deployment Successful When:
1. All containers healthy and running
2. Home tab loads without UserStore errors
3. `/ketchup status` command works
4. No 500 errors in Slack interactions
5. TypedDI logs show successful service resolution
6. Fallback mechanism not triggered during normal operations

### 🔍 Monitoring Points (First 24 Hours)
- **Error Rates**: Should remain at baseline levels
- **Response Times**: No degradation in Slack command response times
- **Service Dependencies**: All 6 essential services remain stable
- **UserStore Access**: No compatibility bridge resolution failures

## Emergency Contacts

### If Issues Arise:
1. **Immediate**: Disable TypedDI via Option 1 above
2. **Escalation**: Full rollback if disabling doesn't resolve
3. **Documentation**: Record any new issues in `TYPED_DI_PROD2_ISSUES.md`

## Version History
- **v2.360.130**: UserStore compatibility fix, enhanced fallback
- **v2.360.129**: Previous version with UserStore resolution issues
- **v2.360.114**: Stable rollback version (pre-TypedDI)