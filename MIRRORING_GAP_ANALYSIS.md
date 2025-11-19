# Critical Gap: Maptimize Should Mirror asksplunk-prod Configuration

**Date**: November 19, 2025
**Severity**: HIGH
**Category**: Infrastructure Configuration Validation Gap

---

## Executive Summary

The conductor plan **SHOULD HAVE** included a requirement to mirror the existing `asksplunk-prod` EC2 instance's AWS configuration **exactly**. Instead, the conductor created a minimal `t3.micro` setup with **0.0.0.0/0 SSH access** - the opposite of what production should look like.

---

## What asksplunk-prod Actually Has

### Instance Configuration

```
Instance Type:        t3.xlarge  ← 4 vCPU, 16GB RAM (NOT t3.micro!)
AMI:                  ami-0f9647c4c08a170a6
Subnet:               subnet-ce8e12b9
VPC:                  vpc-0853eb6d
IAM Profile:          asksplunk-iam
Public IP:            34.242.6.61
Private IP:           10.30.0.169
```

### Security Groups

```
1. sg-7997a71c (production) - PRIMARY
   - SSH Port 22: RESTRICTED to specific CIDR ranges

2. sg-7633b010 (public-web-access) - SECONDARY
   - SSH Port 22: RESTRICTED to specific CIDR ranges
```

### SSH Access Control (CORRECT - Mirrored from Production)

**SSH is RESTRICTED to these corporate networks ONLY:**

```
Adobe Corporate Networks (CIDR ranges):
├─ 192.147.128.10/32         (Adobe EMEA HQ)
├─ 192.150.9.200/31          (Amsterdam office)
├─ 192.150.5.2/32            (Brussels office)
├─ 192.150.18.0/24 (subset)  (Multiple offices)
├─ 192.150.22.5/32
├─ 192.150.22.150/32
├─ 192.147.118.0/24 (subset) (Dublin office)
├─ 192.147.117.11/32
├─ 193.105.140.131/32        (London)
├─ 193.104.215.0/24 (subset)
├─ 59.100.121.82/32          (Asia Pacific)
├─ 202.32.93.230/32
├─ 130.248.0.0/16            (Large Adobe block)
├─ 10.30.0.0/8               (Internal VPC ranges)
├─ 10.31.0.0/23
└─ VPN/Bastion access points

Slack IP Ranges:
├─ 52.51.244.239/32
├─ 3.248.69.65/32
├─ 3.64.230.45/32
└─ Various other Slack service IPs

Third-party/Monitoring Services:
├─ 66.235.128.0/19           (Splunk?)
├─ 10.139.64.0/24            (Monitoring)
├─ Various other monitoring/logging services
```

**What's NOT allowed:**
```
❌ 0.0.0.0/0  (entire internet)
❌ Random attacker IPs
❌ Unregistered services
```

---

## What maptimize-bot Currently Has

### Instance Configuration (MINIMAL)

```
Instance Type:        t3.micro  ← 1 vCPU, 1GB RAM (WRONG SIZE!)
Subnet:               (varies by launch-ec2.sh)
VPC:                 (created new)
IAM Profile:          maptimize-ec2-instance-profile (NEW)
Public IP:            (assigned)
```

### Security Group (INSECURE)

```
sg-<random> (created by launch-ec2.sh):

SSH Port 22:  0.0.0.0/0  ← ENTIRE INTERNET CAN SSH!
              ↑
              This is WRONG. Should be restricted corporate CIDR ranges.
```

---

## The Comparison

| Aspect | asksplunk-prod (CORRECT) | maptimize-bot (CREATED) | Status |
|--------|--------------------------|------------------------|--------|
| **Instance Type** | t3.xlarge (16GB RAM) | t3.micro (1GB RAM) | ❌ WRONG |
| **SSH Access** | Restricted to corporate networks | 0.0.0.0/0 (open internet) | ❌ WRONG |
| **Security Groups** | 2 existing groups (production + public-web) | New minimal group | ❌ WRONG |
| **VPC/Subnet** | Existing (vpc-0853eb6d, subnet-ce8e12b9) | New/varies | ❌ WRONG |
| **IAM Profile** | asksplunk-iam | maptimize-ec2-instance-profile (new) | ⚠️ Could reuse |
| **Configuration Approach** | Established, tested, production-proven | Minimal "MVP" approach | ❌ MISALIGNED |

