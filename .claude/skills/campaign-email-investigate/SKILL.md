---
name: campaign-email-investigate
description: Investigate email delivery, bounces, and MTA issues
---

# Campaign Email Delivery Investigation

Investigate email delivery, bounces, and MTA issues.

## Arguments

```
/campaign-email-investigate <instance> <type> [--timerange=<range>]
```

- `instance`: Campaign instance name (required)
- `type`: delivery_status, bounces, mta_errors, throughput
- `--timerange`: Time range (default: -24h)

## Instructions

### Architecture

```
Campaign App → MTA Process → Momentum ESP → ISP
                   ↓
              mtachild.log    eventlog_momentum
```

### Host Naming (CRITICAL)

- App logs: DASHES (`instance-*`)
- Momentum: UNDERSCORES in InstanceName

### Splunk Queries

**Delivery Status:**
```spl
index=campaign_prod sourcetype=eventlog_momentum host=momentum_prod*
cust.InstanceName="*<instance_underscored>*"
| stats count by cust.Status
```

**Bounces:**
```spl
index=campaign_prod sourcetype=eventlog_momentum host=momentum_prod*
cust.InstanceName="*<instance_underscored>*" cust.Status="bounce*"
| stats count by cust.BounceClass, cust.BounceReason
```

**Bounce Classes:**
| Class | Meaning |
|-------|---------|
| 10 | Invalid Recipient |
| 20 | Soft Bounce |
| 50 | Mail Block |
| 51 | Spam Related |

**MTA Errors:**
```spl
index=campaign_prod sourcetype=mta_log host=<instance>-*
("error" OR "WDB-" OR "failed")
| stats count by error_code
```

### Database Queries

**Delivery Status:**
```sql
SELECT iStatus, count(*)
FROM NmsBroadLogRcp
WHERE tsEvent > now() - interval '24 hours'
GROUP BY iStatus;
```

| iStatus | Meaning |
|---------|---------|
| 1 | Sent |
| 2 | Pending |
| 4 | Failed |
| 5 | Deferred |

### MTA Logs (SSH)

```bash
ssh <instance>-1.campaign.adobe.com \
  "sudo tail -200 /usr/local/neolane/nl6/var/<instance_underscored>/mta*.log | grep -iE 'sent|error|warning'"
```
