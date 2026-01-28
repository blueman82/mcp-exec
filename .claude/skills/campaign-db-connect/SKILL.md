---
name: campaign-db-connect
description: Generate safe database connection sequence for Campaign instance
---

# Campaign Database Connection

Generate safe database connection commands with verification.

## Arguments

```
/campaign-db-connect <instance>
```

- `instance`: Campaign instance name (e.g., comcastbusiness-mkt-prod1) - required

## Instructions

### ⚠️ CRITICAL WARNING

**ALWAYS warn about verifying `$PGHOST` before any database operation!**

The actual database endpoint may differ from the instance name:
- Instance name: `comcastbusiness-mkt-prod1`
- Actual PGHOST: `comcastbusiness-mkt-prod1-restore` ← The REAL database!

Rebooting the wrong database has happened before.

### Generate Connection Sequence

```bash
# Step 1: SSH to Instance
ssh <instance>-1.campaign.adobe.com

# Step 2: Switch to neolane user
sudo su - neolane

# Step 3: Load Environment
cd /usr/local/neolane/nl6
source ./env.sh

# Step 4: Get Database Parameters (VERIFY PGHOST!)
camp-db-params -e > /tmp/dbenv.sh && source /tmp/dbenv.sh
echo "=== VERIFY DATABASE TARGET ==="
echo "PGHOST=$PGHOST"
echo "PGDATABASE=$PGDATABASE"

# Step 5: Connect to PostgreSQL
psql
```

### Verification Query

Once connected, verify correct database:
```sql
SELECT
    pg_postmaster_start_time() as db_start_time,
    now() - pg_postmaster_start_time() as uptime,
    current_database() as database;
```

If uptime shows days/weeks after a recent reboot, **you're on the wrong database!**

### One-Liner for Quick Checks

```bash
ssh <instance>-1.campaign.adobe.com "sudo su - neolane -c 'cd /usr/local/neolane/nl6 && source ./env.sh && camp-db-params -e > /tmp/dbenv.sh && source /tmp/dbenv.sh && echo PGHOST=\$PGHOST && psql -c \"SELECT pg_postmaster_start_time(), now() - pg_postmaster_start_time() as uptime;\"'"
```

### Output Format

Provide the full connection sequence with clear warnings about PGHOST verification.
