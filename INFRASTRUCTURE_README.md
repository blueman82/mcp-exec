# Maptimize Production Infrastructure Documentation

## Overview

This directory contains comprehensive infrastructure documentation for the maptimize-prod application running on AWS. All information was gathered on **2025-11-20** using read-only AWS API queries with the `campaign_prod_v7` profile.

## Documentation Files

### 1. INFRASTRUCTURE_SUMMARY.md (12 KB)
**Comprehensive infrastructure audit report**

The primary documentation file containing:
- Executive summary of the deployment
- Detailed EC2 instance specifications
- VPC and networking configuration
- Security group rules and access policies
- IAM configuration
- Cost optimization recommendations
- High availability assessment
- Security recommendations
- Operational procedures

**Best for:** Complete infrastructure review, compliance audits, architecture planning

**Location:** `/Users/harrison/Documents/Github/camp-ops-emea/maptimize-worktree/INFRASTRUCTURE_SUMMARY.md`

---

### 2. QUICK_REFERENCE.md (5.1 KB)
**Quick lookup guide for common tasks**

Contains:
- Instance IDs and IP addresses
- SSH access commands
- AWS CLI commands for common operations
- Network configuration quick reference
- Security group summary
- Troubleshooting commands
- Important notes and gotchas

**Best for:** Daily operations, quick lookups, CLI command reference

**Location:** `/Users/harrison/Documents/Github/camp-ops-emea/maptimize-worktree/QUICK_REFERENCE.md`

---

### 3. infrastructure-config.json (7.5 KB)
**Structured configuration data in JSON format**

Contains:
- All instance details in machine-readable format
- Complete network configuration
- Security group specifications
- Access points and public IPs
- Recommendations with priority levels
- Operational contacts
- Monitoring status

**Best for:** Automation, integration with other tools, programmatic access, infrastructure-as-code

**Location:** `/Users/harrison/Documents/Github/camp-ops-emea/maptimize-worktree/infrastructure-config.json`

---

### 4. infrastructure-summary.csv (643 B)
**Tabular summary for spreadsheet applications**

Contains:
- Instance IDs
- Instance names and types
- IP addresses (public and private)
- Region and availability zone
- Security groups
- Owner and cost center information

**Best for:** Excel/Google Sheets import, reporting, quick tabular view

**Location:** `/Users/harrison/Documents/Github/camp-ops-emea/maptimize-worktree/infrastructure-summary.csv`

---

## Key Findings Summary

### Deployment Model
- **Active-Active Setup:** Two t3.xlarge instances running in parallel
- **Location:** eu-west-1a (single availability zone)
- **VPC:** vpc-0853eb6d (Production VPC)
- **Launch Date:** 2025-11-19 (recently deployed)

### Instance Details
| Property | Value |
|----------|-------|
| Instance Type | t3.xlarge (4 vCPU, 16 GB RAM) |
| Count | 2 (running) |
| Operating System | Linux/UNIX |
| Security Groups | 2 (production + public-web-access) |
| Key Pair | maptimize-ec2-keypair |

### Access Points
| Instance | Public IP | Private IP | Status |
|----------|-----------|-----------|--------|
| maptimize-prod-1 | 52.213.19.55 | 10.30.0.41 | Running |
| maptimize-prod-2 | 3.252.54.191 | 10.30.0.152 | Running |

### Network Exposure
- **HTTP (80):** Open to 0.0.0.0/0
- **HTTPS (443):** Open to 0.0.0.0/0 (with limited exceptions)
- **SSH (22):** Restricted to approved sources only
- **Monitoring:** Ports 5666, 9997, 9998, 12000 accessible to monitoring infrastructure

### Elastic IPs
- **Status:** Not allocated
- **Impact:** Instances use dynamic public IPs (change on stop/start)
- **Recommendation:** Allocate Elastic IPs for production stability

---

## Important Recommendations

### HIGH PRIORITY

1. **Multi-AZ Deployment**
   - Current: Single AZ (eu-west-1a)
   - Action: Expand to eu-west-1b and eu-west-1c for resilience

2. **Elastic IPs**
   - Current: Dynamic public IPs
   - Action: Allocate Elastic IPs for consistent addressing

3. **Load Balancing**
   - Current: No load balancer documented
   - Action: Implement Application/Network Load Balancer

### MEDIUM PRIORITY

4. **CloudWatch Monitoring**
   - Current: Disabled
   - Action: Enable detailed monitoring for production instances

