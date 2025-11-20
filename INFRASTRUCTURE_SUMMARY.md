# Maptimize Production Infrastructure Summary

**Date Generated:** 2025-11-20
**AWS Profile:** campaign_prod_v7
**Infrastructure Status:** Read-only information gathering

---

## Executive Summary

The maptimize-prod application is deployed on AWS with two production EC2 instances in an active-active configuration. Both instances are located in the same availability zone (eu-west-1a) within the eu-west-1 region and are currently running.

---

## EC2 Instances

### Instance 1: maptimize-prod (Primary)

| Property | Value |
|----------|-------|
| **Instance ID** | `i-05c5614fff69d4200` |
| **Instance Name** | maptimize-prod |
| **Instance Type** | t3.xlarge (2 vCPU, 16GB RAM) |
| **State** | running |
| **Launch Time** | 2025-11-19T23:26:25+00:00 |
| **Region** | eu-west-1 |
| **Availability Zone** | eu-west-1a |
| **AMI ID** | ami-0f9647c4c08a170a6 |

#### Network Configuration

| Property | Value |
|----------|-------|
| **VPC ID** | vpc-0853eb6d (production) |
| **Subnet ID** | subnet-ce8e12b9 |
| **Subnet Name** | production-subnet-1 |
| **Subnet CIDR Block** | 10.30.0.0/24 |
| **Private IP Address** | 10.30.0.41 |
| **Public IP Address** | 52.213.19.55 |
| **Public DNS Name** | ec2-52-213-19-55.eu-west-1.compute.amazonaws.com |
| **Primary ENI ID** | eni-01a8b880e676516b1 |
| **MAC Address** | 06:47:9e:35:08:81 |

#### Storage Configuration

| Property | Value |
|----------|-------|
| **Root Device** | /dev/xvda |
| **Root Device Type** | EBS |
| **Volume ID** | vol-06d225bfc29c29f64 |
| **EBS Optimized** | No |
| **ENA Support** | Yes |

#### Compute Configuration

| Property | Value |
|----------|-------|
| **CPU Cores** | 2 |
| **Threads per Core** | 2 |
| **Hypervisor** | Xen |
| **Virtualization Type** | hvm |
| **Platform** | Linux/UNIX |
| **Current Boot Mode** | legacy-bios |

#### Key Pair

| Property | Value |
|----------|-------|
| **Key Pair Name** | maptimize-ec2-keypair |

---

### Instance 2: maptimize-prod (Secondary)

| Property | Value |
|----------|-------|
| **Instance ID** | `i-083af757db8f80b09` |
| **Instance Name** | maptimize-prod |
| **Instance Type** | t3.xlarge (2 vCPU, 16GB RAM) |
| **State** | running |
| **Launch Time** | 2025-11-19T23:30:28+00:00 |
| **Region** | eu-west-1 |
| **Availability Zone** | eu-west-1a |
| **AMI ID** | ami-0f9647c4c08a170a6 |

#### Network Configuration

| Property | Value |
|----------|-------|
| **VPC ID** | vpc-0853eb6d (production) |
| **Subnet ID** | subnet-ce8e12b9 |
| **Subnet Name** | production-subnet-1 |
| **Subnet CIDR Block** | 10.30.0.0/24 |
| **Private IP Address** | 10.30.0.152 |
| **Public IP Address** | 3.252.54.191 |
| **Public DNS Name** | ec2-3-252-54-191.eu-west-1.compute.amazonaws.com |
| **Primary ENI ID** | eni-0096153eeaddf7078 |
| **MAC Address** | 06:3d:da:fc:e6:cb |

#### Storage Configuration

| Property | Value |
|----------|-------|
| **Root Device** | /dev/xvda |
| **Root Device Type** | EBS |
| **Volume ID** | vol-042cad383ec24880c |
| **EBS Optimized** | No |
| **ENA Support** | Yes |

#### Compute Configuration

| Property | Value |
|----------|-------|
| **CPU Cores** | 2 |
| **Threads per Core** | 2 |
| **Hypervisor** | Xen |
| **Virtualization Type** | hvm |
| **Platform** | Linux/UNIX |
| **Current Boot Mode** | legacy-bios |

#### Key Pair

| Property | Value |
|----------|-------|
| **Key Pair Name** | maptimize-ec2-keypair |

---

## VPC Configuration

### VPC Details

| Property | Value |
|----------|-------|
| **VPC ID** | vpc-0853eb6d |
| **VPC Name** | production |
| **State** | available |
| **CIDR Block** | 10.30.0.0/16 |
| **Tenancy** | default |
| **DNS Support** | Enabled |
| **DHCP Options ID** | dopt-4dec9e28 |
| **Comment** | Production VPC |
| **Emissary Tag** | trusted |

---

## Security Groups

The maptimize-prod instances are protected by two security groups working together:

### Security Group 1: production (sg-7997a71c)

**Description:** Production SG
**VPC ID:** vpc-0853eb6d

#### Inbound Rules

