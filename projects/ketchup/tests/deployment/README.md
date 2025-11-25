# Deployment Readiness Validation System

A comprehensive deployment validation system that ensures production-ready deployments with zero-downtime and automatic rollback capabilities.

## Overview

This system provides:

✅ **Pre-deployment Validation** - Comprehensive checks before deployment
✅ **Production Simulation** - Test deployments in production-like environment
✅ **Automated Rollback** - Automatic rollback on deployment failures
✅ **Continuous Monitoring** - Real-time monitoring with alert generation
✅ **Deployment Dashboard** - Visual monitoring and reporting

## Quick Start

### Install Dependencies

```bash
# From tests/setup directory
make setup
pip install aiohttp boto3 docker matplotlib seaborn jinja2
```

### Run Deployment Validation

```bash
# From tests/setup directory
make pre-deployment-check    # Run complete validation before deployment
make validate-deployment     # Run validation with AWS access
make validate-deployment-quick  # Run validation without AWS
```

### Safe Deployment

```bash
# From tests/setup directory
make safe-deploy            # Deploy with validation and monitoring
```

### Emergency Rollback

```bash
# From tests/setup directory
make emergency-rollback VERSION=v2.0.33
```

## System Components

### 1. Deployment Readiness Validator (`deployment_readiness.py`)

**Purpose**: Comprehensive pre-deployment validation

**Key Features**:
- Code quality checks (Black, Ruff, isort, Pylint)
- Unit test validation (0 failures required)
- DI container initialization testing
- AWS service connectivity verification
- Production environment simulation
- Feature flag validation

**Usage**:
```bash
python -m tests.deployment.deployment_readiness --validate-all
```

**Critical Validations**:
- ❌ **CRITICAL**: Unit tests must pass (currently 112 failures)
- ❌ **CRITICAL**: Code formatting must be clean
- ✅ **CRITICAL**: AWS services accessible
- ✅ **CRITICAL**: SSH connectivity to production servers
- ✅ **CRITICAL**: DI container initialization

### 2. Production Simulation (`production_simulation.py`)

**Purpose**: Test deployments in production-like environment

**Key Features**:
- Docker-based production environment simulation
- Service dependency testing
- Health check validation
- Resource utilization monitoring
- Failure recovery testing

**Usage**:
```bash
python -m tests.deployment.production_simulation --setup-only
python -m tests.deployment.production_simulation --test-only
```

### 3. Automated Rollback System (`rollback_automation.py`)

**Purpose**: Automated rollback with safety checks

**Key Features**:
- Pre-rollback safety validation
- Automatic state backup
- Version availability verification
- Post-rollback health validation
- Comprehensive audit logging

**Usage**:
```bash
python -m tests.deployment.rollback_automation --version v2.0.33 --reason deployment_failure
```

**Safety Features**:
- Version exists in ECR before rollback
- Production servers accessible
- Current services stable
- Rollback cooldown period (30 minutes)
- Automatic backup creation

### 4. Continuous Monitoring (`continuous_monitoring.py`)

**Purpose**: Real-time deployment monitoring

**Key Features**:
- Health endpoint monitoring
- Service availability tracking
- Error rate monitoring
- Resource utilization alerts
- Automatic rollback triggering

**Usage**:
```bash
python -m tests.deployment.continuous_monitoring --version v2.0.34 --duration 60
```

**Monitoring Checks**:
- Load balancer health endpoint
- Individual server health
- Docker service status
- DynamoDB performance
- Error rate thresholds

### 5. Deployment Dashboard (`dashboard.py`)

**Purpose**: Visual monitoring and reporting

**Key Features**:
- Real-time status overview
- Validation trend analysis
- Rollback history tracking
- Alert frequency monitoring
- Comprehensive reporting

**Usage**:
```bash
python -m tests.deployment.dashboard
```

## Makefile Integration

### New Targets Added

```bash
# Validation
make validate-deployment          # Full validation with AWS
make validate-deployment-quick    # Quick validation without AWS

# Rollback
make check-rollback VERSION=v2.0.33     # Check rollback safety
make execute-rollback VERSION=v2.0.33   # Execute rollback
make emergency-rollback VERSION=v2.0.33 # Emergency rollback (no validation)

# Production simulation
make production-simulation        # Run production environment simulation

# Comprehensive deployment
make pre-deployment-check        # Run all pre-deployment validations
make safe-deploy                 # Deploy with validation and monitoring
```

## Current Status

### ❌ Critical Issues (Must Fix Before Deployment)

1. **112 Unit Test Failures**: Must be reduced to 0
   ```bash
   make test-unit  # Shows 112 failed, 1709 passed
   ```

2. **Code Formatting Issues**: Black formatting required
   ```bash
   make pylint  # Fix formatting issues
   ```

### ✅ Ready Components

1. **Infrastructure Connectivity**: Production servers accessible
2. **AWS Services**: DynamoDB, Secrets Manager, ECR accessible
3. **Docker Environment**: Build and deployment scripts ready
4. **Validation Framework**: Comprehensive validation system implemented

## Production Readiness Assessment

**Overall Status**: ❌ **NOT READY**