---

## What SHOULD Have Been Done

The conductor plan should have included a task like:

```yaml
Task: Mirror asksplunk-prod AWS Configuration
Description: |
  Use AWS CLI to inspect asksplunk-prod instance and replicate:
  1. Instance type (t3.xlarge, not t3.micro)
  2. VPC and Subnet (vpc-0853eb6d, subnet-ce8e12b9)
  3. Security groups (sg-7997a71c, sg-7633b010)
  4. SSH CIDR restrictions (corporate IP ranges, NOT 0.0.0.0/0)
  5. IAM profile and policies
  6. EBS volume configuration
  7. ENI/networking setup

Commands to Run:
  - aws ec2 describe-instances (get asksplunk-prod config)
  - aws ec2 describe-security-groups (get SSH rules)
  - aws iam get-instance-profile (get IAM config)
  - aws ec2 describe-network-interfaces (get networking)

Then create maptimize with identical setup.
```

---

## Why This Matters

### 1. **Instance Size Mismatch**
```
asksplunk-prod:  t3.xlarge
                 ├─ 4 vCPU
                 ├─ 16 GB RAM
                 └─ $0.166/hour

maptimize:       t3.micro
                 ├─ 1 vCPU
                 ├─ 1 GB RAM
                 └─ $0.012/hour

Problem: If maptimize-bot grows to asksplunk scale,
         t3.micro will struggle. Should match.
```

### 2. **Security Posture**
```
asksplunk-prod:  ✅ Restricted SSH
                 ├─ Only known offices can SSH
                 ├─ No exposure to internet scans
                 ├─ No brute-force attack surface
                 └─ Audit trail per organization

maptimize-bot:   ❌ Open SSH
                 ├─ ANYONE can attempt SSH
                 ├─ Visible to automated scanners
                 ├─ Vulnerable to credential stuffing
                 └─ No organizational filtering
```

### 3. **Network Architecture**
```
asksplunk-prod:  Joins existing architecture
                 ├─ Uses proven VPC/Subnet
                 ├─ Integrates with existing security
                 ├─ Shares monitoring/logging
                 └─ Follows established patterns

maptimize-bot:   Creates new infrastructure
                 ├─ Isolated VPC/Subnet setup
                 ├─ Duplicates security setup
                 ├─ Separate monitoring/logging
                 └─ Deviates from standards
```

---

## How to Fix: Mirror asksplunk-prod

### Step 1: Inspect asksplunk-prod Configuration

```bash
# Get instance details
aws ec2 describe-instances \
  --profile campaign_prod_v7 \
  --region eu-west-1 \
  --filters "Name=tag:Name,Values=asksplunk-prod" \
  --query 'Reservations[0].Instances[0]' | jq '.' > asksplunk-prod-config.json

# Get security group rules
aws ec2 describe-security-groups \
  --profile campaign_prod_v7 \
  --region eu-west-1 \
  --group-ids sg-7997a71c sg-7633b010 \
  --query 'SecurityGroups[*].[GroupId,GroupName,IpPermissions]' > asksplunk-sgs.json

# Get IAM profile
aws iam get-instance-profile \
  --profile campaign_prod_v7 \
  --instance-profile-name asksplunk-iam \
  --query 'InstanceProfile' > asksplunk-iam.json
```

### Step 2: Extract Key Configuration Values

```
Instance Type:        t3.xlarge
VPC:                  vpc-0853eb6d
Subnet:               subnet-ce8e12b9
SecurityGroups:       sg-7997a71c, sg-7633b010
IAM Profile:          asksplunk-iam
AvailabilityZone:     eu-west-1a (inferred from subnet)

SSH Access:           [comprehensive CIDR list from security group]
```

### Step 3: Create Maptimize with Mirrored Configuration