| Protocol | Port(s) | Source | Description |
|----------|---------|--------|-------------|
| TCP | 80 | 0.0.0.0/0 | HTTP - Open to all |
| TCP | 22 | Multiple IPs | SSH - Adobe offices and approved bastion hosts |
| TCP | 25 | Multiple IPs | SMTP - Email relay |
| TCP | 443 | 103.43.112.97/32 | HTTPS - Adobe Noida office |
| TCP | 5666 | 10.10.0.0/24 | Monitoring |
| TCP | 7777 | sg-7997a71c | Internal traffic - Same SG |
| TCP | 9997 | 10.40.0.0/16 | Monitoring/Logging |
| TCP | 9998 | 10.40.0.0/16 | Monitoring/Logging |
| TCP | 12000 | 10.100.0.0/16 | Internal service |
| ICMP | -1 | 10.10.0.0/24 | Ping/diagnostics |

**SSH Access Allowed From:**
- Adobe offices (multiple locations: Lehi, Ottawa, San Jose, Seattle, Virginia, Noida, Bangalore, Basel, Bucharest, Dublin, Hamburg, Beijing, Singapore, Seoul, Sydney, Tokyo)
- Deploy server: 52.51.244.239/32
- Pitstop server: 3.248.69.65/32
- Campaign AWS jumphost: 3.64.230.45/32
- Balabit bastions (UT1, OR1, MAI1)
- Various enterprise networks and VPNs

#### Outbound Rules

| Protocol | Port(s) | Destination | Description |
|----------|---------|-------------|-------------|
| All | All | 10.30.0.0/16 | VPC internal traffic |
| TCP | 22 | 10.40.0.0/16 | SSH to monitoring |

---

### Security Group 2: public-web-access (sg-7633b010)

**Description:** Gives access to http and https
**VPC ID:** vpc-0853eb6d

#### Inbound Rules

| Protocol | Port(s) | Source | Description |
|----------|---------|--------|-------------|
| TCP | 80 | 0.0.0.0/0 | HTTP - Open to all |
| TCP | 443 | 0.0.0.0/0 | HTTPS - Open to all |
| TCP | 443 | 103.43.112.97/32 | HTTPS - Adobe Noida office |
| TCP | 22 | 130.117.8.254/32 | SSH - FRA3 DC |
| TCP | 22 | 51.124.85.152/31 | SSH - Approved source |
| TCP | 22 | 52.51.244.239/32 | SSH - Deploy server |
| TCP | 22 | 3.248.69.65/32 | SSH - Pitstop server |
| TCP | 22 | 103.43.112.97/32 | SSH - Adobe Noida office |

#### Outbound Rules

| Protocol | Port(s) | Destination | Description |
|----------|---------|-------------|-------------|
| All | All | 0.0.0.0/0 | All traffic outbound |

---

## Elastic IPs

**Status:** No Elastic IPs are currently associated with the maptimize-prod instances.

Both instances are using public IPs assigned directly by AWS, which change upon instance stop/start. For production workloads requiring persistent IPs, consider allocating Elastic IPs.

---

## IAM Configuration

### Instance Profile

| Property | Value |
|----------|-------|
| **Instance Profile Name** | maptimize-instance-profile |
| **Instance Profile ARN** | arn:aws:iam::483013340174:instance-profile/maptimize-instance-profile |
| **Instance Profile ID** | AIPAXA5OWVQHDMHMWPWBY |
| **AWS Account ID** | 483013340174 |

---

## Resource Tags

All maptimize-prod instances are tagged with the following metadata:

| Tag Key | Tag Value |
|---------|-----------|
| Name | maptimize-prod |
| Project | maptimize-slack-bot |
| ManagedBy | MSIO-EMEA |
| CostCenter | MSIO-EMEA |
| Environment | production |
| Owner | harrison |

---

## Network Accessibility

### Public Access Points

| Instance | Public IP | DNS Name | HTTP | HTTPS | SSH |
|----------|-----------|----------|------|-------|-----|
| maptimize-prod (1) | 52.213.19.55 | ec2-52-213-19-55.eu-west-1.compute.amazonaws.com | Yes | Yes | Limited |
| maptimize-prod (2) | 3.252.54.191 | ec2-3-252-54-191.eu-west-1.compute.amazonaws.com | Yes | Yes | Limited |

### Internal Network

- **VPC CIDR:** 10.30.0.0/16
- **Subnet CIDR:** 10.30.0.0/24
- **Private IPs:**
  - maptimize-prod (1): 10.30.0.41
  - maptimize-prod (2): 10.30.0.152

### Monitoring Access

Both instances can be reached for monitoring via:
- Port 5666: Nagios/monitoring from 10.10.0.0/24
- Port 9997/9998: Monitoring from 10.40.0.0/16 (Splunk)

---

## Monitoring Status

| Feature | Status |
|---------|--------|
| CloudWatch Monitoring | Disabled |
| DetailedMonitoring | Not enabled |
| Auto Recovery | Default (enabled) |
| Reboot Migration | Default (enabled) |

