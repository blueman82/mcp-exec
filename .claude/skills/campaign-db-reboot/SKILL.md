---
name: campaign-db-reboot
description: Safe database reboot workflow with verification
---

# Campaign Database Reboot

Safe RDS database reboot with verification steps.

## Arguments

```
/campaign-db-reboot <instance> [--region=<region>]
```

- `instance`: Campaign instance name (required)
- `--region`: AWS region (auto-detect if not provided)

## Instructions

### ⚠️ PRE-REBOOT CHECKLIST

1. **VERIFY PGHOST** - May be `-restore` instance!
2. **Get approval** in Jira ticket
3. **Warn stakeholders** - all connections will be terminated

### Step 1: Verify Database Target

```bash
ssh <instance>-1.campaign.adobe.com \
  "sudo su - neolane -c 'cd /usr/local/neolane/nl6 && source ./env.sh && camp-db-params -e | grep PGHOST'"
```

**CRITICAL**: If PGHOST ends in `-restore`, use THAT name for reboot!

### Step 2: Check Current State

```bash
aws rds describe-db-instances \
  --profile campaign_prod_v8 \
  --region <region> \
  --db-instance-identifier <db-identifier> \
  --query 'DBInstances[0].{Status:DBInstanceStatus,Class:DBInstanceClass}'
```

### Step 3: Execute Reboot

```bash
aws rds reboot-db-instance \
  --profile campaign_prod_v8 \
  --region <region> \
  --db-instance-identifier <db-identifier>
```

### Step 4: Monitor Status

```bash
watch -n 10 "aws rds describe-db-instances \
  --profile campaign_prod_v8 \
  --region <region> \
  --db-instance-identifier <db-identifier> \
  --query 'DBInstances[0].DBInstanceStatus' \
  --output text"
```

### Step 5: Verify Reboot Completed

**Check Events:**
```bash
aws rds describe-events \
  --profile campaign_prod_v8 \
  --region <region> \
  --source-identifier <db-identifier> \
  --source-type db-instance \
  --duration 60
```

Look for: "DB instance shutdown" and "DB instance restarted"

**Check PostgreSQL Uptime:**
```bash
ssh <instance>-1.campaign.adobe.com \
  "sudo su - neolane -c 'cd /usr/local/neolane/nl6 && source ./env.sh && camp-db-params -e > /tmp/dbenv.sh && source /tmp/dbenv.sh && psql -c \"SELECT pg_postmaster_start_time(), now() - pg_postmaster_start_time() as uptime;\"'"
```

Uptime should show minutes, not hours/days!

### Step 6: Verify Queries Cleared

```sql
SELECT pid, now()-query_start as runtime, left(query, 100)
FROM pg_stat_activity
WHERE state NOT LIKE '%idle%'
ORDER BY runtime DESC;
```

### What Reboot Does

- Terminates all active connections
- Aborts running queries
- Rolls back uncommitted transactions
- Cleans up temp tables from stuck queries
- Does NOT preserve query state