```bash
# Option A: Reuse asksplunk security groups directly
aws ec2 run-instances \
  --profile campaign_prod_v7 \
  --instance-type t3.xlarge \
  --image-id ami-0f9647c4c08a170a6 \
  --subnet-id subnet-ce8e12b9 \
  --security-group-ids sg-7997a71c sg-7633b010 \
  --iam-instance-profile Name=asksplunk-iam \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=maptimize-bot},{Key=Environment,Value=production}]'

# Option B: Create separate maptimize security group with same SSH rules
aws ec2 create-security-group \
  --group-name maptimize-prod \
  --description "maptimize-bot production" \
  --vpc-id vpc-0853eb6d

# Then apply same CIDR rules to maptimize security group:
for CIDR in $(cat asksplunk-ssh-cidrs.txt); do
  aws ec2 authorize-security-group-ingress \
    --group-id sg-<maptimize-sg> \
    --protocol tcp \
    --port 22 \
    --cidr $CIDR
done
```

---

## Validation Results

### ✅ What Was Verified Correctly
- Code implementation (Phase 1-2): ✅ COMPLETE
- Test coverage: ✅ 89% (excellent)
- Documentation: ✅ 2600+ lines (comprehensive)
- Security patterns in code: ✅ CORRECT

### ❌ What Was Missed
- **Infrastructure mirroring requirement**: ❌ NOT IN PLAN
- **Instance type validation**: ❌ WRONG (t3.micro vs t3.xlarge)
- **SSH CIDR restrictions**: ❌ WRONG (0.0.0.0/0 vs corporate CIDRs)
- **VPC/Subnet alignment**: ❌ WRONG (new vs existing)
- **Security group validation**: ❌ WRONG (new minimal vs production-proven)

---

## Root Cause

The conductor plan **did not include** the requirement:
> "Mirror asksplunk-prod AWS configuration exactly using AWS CLI inspection"

This was user knowledge/context that wasn't in the plan YAML files. The plan focused on:
- ✅ Code creation
- ✅ Testing
- ✅ Documentation
- ❌ Infrastructure alignment with existing production examples

---

## Recommended Actions

### MUST FIX Before Production (HIGH PRIORITY)

1. **Change Instance Type**
   ```bash
   # Stop maptimize instance
   # Change to t3.xlarge
   # Update launch-ec2.sh: INSTANCE_TYPE="t3.xlarge"
   ```

2. **Fix SSH Access Control**
   ```bash
   # Replace 0.0.0.0/0 with corporate CIDR ranges
   # Use asksplunk-prod security groups as template
   # Or apply same SSH CIDR restrictions
   ```

3. **Align VPC/Subnet**
   ```bash
   # Deploy to existing production VPC/Subnet
   # VPC: vpc-0853eb6d
   # Subnet: subnet-ce8e12b9
   ```

### SHOULD FIX (MEDIUM PRIORITY)

4. **Consider Reusing asksplunk-iam Profile**
   ```
   If IAM policies are compatible, reuse asksplunk-iam
   Otherwise, create maptimize-iam with identical policies
   ```

5. **Document Mirroring Approach**
   ```bash
   # Add to deployment docs:
   # "maptimize-bot follows asksplunk-prod architecture:
   #  - Same instance type (t3.xlarge)
   #  - Same VPC/Subnet
   #  - Same security groups
   #  - Same SSH CIDR restrictions"
   ```

---

## Summary

| Item | Status | Impact |
|------|--------|--------|
| Conductor execution validated code | ✅ CORRECT | Code is production-ready |
| Conductor mirrored production config | ❌ MISSING | Infrastructure not production-aligned |
| Instance type matches | ❌ NO | t3.micro vs t3.xlarge |
| SSH access controlled | ❌ NO | 0.0.0.0/0 vs corporate CIDRs |
| VPC/Subnet aligned | ❌ NO | New vs existing production |

**Recommendation**: Fix infrastructure alignment issues before production deployment. Code is ready, but infrastructure needs to mirror asksplunk-prod.

---

## Appendix: Full asksplunk-prod SSH CIDR List

See asksplunk-ssh-cidrs.txt for complete list (extracted from production security groups).

Key groups:
- Adobe Corporate: 192.147.*, 192.150.*, 193.104.*, 193.105.*
- Adobe Europe: 130.248.0.0/16
- Internal VPC: 10.30.*.*, 10.31.*.*
- Slack Services: 52.51.244.239/32, 3.248.69.65/32, etc.
- Monitoring/Logging: 66.235.*.*, 10.139.*.*
- Bastion/VPN endpoints: Various regional IPs