**Recommendation:** Enable CloudWatch detailed monitoring for production instances.

---

## Metadata and Security

### EC2 Instance Metadata

| Setting | Value |
|---------|-------|
| HTTP Endpoint | Enabled |
| HTTP Tokens | Optional (consider setting to Required for security) |
| HTTP Put Response Hop Limit | 1 |
| IPv6 Support | Disabled |
| Instance Metadata Tags | Disabled |

### DNS Configuration

| Setting | Value |
|---------|-------|
| Hostname Type | ip-name |
| Resource Name DNS A Record | Disabled |
| Resource Name DNS AAAA Record | Disabled |

---

## Capacity and Performance

### Instance Sizing

| Resource | Allocation |
|----------|-----------|
| Instance Type | t3.xlarge |
| vCPU | 4 (2 cores x 2 threads) |
| Memory | 16 GB |
| Network Performance | Up to 5 Gbps |
| Baseline CPU Credit Rate | Variable (t3 burstable) |

### Storage

| Device | Type | Size | Optimization |
|--------|------|------|--------------|
| /dev/xvda (Root) | EBS (gp2/gp3) | Variable | DeleteOnTermination: Yes |

---

## Cost Optimization Opportunities

1. **Elastic IPs**: Neither instance uses an Elastic IP. Consider allocating one for production services requiring consistent IPs.

2. **Instance Monitoring**: DetailedMonitoring is disabled. Enable CloudWatch detailed monitoring for better visibility.

3. **EBS Optimization**: Not enabled. Consider enabling for improved EBS I/O performance if workload is I/O intensive.

4. **T3 Burstable Instances**: Current instances are t3.xlarge burstable. Monitor CPU credit consumption to ensure adequate baseline performance.

5. **Data Transfer**: All instances are in the same AZ and VPC, minimizing data transfer costs.

6. **Reserved Instances/Savings Plans**: If these instances run continuously, Reserved Instances or Compute Savings Plans could reduce costs by 30-70%.

---

## High Availability & Disaster Recovery

### Current Configuration

- **Deployment Model:** Active-Active (both instances in same AZ)
- **Availability Zone:** eu-west-1a (single AZ)
- **Multi-AZ Resilience:** Not implemented
- **Multi-Region Resilience:** Not implemented
- **Backup Strategy:** Not documented

### Recommendations

1. **Multi-AZ Deployment**: Deploy instances across eu-west-1b and eu-west-1c for AZ-level redundancy
2. **Load Balancing**: Place behind an Application/Network Load Balancer
3. **Auto Scaling**: Implement Auto Scaling Groups for automatic recovery
4. **Snapshots**: Regular EBS snapshots for disaster recovery
5. **Cross-Region Backup**: Consider cross-region replication for critical data

---

## Security Assessment

### Positive Controls

- Instances use security groups with restricted SSH access
- HTTP/HTTPS open to internet but through security group rules
- IAM instance profile provides credential management
- VPC provides network isolation
- ENAs support is enabled

### Security Recommendations

1. **Elastic IPs**: Allocate Elastic IPs for consistent public IPs and DDoS protection
2. **Instance Metadata**: Consider changing HTTP Tokens to "Required" for IMDSv2 enforcement
3. **CloudWatch Monitoring**: Enable detailed monitoring for security event detection
4. **VPC Flow Logs**: Enable to monitor network traffic
5. **Systems Manager Session Manager**: Configure to eliminate need for SSH access
6. **CloudTrail**: Ensure API logging is enabled for compliance
7. **Security Groups**: Consider implementing network ACLs for defense in depth
8. **OS Hardening**: Regular patching and vulnerability assessment

---

## Operational Contacts

| Role | Owner |
|------|-------|
| Instance Owner | harrison |
| Project Owner | maptimize-slack-bot team |
| Cost Center | MSIO-EMEA |
| Management | MSIO-EMEA |

---

## Document Information

- **Generated By:** AWS Infrastructure Audit (Read-only Mode)
- **Generation Date:** 2025-11-20
- **AWS Region:** eu-west-1
- **AWS Profile:** campaign_prod_v7
- **Audit Scope:** EC2 Instances, Security Groups, VPC, Networking
- **Data Accuracy:** Current as of generation date

---

## Appendix: AWS CLI Commands Used

All information was gathered using read-only AWS CLI commands:

```bash
# Describe EC2 instances
aws ec2 describe-instances --region eu-west-1 --profile campaign_prod_v7

# Describe security groups
aws ec2 describe-security-groups --region eu-west-1 --profile campaign_prod_v7

# Describe VPC
aws ec2 describe-vpcs --region eu-west-1 --profile campaign_prod_v7

# Describe subnets
aws ec2 describe-subnets --region eu-west-1 --profile campaign_prod_v7

# Check for Elastic IPs
aws ec2 describe-addresses --region eu-west-1 --profile campaign_prod_v7
```

**No changes were made to AWS resources during this audit.**
