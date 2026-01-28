---
name: campaign-aws-ops
description: AWS operations for Campaign infrastructure (RDS/EC2 reboot, status checks)
---

# Campaign AWS Operations

Execute AWS operations for Campaign infrastructure.

## Arguments

```
/campaign-aws-ops <instance> <operation> [--region=<region>]
```

- `instance`: Campaign instance name (required)
- `operation`: rds_reboot, rds_status, rds_storage, ec2_reboot, ec2_status, describe_events
- `--region`: AWS region (auto-detect if not provided)

## Instructions

### AWS Profile Selection

| Profile | Use Case |
|---------|----------|
| campaign_prod_v8 | V8 instances (most common) |
| campaign_prod_v7 | V7 legacy instances |
| camp_dev | Development/staging |

Default to `campaign_prod_v8` for production.

### Region Detection

If region unknown:
```bash
aws ec2 describe-instances \
  --profile campaign_prod_v8 \
  --filters "Name=tag:Name,Values=<instance>-*" \
  --query 'Reservations[0].Instances[0].Placement.AvailabilityZone' \
  --output text | sed 's/.$//'
```

### RDS Operations

**Reboot:**
```bash
aws rds reboot-db-instance \
  --profile campaign_prod_v8 \
  --region <region> \
  --db-instance-identifier <instance>
```

**Status:**
```bash
aws rds describe-db-instances \
  --profile campaign_prod_v8 \
  --region <region> \
  --db-instance-identifier <instance> \
  --query 'DBInstances[0].{Status:DBInstanceStatus,Class:DBInstanceClass,IOPS:Iops}'
```

**Verify Events:**
```bash
aws rds describe-events \
  --profile campaign_prod_v8 \
  --region <region> \
  --source-identifier <instance> \
  --source-type db-instance \
  --duration 60
```

### RDS Storage Monitoring

**Current Storage Capacity:**
```bash
aws rds describe-db-instances \
  --profile campaign_prod_v8 \
  --region <region> \
  --db-instance-identifier <instance> \
  --query 'DBInstances[0].{AllocatedStorage:AllocatedStorage,StorageType:StorageType,Iops:Iops,MaxAllocatedStorage:MaxAllocatedStorage}'
```

**Storage Metrics (last 6 hours):**
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name FreeStorageSpace \
  --dimensions Name=DBInstanceIdentifier,Value=<instance> \
  --start-time $(date -u -v-6H +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 900 \
  --statistics Average Minimum Maximum \
  --profile campaign_prod_v8 \
  --region <region>
```

**Storage Metrics (last 24 hours, hourly):**
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name FreeStorageSpace \
  --dimensions Name=DBInstanceIdentifier,Value=<instance> \
  --start-time $(date -u -v-24H +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 3600 \
  --statistics Average Minimum Maximum \
  --profile campaign_prod_v8 \
  --region <region>
```

**Interpret Storage Values:**
- Values are in **bytes** - divide by 1073741824 for GB
- `Minimum` shows worst-case during period
- Sharp drops = large temp tables created
- Gradual drops = data growth or bloat

### EC2 Operations

**Find Instance IDs:**
```bash
aws ec2 describe-instances \
  --profile campaign_prod_v8 \
  --region <region> \
  --filters "Name=tag:Name,Values=<instance>-*" \
  --query 'Reservations[*].Instances[*].[InstanceId,Tags[?Key==`Name`].Value|[0],State.Name]' \
  --output table
```

**Reboot:**
```bash
aws ec2 reboot-instances \
  --profile campaign_prod_v8 \
  --region <region> \
  --instance-ids <instance-id>
```

### Important Notes

1. **RDS reboot terminates all connections** - queries abort
2. **gp3 IOPS/throughput changes are online** - no reboot needed
3. **Don't mention profile names in Jira** - say "v8 account"
4. **Verify PGHOST before RDS operations** - may be `-restore` instance!