### Test Coverage
- Unit Tests: ❌ 112 failures (critical)
- Integration Tests: ⚠️ Available but not validated
- E2E Tests: ⚠️ Available
- Code Quality: ❌ Formatting issues (critical)

### Infrastructure
- SSH Connectivity: ✅ Both prod servers accessible
- AWS Services: ✅ All required services accessible
- Docker Services: ✅ Running and healthy
- Load Balancer: ✅ Health checks responding

### Deployment Requirements
- [ ] Fix 112 unit test failures
- [ ] Resolve code formatting issues
- [ ] Validate DI container in production configuration
- [x] Environment variables configured
- [x] Feature flags configured
- [x] SSH access configured
- [x] AWS credentials configured

## Deployment Process

### Safe Deployment Steps

1. **Pre-Deployment Validation**
   ```bash
   make pre-deployment-check
   ```
   - Must return exit code 0
   - Validates all critical requirements

2. **Production Simulation** (Optional)
   ```bash
   make production-simulation
   ```
   - Tests deployment in Docker environment
   - Validates service interactions

3. **Deployment with Monitoring**
   ```bash
   make safe-deploy
   ```
   - Runs validation
   - Deploys to production
   - Monitors for issues
   - Auto-rollback on failure

4. **Post-Deployment Monitoring**
   ```bash
   python -m tests.deployment.continuous_monitoring --version v2.0.34 --duration 60
   ```
   - Monitor for 60 minutes
   - Generate health reports
   - Alert on issues

### Emergency Procedures

#### Immediate Rollback
```bash
make emergency-rollback VERSION=v2.0.33
```

#### Check Rollback Safety
```bash
make check-rollback VERSION=v2.0.33
```

#### Generate Dashboard
```bash
python -m tests.deployment.dashboard
```

## File Structure

```
tests/deployment/
├── __init__.py                    # Package initialization
├── deployment_readiness.py       # Main validation system
├── production_simulation.py      # Production environment simulation
├── rollback_automation.py        # Automated rollback system
├── continuous_monitoring.py      # Real-time monitoring
├── dashboard.py                  # Visual dashboard
├── README.md                     # This file
├── reports/                      # Validation reports
│   ├── deployment_readiness_*.txt
│   ├── monitoring_summary_*.json
│   └── post_deployment_*.txt
├── rollback_logs/                # Rollback audit logs
│   └── rollback_*.json
├── backups/                      # State backups
│   └── backup_*.json
└── dashboard/                    # Dashboard assets
    └── *.html, *.png
```

## Success Criteria

### Zero-Downtime Deployments
- ✅ Automated validation prevents bad deployments
- ✅ Rollback automation minimizes downtime
- ✅ Health monitoring detects issues quickly

### Automatic Rollback on Failures
- ✅ Health check failures trigger rollback
- ✅ Error rate thresholds trigger rollback
- ✅ Service unavailability triggers rollback

### Comprehensive Pre-Deployment Validation
- ❌ Unit tests must pass (currently failing)
- ❌ Code quality must pass (currently failing)
- ✅ Infrastructure connectivity validated
- ✅ AWS services validated
- ✅ Production environment simulation

### Production Environment Parity in Testing
- ✅ Docker-based simulation environment
- ✅ Production environment variables
- ✅ Service dependency testing
- ✅ Resource utilization monitoring

## Next Steps

### Immediate Actions Required

1. **Fix Unit Tests**
   ```bash
   make test-unit
   # Address the 112 failing tests
   ```

2. **Fix Code Quality**
   ```bash
   make pylint
   # Fix formatting and linting issues
   ```

3. **Validate System Integration**
   ```bash
   make pre-deployment-check
   # Should pass with 0 exit code
   ```

### Once Tests Pass

1. **Test Production Simulation**
   ```bash
   make production-simulation
   ```

2. **Perform Safe Deployment**
   ```bash
   make safe-deploy
   ```

3. **Monitor Deployment**
   ```bash
   python -m tests.deployment.continuous_monitoring --version <new_version> --duration 60
   ```

### Continuous Improvement

1. **Set up automated validation in CI/CD**
2. **Integrate with monitoring systems**
3. **Regular dashboard review**
4. **Refine rollback triggers**

## Troubleshooting

### Common Issues

1. **Module Import Errors**
   - Ensure PYTHONPATH includes project root
   - Install required dependencies: `pip install aiohttp boto3 docker`

2. **AWS Connectivity Issues**
   - Verify AWS profile: `export AWS_PROFILE=campaign_prod_v7`
   - Check credentials: `aws sts get-caller-identity`

3. **SSH Connectivity Issues**
   - Verify SSH keys configured for production servers
   - Test manually: `ssh ketchup-prod1.campaign.adobe.com`

4. **Docker Issues**
   - Ensure Docker daemon is running
   - Check available images: `docker images`

### Support

For issues with the deployment validation system:

1. Check logs in `tests/deployment/reports/`
2. Review rollback logs in `tests/deployment/rollback_logs/`
3. Generate dashboard for system overview
4. Consult production server logs for deployment issues

---

**Remember**: This system prevents the DI container initialization failures and service integration issues that caused previous deployment problems. Always run `make pre-deployment-check` before any production deployment.
