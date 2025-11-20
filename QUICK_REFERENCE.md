# Maptimize Production Infrastructure - Quick Reference

## Instance Access

### Instance 1 (Primary)
- **Instance ID:** i-05c5614fff69d4200
- **Public IP:** 52.213.19.55
- **Private IP:** 10.30.0.41
- **Region:** eu-west-1a

### Instance 2 (Secondary)
- **Instance ID:** i-083af757db8f80b09
- **Public IP:** 3.252.54.191
- **Private IP:** 10.30.0.152
- **Region:** eu-west-1a

## Quick Commands

### SSH Access
```bash
# Instance 1
ssh -i maptimize-ec2-keypair ec2-user@52.213.19.55
ssh -i maptimize-ec2-keypair ec2-user@10.30.0.41

# Instance 2
ssh -i maptimize-ec2-keypair ec2-user@3.252.54.191
ssh -i maptimize-ec2-keypair ec2-user@10.30.0.152
```

### AWS CLI Commands

```bash
# Describe all instances
aws ec2 describe-instances \
  --region eu-west-1 \
  --profile campaign_prod_v7 \
  --filters "Name=tag:Name,Values=maptimize-prod"

# Get instance status
aws ec2 describe-instance-status \
  --instance-ids i-05c5614fff69d4200 i-083af757db8f80b09 \
  --region eu-west-1 \
  --profile campaign_prod_v7

# Check security groups
aws ec2 describe-security-groups \
  --group-ids sg-7997a71c sg-7633b010 \
  --region eu-west-1 \
  --profile campaign_prod_v7

# Get VPC details
aws ec2 describe-vpcs \
  --vpc-ids vpc-0853eb6d \
  --region eu-west-1 \
  --profile campaign_prod_v7
```

## Network Configuration

| Item | Value |
|------|-------|
| **VPC** | vpc-0853eb6d (production) |
| **VPC CIDR** | 10.30.0.0/16 |
| **Subnet** | subnet-ce8e12b9 |
| **Subnet CIDR** | 10.30.0.0/24 |
| **Availability Zone** | eu-west-1a |
| **Key Pair** | maptimize-ec2-keypair |

## Security Groups

### sg-7997a71c (production)
- **Inbound:** HTTP (80), SMTP (25), HTTPS (443), SSH (22 - limited), Monitoring (5666, 9997, 9998, 12000)
- **Outbound:** VPC internal (10.30.0.0/16), SSH to monitoring (10.40.0.0/16)

### sg-7633b010 (public-web-access)
- **Inbound:** HTTP (80), HTTPS (443), SSH (22 - limited)
- **Outbound:** All traffic to internet (0.0.0.0/0)

## Instance Specifications

| Feature | Value |
|---------|-------|
| **Instance Type** | t3.xlarge |
| **vCPU** | 4 (2 cores, 2 threads each) |
| **Memory** | 16 GB |
| **Root Volume** | EBS (/dev/xvda) |
| **Hypervisor** | Xen |
| **Platform** | Linux/UNIX |
| **Tenancy** | Default |

## Monitoring Access Points

### SSH Access Sources (Allowed)
- Adobe offices (multiple locations)
- Deploy server: 52.51.244.239
- Pitstop server: 3.248.69.65
- Campaign AWS jumphost: 3.64.230.45
- Balabit bastions (UT1, OR1, MAI1)
- FRA3 DC: 130.117.8.254
- Approved networks: 51.124.85.152/31, 103.43.112.97

### Monitoring Ports
- **Port 5666:** Nagios monitoring
- **Port 9997/9998:** Splunk logging
- **Port 12000:** Internal service
- **Port 7777:** Internal traffic (sg-7997a71c to sg-7997a71c)

## Public Access

| Port | Protocol | Accessible | Purpose |
|------|----------|-----------|---------|
| 80 | HTTP | Yes (0.0.0.0/0) | Web traffic |
| 443 | HTTPS | Yes (0.0.0.0/0) | Secure web traffic |
| 22 | SSH | Limited | Administrative access |

## IAM Configuration

- **Instance Profile:** maptimize-instance-profile
- **AWS Account:** 483013340174
- **Service Role:** Associated with instance profile

## Resource Tags

All instances are tagged as:
- **Environment:** production
- **Project:** maptimize-slack-bot
- **Owner:** harrison
- **CostCenter:** MSIO-EMEA
- **ManagedBy:** MSIO-EMEA

## Important Notes

1. **No Elastic IPs Allocated** - Instances use dynamic public IPs. Consider allocating for production stability.

2. **Single AZ Deployment** - Both instances in eu-west-1a. No multi-AZ redundancy currently implemented.

3. **Monitoring Disabled** - CloudWatch detailed monitoring is not enabled. Recommended for production.

4. **Recent Launch** - Both instances launched on 2025-11-19 (recent deployment).

5. **Active-Active Setup** - Both instances running in parallel, suggesting load balancing is configured externally.

## Troubleshooting

### Check Instance Status
```bash
aws ec2 describe-instance-status \
  --instance-ids i-05c5614fff69d4200 \
  --region eu-west-1 \
  --profile campaign_prod_v7
```

### View Security Group Rules
```bash
aws ec2 describe-security-groups \
  --group-ids sg-7997a71c \
  --region eu-west-1 \
  --profile campaign_prod_v7
```

### Get Network Interface Details
```bash
aws ec2 describe-network-interfaces \
  --network-interface-ids eni-01a8b880e676516b1 \
  --region eu-west-1 \
  --profile campaign_prod_v7
```

### Check Running Processes (SSH Required)
```bash
ssh -i maptimize-ec2-keypair ec2-user@52.213.19.55 'ps aux | grep maptimize'
```

### View Instance Logs (CloudWatch)
```bash
# Requires CloudWatch logging to be configured
aws logs tail /aws/ec2/maptimize-prod --follow \
  --region eu-west-1 \
  --profile campaign_prod_v7
```

## Additional Resources

- Full documentation: See `INFRASTRUCTURE_SUMMARY.md`
- JSON configuration: See `infrastructure-config.json`
- AWS console: https://console.aws.amazon.com/ec2/
- Instance metadata: http://169.254.169.254/latest/meta-data/ (from instance)

## Last Updated

- **Date:** 2025-11-20
- **Source:** AWS API read-only audit
- **Profile:** campaign_prod_v7
- **Region:** eu-west-1

---

**Read-only mode used for all queries. No changes made to AWS resources.**