5. **Security Hardening**
   - Action: Enforce IMDSv2 (HTTP Tokens: Required)
   - Action: Enable VPC Flow Logs
   - Action: Configure Systems Manager Session Manager

6. **Cost Optimization**
   - Action: Consider Reserved Instances or Compute Savings Plans
   - Potential savings: 30-70% for continuous workloads

### LOW PRIORITY

7. **Auto Scaling Groups**
   - Current: Manual instance management
   - Action: Implement ASG for automatic recovery

---

## Quick Access Commands

### View All Documentation
```bash
cd /Users/harrison/Documents/Github/camp-ops-emea/maptimize-worktree

# View comprehensive summary
cat INFRASTRUCTURE_SUMMARY.md

# View quick reference
cat QUICK_REFERENCE.md

# View JSON configuration
cat infrastructure-config.json | jq '.'

# View CSV data
cat infrastructure-summary.csv
```

### AWS CLI Commands
```bash
# List instances
aws ec2 describe-instances \
  --region eu-west-1 \
  --profile campaign_prod_v7 \
  --filters "Name=tag:Name,Values=maptimize-prod"

# Get instance status
aws ec2 describe-instance-status \
  --instance-ids i-05c5614fff69d4200 i-083af757db8f80b09 \
  --region eu-west-1 \
  --profile campaign_prod_v7
```

---

## Security Assessment

### Current Controls
- Security groups restrict SSH access to known sources
- HTTP/HTTPS accessible but through security groups
- IAM instance profiles for credential management
- VPC provides network isolation

### Recommended Enhancements
- Allocate Elastic IPs for DDoS protection
- Enable IMDSv2 for instance metadata security
- Implement VPC Flow Logs for network monitoring
- Enable CloudTrail for API logging
- Configure Systems Manager for SSH-less access

---

## Operational Contacts

| Role | Person | Email/Reference |
|------|--------|-----------------|
| Instance Owner | harrison | Tag: Owner=harrison |
| Project | maptimize-slack-bot | Tag: Project=maptimize-slack-bot |
| Cost Center | MSIO-EMEA | Tag: CostCenter=MSIO-EMEA |
| Management | MSIO-EMEA | Tag: ManagedBy=MSIO-EMEA |

---

## Audit Information

- **Audit Date:** 2025-11-20
- **AWS Profile:** campaign_prod_v7
- **AWS Region:** eu-west-1
- **Audit Scope:** EC2, VPC, Security Groups, Networking
- **Audit Mode:** Read-only (no changes made)
- **Data Format:** AWS CLI JSON output
- **Compliance:** All information gathered through standard AWS APIs

---

## Using These Documents

### For Infrastructure Review
1. Start with INFRASTRUCTURE_SUMMARY.md for complete overview
2. Review recommendations section
3. Cross-reference with QUICK_REFERENCE.md for specific details

### For Daily Operations
1. Use QUICK_REFERENCE.md for command syntax
2. Reference infrastructure-config.json for programmatic access
3. Check security group rules for access validation

### For Compliance/Audit
1. Reference INFRASTRUCTURE_SUMMARY.md for comprehensive audit trail
2. Use infrastructure-config.json for structured data export
3. Include infrastructure-summary.csv in reports

### For Automation
1. Parse infrastructure-config.json in scripts
2. Reference instance IDs for AWS CLI commands
3. Use tags for resource identification and billing

---

## Next Steps

1. **Review Security Recommendations**
   - Allocate Elastic IPs
   - Enable detailed CloudWatch monitoring
   - Implement load balancing

2. **Plan High Availability**
   - Design multi-AZ deployment
   - Configure Auto Scaling Groups
   - Implement backup strategy

3. **Cost Optimization**
   - Analyze utilization patterns
   - Consider Reserved Instances
   - Implement cost anomaly detection

4. **Update Documentation**
   - Update this README as infrastructure changes
   - Keep JSON configuration in sync with AWS resources
   - Maintain QUICK_REFERENCE.md with current IP addresses

---

## Document Maintenance

**Last Updated:** 2025-11-20
**Next Review:** 2025-12-20 (recommended monthly review)
**Owner:** harrison
**Change Log:**
- Initial documentation created on 2025-11-20

---

## Related Resources

- AWS Console: https://console.aws.amazon.com/ec2/
- EC2 Instance Types: https://aws.amazon.com/ec2/instance-types/
- Security Best Practices: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-security.html
- VPC Documentation: https://docs.aws.amazon.com/vpc/
- Well-Architected Framework: https://aws.amazon.com/architecture/well-architected/

---

**No changes were made to AWS resources during this audit. All information is based on read-only API queries.**
