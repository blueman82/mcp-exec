# Campaign Operations Skills for Claude Code

17 specialized skills for Adobe Campaign operations, troubleshooting, and incident response.

## Quick Start

```bash
# Copy all campaign skills to your global skills directory
cp -r ~/.claude/skills/campaign-* ~/.claude/skills/
```

Skills are then available via `/skill-name` syntax in Claude Code.

---

## Skills by Category

| Category | Skills |
|----------|--------|
| **Database** | db-connect, db-diagnose, db-reboot, index-fix |
| **Infrastructure** | aws-ops, ebs-rescue, newrelic-check |
| **Monitoring** | apache-check, nlserver-status, splunk-query |
| **Troubleshooting** | oom-investigate, core-dump-analyze, email-investigate |
| **Maintenance** | orphan-cleanup, workflow-states |
| **Documentation** | rca, jira-rca |

---

## Database Skills

### `/campaign-db-connect <instance>`
Safe database connection with PGHOST verification. Warns about `-restore` suffix to prevent wrong-database operations.

### `/campaign-db-diagnose <instance> [issue]`
Comprehensive diagnosis: running queries, locks, bloat, index usage, wait events, storage consumers, keepResult audit.

### `/campaign-db-reboot <instance> [--region=<region>]`
Safe RDS reboot: verify PGHOST, get approval, monitor status, verify uptime shows minutes not hours.

### `/campaign-index-fix <instance> [--table] [--column]`
Create indexes for slow queries. Always use `CREATE INDEX CONCURRENTLY`.

---

## Infrastructure Skills

### `/campaign-aws-ops <instance> <operation> [--region]`
**Operations:** `rds_reboot`, `rds_status`, `rds_storage`, `ec2_reboot`, `ec2_status`, `describe_events`

**Profiles:** `campaign_prod_v8` (default), `campaign_prod_v7` (legacy), `camp_dev`

### `/campaign-ebs-rescue <instance> [--container=<n>]`
Recover full root volumes via rescue instance. **Requirement:** Same Availability Zone.

### `/campaign-newrelic-check <instance> [--timerange]`
Query CPU, memory, disk, process metrics. Thresholds: CPU >80%, Memory >85%, Disk >90% = critical.

---

## Monitoring Skills

### `/campaign-apache-check <instance> [--type=<check_type>]`
**Types:** `errors`, `access`, `status_codes`, `ssl`, `soap_router`

**Logs:** `/var/log/apache2/{access,ssl_access,error}.log`

### `/campaign-nlserver-status <instance> [--container=<n>]`
Check process health via pdump. Key processes: watchdog, web@default, mta, wfserver, inMail, sms.

### `/campaign-splunk-query <instance> <query_type> [--timerange]`
**Types:** `email_delivery`, `bounces`, `mta_errors`, `apache_errors`, `workflow_errors`

**Critical:** App logs use DASHES (`instance-*`), Momentum uses UNDERSCORES in `cust.InstanceName`.

---

## Troubleshooting Skills

### `/campaign-oom-investigate <instance> [--container=<n>]`
Investigate OOM events. **Key insight:** "X invoked oom-killer" = X *triggered* OOM, not *caused* it.

**Common causes:** Large psql queries, GDPR exports, memory-heavy workflows, no swap.

### `/campaign-core-dump-analyze <instance> [--timestamp]`
Download/analyze core dumps from `s3://campaign-capture/core_dumps/<instance>/<timestamp>/`

Size reference: ~2MB (Apache child), ~30MB (Apache main), ~500MB+ (nlserverweb).

### `/campaign-email-investigate <instance> <type> [--timerange]`
**Types:** `delivery_status`, `bounces`, `mta_errors`, `throughput`

**Bounce classes:** 10=Invalid Recipient, 20=Soft, 50=Mail Block, 51=Spam.

---

## Maintenance Skills

### `/campaign-orphan-cleanup <instance> <action>`
**Actions:** `analyze`, `generate_drop`, `execute_drop`

**Safety:** NEVER drop tables for states 2 (Running), 13 (Error), 15 (Paused), 20 (Starting).

### `/campaign-workflow-states [--query=<type>]`
Reference for workflow states. **Queries:** `running`, `stuck`, `errors`, `recent`

| istate | Status | Safe to Drop? |
|--------|--------|---------------|
| 0 | Being edited | Yes |
| 2 | Running | NO |
| 11 | Finished | Yes |
| 13 | Error | NO |
| 15 | Paused | NO |
| 20 | Starting | NO |

---

## Documentation Skills

### `/campaign-rca <ticket> <incident_type>`
Generate RCA documentation. **Types:** `oom`, `crash`, `slow_queries`, `stuck_workflows`, `reboot`, `outage`

**Structure:** Summary → Timeline → Evidence → Actions → Recommendations

### `/campaign-jira-rca <ticket> <issue_type>`
Jira wiki markup comments. **Types:** `db_performance`, `oom`, `stuck_workflows`, `reboot`, `index_fix`, `cleanup`

**Rules:** Draft first, no internal details (AWS profiles), include SQL, attach CSVs.

---

## Installation Options

### Copy All Skills
```bash
for skill in ~/.claude/skills/campaign-*; do
  cp -r "$skill" ~/.claude/skills/
done
```

### Symlink (Recommended - stays in sync)
```bash
for skill in ~/.claude/skills/campaign-*; do
  ln -s "$skill" ~/.claude/skills/$(basename "$skill")
done
```

### Copy Specific Skills
```bash
cp -r ~/.claude/skills/campaign-db-diagnose ~/.claude/skills/
cp -r ~/.claude/skills/campaign-rca ~/.claude/skills/
```

## Skill File Structure

```
~/.claude/skills/
└── campaign-<name>/
    └── SKILL.md          # YAML frontmatter + instructions
```

---

## Critical Gotchas

| Issue | Solution |
|-------|----------|
| Wrong database | Always verify PGHOST - may end in `-restore` |
| Splunk host mismatch | Dashes for app logs, underscores for Momentum |
| Dropped running workflow tables | Check istate - never drop for 2, 13, 15, 20 |
| Wrong AWS profile | Use v8 for most instances, v7 for legacy only |
| Internal info in Jira | Never mention AWS profile names |

---

## Full Skill Reference

| Skill | Description |
|-------|-------------|
| `campaign-apache-check` | Check Apache logs and status |
| `campaign-aws-ops` | AWS operations (RDS/EC2 reboot, status) |
| `campaign-core-dump-analyze` | Download and analyze core dumps from S3 |
| `campaign-db-connect` | Generate safe database connection sequence |
| `campaign-db-diagnose` | Diagnose PostgreSQL performance issues |
| `campaign-db-reboot` | Safe database reboot workflow |
| `campaign-ebs-rescue` | EBS rescue procedure for full volumes |
| `campaign-email-investigate` | Investigate email delivery/bounces/MTA |
| `campaign-index-fix` | Create indexes for slow queries |
| `campaign-jira-rca` | Generate Jira wiki markup RCA comments |
| `campaign-newrelic-check` | Check New Relic metrics |
| `campaign-nlserver-status` | Check nlserver process health |
| `campaign-oom-investigate` | Investigate OOM events |
| `campaign-orphan-cleanup` | Clean up orphaned wkf* temp tables |
| `campaign-rca` | Generate comprehensive RCA documentation |
| `campaign-splunk-query` | Build Splunk SPL queries |
| `campaign-workflow-states` | Workflow states reference and queries |
