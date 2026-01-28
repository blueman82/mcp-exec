---
name: campaign-nlserver-status
description: Check nlserver process health and status for Campaign instance
---

# Campaign nlserver Process Status

Check nlserver process health and status.

## Arguments

```
/campaign-nlserver-status <instance> [--container=<n>]
```

- `instance`: Campaign instance name (required)
- `--container`: Container number 1, 2, 3 (default: 1)

## Instructions

### Run pdump Command

```bash
ssh <instance>-<container>.campaign.adobe.com \
  "sudo -u neolane /usr/local/neolane/nl6/bin/nlserver pdump -instance:<instance_underscored>" 2>&1 | tail -50
```

For nl7: Replace `nl6` with `nl7`.

### Process Reference

| Process | Description | Typical Memory |
|---------|-------------|----------------|
| watchdog | Master process | 15-30 MB |
| web@default | Web server | 1-4 GB |
| mta@instance | Mail Transfer Agent | 200-800 MB |
| wfserver@instance | Workflow server | 30-100 MB |
| inMail@instance | Bounce processing | 40-80 MB |
| sms@instance | SMS connector | 30-60 MB |

### Status Indicators

| Status | Meaning |
|--------|---------|
| idle | Running, waiting for work |
| active | Currently executing |
| starting | Initializing |
| stopped | Not running |

### Check Logs

```bash
# MTA Log
ssh <instance>-1.campaign.adobe.com \
  "sudo tail -100 /usr/local/neolane/nl6/var/<instance>/mta*.log"

# Workflow Log
ssh <instance>-1.campaign.adobe.com \
  "sudo tail -100 /usr/local/neolane/nl6/var/<instance>/wfserver*.log"
```

### Restart Services

```bash
# Restart all
ssh <instance>-1.campaign.adobe.com \
  "sudo su - neolane -c '/usr/local/neolane/nl6/bin/nlserver restart'"

# Restart specific module
ssh <instance>-1.campaign.adobe.com \
  "sudo su - neolane -c '/usr/local/neolane/nl6/bin/nlserver restart web@default'"
```

### Output Format

Present pdump output with:
- Process list with memory usage
- Status indicators
- Any processes with unusual memory or status
- Log path references
